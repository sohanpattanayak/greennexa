"""
backend/services/anomaly.py — Anomaly Detection Service
Three-layer approach:
  1. Static threshold check (always active, no training needed)
  2. Z-score rolling window (always active)
  3. Isolation Forest (active once trained — sklearn primary)
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sqlalchemy.orm import Session

from backend.core.config import get_settings
from backend.db import crud, models
from backend.ml.feature_engineering import (
    readings_to_dataframe, add_time_features, add_rolling_features, build_feature_matrix
)

log = logging.getLogger("sfeid.anomaly")
cfg = get_settings()

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "ml", "saved_models")
os.makedirs(MODEL_DIR, exist_ok=True)


# ── Model cache (in-memory, loaded at startup) ────────────────────────────────
_model_cache: dict[str, tuple[IsolationForest, StandardScaler]] = {}


def _model_key(facility_id: int, metric_type: str) -> str:
    return f"{facility_id}_{metric_type}"


def load_models_from_db(db: Session):
    """Called at startup — loads all active Isolation Forest models into memory."""
    from backend.db.models import MLModel
    active = (
        db.query(MLModel)
        .filter(MLModel.model_type == "isolation_forest", MLModel.is_active == True)
        .all()
    )
    for m in active:
        _load_model(m.facility_id, m.metric_type, m.model_path)
    log.info(f"Loaded {len(active)} Isolation Forest model(s) into cache.")


def _load_model(facility_id: int, metric_type: str,
                model_path: str) -> Optional[tuple]:
    try:
        bundle = joblib.load(model_path)
        key    = _model_key(facility_id, metric_type)
        _model_cache[key] = (bundle["model"], bundle["scaler"])
        return _model_cache[key]
    except Exception as exc:
        log.warning(f"Failed to load model {model_path}: {exc}")
        return None


# ── Training ──────────────────────────────────────────────────────────────────

def train_isolation_forest(db: Session, facility_id: int, metric_type: str) -> bool:
    """
    Train Isolation Forest on 30-day history.
    Saves model to disk and records in ml_models table.
    Returns True on success.
    """
    readings = crud.get_readings_last_n_days(db, facility_id, metric_type, days=30)
    if len(readings) < cfg.min_rows_for_isolation_forest:
        log.info(f"Not enough data to train IsolationForest for {metric_type} "
                 f"(have {len(readings)}, need {cfg.min_rows_for_isolation_forest})")
        return False

    df = readings_to_dataframe(readings)
    X, feat_cols = build_feature_matrix(df)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = IsolationForest(
        n_estimators=100,
        contamination=cfg.isolation_forest_contamination,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_scaled)

    # Compute approximate accuracy proxy (fraction correctly labelled as normal on training set)
    preds    = model.predict(X_scaled)
    accuracy = float(np.mean(preds == 1))   # fraction labelled inlier

    # Save to disk
    fname      = f"if_{facility_id}_{metric_type}.pkl"
    model_path = os.path.join(MODEL_DIR, fname)
    joblib.dump({"model": model, "scaler": scaler, "features": feat_cols}, model_path)

    # Deactivate old models
    from backend.db.models import MLModel
    db.query(MLModel).filter(
        MLModel.facility_id == facility_id,
        MLModel.metric_type == metric_type,
        MLModel.model_type  == "isolation_forest",
    ).update({"is_active": False})

    # Register new model
    new_model = MLModel(
        model_type="isolation_forest",
        metric_type=metric_type,
        facility_id=facility_id,
        model_path=model_path,
        accuracy_score=accuracy,
        is_active=True,
    )
    db.add(new_model)
    db.commit()

    # Update in-memory cache
    _model_cache[_model_key(facility_id, metric_type)] = (model, scaler)
    log.info(f"IsolationForest trained for {metric_type} @ facility {facility_id} — accuracy proxy {accuracy:.2%}")
    return True


# ── Detection ─────────────────────────────────────────────────────────────────

def detect_anomalies(db: Session, facility_id: int) -> int:
    """
    Run all three detection methods on recent readings.
    Inserts confirmed anomalies into the anomalies table.
    Returns total count of new anomalies inserted.
    """
    facility = crud.get_facility(db, facility_id)
    if not facility:
        return 0

    sensors   = crud.get_sensors(db, facility_id)
    thresholds_map = {
        t.metric_type: t
        for t in crud.get_all_thresholds(db, facility.facility_type_id)
    }

    total_detected = 0
    now = datetime.utcnow()

    for sensor in sensors:
        mt  = sensor.metric_type
        thr = thresholds_map.get(mt)

        # Load recent readings (last 3 hours for z-score; latest for threshold)
        recent = crud.get_readings_last_n_hours(db, facility_id, mt, hours=3)
        if not recent:
            continue

        latest = recent[-1]   # most recent

        # ── Method 1: Static threshold ───────────────────────────────────────
        anomaly_found = False
        severity      = "low"
        method        = "threshold"

        if thr:
            if thr.critical_high and latest.value > thr.critical_high:
                anomaly_found = True; severity = "critical"
            elif thr.warn_high and latest.value > thr.warn_high:
                anomaly_found = True; severity = "high"
            elif thr.critical_low and latest.value < thr.critical_low:
                anomaly_found = True; severity = "critical"
            elif thr.warn_low and latest.value < thr.warn_low:
                anomaly_found = True; severity = "medium"

        # ── Method 2: Z-score ─────────────────────────────────────────────
        if len(recent) >= 5:
            values = np.array([r.value for r in recent[:-1]])   # exclude latest
            mean, std = values.mean(), values.std()
            if std > 0:
                z = abs((latest.value - mean) / std)
                if z > cfg.anomaly_zscore_threshold:
                    if not anomaly_found:
                        anomaly_found = True
                        severity = _z_to_severity(z)
                        method   = "z_score"

        # ── Method 3: Isolation Forest ────────────────────────────────────
        key = _model_key(facility_id, mt)
        if key in _model_cache:
            try:
                model, scaler = _model_cache[key]
                df = readings_to_dataframe(recent)
                X, _ = build_feature_matrix(df)
                X_s  = scaler.transform(X[-1:])   # score only the latest point
                pred = model.predict(X_s)[0]       # 1=normal, -1=anomaly
                score = model.score_samples(X_s)[0]  # more negative = more anomalous

                if pred == -1:
                    if not anomaly_found:
                        anomaly_found = True
                        severity = _iso_score_to_severity(score)
                        method   = "isolation_forest"
                    # IF confirms → upgrade severity
                    elif severity in ("low", "medium"):
                        severity = "high"
                        method   = "isolation_forest"
            except Exception as exc:
                log.debug(f"IsolationForest scoring failed for {mt}: {exc}")

        if anomaly_found:
            # Dedup: skip if same sensor already has an open anomaly in the last 5 minutes
            recent_count = crud.count_recent_anomalies(db, sensor.id, hours=0)
            five_min_ago = now - timedelta(minutes=5)
            from sqlalchemy import func
            existing = (
                db.query(models.Anomaly)
                .filter(
                    models.Anomaly.sensor_id == sensor.id,
                    models.Anomaly.is_resolved == False,
                    models.Anomaly.detected_at >= five_min_ago,
                )
                .first()
            )
            if existing:
                continue   # already recorded this recently

            crud.create_anomaly(
                db,
                sensor_id=sensor.id,
                facility_id=facility_id,
                zone_id=sensor.zone_id,
                metric_type=mt,
                value=latest.value,
                threshold_low=thr.warn_low if thr else None,
                threshold_high=thr.warn_high if thr else None,
                severity=severity,
                detection_method=method,
            )
            total_detected += 1

    return total_detected


def _z_to_severity(z: float) -> str:
    if z > 5:   return "critical"
    if z > 4:   return "high"
    if z > 3:   return "medium"
    return "low"


def _iso_score_to_severity(score: float) -> str:
    """Isolation Forest score_samples — more negative = more anomalous."""
    if score < -0.5:  return "critical"
    if score < -0.35: return "high"
    if score < -0.20: return "medium"
    return "low"

"""
backend/services/priority.py — Priority Engine Service

Deterministic weighted scoring of anomalies into a ranked alert list.
sklearn MinMaxScaler used to normalise the 5 input factors.
No LLM required.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
from sklearn.preprocessing import MinMaxScaler
from sqlalchemy.orm import Session

from backend.core.config import get_settings
from backend.db import crud, models

log = logging.getLogger("sfeid.priority")
cfg = get_settings()

# Fixed bounds for MinMaxScaler (theoretical min/max — no training data needed)
FACTOR_BOUNDS = {
    # factor:         [min, max]
    "severity":    [0.0, 100.0],
    "trend":       [0.0, 100.0],
    "impact":      [0.0, 100.0],
    "time_urgency":[0.0, 100.0],
    "recurrence":  [0.0, 100.0],
}

_SEVERITY_SCORES = {"critical": 100.0, "high": 75.0, "medium": 50.0, "low": 25.0}


def run_priority_engine(db: Session, facility_id: int) -> int:
    """
    Score all unresolved anomalies and upsert priority alerts.
    Returns the count of alerts processed.
    """
    anomalies = crud.get_anomalies(db, facility_id, resolved=False, limit=200)
    if not anomalies:
        return 0

    processed = 0
    for anomaly in anomalies:
        factors = _compute_factors(db, anomaly)
        score   = _weighted_score(factors)
        tier, _ = _priority_tier(score)

        title       = f"[{tier}] {anomaly.metric_type.replace('_', ' ').title()} anomaly"
        description = (
            f"Sensor reading {anomaly.value:.2f} detected as {anomaly.severity} severity "
            f"via {anomaly.detection_method}. "
            f"Threshold: {anomaly.threshold_low}–{anomaly.threshold_high}."
        )

        crud.upsert_priority_alert(
            db,
            facility_id=facility_id,
            anomaly_id=anomaly.id,
            title=title,
            description=description,
            priority_score=round(score, 1),
            factors_json=json.dumps(factors),
        )
        processed += 1

    log.info(f"Priority engine processed {processed} anomalies for facility {facility_id}")
    return processed


def _compute_factors(db: Session, anomaly: models.Anomaly) -> dict:
    """Compute the 5 raw factor scores (0–100) for one anomaly."""

    # 1. Severity score
    severity_score = _SEVERITY_SCORES.get(anomaly.severity, 25.0)

    # 2. Trend score (worsening vs. improving)
    trend_score = _compute_trend(db, anomaly)

    # 3. Impact score (affected zone occupancy)
    impact_score = _compute_impact(db, anomaly)

    # 4. Time urgency (minutes unresolved, cap at 240)
    minutes = (datetime.utcnow() - anomaly.detected_at).total_seconds() / 60
    time_urgency_score = min(100.0, (minutes / 240) * 100)

    # 5. Recurrence (same sensor anomalies in last 24h)
    recent_count = crud.count_recent_anomalies(db, anomaly.sensor_id, hours=24)
    recurrence_score = min(100.0, (recent_count / 5) * 100)

    return {
        "severity":     round(severity_score, 1),
        "trend":        round(trend_score, 1),
        "impact":       round(impact_score, 1),
        "time_urgency": round(time_urgency_score, 1),
        "recurrence":   round(recurrence_score, 1),
    }


def _weighted_score(factors: dict) -> float:
    """Apply MinMaxScaler (fixed bounds) + weighted sum → 0–100."""
    raw = np.array([[
        factors["severity"],
        factors["trend"],
        factors["impact"],
        factors["time_urgency"],
        factors["recurrence"],
    ]])

    # Fixed min/max bounds — no training needed
    bounds_min = np.array([0.0, 0.0, 0.0, 0.0, 0.0])
    bounds_max = np.array([100.0, 100.0, 100.0, 100.0, 100.0])
    normalised  = (raw - bounds_min) / (bounds_max - bounds_min)
    normalised  = np.clip(normalised, 0.0, 1.0)[0]

    weights = np.array([
        cfg.priority_w_severity,
        cfg.priority_w_trend,
        cfg.priority_w_impact,
        cfg.priority_w_time,
        cfg.priority_w_recurrence,
    ])
    return float(np.dot(weights, normalised) * 100)


def _compute_trend(db: Session, anomaly: models.Anomaly) -> float:
    """
    Score 0–100 for how the metric is trending.
    Positive slope (worsening) → higher score.
    """
    readings = crud.get_readings_last_n_hours(
        db, anomaly.facility_id, anomaly.metric_type, hours=2
    )
    if len(readings) < 4:
        return 50.0   # not enough data → neutral

    values = np.array([r.value for r in readings])
    # Simple linear trend via polyfit
    x     = np.arange(len(values), dtype=float)
    slope = np.polyfit(x, values, 1)[0]

    # Normalise slope to 0–100: flat=50, positive(worsening)>50, negative<50
    # Scale: slope of ±5%/interval → ±50 points
    norm = 50.0 + (slope / (abs(anomaly.value) + 1e-6)) * 50.0 * 10
    return float(np.clip(norm, 0.0, 100.0))


def _compute_impact(db: Session, anomaly: models.Anomaly) -> float:
    """
    Score based on zone occupancy as a fraction of campus capacity.
    Higher occupancy in affected zone → higher impact.
    """
    occ_readings = crud.get_readings_last_n_hours(
        db, anomaly.facility_id, "occupancy_count", hours=1
    )
    if not occ_readings:
        return 50.0

    avg_occ   = float(np.mean([r.value for r in occ_readings]))
    max_cap   = 5000.0   # configurable; matches threshold seed
    occ_frac  = min(1.0, avg_occ / max_cap)
    return round(occ_frac * 100, 1)


def _priority_tier(score: float) -> tuple[str, str]:
    if score >= 80: return ("Critical", "#FF4B4B")
    if score >= 60: return ("High",     "#FF8C00")
    if score >= 40: return ("Medium",   "#FFD700")
    return ("Low",          "#2E8B57")

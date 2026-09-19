"""
backend/services/scorer.py — Sustainability & Operations Scoring Service

Computes a 0–100 composite score daily per facility.
Uses sklearn MinMaxScaler for normalisation (thresholds act as bounds).
No LLM required — purely data-driven weighted formula.
"""

import json
import logging
from datetime import datetime, date, timedelta
from typing import Optional

import numpy as np
from sklearn.preprocessing import MinMaxScaler
from sqlalchemy.orm import Session

from backend.core.config import get_settings
from backend.db import crud

log = logging.getLogger("sfeid.scorer")
cfg = get_settings()


def compute_sustainability_score(db: Session, facility_id: int,
                                  score_date: Optional[date] = None) -> dict:
    """
    Compute today's sustainability score and persist it.
    Returns a dict with overall + sub-scores.
    """
    score_date = score_date or date.today()
    facility   = crud.get_facility(db, facility_id)
    if not facility:
        return {}

    thresholds = {
        t.metric_type: t
        for t in crud.get_all_thresholds(db, facility.facility_type_id)
    }

    # Use last 24h of data for today's score
    since = datetime.utcnow() - timedelta(hours=24)

    def avg(metric_type: str) -> Optional[float]:
        readings = crud.get_readings_last_n_hours(db, facility_id, metric_type, hours=24)
        if not readings:
            return None
        return float(np.mean([r.value for r in readings]))

    # ── Sub-scores ────────────────────────────────────────────────────────────

    energy_score    = _score_lower_better("energy_kwh",         avg, thresholds)
    water_score     = _score_lower_better("water_litres",       avg, thresholds)
    waste_score     = _score_waste(                             avg, thresholds)
    air_score       = _score_air(                               avg, thresholds)
    occupancy_score = _score_occupancy(                         avg, thresholds)

    # Weighted overall
    weights = {
        "energy":    cfg.score_w_energy,
        "water":     cfg.score_w_water,
        "waste":     cfg.score_w_waste,
        "air":       cfg.score_w_air,
        "occupancy": cfg.score_w_occupancy,
    }
    scores  = {
        "energy":    energy_score,
        "water":     water_score,
        "waste":     waste_score,
        "air":       air_score,
        "occupancy": occupancy_score,
    }

    # Use available sub-scores only (skip None)
    total_w = 0.0
    weighted = 0.0
    for k, w in weights.items():
        s = scores[k]
        if s is not None:
            weighted += w * s
            total_w  += w

    overall = round((weighted / total_w) * 100, 1) if total_w > 0 else 0.0

    details = {
        "computed_at":    datetime.utcnow().isoformat(),
        "hours_window":   24,
        "sub_scores_raw": scores,
    }

    # Persist
    crud.upsert_score(
        db,
        facility_id=facility_id,
        score_date=score_date,
        overall_score=overall,
        energy_score=round((energy_score or 0) * 100, 1),
        water_score=round((water_score  or 0) * 100, 1),
        waste_score=round((waste_score  or 0) * 100, 1),
        air_score=round((air_score      or 0) * 100, 1),
        occupancy_score=round((occupancy_score or 0) * 100, 1),
        details_json=json.dumps(details),
    )

    return {
        "facility_id":    facility_id,
        "score_date":     score_date.isoformat(),
        "overall_score":  overall,
        "energy_score":   round((energy_score or 0) * 100, 1),
        "water_score":    round((water_score  or 0) * 100, 1),
        "waste_score":    round((waste_score  or 0) * 100, 1),
        "air_score":      round((air_score    or 0) * 100, 1),
        "occupancy_score":round((occupancy_score or 0) * 100, 1),
        "grade":          _score_to_grade(overall),
    }


# ── Sub-score helpers ─────────────────────────────────────────────────────────

def _normalise_lower_is_better(value: float, critical_high: float,
                                warn_high: float) -> float:
    """Returns 0–1 where lower value = higher score."""
    if value <= 0:
        return 1.0
    if critical_high and value >= critical_high:
        return 0.0
    if warn_high:
        return max(0.0, 1.0 - (value / critical_high)) if critical_high else 0.5
    return 0.5


def _score_lower_better(metric_type: str, avg_fn, thresholds: dict) -> Optional[float]:
    val = avg_fn(metric_type)
    if val is None:
        return None
    t = thresholds.get(metric_type)
    if t and t.critical_high:
        return _normalise_lower_is_better(val, t.critical_high, t.warn_high)
    return 0.5   # no threshold → neutral score


def _score_waste(avg_fn, thresholds: dict) -> Optional[float]:
    fill = avg_fn("bin_fill_pct")
    if fill is None:
        return None
    # Score decreases as bin approaches 100%
    return max(0.0, 1.0 - (fill / 100.0))


def _score_air(avg_fn, thresholds: dict) -> Optional[float]:
    pm25 = avg_fn("pm25")
    pm10 = avg_fn("pm10")
    scores = []
    for metric, val in [("pm25", pm25), ("pm10", pm10)]:
        if val is None:
            continue
        t = thresholds.get(metric)
        if t and t.critical_high:
            scores.append(_normalise_lower_is_better(val, t.critical_high, t.warn_high))
        else:
            scores.append(0.5)
    return float(np.mean(scores)) if scores else None


def _score_occupancy(avg_fn, thresholds: dict) -> Optional[float]:
    """Higher occupancy within capacity = better space utilisation."""
    occ = avg_fn("occupancy_count")
    if occ is None:
        return None
    t = thresholds.get("occupancy_count")
    max_cap = t.critical_high if (t and t.critical_high) else 5000.0
    util    = min(1.0, occ / max_cap)
    # Target range: 50–85% is optimal
    if 0.50 <= util <= 0.85:
        return 1.0
    if util < 0.50:
        return util / 0.50   # proportional below target
    # Over 85% — slight penalty for overcrowding
    return max(0.0, 1.0 - (util - 0.85) * 4)


def _score_to_grade(score: float) -> str:
    if score >= 85: return "A+"
    if score >= 75: return "A"
    if score >= 65: return "B"
    if score >= 50: return "C"
    if score >= 35: return "D"
    return "F"

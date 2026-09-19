"""
backend/routers/analytics.py — Trends, anomaly detection, forecast, summary
"""

from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.db import crud, models
from backend.schemas.analytics import (
    TrendResponse, TrendPoint, AnomalyOut, ForecastResponse,
    ForecastPoint, SummaryStats, DetectAnomaliesResponse,
)
from backend.services import anomaly as anomaly_svc
from backend.services import forecast as forecast_svc

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/trends", response_model=TrendResponse)
def get_trends(
    facility_id: int     = Query(...),
    metric_type: str     = Query(...),
    granularity: str     = Query("hourly"),   # hourly | daily
    hours:       int     = Query(48),
    db: Session = Depends(get_db),
):
    """Aggregated trend data for a metric over the last N hours."""
    readings = crud.get_readings_last_n_hours(db, facility_id, metric_type, hours=hours)
    if not readings:
        return TrendResponse(
            facility_id=facility_id, metric_type=metric_type,
            granularity=granularity, points=[]
        )

    df = pd.DataFrame([{"ts": r.timestamp, "val": r.value} for r in readings])
    df["ts"] = pd.to_datetime(df["ts"])
    df = df.set_index("ts")

    freq = "h" if granularity == "hourly" else "D"
    agg  = df.resample(freq).agg(
        avg_value=("val", "mean"),
        min_value=("val", "min"),
        max_value=("val", "max"),
    ).dropna().reset_index()

    points = [
        TrendPoint(
            timestamp=row["ts"],
            avg_value=round(float(row["avg_value"]), 2),
            min_value=round(float(row["min_value"]), 2),
            max_value=round(float(row["max_value"]), 2),
        )
        for _, row in agg.iterrows()
    ]
    return TrendResponse(
        facility_id=facility_id, metric_type=metric_type,
        granularity=granularity, points=points
    )


@router.get("/anomalies", response_model=list[AnomalyOut])
def list_anomalies(
    facility_id: int           = Query(...),
    resolved:    bool          = Query(False),
    severity:    Optional[str] = Query(None),
    limit:       int           = Query(100),
    db: Session = Depends(get_db),
):
    return crud.get_anomalies(db, facility_id, resolved=resolved,
                               severity=severity, limit=limit)


@router.post("/anomalies/detect", response_model=DetectAnomaliesResponse)
def run_anomaly_detection(facility_id: int = Query(...), db: Session = Depends(get_db)):
    """Run anomaly detection on recent readings + trigger priority engine."""
    from backend.services import priority as priority_svc

    detected = anomaly_svc.detect_anomalies(db, facility_id)
    if detected > 0:
        priority_svc.run_priority_engine(db, facility_id)

    return DetectAnomaliesResponse(
        detected=detected,
        message=f"Detected {detected} new anomaly event(s). Priority engine updated."
    )


@router.get("/forecast", response_model=Optional[ForecastResponse])
def get_forecast(
    facility_id: int = Query(...),
    metric_type: str = Query(...),
    db: Session = Depends(get_db),
):
    payload = forecast_svc.get_or_generate_forecast(db, facility_id, metric_type)
    if not payload:
        raise HTTPException(404, "Insufficient data for forecast. Collect more readings first.")

    points = [
        ForecastPoint(
            timestamp=datetime.fromisoformat(p["timestamp"]),
            yhat=p["yhat"],
            yhat_lower=p.get("yhat_lower"),
            yhat_upper=p.get("yhat_upper"),
        )
        for p in payload["points"]
    ]
    return ForecastResponse(
        facility_id=facility_id,
        metric_type=metric_type,
        model_used=payload["model_used"],
        generated_at=datetime.fromisoformat(payload["generated_at"]),
        horizon_hours=payload["horizon_hours"],
        points=points,
    )


@router.post("/forecast/generate")
def generate_forecast(
    facility_id: int = Query(...),
    metric_type: str = Query(...),
    db: Session = Depends(get_db),
):
    """Force-regenerate a forecast (ignores cache)."""
    payload = forecast_svc.generate_forecast(db, facility_id, metric_type)
    if not payload:
        raise HTTPException(400, "Not enough data to generate forecast.")
    return {"model_used": payload["model_used"], "points": len(payload["points"])}


@router.get("/summary", response_model=list[SummaryStats])
def summary_stats(
    facility_id: int = Query(...),
    hours:       int = Query(24),
    db: Session = Depends(get_db),
):
    """Quick stats (min/max/avg/latest) per metric for the last N hours."""
    sensors = crud.get_sensors(db, facility_id)
    results = []

    METRIC_UNITS = {
        "energy_kwh": "kWh", "pm25": "µg/m³", "pm10": "µg/m³",
        "water_litres": "L", "bin_fill_pct": "%",
        "temperature_c": "°C", "humidity_pct": "%",
        "occupancy_count": "count", "parking_count": "count",
        "equipment_util_pct": "%",
    }

    seen_metrics = set()
    for sensor in sensors:
        mt = sensor.metric_type
        if mt in seen_metrics:
            continue
        seen_metrics.add(mt)

        readings = crud.get_readings_last_n_hours(db, facility_id, mt, hours=hours)
        if not readings:
            continue

        vals = [r.value for r in readings]
        results.append(SummaryStats(
            metric_type=mt,
            avg=round(float(np.mean(vals)), 2),
            min_val=round(float(min(vals)), 2),
            max_val=round(float(max(vals)), 2),
            latest=round(float(readings[-1].value), 2),
            unit=METRIC_UNITS.get(mt, ""),
            period_hours=hours,
        ))

    return results

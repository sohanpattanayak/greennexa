"""
backend/db/crud.py — CRUD helpers for all models
"""

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from backend.db import models


# ── Sensor Readings ────────────────────────────────────────────────────────────

def create_reading(db: Session, sensor_id: int, facility_id: int, zone_id: Optional[int],
                   metric_type: str, value: float, source: str = "synthetic",
                   timestamp: Optional[datetime] = None) -> models.SensorReading:
    row = models.SensorReading(
        sensor_id=sensor_id, facility_id=facility_id, zone_id=zone_id,
        metric_type=metric_type, value=value, source=source,
        timestamp=timestamp or datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def bulk_create_readings(db: Session, rows: list[dict]) -> int:
    """Insert many readings at once. rows: list of dicts matching SensorReading fields."""
    db.bulk_insert_mappings(models.SensorReading, rows)
    db.commit()
    return len(rows)


def get_latest_readings(db: Session, facility_id: int) -> list[models.SensorReading]:
    """Return the single most-recent reading for every metric in a facility."""
    subq = (
        db.query(
            models.SensorReading.metric_type,
            func.max(models.SensorReading.timestamp).label("max_ts"),
        )
        .filter(models.SensorReading.facility_id == facility_id)
        .group_by(models.SensorReading.metric_type)
        .subquery()
    )
    return (
        db.query(models.SensorReading)
        .join(subq, (models.SensorReading.metric_type == subq.c.metric_type)
              & (models.SensorReading.timestamp == subq.c.max_ts)
              & (models.SensorReading.facility_id == facility_id))
        .all()
    )


def get_readings_range(db: Session, facility_id: int, metric_type: str,
                       start: datetime, end: datetime,
                       limit: int = 2000) -> list[models.SensorReading]:
    return (
        db.query(models.SensorReading)
        .filter(
            models.SensorReading.facility_id == facility_id,
            models.SensorReading.metric_type == metric_type,
            models.SensorReading.timestamp >= start,
            models.SensorReading.timestamp <= end,
        )
        .order_by(models.SensorReading.timestamp)
        .limit(limit)
        .all()
    )


def get_readings_last_n_hours(db: Session, facility_id: int, metric_type: str,
                               hours: int = 24) -> list[models.SensorReading]:
    since = datetime.utcnow() - timedelta(hours=hours)
    return (
        db.query(models.SensorReading)
        .filter(
            models.SensorReading.facility_id == facility_id,
            models.SensorReading.metric_type == metric_type,
            models.SensorReading.timestamp >= since,
        )
        .order_by(models.SensorReading.timestamp)
        .all()
    )


def get_readings_last_n_days(db: Session, facility_id: int, metric_type: str,
                              days: int = 30) -> list[models.SensorReading]:
    since = datetime.utcnow() - timedelta(days=days)
    return (
        db.query(models.SensorReading)
        .filter(
            models.SensorReading.facility_id == facility_id,
            models.SensorReading.metric_type == metric_type,
            models.SensorReading.timestamp >= since,
        )
        .order_by(models.SensorReading.timestamp)
        .all()
    )


# ── Sensors ────────────────────────────────────────────────────────────────────

def get_sensors(db: Session, facility_id: int) -> list[models.Sensor]:
    return (
        db.query(models.Sensor)
        .filter(models.Sensor.facility_id == facility_id, models.Sensor.is_active == True)
        .all()
    )


def get_sensor_by_id(db: Session, sensor_id: int) -> Optional[models.Sensor]:
    return db.query(models.Sensor).filter(models.Sensor.id == sensor_id).first()


def get_sensor_by_metric(db: Session, facility_id: int,
                          metric_type: str) -> Optional[models.Sensor]:
    return (
        db.query(models.Sensor)
        .filter(models.Sensor.facility_id == facility_id,
                models.Sensor.metric_type == metric_type,
                models.Sensor.is_active == True)
        .first()
    )


# ── Thresholds ─────────────────────────────────────────────────────────────────

def get_threshold(db: Session, facility_type_id: int,
                  metric_type: str) -> Optional[models.Threshold]:
    return (
        db.query(models.Threshold)
        .filter(models.Threshold.facility_type_id == facility_type_id,
                models.Threshold.metric_type == metric_type)
        .first()
    )


def get_all_thresholds(db: Session, facility_type_id: int) -> list[models.Threshold]:
    return (
        db.query(models.Threshold)
        .filter(models.Threshold.facility_type_id == facility_type_id)
        .all()
    )


def update_threshold(db: Session, threshold_id: int, **kwargs) -> Optional[models.Threshold]:
    row = db.query(models.Threshold).filter(models.Threshold.id == threshold_id).first()
    if row:
        for k, v in kwargs.items():
            setattr(row, k, v)
        db.commit()
        db.refresh(row)
    return row


# ── Anomalies ──────────────────────────────────────────────────────────────────

def create_anomaly(db: Session, **kwargs) -> models.Anomaly:
    row = models.Anomaly(**kwargs)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_anomalies(db: Session, facility_id: int,
                  resolved: Optional[bool] = False,
                  severity: Optional[str] = None,
                  limit: int = 100) -> list[models.Anomaly]:
    q = db.query(models.Anomaly).filter(models.Anomaly.facility_id == facility_id)
    if resolved is not None:
        q = q.filter(models.Anomaly.is_resolved == resolved)
    if severity:
        q = q.filter(models.Anomaly.severity == severity)
    return q.order_by(desc(models.Anomaly.detected_at)).limit(limit).all()


def resolve_anomaly(db: Session, anomaly_id: int) -> Optional[models.Anomaly]:
    row = db.query(models.Anomaly).filter(models.Anomaly.id == anomaly_id).first()
    if row:
        row.is_resolved = True
        row.resolved_at = datetime.utcnow()
        db.commit()
        db.refresh(row)
    return row


def count_recent_anomalies(db: Session, sensor_id: int, hours: int = 24) -> int:
    since = datetime.utcnow() - timedelta(hours=hours)
    return (
        db.query(func.count(models.Anomaly.id))
        .filter(models.Anomaly.sensor_id == sensor_id,
                models.Anomaly.detected_at >= since)
        .scalar()
    )


# ── Forecasts ─────────────────────────────────────────────────────────────────

def upsert_forecast(db: Session, facility_id: int, metric_type: str,
                    forecast_json: str, model_used: str = "prophet",
                    horizon_hours: int = 24) -> models.Forecast:
    row = models.Forecast(
        facility_id=facility_id, metric_type=metric_type,
        forecast_json=forecast_json, model_used=model_used,
        horizon_hours=horizon_hours, generated_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_latest_forecast(db: Session, facility_id: int,
                         metric_type: str) -> Optional[models.Forecast]:
    return (
        db.query(models.Forecast)
        .filter(models.Forecast.facility_id == facility_id,
                models.Forecast.metric_type == metric_type)
        .order_by(desc(models.Forecast.generated_at))
        .first()
    )


# ── Recommendations ──────────────────────────────────────────────────────────

def create_recommendation(db: Session, **kwargs) -> models.Recommendation:
    row = models.Recommendation(**kwargs)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_recommendations(db: Session, facility_id: int,
                         acknowledged: Optional[bool] = False,
                         limit: int = 20) -> list[models.Recommendation]:
    q = db.query(models.Recommendation).filter(
        models.Recommendation.facility_id == facility_id
    )
    if acknowledged is not None:
        q = q.filter(models.Recommendation.is_acknowledged == acknowledged)
    return q.order_by(desc(models.Recommendation.priority_score)).limit(limit).all()


def acknowledge_recommendation(db: Session, rec_id: int) -> Optional[models.Recommendation]:
    row = db.query(models.Recommendation).filter(models.Recommendation.id == rec_id).first()
    if row:
        row.is_acknowledged = True
        row.acknowledged_at = datetime.utcnow()
        db.commit()
        db.refresh(row)
    return row


# ── Priority Alerts ──────────────────────────────────────────────────────────

def upsert_priority_alert(db: Session, facility_id: int, anomaly_id: int,
                           title: str, description: str, priority_score: float,
                           factors_json: str) -> models.PriorityAlert:
    # Check if open alert exists for this anomaly
    existing = (
        db.query(models.PriorityAlert)
        .filter(models.PriorityAlert.anomaly_id == anomaly_id,
                models.PriorityAlert.status != "resolved")
        .first()
    )
    if existing:
        existing.priority_score = priority_score
        existing.factors_json   = factors_json
        existing.title          = title
        db.commit()
        db.refresh(existing)
        return existing

    row = models.PriorityAlert(
        facility_id=facility_id, anomaly_id=anomaly_id,
        title=title, description=description,
        priority_score=priority_score, factors_json=factors_json,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_priority_alerts(db: Session, facility_id: int,
                         status: Optional[str] = None,
                         limit: int = 50) -> list[models.PriorityAlert]:
    q = db.query(models.PriorityAlert).filter(
        models.PriorityAlert.facility_id == facility_id
    )
    if status:
        q = q.filter(models.PriorityAlert.status == status)
    return q.order_by(desc(models.PriorityAlert.priority_score)).limit(limit).all()


def update_priority_alert(db: Session, alert_id: int, **kwargs) -> Optional[models.PriorityAlert]:
    row = db.query(models.PriorityAlert).filter(models.PriorityAlert.id == alert_id).first()
    if row:
        for k, v in kwargs.items():
            setattr(row, k, v)
        db.commit()
        db.refresh(row)
    return row


# ── Sustainability Scores ─────────────────────────────────────────────────────

def upsert_score(db: Session, facility_id: int, **kwargs) -> models.SustainabilityScore:
    from datetime import date
    score_date = kwargs.pop("score_date", date.today())
    row = (
        db.query(models.SustainabilityScore)
        .filter(models.SustainabilityScore.facility_id == facility_id,
                models.SustainabilityScore.score_date == score_date)
        .first()
    )
    if row:
        for k, v in kwargs.items():
            setattr(row, k, v)
        row.computed_at = datetime.utcnow()
    else:
        row = models.SustainabilityScore(
            facility_id=facility_id, score_date=score_date, **kwargs
        )
        db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_score_history(db: Session, facility_id: int, days: int = 30) -> list[models.SustainabilityScore]:
    from datetime import date
    since = date.today() - timedelta(days=days)
    return (
        db.query(models.SustainabilityScore)
        .filter(models.SustainabilityScore.facility_id == facility_id,
                models.SustainabilityScore.score_date >= since)
        .order_by(models.SustainabilityScore.score_date)
        .all()
    )


# ── Chat History ──────────────────────────────────────────────────────────────

def add_chat_message(db: Session, facility_id: int, role: str,
                     message: str, source: str = "rule_engine") -> models.ChatHistory:
    row = models.ChatHistory(facility_id=facility_id, role=role,
                             message=message, source=source)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_chat_history(db: Session, facility_id: int,
                     limit: int = 50) -> list[models.ChatHistory]:
    return (
        db.query(models.ChatHistory)
        .filter(models.ChatHistory.facility_id == facility_id)
        .order_by(models.ChatHistory.created_at)
        .limit(limit)
        .all()
    )


# ── Facilities ────────────────────────────────────────────────────────────────

def get_all_facilities(db: Session) -> list[models.Facility]:
    return db.query(models.Facility).all()


def get_facility(db: Session, facility_id: int) -> Optional[models.Facility]:
    return db.query(models.Facility).filter(models.Facility.id == facility_id).first()


# ── Simulation Runs ───────────────────────────────────────────────────────────

def create_simulation_run(db: Session, facility_id: int, name: str,
                           parameters_json: str, results_json: str,
                           impact_score: float) -> models.SimulationRun:
    row = models.SimulationRun(
        facility_id=facility_id, name=name,
        parameters_json=parameters_json, results_json=results_json,
        impact_score=impact_score,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_simulation_runs(db: Session, facility_id: int,
                         limit: int = 20) -> list[models.SimulationRun]:
    return (
        db.query(models.SimulationRun)
        .filter(models.SimulationRun.facility_id == facility_id)
        .order_by(desc(models.SimulationRun.created_at))
        .limit(limit)
        .all()
    )

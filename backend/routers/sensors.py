"""
backend/routers/sensors.py — Sensor registry and reading query endpoints
"""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.db import crud
from backend.schemas.sensor import SensorOut, SensorReadingOut, LiveMetric

# Static unit map — matches sensor.unit in seed data
METRIC_UNITS = {
    "energy_kwh":         "kWh",
    "pm25":               "µg/m³",
    "pm10":               "µg/m³",
    "water_litres":       "L",
    "bin_fill_pct":       "%",
    "temperature_c":      "°C",
    "humidity_pct":       "%",
    "occupancy_count":    "count",
    "parking_count":      "count",
    "equipment_util_pct": "%",
}

router = APIRouter(prefix="/sensors", tags=["Sensors"])
readings_router = APIRouter(prefix="/readings", tags=["Readings"])


@router.get("/", response_model=list[SensorOut])
def list_sensors(facility_id: int = Query(...), db: Session = Depends(get_db)):
    """List all active sensors for a facility."""
    return crud.get_sensors(db, facility_id)


@router.get("/{sensor_id}/latest", response_model=SensorReadingOut)
def latest_reading(sensor_id: int, db: Session = Depends(get_db)):
    """Latest reading for a specific sensor."""
    from sqlalchemy import desc
    from backend.db.models import SensorReading
    row = (
        db.query(SensorReading)
        .filter(SensorReading.sensor_id == sensor_id)
        .order_by(desc(SensorReading.timestamp))
        .first()
    )
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="No readings found for this sensor.")
    return row


@readings_router.get("/live", response_model=list[LiveMetric])
def live_readings(facility_id: int = Query(...), db: Session = Depends(get_db)):
    """
    Returns the latest reading for every metric in a facility.
    Used by Dashboard KPI tiles.
    """
    rows   = crud.get_latest_readings(db, facility_id)
    result = []
    for r in rows:
        sensor = crud.get_sensor_by_id(db, r.sensor_id)
        result.append(LiveMetric(
            metric_type=r.metric_type,
            value=r.value,
            unit=sensor.unit if sensor else METRIC_UNITS.get(r.metric_type, ""),
            timestamp=r.timestamp,
            source=r.source,
            sensor_id=r.sensor_id,
            zone_id=r.zone_id,
        ))
    return result


@readings_router.get("/", response_model=list[SensorReadingOut])
def query_readings(
    facility_id:  int                = Query(...),
    metric_type:  str                = Query(...),
    start:        Optional[datetime] = Query(None),
    end:          Optional[datetime] = Query(None),
    limit:        int                = Query(2000, le=10000),
    db: Session = Depends(get_db),
):
    """
    Time-range query for historical readings.
    Defaults: last 24 hours if start/end not provided.
    """
    end   = end   or datetime.utcnow()
    start = start or (end - timedelta(hours=24))
    return crud.get_readings_range(db, facility_id, metric_type, start, end, limit)

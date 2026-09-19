"""
backend/routers/ingest.py — Sensor data ingestion endpoints
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.db import crud
from backend.schemas.sensor import (
    BulkReadingIn, ManualReadingIn, IngestResponse, SensorReadingIn,
)
from backend.core import scheduler

router = APIRouter(prefix="/ingest", tags=["Ingestion"])


@router.post("/sensor", response_model=IngestResponse)
def ingest_sensor_readings(payload: BulkReadingIn, db: Session = Depends(get_db)):
    """
    Receive batch sensor readings from ESP32 / any HTTP client.
    Validates sensor IDs exist before inserting.
    """
    rows   = []
    errors = []

    for item in payload.readings:
        sensor = crud.get_sensor_by_id(db, item.sensor_id)
        if sensor is None:
            errors.append(f"sensor_id={item.sensor_id} not found")
            continue
        rows.append({
            "sensor_id":   item.sensor_id,
            "facility_id": sensor.facility_id,
            "zone_id":     sensor.zone_id,
            "metric_type": item.metric_type or sensor.metric_type,
            "value":       item.value,
            "timestamp":   item.timestamp,
            "source":      item.source,
        })

    if not rows:
        raise HTTPException(status_code=422, detail=f"No valid readings. Errors: {errors}")

    inserted = crud.bulk_create_readings(db, rows)
    msg = f"Inserted {inserted} reading(s)."
    if errors:
        msg += f" Skipped: {errors}"
    return IngestResponse(inserted=inserted, message=msg)


@router.post("/sensor/single", response_model=IngestResponse)
def ingest_single_reading(item: SensorReadingIn, db: Session = Depends(get_db)):
    """Convenience endpoint for a single sensor reading."""
    return ingest_sensor_readings(BulkReadingIn(readings=[item]), db)


@router.post("/manual", response_model=IngestResponse)
def ingest_manual(payload: ManualReadingIn, db: Session = Depends(get_db)):
    """
    Admin manual data entry. Finds the sensor for the facility+metric,
    creates a reading tagged as source='manual'.
    """
    sensor = crud.get_sensor_by_metric(db, payload.facility_id, payload.metric_type)
    if sensor is None:
        raise HTTPException(
            status_code=404,
            detail=f"No active sensor for metric '{payload.metric_type}' in facility {payload.facility_id}",
        )
    crud.create_reading(
        db,
        sensor_id=sensor.id,
        facility_id=payload.facility_id,
        zone_id=payload.zone_id or sensor.zone_id,
        metric_type=payload.metric_type,
        value=payload.value,
        source="manual",
    )
    return IngestResponse(inserted=1, message="Manual reading inserted.")


@router.post("/synthetic/toggle", summary="Start or stop synthetic data generator")
def toggle_synthetic(enable: bool = True):
    result = scheduler.toggle_synthetic(enable)
    action = "started" if result else "stopped"
    return {"running": result, "message": f"Synthetic generator {action}."}


@router.get("/synthetic/status", summary="Check synthetic generator status")
def synthetic_status():
    return scheduler.synthetic_status()

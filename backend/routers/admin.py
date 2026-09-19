"""
backend/routers/admin.py — Admin endpoints (facilities, zones, sensors, thresholds, auth)
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.db import crud, models
from backend.schemas.admin import (
    FacilityOut, FacilityCreate, ZoneOut, ThresholdOut, ThresholdUpdate,
    AuthVerifyIn, AuthVerifyOut,
)
from backend.core.config import get_settings

router = APIRouter(prefix="/admin", tags=["Admin"])


# ── Auth ──────────────────────────────────────────────────────────────────────

@router.post("/auth/verify", response_model=AuthVerifyOut)
def verify_password(payload: AuthVerifyIn):
    cfg = get_settings()
    if payload.password == cfg.admin_password:
        return AuthVerifyOut(ok=True, message="Authenticated.")
    raise HTTPException(status_code=401, detail="Incorrect password.")


# ── Facilities ────────────────────────────────────────────────────────────────

@router.get("/facilities", response_model=list[FacilityOut])
def list_facilities(db: Session = Depends(get_db)):
    return crud.get_all_facilities(db)


@router.post("/facilities", response_model=FacilityOut, status_code=201)
def create_facility(payload: FacilityCreate, db: Session = Depends(get_db)):
    row = models.Facility(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/facilities/{facility_id}", status_code=204)
def delete_facility(facility_id: int, db: Session = Depends(get_db)):
    row = crud.get_facility(db, facility_id)
    if not row:
        raise HTTPException(404, "Facility not found.")
    db.delete(row)
    db.commit()


# ── Zones ─────────────────────────────────────────────────────────────────────

@router.get("/zones", response_model=list[ZoneOut])
def list_zones(facility_id: int, db: Session = Depends(get_db)):
    return (
        db.query(models.Zone)
        .filter(models.Zone.facility_id == facility_id)
        .all()
    )


@router.post("/zones", response_model=ZoneOut, status_code=201)
def create_zone(facility_id: int, name: str, zone_type: str = "",
                floor_number: int = 0, db: Session = Depends(get_db)):
    row = models.Zone(facility_id=facility_id, name=name,
                      zone_type=zone_type, floor_number=floor_number)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# ── Sensors ───────────────────────────────────────────────────────────────────

@router.get("/sensors", response_model=list)
def list_sensors_admin(facility_id: int, db: Session = Depends(get_db)):
    from backend.schemas.sensor import SensorOut
    sensors = crud.get_sensors(db, facility_id)
    return [SensorOut.model_validate(s) for s in sensors]


# ── Thresholds ────────────────────────────────────────────────────────────────

@router.get("/thresholds", response_model=list[ThresholdOut])
def get_thresholds(facility_type_id: int = 1, db: Session = Depends(get_db)):
    return crud.get_all_thresholds(db, facility_type_id)


@router.put("/thresholds/{threshold_id}", response_model=ThresholdOut)
def update_threshold(threshold_id: int, payload: ThresholdUpdate,
                     db: Session = Depends(get_db)):
    row = crud.update_threshold(
        db, threshold_id,
        **{k: v for k, v in payload.model_dump().items() if v is not None}
    )
    if not row:
        raise HTTPException(404, "Threshold not found.")
    return row

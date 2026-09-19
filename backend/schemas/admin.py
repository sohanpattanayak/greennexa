"""
backend/schemas/admin.py — Pydantic schemas for admin endpoints
"""

from typing import Optional
from pydantic import BaseModel


class FacilityOut(BaseModel):
    id:               int
    name:             str
    city:             str
    state:            str
    facility_type_id: int
    area_sqft:        Optional[float]
    building_count:   Optional[int]

    model_config = {"from_attributes": True}


class FacilityCreate(BaseModel):
    name:             str
    city:             str
    state:            str
    facility_type_id: int
    area_sqft:        Optional[float] = None
    building_count:   int = 1


class ZoneOut(BaseModel):
    id:           int
    facility_id:  int
    name:         str
    zone_type:    Optional[str]
    floor_number: int

    model_config = {"from_attributes": True}


class ThresholdOut(BaseModel):
    id:               int
    facility_type_id: int
    metric_type:      str
    warn_low:         Optional[float]
    warn_high:        Optional[float]
    critical_low:     Optional[float]
    critical_high:    Optional[float]
    unit:             Optional[str]
    notes:            Optional[str]

    model_config = {"from_attributes": True}


class ThresholdUpdate(BaseModel):
    warn_low:      Optional[float] = None
    warn_high:     Optional[float] = None
    critical_low:  Optional[float] = None
    critical_high: Optional[float] = None
    notes:         Optional[str]   = None


class AuthVerifyIn(BaseModel):
    password: str


class AuthVerifyOut(BaseModel):
    ok:      bool
    message: str

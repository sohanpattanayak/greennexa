"""
backend/schemas/sensor.py — Pydantic schemas for sensor & reading endpoints
"""

from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field


# ── Ingest ────────────────────────────────────────────────────────────────────

class SensorReadingIn(BaseModel):
    """Single reading payload — from ESP32 or script."""
    sensor_id:   int
    metric_type: str
    value:       float
    timestamp:   Optional[datetime] = None
    source:      Literal["esp32", "synthetic", "manual"] = "esp32"


class BulkReadingIn(BaseModel):
    readings: list[SensorReadingIn]


class ManualReadingIn(BaseModel):
    """Admin manual entry."""
    facility_id: int
    zone_id:     Optional[int] = None
    metric_type: str
    value:       float = Field(..., description="Reading value in the metric's unit")
    notes:       Optional[str] = None


# ── Responses ─────────────────────────────────────────────────────────────────

class SensorReadingOut(BaseModel):
    id:          int
    sensor_id:   int
    facility_id: int
    zone_id:     Optional[int]
    metric_type: str
    value:       float
    timestamp:   datetime
    source:      str

    model_config = {"from_attributes": True}


class SensorOut(BaseModel):
    id:          int
    facility_id: int
    zone_id:     Optional[int]
    metric_type: str
    unit:        str
    description: Optional[str]
    mac_address: Optional[str]
    is_active:   bool

    model_config = {"from_attributes": True}


class LiveMetric(BaseModel):
    metric_type:  str
    value:        float
    unit:         str
    timestamp:    datetime
    source:       str
    sensor_id:    int
    zone_id:      Optional[int]


class IngestResponse(BaseModel):
    inserted: int
    message:  str

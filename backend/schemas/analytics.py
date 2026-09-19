"""
backend/schemas/analytics.py — Pydantic schemas for analytics endpoints
"""

from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel


class TrendPoint(BaseModel):
    timestamp: datetime
    avg_value: float
    min_value: float
    max_value: float


class TrendResponse(BaseModel):
    facility_id: int
    metric_type: str
    granularity: str   # hourly | daily
    points:      list[TrendPoint]


class AnomalyOut(BaseModel):
    id:               int
    sensor_id:        int
    facility_id:      int
    zone_id:          Optional[int]
    metric_type:      str
    value:            float
    threshold_low:    Optional[float]
    threshold_high:   Optional[float]
    severity:         str
    detected_at:      datetime
    is_resolved:      bool
    detection_method: str

    model_config = {"from_attributes": True}


class ForecastPoint(BaseModel):
    timestamp:   datetime
    yhat:        float
    yhat_lower:  Optional[float] = None
    yhat_upper:  Optional[float] = None


class ForecastResponse(BaseModel):
    facility_id:   int
    metric_type:   str
    model_used:    str   # prophet | linear_regression_fallback
    generated_at:  datetime
    horizon_hours: int
    points:        list[ForecastPoint]


class SummaryStats(BaseModel):
    metric_type: str
    avg:         float
    min_val:     float
    max_val:     float
    latest:      float
    unit:        str
    period_hours: int


class DetectAnomaliesResponse(BaseModel):
    detected: int
    message:  str

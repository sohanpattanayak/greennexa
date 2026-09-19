"""
backend/services/synthetic.py — Realistic synthetic sensor data generator
Generates college-campus-realistic readings for all 10 metrics.
"""

import math
import random
from datetime import datetime

from sqlalchemy.orm import Session

from backend.db import crud


# Stateful bin fill (persists across calls within a process run)
_bin_fill: float = 20.0
_rng = random.Random(None)   # seeded from system time for variability


def _is_weekday(dt: datetime) -> bool:
    return dt.weekday() < 5


def _college_activity(hour: int, weekday: bool) -> float:
    """Returns 0.0–1.0 campus activity level."""
    if not weekday:
        return 0.08 + 0.04 * math.sin(math.pi * hour / 12)
    if hour < 7:
        return 0.05
    elif 7 <= hour < 9:
        return 0.05 + 0.80 * ((hour - 7) / 2)
    elif 9 <= hour <= 17:
        return 0.85 + 0.12 * math.sin(math.pi * (hour - 9) / 8)
    elif 17 < hour <= 20:
        return 0.85 - 0.72 * ((hour - 17) / 3)
    return 0.08


def generate_all_readings(sensors: list, facility_id: int) -> list[dict]:
    """
    Generate one reading per active sensor for the current moment.
    Returns list of dicts ready for bulk_insert_mappings.
    """
    global _bin_fill
    now     = datetime.utcnow()
    hour    = now.hour
    weekday = _is_weekday(now)
    factor  = _college_activity(hour, weekday)

    # Pre-calculate correlated values
    temp     = _gen_temperature(hour)
    pm25     = _gen_pm25(hour, weekday)
    occ      = _gen_occupancy(factor)

    metric_fn = {
        "energy_kwh":         lambda: _gen_energy(factor),
        "pm25":               lambda: pm25,
        "pm10":               lambda: _gen_pm10(pm25),
        "water_litres":       lambda: _gen_water(hour, factor, weekday),
        "bin_fill_pct":       lambda: _gen_bin_fill(factor),
        "temperature_c":      lambda: temp,
        "humidity_pct":       lambda: _gen_humidity(temp),
        "occupancy_count":    lambda: float(occ),
        "parking_count":      lambda: float(_gen_parking(occ)),
        "equipment_util_pct": lambda: _gen_equipment(hour, weekday),
    }

    rows = []
    for sensor in sensors:
        if not sensor.is_active:
            continue
        fn = metric_fn.get(sensor.metric_type)
        if fn is None:
            continue
        rows.append({
            "sensor_id":   sensor.id,
            "facility_id": facility_id,
            "zone_id":     sensor.zone_id,
            "metric_type": sensor.metric_type,
            "value":       float(fn()),
            "timestamp":   now,
            "source":      "synthetic",
        })
    return rows


# ── Individual generators ─────────────────────────────────────────────────────

def _gen_energy(factor: float) -> float:
    base  = 3.0 + 18.0 * factor
    noise = _rng.gauss(0, 0.9)
    return max(0.5, round(base + noise, 2))


def _gen_pm25(hour: int, weekday: bool) -> float:
    base = 12.0
    if weekday and hour in (8, 9, 17, 18, 19):
        base += _rng.uniform(10, 22)
    noise = _rng.gauss(0, 2.5)
    return max(2.0, round(base + noise, 2))


def _gen_pm10(pm25: float) -> float:
    ratio = _rng.uniform(1.7, 2.3)
    return max(5.0, round(pm25 * ratio, 2))


def _gen_water(hour: int, factor: float, weekday: bool) -> float:
    base  = 50.0 + 280.0 * factor
    if weekday and 11 <= hour <= 14:
        base += _rng.uniform(100, 200)   # canteen lunch rush
    noise = _rng.gauss(0, 22)
    return max(0.0, round(base + noise, 2))


def _gen_bin_fill(factor: float) -> float:
    global _bin_fill
    fill_rate = factor * _rng.uniform(0.15, 0.6)  # % per interval
    _bin_fill = min(100.0, _bin_fill + fill_rate)
    if _bin_fill >= 82.0:
        _bin_fill = _rng.uniform(3.0, 10.0)        # collection event
    return round(_bin_fill, 1)


def _gen_temperature(hour: int) -> float:
    base  = 26.0
    swing = 5.0
    angle = 2 * math.pi * (hour - 5) / 24
    noise = _rng.gauss(0, 0.35)
    return round(base + swing * math.sin(angle) + noise, 1)


def _gen_humidity(temp: float) -> float:
    base  = 62.0 - 1.1 * (temp - 20.0)
    noise = _rng.gauss(0, 2.0)
    return max(20.0, min(95.0, round(base + noise, 1)))


def _gen_occupancy(factor: float) -> int:
    count = int(4800 * factor + _rng.gauss(0, 90))
    return max(0, min(5000, count))


def _gen_parking(occupancy: int) -> int:
    count = int(occupancy / 8.5 + _rng.gauss(0, 12))
    return max(0, min(500, count))


def _gen_equipment(hour: int, weekday: bool) -> float:
    util = 8.0
    if weekday:
        if 9 <= hour < 11 or 14 <= hour < 16:
            util = _rng.uniform(62.0, 92.0)   # lab practical hours
        elif 8 <= hour < 18:
            util = _rng.uniform(18.0, 42.0)   # general usage
    noise = _rng.gauss(0, 2.5)
    return max(0.0, min(100.0, round(util + noise, 1)))

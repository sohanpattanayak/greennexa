"""
generate_seed.py — SFEID Historical Seed Data Generator
========================================================
Generates 7 days of realistic synthetic sensor readings for
SFEID College of Engineering and inserts them into MySQL.

Run ONCE after applying schema.sql:
    python database/generate_seed.py

Requires: pymysql, python-dotenv
"""

import os
import math
import random
from datetime import datetime, timedelta

import pymysql
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# ── DB connection ──────────────────────────────────────────────────────────────
conn = pymysql.connect(
    host     = os.getenv("DB_HOST", "localhost"),
    port     = int(os.getenv("DB_PORT", 3306)),
    user     = os.getenv("DB_USER", "root"),
    password = os.getenv("DB_PASSWORD", ""),
    database = os.getenv("DB_NAME", "sfeid_db"),
    charset  = "utf8mb4",
)
cursor = conn.cursor()

# ── Constants ──────────────────────────────────────────────────────────────────
FACILITY_ID  = 1
DAYS_BACK    = 7          # how many days of history to generate
INTERVAL_MIN = 5          # one reading every 5 minutes
SENSORS = {
    # sensor_id: (zone_id, metric_type)
    1:  (1, "energy_kwh"),
    2:  (2, "pm25"),
    3:  (2, "pm10"),
    4:  (3, "water_litres"),
    5:  (3, "bin_fill_pct"),
    6:  (1, "temperature_c"),
    7:  (1, "humidity_pct"),
    8:  (1, "occupancy_count"),
    9:  (4, "parking_count"),
    10: (2, "equipment_util_pct"),
}

random.seed(42)   # reproducible demo data


def is_weekday(dt: datetime) -> bool:
    return dt.weekday() < 5


def college_hour_factor(hour: int, is_wd: bool) -> float:
    """Returns 0.0–1.0 representing campus activity level for a given hour."""
    if not is_wd:
        # Weekend: low baseline activity (hostel, security)
        return 0.10 + 0.05 * math.sin(math.pi * hour / 12)

    # Weekday activity curve (8 AM → peak → 6 PM → drop)
    if hour < 7:
        return 0.05
    elif 7 <= hour < 9:
        return 0.05 + 0.80 * ((hour - 7) / 2)   # ramp up
    elif 9 <= hour <= 17:
        return 0.85 + 0.15 * math.sin(math.pi * (hour - 9) / 8)
    elif 17 < hour <= 20:
        return 0.85 - 0.70 * ((hour - 17) / 3)  # ramp down
    else:
        return 0.10


def gen_energy(dt: datetime) -> float:
    """kWh per 5-minute interval (base 3 kWh, peak ~18 kWh)."""
    factor = college_hour_factor(dt.hour, is_weekday(dt))
    base   = 3.0 + 15.0 * factor
    noise  = random.gauss(0, 0.8)
    return max(0.5, round(base + noise, 2))


def gen_pm25(dt: datetime) -> float:
    """µg/m³ — traffic peaks at 8–10 AM and 5–7 PM."""
    base  = 12.0
    if is_weekday(dt) and dt.hour in (8, 9, 17, 18):
        base += 18.0
    noise = random.gauss(0, 2.5)
    return max(2.0, round(base + noise, 2))


def gen_pm10(pm25: float) -> float:
    """PM10 ≈ 1.8–2.2× PM2.5."""
    ratio = random.uniform(1.8, 2.2)
    return max(5.0, round(pm25 * ratio, 2))


def gen_water(dt: datetime) -> float:
    """Litres per 5-minute interval — canteen peaks at 12–2 PM."""
    factor = college_hour_factor(dt.hour, is_weekday(dt))
    # Extra canteen spike at lunch
    canteen_boost = 0
    if is_weekday(dt) and 11 <= dt.hour <= 14:
        canteen_boost = 150.0
    base  = 50.0 + 250.0 * factor + canteen_boost
    noise = random.gauss(0, 20)
    return max(0.0, round(base + noise, 2))


_bin_fill = {sid: 0.0 for sid in [5]}   # stateful fill level per sensor

def gen_bin_fill(dt: datetime) -> float:
    """% fill — slow accumulation, reset when collection triggered (>80%)."""
    global _bin_fill
    fill_rate = 0.0
    if is_weekday(dt) and 8 <= dt.hour <= 20:
        fill_rate = random.uniform(0.2, 0.8)  # % per 5-min interval
    _bin_fill[5] = min(100.0, _bin_fill[5] + fill_rate)
    if _bin_fill[5] >= 82.0:
        _bin_fill[5] = random.uniform(2.0, 8.0)   # waste collected
    return round(_bin_fill[5], 1)


def gen_temperature(dt: datetime) -> float:
    """°C — sinusoidal daily: min ~20°C at 5 AM, max ~30°C at 3 PM."""
    base  = 25.0
    swing = 5.0
    angle = 2 * math.pi * (dt.hour - 5) / 24
    temp  = base + swing * math.sin(angle)
    noise = random.gauss(0, 0.3)
    return round(temp + noise, 1)


def gen_humidity(temp_c: float) -> float:
    """% — inversely correlated with temperature."""
    base  = 65.0 - 1.0 * (temp_c - 20.0)
    noise = random.gauss(0, 2.0)
    return max(20.0, min(95.0, round(base + noise, 1)))


def gen_occupancy(dt: datetime) -> int:
    """Head count — step function for college schedule."""
    factor = college_hour_factor(dt.hour, is_weekday(dt))
    count  = int(4800 * factor + random.gauss(0, 80))
    return max(0, min(5000, count))


def gen_parking(occupancy: int) -> int:
    """Parking count — correlated with occupancy / 8 (assume 8 pax per vehicle avg)."""
    count = int(occupancy / 8.5 + random.gauss(0, 10))
    return max(0, min(500, count))


def gen_equipment_util(dt: datetime) -> float:
    """% — spikes during lab practicals (9–11 AM, 2–4 PM weekdays)."""
    util = 10.0
    if is_weekday(dt):
        if 9 <= dt.hour < 11 or 14 <= dt.hour < 16:
            util = random.uniform(65.0, 90.0)
        elif 8 <= dt.hour < 18:
            util = random.uniform(20.0, 45.0)
    noise = random.gauss(0, 2.0)
    return max(0.0, min(100.0, round(util + noise, 1)))


# ── Generate and insert ────────────────────────────────────────────────────────
now   = datetime.now().replace(second=0, microsecond=0)
start = now - timedelta(days=DAYS_BACK)

rows  = []
dt    = start

print(f"Generating readings from {start} to {now} (every {INTERVAL_MIN} min)...")
tick  = 0

while dt <= now:
    tick += 1
    temp  = gen_temperature(dt)
    pm25  = gen_pm25(dt)
    occ   = gen_occupancy(dt)

    metric_values = {
        "energy_kwh":        gen_energy(dt),
        "pm25":              pm25,
        "pm10":              gen_pm10(pm25),
        "water_litres":      gen_water(dt),
        "bin_fill_pct":      gen_bin_fill(dt),
        "temperature_c":     temp,
        "humidity_pct":      gen_humidity(temp),
        "occupancy_count":   occ,
        "parking_count":     gen_parking(occ),
        "equipment_util_pct": gen_equipment_util(dt),
    }

    for sensor_id, (zone_id, metric_type) in SENSORS.items():
        value = metric_values[metric_type]
        rows.append((sensor_id, FACILITY_ID, zone_id, metric_type,
                     float(value), dt, "synthetic"))

    # Batch insert every 500 rows
    if len(rows) >= 500:
        cursor.executemany(
            "INSERT INTO sensor_readings "
            "(sensor_id, facility_id, zone_id, metric_type, value, timestamp, source) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            rows,
        )
        conn.commit()
        rows = []

    dt += timedelta(minutes=INTERVAL_MIN)

# Flush remaining
if rows:
    cursor.executemany(
        "INSERT INTO sensor_readings "
        "(sensor_id, facility_id, zone_id, metric_type, value, timestamp, source) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        rows,
    )
    conn.commit()

total_ticks = tick
total_rows  = total_ticks * len(SENSORS)
print(f"✅ Inserted ~{total_rows:,} sensor readings across {len(SENSORS)} sensors.")
print("   Seed generation complete. Open MySQL Workbench to verify.")

cursor.close()
conn.close()

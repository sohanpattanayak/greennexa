"""
data_simulator/mock_esp32.py — ESP32 Hardware Simulator Script

Simulates a physical ESP32 microcontroller sending HTTP POST readings
to the FastAPI `/ingest/sensor` endpoint every N seconds.
"""

import time
import random
import requests
from datetime import datetime

API_URL = "http://localhost:8000/ingest/sensor"
INTERVAL_SECONDS = 30

# Demo campus sensors (matching database IDs 1–10)
SENSORS = [
    {"sensor_id": 1, "metric_type": "energy_kwh",         "base": 12.0, "unit": "kWh"},
    {"sensor_id": 2, "metric_type": "pm25",               "base": 15.0, "unit": "µg/m³"},
    {"sensor_id": 3, "metric_type": "pm10",               "base": 30.0, "unit": "µg/m³"},
    {"sensor_id": 4, "metric_type": "water_litres",       "base": 180.0,"unit": "L"},
    {"sensor_id": 5, "metric_type": "bin_fill_pct",       "base": 45.0, "unit": "%"},
    {"sensor_id": 6, "metric_type": "temperature_c",      "base": 26.5, "unit": "°C"},
    {"sensor_id": 7, "metric_type": "humidity_pct",       "base": 58.0, "unit": "%"},
    {"sensor_id": 8, "metric_type": "occupancy_count",    "base": 2400.0,"unit": "people"},
    {"sensor_id": 9, "metric_type": "parking_count",      "base": 220.0, "unit": "vehicles"},
    {"sensor_id": 10,"metric_type": "equipment_util_pct", "base": 65.0, "unit": "%"},
]


def generate_reading(sensor: dict) -> dict:
    base = sensor["base"]
    # 5% chance to simulate a spike anomaly
    if random.random() < 0.05:
        value = base * random.uniform(1.8, 2.5)
        print(f"🔥 SPIKE ANOMALY generated for {sensor['metric_type']}: {value:.2f}")
    else:
        value = base + random.gauss(0, base * 0.08)

    return {
        "sensor_id":   sensor["sensor_id"],
        "metric_type": sensor["metric_type"],
        "value":       round(max(0.0, value), 2),
        "timestamp":   datetime.utcnow().isoformat(),
        "source":      "esp32",
    }


def main():
    print(f"📡 ESP32 Mock Hardware Simulator starting...")
    print(f"Target Endpoint: {API_URL}")
    print(f"Interval: {INTERVAL_SECONDS} seconds\n")

    while True:
        payload = {"readings": [generate_reading(s) for s in SENSORS]}
        try:
            r = requests.post(API_URL, json=payload, timeout=10)
            if r.status_code == 200:
                data = r.json()
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Batch sent successfully! {data.get('message')}")
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ API returned HTTP {r.status_code}: {r.text}")
        except Exception as exc:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Connection error: {exc}. Retrying in {INTERVAL_SECONDS}s...")

        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()

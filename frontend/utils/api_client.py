"""
frontend/utils/api_client.py — Typed HTTP wrappers for all FastAPI endpoints.

All functions return plain Python dicts/lists.
On HTTP error, returns an empty result + logs a warning — never crashes the UI.
"""

import logging
from datetime import datetime
from typing import Optional

import requests

log = logging.getLogger("sfeid.api_client")
# Set via st.session_state, st.secrets, or fallback to Render URL
try:
  import streamlit as st

  _BASE = st.secrets.get("API_BASE_URL", "https://greennexa.onrender.com")
except Exception:
  _BASE = "https://greennexa.onrender.com"


def _base() -> str:
  """Return API base URL - overridable via session state in app.py."""
  return"https://greennexa.onrender.com"

def _get(path: str, params: dict = None) -> dict | list:
    try:
        r = requests.get(f"{_base()}{path}", params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        log.warning(f"GET {path} failed: {exc}")
        return {} if not path.endswith("/") else []


def _post(path: str, json: dict = None, params: dict = None) -> dict:
    try:
        r = requests.post(f"{_base()}{path}", json=json, params=params, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        log.warning(f"POST {path} failed: {exc}")
        return {}


def _patch(path: str, json: dict = None) -> dict:
    try:
        r = requests.patch(f"{_base()}{path}", json=json, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        log.warning(f"PATCH {path} failed: {exc}")
        return {}


def _delete(path: str) -> bool:
    try:
        r = requests.delete(f"{_base()}{path}", timeout=10)
        return r.status_code in (200, 204)
    except Exception:
        return False


# ── Health ────────────────────────────────────────────────────────────────────

def health() -> dict:
    return _get("/health")


def api_status() -> dict:
    return _get("/")


# ── Sensors & Readings ────────────────────────────────────────────────────────

def get_sensors(facility_id: int) -> list:
    return _get("/sensors/", {"facility_id": facility_id}) or []


def get_live_readings(facility_id: int) -> list:
    return _get("/readings/live", {"facility_id": facility_id}) or []


def get_readings(facility_id: int, metric_type: str,
                 start: Optional[datetime] = None,
                 end: Optional[datetime]   = None,
                 limit: int = 2000) -> list:
    params = {"facility_id": facility_id, "metric_type": metric_type, "limit": limit}
    if start:
        params["start"] = start.isoformat()
    if end:
        params["end"]   = end.isoformat()
    return _get("/readings/", params) or []


# ── Ingestion ─────────────────────────────────────────────────────────────────

def ingest_manual(facility_id: int, metric_type: str, value: float,
                   zone_id: Optional[int] = None) -> dict:
    return _post("/ingest/manual", {
        "facility_id": facility_id,
        "metric_type": metric_type,
        "value":       value,
        "zone_id":     zone_id,
    })


def toggle_synthetic(enable: bool) -> dict:
    return _post("/ingest/synthetic/toggle", params={"enable": str(enable).lower()})


def synthetic_status() -> dict:
    return _get("/ingest/synthetic/status")


# ── Analytics ─────────────────────────────────────────────────────────────────

def get_trends(facility_id: int, metric_type: str,
               granularity: str = "hourly",
               hours: int = 48) -> dict:
    return _get("/analytics/trends", {
        "facility_id": facility_id,
        "metric_type": metric_type,
        "granularity": granularity,
        "hours":       hours,
    })


def get_anomalies(facility_id: int, resolved: bool = False,
                  severity: Optional[str] = None, limit: int = 100) -> list:
    params = {"facility_id": facility_id, "resolved": resolved, "limit": limit}
    if severity:
        params["severity"] = severity
    return _get("/analytics/anomalies", params) or []


def trigger_anomaly_detection(facility_id: int) -> dict:
    return _post("/analytics/anomalies/detect", params={"facility_id": facility_id})


def get_forecast(facility_id: int, metric_type: str) -> dict:
    return _get("/analytics/forecast", {"facility_id": facility_id, "metric_type": metric_type})


def generate_forecast(facility_id: int, metric_type: str) -> dict:
    return _post("/analytics/forecast/generate", params={
        "facility_id": facility_id, "metric_type": metric_type
    })


def get_summary(facility_id: int, hours: int = 24) -> list:
    return _get("/analytics/summary", {"facility_id": facility_id, "hours": hours}) or []


# ── AI & Chat ─────────────────────────────────────────────────────────────────

def ai_status() -> dict:
    return _get("/ai/status")


def get_recommendations(facility_id: int, acknowledged: bool = False,
                        limit: int = 20) -> list:
    return _get("/ai/recommendations/", {
        "facility_id": facility_id, "acknowledged": acknowledged, "limit": limit
    }) or []


def generate_recommendations(facility_id: int) -> dict:
    return _post("/ai/recommendations/generate", params={"facility_id": facility_id})


def acknowledge_recommendation(rec_id: int) -> dict:
    return _patch(f"/ai/recommendations/{rec_id}/acknowledge")


def send_chat_message(facility_id: int, message: str) -> dict:
    return _post("/ai/chat", {"facility_id": facility_id, "message": message})


def get_chat_history(facility_id: int, limit: int = 50) -> list:
    return _get("/ai/chat/history", {"facility_id": facility_id, "limit": limit}) or []


# ── Priority ──────────────────────────────────────────────────────────────────

def get_priority_alerts(facility_id: int, status: Optional[str] = None,
                        limit: int = 50) -> list:
    params = {"facility_id": facility_id, "limit": limit}
    if status:
        params["status"] = status
    return _get("/priority/alerts", params) or []


def run_priority_engine(facility_id: int) -> dict:
    return _post("/priority/run", params={"facility_id": facility_id})


def update_alert(alert_id: int, status: Optional[str] = None,
                 assigned_to: Optional[str] = None) -> dict:
    return _patch(f"/priority/alerts/{alert_id}", {
        "status": status, "assigned_to": assigned_to
    })


# ── Scores ────────────────────────────────────────────────────────────────────

def get_sustainability_score(facility_id: int) -> dict:
    return _get("/scores/sustainability", {"facility_id": facility_id})


def get_score_history(facility_id: int, days: int = 30) -> list:
    return _get("/scores/history", {"facility_id": facility_id, "days": days}) or []


def compute_score(facility_id: int) -> dict:
    return _post("/scores/compute", params={"facility_id": facility_id})


# ── Scenario Simulation ───────────────────────────────────────────────────────

def run_simulation(params: dict) -> dict:
    return _post("/scenario/simulate", params)


def get_simulation_runs(facility_id: int, limit: int = 20) -> list:
    return _get("/scenario/runs", {"facility_id": facility_id, "limit": limit}) or []


def delete_simulation_run(run_id: int) -> bool:
    return _delete(f"/scenario/runs/{run_id}")


# ── Admin ─────────────────────────────────────────────────────────────────────

def verify_password(password: str) -> bool:
    result = _post("/admin/auth/verify", {"password": password})
    return result.get("ok", False)


def get_facilities() -> list:
    return _get("/admin/facilities") or []


def get_thresholds(facility_type_id: int = 1) -> list:
    return _get("/admin/thresholds", {"facility_type_id": facility_type_id}) or []


def update_threshold(threshold_id: int, updates: dict) -> dict:
    try:
        r = requests.put(f"{_base()}/admin/thresholds/{threshold_id}",
                         json=updates, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        log.warning(f"PUT /admin/thresholds/{threshold_id} failed: {exc}")
        return {}

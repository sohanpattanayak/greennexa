"""
backend/services/voice_chat.py — Admin Chat Service

Rule-based intent classifier + template responses.
Optionally enhanced by Gemini when GEMINI_API_KEY is set.
Also handles audio transcription via SpeechRecognition library (free).
"""

import io
import logging
from datetime import datetime

import numpy as np
from sqlalchemy.orm import Session

from backend.core.config import get_settings
from backend.db import crud

log = logging.getLogger("sfeid.voice_chat")
cfg = get_settings()

# ── Intent keyword map ─────────────────────────────────────────────────────────
INTENT_KEYWORDS = {
    "query_energy":       ["energy", "power", "kwh", "electricity", "consumption"],
    "query_water":        ["water", "usage", "litres", "liter", "flow"],
    "query_air":          ["air", "pm2.5", "pm25", "pm10", "pollution", "aqi", "quality"],
    "query_temperature":  ["temperature", "temp", "hvac", "heat", "cool", "cold", "hot"],
    "query_humidity":     ["humidity", "humid", "moisture"],
    "query_occupancy":    ["occupancy", "occupant", "people", "crowd", "students", "staff"],
    "query_waste":        ["waste", "bin", "trash", "garbage", "fill"],
    "query_parking":      ["parking", "vehicle", "car", "park"],
    "query_equipment":    ["equipment", "lab", "utilisation", "utilization", "machine"],
    "query_anomalies":    ["anomaly", "anomalies", "alert", "problem", "issue", "fault", "error"],
    "query_score":        ["score", "sustainability", "green", "grade", "rating", "performance"],
    "query_forecast":     ["forecast", "predict", "prediction", "tomorrow", "next", "future"],
    "query_recommendations":["recommend", "suggestion", "advice", "tip", "improve", "should"],
    "query_priority":     ["priority", "urgent", "critical", "top", "worst"],
    "action_simulate":    ["simulate", "scenario", "what if", "what-if", "if i", "reduce", "change"],
    "show_help":          ["help", "commands", "what can", "how to", "list"],
}


def classify_intent(message: str) -> str:
    """Returns the best-matching intent for a user message."""
    msg_lower = message.lower()
    best_intent = "unknown"
    best_count  = 0

    for intent, keywords in INTENT_KEYWORDS.items():
        count = sum(1 for kw in keywords if kw in msg_lower)
        if count > best_count:
            best_count  = count
            best_intent = intent

    return best_intent if best_count > 0 else "unknown"


def get_context_snapshot(db: Session, facility_id: int) -> dict:
    """Build a lightweight context dict for template filling and LLM enhancement."""
    live = crud.get_latest_readings(db, facility_id)
    live_map = {r.metric_type: round(r.value, 2) for r in live}

    anomalies = crud.get_anomalies(db, facility_id, resolved=False, limit=5)
    alerts    = crud.get_priority_alerts(db, facility_id, limit=1)
    score_row = crud.get_score_history(db, facility_id, days=1)

    return {
        "live":          live_map,
        "anomaly_count": len(anomalies),
        "top_anomaly":   anomalies[0] if anomalies else None,
        "top_alert":     alerts[0]    if alerts    else None,
        "score":         score_row[-1].overall_score if score_row else None,
        "facility_id":   facility_id,
    }


def build_response(intent: str, ctx: dict, message: str) -> str:
    """Return a plain-text response for the given intent using live context."""
    live = ctx.get("live", {})
    n_anomalies = ctx.get("anomaly_count", 0)
    score       = ctx.get("score")

    def val(metric, unit=""):
        v = live.get(metric)
        return f"{v:.2f} {unit}".strip() if v is not None else "no data"

    if intent == "query_energy":
        return (
            f"⚡ **Energy Consumption**\n"
            f"Current reading: **{val('energy_kwh', 'kWh')}**\n"
            f"{'🔴 Above threshold — check Priority Engine.' if live.get('energy_kwh', 0) > 70 else '✅ Within normal range.'}"
        )
    elif intent == "query_water":
        return f"💧 **Water Usage**\nCurrent: **{val('water_litres', 'L/hr')}**"

    elif intent == "query_air":
        return (
            f"🌫️ **Air Quality**\n"
            f"PM2.5: **{val('pm25', 'µg/m³')}** | PM10: **{val('pm10', 'µg/m³')}**\n"
            f"{'⚠️ PM levels elevated. Check ventilation.' if live.get('pm25', 0) > 35 else '✅ Air quality is acceptable.'}"
        )
    elif intent == "query_temperature":
        return f"🌡️ **Temperature**\nCurrent: **{val('temperature_c', '°C')}** | Humidity: **{val('humidity_pct', '%')}**"

    elif intent == "query_humidity":
        return f"💦 **Humidity**\nCurrent: **{val('humidity_pct', '%')}**"

    elif intent == "query_occupancy":
        return f"👥 **Occupancy**\nCurrent: **{val('occupancy_count', 'people')}** | Parking: **{val('parking_count', 'vehicles')}**"

    elif intent == "query_waste":
        fill = live.get("bin_fill_pct", 0)
        status = "🔴 Critical — dispatch collection" if fill >= 90 else ("🟡 Getting full" if fill >= 75 else "✅ Normal")
        return f"🗑️ **Waste Bin Status**\nFill level: **{fill:.1f}%** — {status}"

    elif intent == "query_parking":
        return f"🚗 **Parking**\nCurrent: **{val('parking_count', 'vehicles')}**"

    elif intent == "query_equipment":
        return f"🔧 **Equipment Utilisation**\nCurrent: **{val('equipment_util_pct', '%')}**"

    elif intent == "query_anomalies":
        top = ctx.get("top_anomaly")
        if n_anomalies == 0:
            return "✅ **No active anomalies** detected right now."
        top_str = f"\nTop: {top.metric_type} = {top.value:.2f} ({top.severity})" if top else ""
        return f"🚨 **{n_anomalies} active anomaly/anomalies** detected.{top_str}\nVisit the **Anomaly Monitor** page for details."

    elif intent == "query_score":
        if score:
            return f"🌿 **Sustainability Score: {score:.1f}/100**\nGo to the Score page for sub-score breakdown."
        return "🌿 Sustainability score is being computed. Check the Score page shortly."

    elif intent == "query_forecast":
        return "🔮 **Forecast** is available on the Forecast page. Select a metric to see the 24-hour Prophet prediction with confidence intervals."

    elif intent == "query_recommendations":
        return "💡 AI Insights page contains the latest recommendations. Use **Generate Recommendations** button to refresh with current data."

    elif intent == "query_priority":
        alert = ctx.get("top_alert")
        if alert:
            return f"⚡ **Top Priority Alert** (score {alert.priority_score:.0f}): {alert.title}\nStatus: {alert.status}"
        return "✅ No high-priority alerts currently open."

    elif intent == "action_simulate":
        return "🔬 For what-if scenarios, visit the **Scenario Simulator** page. You can adjust occupancy, HVAC, lighting, renewable energy, and more to preview impact."

    elif intent == "show_help":
        return (
            "🤖 **I can answer questions about:**\n"
            "- Energy, Water, Air Quality, Temperature, Waste, Occupancy\n"
            "- Active anomalies and alerts\n"
            "- Sustainability score and forecasts\n"
            "- AI recommendations and priority engine\n"
            "- Scenario simulation (redirects to Simulator page)\n\n"
            "Try: *'What is the current energy consumption?'* or *'Are there any anomalies?'*"
        )
    else:
        return (
            "🤔 I'm not sure I understood that. Try asking about:\n"
            "energy, water, air quality, anomalies, sustainability score, forecast, or recommendations.\n"
            "Type **help** to see all supported questions."
        )


def process_chat(db: Session, facility_id: int, message: str) -> dict:
    """Main chat pipeline: classify → fetch context → build response → optionally enhance with LLM."""
    intent = classify_intent(message)
    ctx    = get_context_snapshot(db, facility_id)
    reply  = build_response(intent, ctx, message)
    source = "rule_engine"

    # ── Optional Gemini enhancement ────────────────────────────────────────────
    if cfg.llm_enabled:
        try:
            from backend.services.gemini_svc import enhance_chat_response
            reply  = enhance_chat_response(message, reply, ctx)
            source = "llm"
        except Exception as exc:
            log.warning(f"Gemini enhancement failed, using rule response: {exc}")

    # Persist
    crud.add_chat_message(db, facility_id, role="user",      message=message,   source=source)
    crud.add_chat_message(db, facility_id, role="assistant", message=reply,      source=source)

    return {"reply": reply, "source": source, "intent": intent}


def transcribe_audio(audio_bytes: bytes) -> str:
    """
    Transcribe audio using SpeechRecognition (Google Web Speech API — free).
    Returns empty string on failure (falls back to text input).
    """
    try:
        import io
        import speech_recognition as sr

        r = sr.Recognizer()
        with sr.AudioFile(io.BytesIO(audio_bytes)) as source:
            audio = r.record(source)

        text = r.recognize_google(audio, language="en-IN")   # Indian English
        return text

    except Exception as exc:
        log.warning(f"Transcription failed: {exc}")
        return ""

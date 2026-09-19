"""
frontend/pages/1_Dashboard.py — Live KPI Dashboard
Auto-refreshes every 60 seconds.
"""

import streamlit as st
from streamlit_autorefresh import st_autorefresh
import plotly.graph_objects as go
from datetime import datetime

from frontend.utils.state      import init_state, get_facility_id, get_facility_name
from frontend.utils.api_client import get_live_readings, synthetic_status, get_anomalies
from frontend.utils.formatting import (
    metric_label, metric_unit, metric_emoji, fmt_value, SEVERITY_COLORS
)

st.set_page_config(page_title="Dashboard | SFEID", layout="wide", page_icon="📊")
hide_st_style = """
    <style>
    [data-testid="stHeader"] {visibility: hidden;}
    [data-testid="stToolbar"] {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """
st.markdown(hide_st_style, unsafe_allow_html=True)
st.markdown(hide_st_style, unsafe_allow_html=True)
init_state()

facility_id   = get_facility_id()
facility_name = get_facility_name()

# Auto-refresh every 60 seconds
refresh_count = st_autorefresh(interval=60_000, key="dashboard_refresh")

st.markdown(f"## 📊 Live Dashboard — {facility_name}")
st.caption(f"Auto-refreshes every 60 seconds · Last updated: {datetime.now().strftime('%H:%M:%S')}")

# ── Fetch data ─────────────────────────────────────────────────────────────────
live_readings = get_live_readings(facility_id)
syn_status    = synthetic_status()
anomalies     = get_anomalies(facility_id, resolved=False, limit=50)

# Data source banner
if syn_status.get("running"):
    st.info("🔵 **DEMO DATA** — Synthetic data generator is active. Data is realistic but simulated.")

if not live_readings:
    st.warning("⚠️ No live readings available. Is the backend running and database populated?")
    st.stop()

# Build map: metric_type → reading
readings_map = {r["metric_type"]: r for r in live_readings}

# Active anomaly metric types
anomaly_metrics = {a["metric_type"] for a in anomalies}

# ── KPI tiles row 1 ────────────────────────────────────────────────────────────
st.subheader("⚡ Energy & Air")
cols = st.columns(4)

KPI_METRICS_R1 = ["energy_kwh", "pm25", "pm10", "temperature_c"]
for i, mt in enumerate(KPI_METRICS_R1):
    r = readings_map.get(mt)
    with cols[i]:
        if r:
            label   = f"{metric_emoji(mt)} {metric_label(mt)}"
            value   = fmt_value(r["value"], mt)
            source  = r.get("source", "synthetic")
            is_anom = mt in anomaly_metrics
            delta   = "🚨 ANOMALY" if is_anom else "✅ Normal"
            st.metric(label, value, delta=delta,
                      delta_color="inverse" if is_anom else "normal")
            st.caption(f"Source: {'🔵 DEMO' if source == 'synthetic' else ('📡 LIVE' if source == 'esp32' else '✏️ MANUAL')}")
        else:
            st.metric(f"{metric_emoji(mt)} {metric_label(mt)}", "—")

# ── KPI tiles row 2 ────────────────────────────────────────────────────────────
st.subheader("💧 Water, Waste & Occupancy")
cols2 = st.columns(4)

KPI_METRICS_R2 = ["water_litres", "bin_fill_pct", "occupancy_count", "parking_count"]
for i, mt in enumerate(KPI_METRICS_R2):
    r = readings_map.get(mt)
    with cols2[i]:
        if r:
            label   = f"{metric_emoji(mt)} {metric_label(mt)}"
            value   = fmt_value(r["value"], mt)
            is_anom = mt in anomaly_metrics
            delta   = "🚨 ANOMALY" if is_anom else "✅ Normal"
            st.metric(label, value, delta=delta,
                      delta_color="inverse" if is_anom else "normal")
        else:
            st.metric(f"{metric_emoji(mt)} {metric_label(mt)}", "—")

# ── Extra row ─────────────────────────────────────────────────────────────────
cols3 = st.columns(3)
for i, mt in enumerate(["humidity_pct", "equipment_util_pct"]):
    r = readings_map.get(mt)
    with cols3[i]:
        if r:
            label   = f"{metric_emoji(mt)} {metric_label(mt)}"
            value   = fmt_value(r["value"], mt)
            is_anom = mt in anomaly_metrics
            delta   = "🚨 ANOMALY" if is_anom else "✅ Normal"
            st.metric(label, value, delta=delta,
                      delta_color="inverse" if is_anom else "normal")

with cols3[2]:
    open_anom = len(anomalies)
    critical  = sum(1 for a in anomalies if a["severity"] == "critical")
    st.metric("🚨 Active Anomalies", open_anom,
              delta=f"{critical} critical",
              delta_color="inverse" if critical > 0 else "normal")

st.divider()

# ── Gauge Charts ───────────────────────────────────────────────────────────────
st.subheader("📡 Sensor Gauges")

GAUGE_METRICS = [
    ("energy_kwh",      0,   90,  "kWh"),
    ("pm25",            0,   75,  "µg/m³"),
    ("bin_fill_pct",    0,  100,  "%"),
    ("occupancy_count", 0, 5000,  "people"),
]

gcols = st.columns(4)
for i, (mt, lo, hi, unit) in enumerate(GAUGE_METRICS):
    r = readings_map.get(mt)
    with gcols[i]:
        val = r["value"] if r else 0.0
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=val,
            title={"text": metric_label(mt)},
            number={"suffix": f" {unit}"},
            gauge={
                "axis": {"range": [lo, hi]},
                "bar":  {"color": "#2E8B57"},
                "steps": [
                    {"range": [lo,       hi*0.5], "color": "#1A2E1A"},
                    {"range": [hi*0.5,   hi*0.8], "color": "#2D4A2D"},
                    {"range": [hi*0.8,   hi],     "color": "#4A1C1C"},
                ],
                "threshold": {
                    "line": {"color": "red", "width": 3},
                    "thickness": 0.75,
                    "value": hi * 0.85,
                },
            },
        ))
        fig.update_layout(
            height=200, margin=dict(l=10, r=10, t=30, b=0),
            paper_bgcolor="rgba(0,0,0,0)", font_color="#31333F",
        )
        st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── Recent Anomalies Summary Table ─────────────────────────────────────────────
if anomalies:
    st.subheader("🚨 Recent Anomalies")
    rows = []
    for a in anomalies[:10]:
        rows.append({
            "Severity":  SEVERITY_COLORS.get(a["severity"], "#aaa"),
            "Metric":    metric_label(a["metric_type"]),
            "Value":     fmt_value(a["value"], a["metric_type"]),
            "Method":    a["detection_method"].replace("_", " ").title(),
            "Detected":  a["detected_at"][:16].replace("T", " "),
        })
    import pandas as pd
    df = pd.DataFrame(rows)
    st.dataframe(df[["Metric", "Value", "Severity", "Method", "Detected"]],
                 use_container_width=True, hide_index=True)

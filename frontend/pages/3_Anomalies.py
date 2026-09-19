"""
frontend/pages/3_Anomalies.py — Anomaly Detection & Monitoring Dashboard
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

from frontend.utils.state      import init_state, get_facility_id, get_facility_name
from frontend.utils.api_client import get_anomalies, trigger_anomaly_detection
from frontend.utils.formatting import (
    metric_label, metric_unit, fmt_value, SEVERITY_COLORS, SEVERITY_EMOJI
)

st.set_page_config(page_title="Anomalies | SFEID", layout="wide", page_icon="🚨")
init_state()

facility_id   = get_facility_id()
facility_name = get_facility_name()

st.markdown(f"## 🚨 Anomaly Detection & Monitoring — {facility_name}")
st.caption(
    "3-Tier Anomaly Engine: (1) Configurable Static Thresholds · "
    "(2) Z-Score Rolling Window · (3) scikit-learn Isolation Forest"
)

# ── Action buttons ─────────────────────────────────────────────────────────────
col1, col2 = st.columns([3, 1])
with col2:
    if st.button("⚡ Run Detection Now", use_container_width=True):
        res = trigger_anomaly_detection(facility_id)
        st.success(res.get("message", "Detection complete."))
        st.rerun()

# ── Filters ───────────────────────────────────────────────────────────────────
fcol1, fcol2, fcol3 = st.columns(3)
with fcol1:
    status_filter = st.selectbox("Status", ["Unresolved (Open)", "Resolved", "All"])
with fcol2:
    severity_filter = st.selectbox("Severity Filter", ["All", "critical", "high", "medium", "low"])
with fcol3:
    method_filter = st.selectbox("Detection Method", ["All", "threshold", "z_score", "isolation_forest"])

# Resolve filter values for API call
resolved_param = None if status_filter == "All" else (status_filter == "Resolved")
severity_param = None if severity_filter == "All" else severity_filter

anomalies = get_anomalies(facility_id, resolved=resolved_param, severity=severity_param, limit=150)

if method_filter != "All":
    anomalies = [a for a in anomalies if a["detection_method"] == method_filter]

# ── Summary metrics ───────────────────────────────────────────────────────────
sc1, sc2, sc3, sc4 = st.columns(4)
total_count    = len(anomalies)
critical_count = sum(1 for a in anomalies if a["severity"] == "critical")
iso_count      = sum(1 for a in anomalies if a["detection_method"] == "isolation_forest")
z_count        = sum(1 for a in anomalies if a["detection_method"] == "z_score")

with sc1:
    st.metric("Total Filtered Events", total_count)
with sc2:
    st.metric("Critical Severities", critical_count, delta="Immediate attention" if critical_count > 0 else "None", delta_color="inverse")
with sc3:
    st.metric("Isolation Forest Hits", iso_count, help="ML multivariate anomaly detections")
with sc4:
    st.metric("Z-Score Spike Hits", z_count, help="Rolling statistical deviation detections")

st.divider()

if not anomalies:
    st.success("✅ No anomaly events match the selected filters.")
    st.stop()

# ── Severity breakdown chart ──────────────────────────────────────────────────
df = pd.DataFrame(anomalies)
df["detected_at"] = pd.to_datetime(df["detected_at"])

col_chart1, col_chart2 = st.columns(2)

with col_chart1:
    st.subheader("📊 Anomaly Breakdown by Metric")
    metric_counts = df["metric_type"].map(metric_label).value_counts().reset_index()
    metric_counts.columns = ["Metric", "Count"]
    fig_m = px.bar(metric_counts, x="Metric", y="Count", color="Metric",
                   color_discrete_sequence=px.colors.qualitative.Set2)
    fig_m.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                        font_color="#FAFAFA", height=280, showlegend=False)
    st.plotly_chart(fig_m, use_container_width=True)

with col_chart2:
    st.subheader("🤖 Anomaly Breakdown by Method")
    method_counts = df["detection_method"].value_counts().reset_index()
    method_counts.columns = ["Method", "Count"]
    fig_method = px.pie(method_counts, names="Method", values="Count", hole=0.4,
                        color_discrete_sequence=["#FF4B4B", "#FF8C00", "#2E8B57"])
    fig_method.update_layout(paper_bgcolor="rgba(0,0,0,0)", font_color="#FAFAFA", height=280)
    st.plotly_chart(fig_method, use_container_width=True)

st.divider()

# ── Anomaly Events List ────────────────────────────────────────────────────────
st.subheader("📋 Anomaly Event Log")

for a in anomalies:
    sev   = a["severity"]
    emoji = SEVERITY_EMOJI.get(sev, "⚪")
    color = SEVERITY_COLORS.get(sev, "#aaa")
    mt    = a["metric_type"]
    val_str = fmt_value(a["value"], mt)
    ts_str  = a["detected_at"][:16].replace("T", " ")
    method  = a["detection_method"].replace("_", " ").title()

    with st.expander(f"{emoji} [{sev.upper()}] {metric_label(mt)} — {val_str} ({ts_str})"):
        ec1, ec2, ec3 = st.columns(3)
        with ec1:
            st.markdown(f"**Metric:** {metric_label(mt)}")
            st.markdown(f"**Observed Value:** `{val_str}`")
            st.markdown(f"**Severity:** <span style='color:{color}; font-weight:bold;'>{sev.upper()}</span>", unsafe_allow_html=True)
        with ec2:
            st.markdown(f"**Detection Method:** `{method}`")
            st.markdown(f"**Lower Threshold:** `{a.get('threshold_low') or 'None'}`")
            st.markdown(f"**Upper Threshold:** `{a.get('threshold_high') or 'None'}`")
        with ec3:
            st.markdown(f"**Detected At:** `{ts_str}`")
            st.markdown(f"**Status:** `{'Resolved' if a['is_resolved'] else 'OPEN'}`")

        if method == "isolation_forest":
            st.info("🤖 **Isolation Forest Note:** Multi-variate outlier score exceeded contamination threshold based on recent pattern history.")
        elif method == "z_score":
            st.info("📈 **Z-Score Note:** Reading deviated significantly (> 3 std dev) from recent 3-hour rolling mean.")

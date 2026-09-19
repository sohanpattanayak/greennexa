"""
frontend/pages/6_Priority_Engine.py — AI Priority Engine & Incident Queue
"""

import json
import streamlit as st
import pandas as pd
import plotly.express as px

from utils.api_client import (
    get_priority_alerts,
    run_priority_engine,
    update_alert,
)
from utils.formatting import STATUS_EMOJI, priority_tier
from utils.state import get_facility_id, get_facility_name, init_state

st.set_page_config(page_title="Priority Engine | SFEID", layout="wide", page_icon="⚡")
init_state()

facility_id   = get_facility_id()
facility_name = get_facility_name()

st.markdown(f"## ⚡ AI Priority Engine & Incident Queue — {facility_name}")
st.caption(
    "Deterministic multi-factor incident ranking. Normalises 5 critical metrics via scikit-learn MinMaxScaler: "
    "(1) Anomaly Severity · (2) Rate of Change Trend · (3) Occupancy Impact · "
    "(4) Time Urgency · (5) Recurrence Count."
)

# ── Control Bar ───────────────────────────────────────────────────────────────
col1, col2 = st.columns([3, 1])

with col2:
    if st.button("🔄 Re-calculate Priority Scores", use_container_width=True):
        with st.spinner("Scoring open anomalies..."):
            res = run_priority_engine(facility_id)
            st.success(res.get("message", "Priority Engine run complete."))
            st.rerun()

# ── Filters ───────────────────────────────────────────────────────────────────
fcol1, fcol2 = st.columns(2)
with fcol1:
    status_filter = st.selectbox("Filter Status", ["All Open & In-Progress", "open", "in_progress", "resolved", "All"])

status_param = None if status_filter == "All" else (None if status_filter == "All Open & In-Progress" else status_filter)
alerts = get_priority_alerts(facility_id, status=status_param, limit=100)

if status_filter == "All Open & In-Progress":
    alerts = [a for a in alerts if a["status"] in ("open", "in_progress")]

# ── Summary Metrics ───────────────────────────────────────────────────────────
ac1, ac2, ac3, ac4 = st.columns(4)

total_alerts = len(alerts)
crit_alerts  = sum(1 for a in alerts if a["priority_score"] >= 80)
high_alerts  = sum(1 for a in alerts if 60 <= a["priority_score"] < 80)
open_alerts  = sum(1 for a in alerts if a["status"] == "open")

with ac1:
    st.metric("Active Queue Items", total_alerts)
with ac2:
    st.metric("Critical Alerts (Score ≥ 80)", crit_alerts, delta="Requires immediate action" if crit_alerts > 0 else "Clear", delta_color="inverse")
with ac3:
    st.metric("High Alerts (Score 60–79)", high_alerts)
with ac4:
    st.metric("Unassigned Open Items", open_alerts)

st.divider()

if not alerts:
    st.success("✅ Priority queue is clear! No active incident alerts.")
    st.stop()

# ── Priority Queue List ────────────────────────────────────────────────────────
st.subheader("📋 Ranked Incident Queue")

for alert in alerts:
    score = alert.get("priority_score", 0.0)
    tier, color = priority_tier(score)
    status = alert.get("status", "open")
    s_emoji = STATUS_EMOJI.get(status, "❓")
    assigned = alert.get("assigned_to") or "Unassigned"

    with st.expander(f"{tier} | Score: {score:.0f} | {alert['title']} ({s_emoji} {status.upper()})"):
        ac1, ac2 = st.columns([3, 1])

        with ac1:
            st.markdown(f"**Description:** {alert.get('description', '')}")

            # Parse factor breakdown JSON
            factors_raw = alert.get("factors_json")
            if factors_raw:
                try:
                    f = json.loads(factors_raw)
                    st.markdown("**Factor Breakdown (MinMaxScaler 0–100):**")
                    fcols = st.columns(5)
                    fcols[0].metric("Severity", f.get("severity", 0))
                    fcols[1].metric("Trend", f.get("trend", 0))
                    fcols[2].metric("Impact", f.get("impact", 0))
                    fcols[3].metric("Time Urgency", f.get("time_urgency", 0))
                    fcols[4].metric("Recurrence", f.get("recurrence", 0))
                except Exception:
                    pass

        with ac2:
            st.markdown(f"**Priority Score:** <span style='color:{color}; font-weight:bold; font-size:1.4em;'>{score:.0f} / 100</span>", unsafe_allow_html=True)
            st.markdown(f"**Assigned To:** `{assigned}`")
            st.markdown(f"**Created:** `{alert.get('created_at', '')[:16].replace('T', ' ')}`")

            st.write("")
            # Incident management controls
            new_status = st.selectbox(
                "Update Status",
                ["open", "in_progress", "resolved"],
                index=["open", "in_progress", "resolved"].index(status),
                key=f"status_sel_{alert['id']}"
            )
            new_assignee = st.text_input("Assign Staff Member", value=alert.get("assigned_to") or "", key=f"assign_input_{alert['id']}")

            if st.button("💾 Save Changes", key=f"save_alert_{alert['id']}", use_container_width=True):
                update_alert(alert["id"], status=new_status, assigned_to=new_assignee or None)
                st.success("Alert updated!")
                st.rerun()

"""
frontend/pages/8_Sustainability_Score.py — Campus Sustainability & Operations Score Card
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from utils.api_client import (
    compute_score,
    get_score_history,
    get_sustainability_score,
)
from utils.formatting import score_color
from utils.state import get_facility_id, get_facility_name, init_state

st.set_page_config(page_title="Sustainability Score | SFEID", layout="wide", page_icon="🌿")
init_state()

facility_id   = get_facility_id()
facility_name = get_facility_name()

st.markdown(f"## 🌿 Campus Sustainability & Operations Score — {facility_name}")
st.caption(
    "Deterministic 0–100 composite index calculated daily. "
    "Weights: Energy (30%) · Air Quality (20%) · Water (20%) · Waste (15%) · Occupancy Efficiency (15%)."
)

# ── Control Bar ───────────────────────────────────────────────────────────────
col1, col2 = st.columns([3, 1])

with col2:
    if st.button("🔄 Re-Compute Today's Score", use_container_width=True):
        with st.spinner("Computing sub-scores..."):
            score_data = compute_score(facility_id)
            st.success("Score updated!")
            st.rerun()

# Fetch latest score
score_data = get_sustainability_score(facility_id)

if not score_data:
    st.warning("⚠️ Score data unavailable. Is backend running?")
    st.stop()

overall = score_data.get("overall_score", 0.0)
grade   = score_data.get("grade", "N/A")
color   = score_color(overall)

# ── Score Gauge & Grade Hero ──────────────────────────────────────────────────
st.divider()

hcol1, hcol2 = st.columns([1, 2])

with hcol1:
    st.markdown(
        f"""
        <div style="background-color: #1A1D27; border-radius: 12px; padding: 25px; text-align: center; border: 2px solid {color};">
            <h4 style="margin: 0; color: #aaa;">OVERALL RATING</h4>
            <h1 style="font-size: 4em; margin: 10px 0; color: {color};">{overall:.1f}</h1>
            <h2 style="margin: 0; color: #FAFAFA;">Grade: <span style="color:{color};">{grade}</span></h2>
            <p style="color: #888; font-size: 0.9em; margin-top: 10px;">Date: {score_data.get('score_date', '')}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

with hcol2:
    # Sub-scores radar / bar breakdown
    sub_scores = {
        "⚡ Energy Efficiency": score_data.get("energy_score", 0.0),
        "🌫️ Air Quality Index":  score_data.get("air_score", 0.0),
        "💧 Water Conservation": score_data.get("water_score", 0.0),
        "🗑️ Waste Management":   score_data.get("waste_score", 0.0),
        "👥 Space Utilisation":  score_data.get("occupancy_score", 0.0),
    }

    fig_sub = go.Figure(go.Bar(
        x=list(sub_scores.values()),
        y=list(sub_scores.keys()),
        orientation="h",
        marker=dict(color=["#2E8B57" if v >= 70 else ("#FFD700" if v >= 50 else "#FF4B4B") for v in sub_scores.values()]),
        text=[f"{v:.1f}/100" for v in sub_scores.values()],
        textposition="auto",
    ))
    fig_sub.update_layout(
        title="Category Sub-Score Breakdown (0–100 Scale)",
        xaxis=dict(range=[0, 100]),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#FAFAFA"), height=250, margin=dict(l=10, r=10, t=40, b=10),
    )
    st.plotly_chart(fig_sub, use_container_width=True)

st.divider()

# ── Historical Score Trend Line ────────────────────────────────────────────────
st.subheader("📈 30-Day Sustainability Score History")

history = get_score_history(facility_id, days=30)
if history:
    df_h = pd.DataFrame(history)
    df_h["score_date"] = pd.to_datetime(df_h["score_date"])

    fig_hist = go.Figure()
    fig_hist.add_trace(go.Scatter(
        x=df_h["score_date"], y=df_h["overall_score"],
        mode="lines+markers", name="Overall Score",
        line=dict(color="#2E8B57", width=3),
    ))
    fig_hist.add_trace(go.Scatter(
        x=df_h["score_date"], y=df_h["energy_score"],
        mode="lines", name="Energy Sub-Score", line=dict(color="#FF8C00", dash="dot")
    ))
    fig_hist.add_trace(go.Scatter(
        x=df_h["score_date"], y=df_h["water_score"],
        mode="lines", name="Water Sub-Score", line=dict(color="#3182CE", dash="dot")
    ))

    fig_hist.update_layout(
        xaxis_title="Date", yaxis_title="Score (0–100)",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#FAFAFA"), height=350,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig_hist, use_container_width=True)
else:
    st.info("No historical score data recorded yet.")

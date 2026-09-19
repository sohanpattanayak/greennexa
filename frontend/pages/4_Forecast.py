"""
frontend/pages/4_Forecast.py — Time-Series Forecasting Page (Prophet & Linear Regression)
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

from frontend.utils.state      import init_state, get_facility_id, get_facility_name
from frontend.utils.api_client import get_forecast, generate_forecast, get_trends
from frontend.utils.formatting import (
    metric_label, metric_unit, metric_emoji, METRIC_LABELS, fmt_value
)

st.set_page_config(page_title="Forecast | SFEID", layout="wide", page_icon="🔮")
init_state()

facility_id   = get_facility_id()
facility_name = get_facility_name()

st.markdown(f"## 🔮 Short-Term Time-Series Forecasting — {facility_name}")
st.caption(
    "24-Hour Horizon Forecasting with Confidence Intervals. "
    "Primary Model: **Meta Prophet** (daily & weekly seasonality + India public holidays). "
    "Cold-Start Fallback: **scikit-learn Linear Regression**."
)

# ── Select metric ─────────────────────────────────────────────────────────────
forecastable_metrics = {
    f"{metric_emoji(k)} {v[0]}": k
    for k, v in METRIC_LABELS.items()
    if k in ("energy_kwh", "water_litres", "bin_fill_pct", "pm25", "occupancy_count", "temperature_c")
}

fcol1, fcol2 = st.columns([3, 1])

with fcol1:
    selected_label = st.selectbox("Select Metric to Forecast", list(forecastable_metrics.keys()))
    metric_type    = forecastable_metrics[selected_label]

with fcol2:
    st.write("")
    st.write("")
    if st.button("🔄 Force Re-train & Predict", use_container_width=True):
        with st.spinner("Training model & generating 24h prediction..."):
            res = generate_forecast(facility_id, metric_type)
            if res.get("points"):
                st.success(f"Forecast updated using **{res.get('model_used')}**.")
            else:
                st.error("Could not generate forecast. Check database readings.")
            st.rerun()

st.divider()

# ── Fetch forecast data ────────────────────────────────────────────────────────
forecast_data = get_forecast(facility_id, metric_type)

if not forecast_data or not forecast_data.get("points"):
    st.warning(
        f"⚠️ No active forecast available for **{metric_label(metric_type)}**. "
        "Click 'Force Re-train & Predict' above to generate one."
    )
    st.stop()

model_used   = forecast_data.get("model_used", "prophet")
generated_at = forecast_data.get("generated_at", "")[:16].replace("T", " ")
points       = forecast_data.get("points", [])

df_f = pd.DataFrame(points)
df_f["timestamp"] = pd.to_datetime(df_f["timestamp"])

# Fetch last 48 hours of actual historical readings for continuity
hist_data = get_trends(facility_id, metric_type, granularity="hourly", hours=48)
hist_points = hist_data.get("points", []) if isinstance(hist_data, dict) else []
df_h = pd.DataFrame(hist_points) if hist_points else pd.DataFrame()
if not df_h.empty:
    df_h["timestamp"] = pd.to_datetime(df_h["timestamp"])

unit  = metric_unit(metric_type)
label = metric_label(metric_type)

# Model badge
if model_used == "prophet":
    st.info(f"✨ **Active Model:** Meta Prophet (with India holiday integration) · Generated: {generated_at}")
else:
    st.info(f"⚡ **Active Model:** scikit-learn Linear Regression (Cold-start fallback) · Generated: {generated_at}")

# ── Plotly Forecast Chart ──────────────────────────────────────────────────────
fig = go.Figure()

# 1. Historical Actuals (Solid line)
if not df_h.empty:
    fig.add_trace(go.Scatter(
        x=df_h["timestamp"],
        y=df_h["avg_value"],
        mode="lines",
        name="Historical Actuals (Last 48h)",
        line=dict(color="#2E8B57", width=2),
        hovertemplate="<b>%{x}</b><br>Actual: %{y:.2f} " + unit + "<extra></extra>",
    ))

# 2. Confidence Interval (Upper & Lower bounds shaded)
if "yhat_upper" in df_f.columns and "yhat_lower" in df_f.columns:
    fig.add_trace(go.Scatter(
        x=pd.concat([df_f["timestamp"], df_f["timestamp"][::-1]]),
        y=pd.concat([df_f["yhat_upper"], df_f["yhat_lower"][::-1]]),
        fill="toself",
        fillcolor="rgba(255, 140, 0, 0.18)",
        line=dict(color="rgba(255,255,255,0)"),
        hoverinfo="skip",
        name="80% Confidence Interval",
    ))

# 3. Forecast Line (Dashed line)
fig.add_trace(go.Scatter(
    x=df_f["timestamp"],
    y=df_f["yhat"],
    mode="lines+markers",
    name="24-Hour Forecast (Predicted)",
    line=dict(color="#FF8C00", width=2.5, dash="dash"),
    marker=dict(size=4),
    hovertemplate="<b>%{x}</b><br>Predicted: %{y:.2f} " + unit + "<extra></extra>",
))

fig.update_layout(
    title=f"24-Hour {label} Forecast & Historical Continuity",
    xaxis_title="Time",
    yaxis_title=f"{label} ({unit})",
    hovermode="x unified",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#FAFAFA"),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    height=450,
)
fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor="#2A2D3A")
fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor="#2A2D3A")

st.plotly_chart(fig, use_container_width=True)

# ── Forecast Key Insights Cards ───────────────────────────────────────────────
st.subheader("💡 Forecast Insights")

c1, c2, c3, c4 = st.columns(4)

predicted_avg = df_f["yhat"].mean()
predicted_peak = df_f["yhat"].max()
peak_time     = df_f.loc[df_f["yhat"].idxmax()]["timestamp"].strftime("%I:%M %p")
total_24h     = df_f["yhat"].sum() if metric_type == "energy_kwh" else None

with c1:
    st.metric("Predicted 24h Average", fmt_value(predicted_avg, metric_type))
with c2:
    st.metric("Expected Peak Draw", fmt_value(predicted_peak, metric_type))
with c3:
    st.metric("Expected Peak Time", peak_time)
with c4:
    if total_24h:
        est_cost = total_24h * 8.0  # ₹8/kWh
        st.metric("Est. 24h Energy Cost", f"₹{est_cost:,.0f}")
    else:
        st.metric("Forecast Window", "24 Hours")

st.divider()

# ── Raw Forecast Table ────────────────────────────────────────────────────────
with st.expander("📋 View Hourly Forecast Breakdown"):
    st.dataframe(df_f, use_container_width=True, hide_index=True)

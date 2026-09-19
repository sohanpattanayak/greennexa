"""
frontend/pages/2_Trends.py — Historical Trends & Interactive Graphs
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime, timedelta

 from utils.api_client import get_readings, get_trends
from utils.formatting import (
    METRIC_LABELS,
    fmt_value,
    metric_emoji,
    metric_label,
    metric_unit,
)
from utils.state import get_facility_id, get_facility_name, init_state

st.set_page_config(page_title="Trends | SFEID", layout="wide", page_icon="📈")
init_state()

facility_id   = get_facility_id()
facility_name = get_facility_name()

st.markdown(f"## 📈 Trend Analysis — {facility_name}")
st.caption("Interactive time-series graphs with hourly/daily aggregation across all 10 facility metrics.")

# ── Controls ───────────────────────────────────────────────────────────────────
col1, col2, col3 = st.columns([2, 1, 1])

metric_options = {f"{metric_emoji(k)} {v[0]}": k for k, v in METRIC_LABELS.items()}

with col1:
    selected_label = st.selectbox("Select Metric", list(metric_options.keys()))
    metric_type    = metric_options[selected_label]

with col2:
    granularity = st.radio("Granularity", ["hourly", "daily"], horizontal=True)

with col3:
    time_window = st.selectbox("Time Window", [
        ("Last 24 Hours", 24),
        ("Last 48 Hours", 48),
        ("Last 7 Days",  168),
        ("Last 30 Days", 720),
    ], format_func=lambda x: x[0])
    hours = time_window[1]

st.divider()

# ── Fetch trend data ──────────────────────────────────────────────────────────
trend_data = get_trends(facility_id, metric_type, granularity=granularity, hours=hours)
unit       = metric_unit(metric_type)
label      = metric_label(metric_type)

points = trend_data.get("points", []) if isinstance(trend_data, dict) else []

if not points:
    st.info(f"ℹ️ No trend data found for **{label}** over the selected period ({time_window[0]}).")
    st.stop()

df = pd.DataFrame(points)
df["timestamp"] = pd.to_datetime(df["timestamp"])

# ── Primary Line Chart (Plotly) ────────────────────────────────────────────────
fig = go.Figure()

# Mean line
fig.add_trace(go.Scatter(
    x=df["timestamp"],
    y=df["avg_value"],
    mode="lines",
    name="Average Value",
    line=dict(color="#00E5FF", width=2.5),
    hovertemplate="<b>%{x}</b><br>Average: <b>%{y:.2f} " + unit + "</b><extra></extra>",
))

fig.update_layout(
    title=f"{label} Trend ({granularity.title()} Aggregation)",
    xaxis_title="Time",
    yaxis_title=f"{label} ({unit})",
    hovermode="x unified",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#FAFAFA"),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    height=420,
)
fig.update_xaxes(showgrid=True,gridcolor="#1F2430")
fig.update_yaxes(showgrid=True,gridcolor="#1F2430")
st.plotly_chart(fig, use_container_width=True)

# ── Summary Statistics Cards ───────────────────────────────────────────────────
st.subheader("📊 Period Statistics")
scol1, scol2, scol3, scol4 = st.columns(4)

avg_val = df["avg_value"].mean()
min_val = df["min_value"].min()
max_val = df["max_value"].max()
latest  = df["avg_value"].iloc[-1] if not df.empty else 0.0

with scol1:
    st.metric("Latest Value", fmt_value(latest, metric_type))
with scol2:
    st.metric("Period Average", fmt_value(avg_val, metric_type))
with scol3:
    st.metric("Period Minimum", fmt_value(min_val, metric_type))
with scol4:
    st.metric("Period Maximum", fmt_value(max_val, metric_type))

st.divider()

# ── Multi-metric Comparison ───────────────────────────────────────────────────
with st.expander("🔀 Multi-Metric Comparison (Overlay 2 Metrics)"):
    mcol1, mcol2 = st.columns(2)
    with mcol1:
        m1 = st.selectbox("Metric 1", list(metric_options.keys()), index=0, key="comp_m1")
    with mcol2:
        m2 = st.selectbox("Metric 2", list(metric_options.keys()), index=1, key="comp_m2")

    mt1, mt2 = metric_options[m1], metric_options[m2]
    t1 = get_trends(facility_id, mt1, granularity=granularity, hours=hours)
    t2 = get_trends(facility_id, mt2, granularity=granularity, hours=hours)

    p1 = t1.get("points", []) if isinstance(t1, dict) else []
    p2 = t2.get("points", []) if isinstance(t2, dict) else []

    if p1 and p2:
        df1 = pd.DataFrame(p1); df1["ts"] = pd.to_datetime(df1["timestamp"])
        df2 = pd.DataFrame(p2); df2["ts"] = pd.to_datetime(df2["timestamp"])

        fig_comp = go.Figure()
        fig_comp.add_trace(go.Scatter(
            x=df1["ts"], y=df1["avg_value"], name=metric_label(mt1),
            line=dict(color="#2E8B57", width=2)
        ))
        fig_comp.add_trace(go.Scatter(
            x=df2["ts"], y=df2["avg_value"], name=metric_label(mt2),
            yaxis="y2", line=dict(color="#FF8C00", width=2)
        ))

        fig_comp.update_layout(
            title=f"Comparison: {metric_label(mt1)} vs. {metric_label(mt2)}",
            xaxis=dict(title="Time"),
            yaxis=dict(title=f"{metric_label(mt1)} ({metric_unit(mt1)})", title_font=dict(color="#2E8B57")),
            yaxis2=dict(title=f"{metric_label(mt2)} ({metric_unit(mt2)})", title_font=dict(color="#FF8C00"),
                        overlaying="y", side="right"),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#FAFAFA"), height=350,
        )
        st.plotly_chart(fig_comp, use_container_width=True)

# ── Raw Data Table ─────────────────────────────────────────────────────────────
with st.expander("📋 Export / View Aggregated Data"):
    st.dataframe(df, use_container_width=True, hide_index=True)
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Download CSV",
        data=csv,
        file_name=f"sfeid_{metric_type}_{granularity}.csv",
        mime="text/csv",
    )

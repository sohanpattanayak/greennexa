"""
frontend/pages/7_Scenario_Simulator.py — What-If & Scenario Simulation Sandbox
"""

import json
import streamlit as st
import plotly.graph_objects as go

from utils.api_client import get_simulation_runs, run_simulation
from utils.formatting import fmt_delta, fmt_inr
from utils.state import get_facility_id, get_facility_name, init_state
st.set_page_config(page_title="Scenario Simulator | SFEID", layout="wide", page_icon="🔬")
init_state()

facility_id   = get_facility_id()
facility_name = get_facility_name()

st.markdown(f"## 🔬 What-If & Scenario Simulation Sandbox — {facility_name}")
st.caption(
    "Simulate operational policy changes (HVAC setpoints, occupancy levels, lighting hours, "
    "renewable integration, water recycling) and preview predicted impacts on energy consumption, "
    "costs (₹), CO₂ emissions, and sustainability score."
)

st.divider()

# ── Simulation Form Controls ──────────────────────────────────────────────────
with st.form("scenario_form"):
    st.subheader("⚙️ Scenario Input Parameters")

    sc_name = st.text_input("Scenario Name", value="Summer Energy Saving Policy")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("#### 👥 Occupancy & Scheduling")
        occ_pct = st.slider("Target Occupancy (% of 5,000 capacity)", 10, 100, 80, step=5)
        smart_sched = st.checkbox("Enable Smart Equipment Scheduling (-8% energy)", value=True)

    with col2:
        st.markdown("#### 🌡️ Climate & Lighting")
        hvac_set = st.slider("HVAC Setpoint (°C)", 18.0, 30.0, 24.0, step=0.5, help="Baseline is 24.0°C. Raising setpoint saves ~0.4 kWh/°C per 1,000 sqft")
        lighting_h = st.slider("Lighting Operating Hours/Day", 4.0, 24.0, 12.0, step=1.0)

    with col3:
        st.markdown("#### 🌿 Renewable & Conservation")
        renewable_pct = st.slider("Rooftop Solar / Renewable Energy Integration (%)", 0.0, 100.0, 15.0, step=5.0)
        recycling_pct = st.slider("Greywater Recycling Efficiency (%)", 0.0, 100.0, 25.0, step=5.0)

    submit_sim = st.form_submit_button("🚀 Run What-If Simulation", use_container_width=True)

# ── Process Simulation ────────────────────────────────────────────────────────
if submit_sim or st.session_state.get("sim_result") is not None:
    if submit_sim:
        payload = {
            "facility_id":         facility_id,
            "name":                sc_name,
            "occupancy_pct":       occ_pct,
            "hvac_setpoint_c":     hvac_set,
            "lighting_hours":      lighting_h,
            "renewable_pct":       renewable_pct,
            "water_recycling_pct": recycling_pct,
            "smart_scheduling":    smart_sched,
        }
        res = run_simulation(payload)
        st.session_state.sim_result = res
    else:
        res = st.session_state.sim_result

    if res:
        st.divider()
        st.subheader(f"📊 Results: {res.get('name', 'Scenario')}")

        # Primary Impact Cards
        e_kwh   = res.get("energy_delta_kwh", 0)
        e_cost  = res.get("energy_cost_delta_inr", 0)
        w_lit   = res.get("water_delta_litres", 0)
        co2_kg  = res.get("co2_delta_kg", 0)
        s_delta = res.get("score_delta", 0)

        mc1, mc2, mc3, mc4, mc5 = st.columns(5)

        with mc1:
            st.metric("Energy Impact", f"{e_kwh:+.1f} kWh", delta=f"{e_kwh:+.1f} kWh", delta_color="inverse" if e_kwh > 0 else "normal")
        with mc2:
            st.metric("Financial Delta", fmt_inr(e_cost), delta=fmt_inr(e_cost), delta_color="inverse" if e_cost > 0 else "normal")
        with mc3:
            st.metric("Water Delta", f"{w_lit:+.0f} L", delta=f"{w_lit:+.0f} L", delta_color="inverse" if w_lit > 0 else "normal")
        with mc4:
            st.metric("CO₂ Emissions Delta", f"{co2_kg:+.1f} kg", delta=f"{co2_kg:+.1f} kg", delta_color="inverse" if co2_kg > 0 else "normal")
        with mc5:
            st.metric("Score Delta", f"{s_delta:+.1f} pts", delta=f"{s_delta:+.1f} pts", delta_color="normal" if s_delta > 0 else "inverse")

        st.write("")

        # Visual Comparison Charts
        col_c1, col_c2 = st.columns(2)

        base_sum = res.get("baseline_summary", {})
        sim_sum  = res.get("simulated_summary", {})

        with col_c1:
            st.markdown("#### ⚡ 24h Energy Consumption Comparison")
            fig_e = go.Figure(data=[
                go.Bar(name="Baseline Actual", x=["Daily Energy (kWh)"], y=[base_sum.get("energy_kwh", 0)], marker_color="#4A5568"),
                go.Bar(name="Simulated Scenario", x=["Daily Energy (kWh)"], y=[sim_sum.get("energy_kwh", 0)], marker_color="#2E8B57" if e_kwh < 0 else "#FF8C00"),
            ])
            fig_e.update_layout(barmode="group", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#FAFAFA", height=300)
            st.plotly_chart(fig_e, use_container_width=True)

        with col_c2:
            st.markdown("#### 💧 Daily Water Usage Comparison")
            fig_w = go.Figure(data=[
                go.Bar(name="Baseline Actual", x=["Daily Water (L)"], y=[base_sum.get("water_litres", 0)], marker_color="#4A5568"),
                go.Bar(name="Simulated Scenario", x=["Daily Water (L)"], y=[sim_sum.get("water_litres", 0)], marker_color="#3182CE" if w_lit < 0 else "#FF8C00"),
            ])
            fig_w.update_layout(barmode="group", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#FAFAFA", height=300)
            st.plotly_chart(fig_w, use_container_width=True)

st.divider()

# ── Previous Runs History ─────────────────────────────────────────────────────
with st.expander("📜 Saved Simulation Runs"):
    runs = get_simulation_runs(facility_id)
    if runs:
        rows = []
        for r in runs:
            results = r.get("results", {})
            rows.append({
                "Scenario Name": r.get("name"),
                "Impact Score":  f"{r.get('impact_score', 0):.1f}/100",
                "Energy Impact": f"{results.get('energy_delta_kwh', 0):+.1f} kWh",
                "Cost Delta":    fmt_inr(results.get("energy_cost_delta_inr", 0)),
                "Date":          r.get("created_at", "")[:16].replace("T", " "),
            })
        import pandas as pd
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.caption("No saved simulation runs found.")

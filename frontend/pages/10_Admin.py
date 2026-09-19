"""
frontend/pages/10_Admin.py — Admin Portal & System Settings
"""

import streamlit as st
import pandas as pd
from utils.api_client import (
    get_sensors,
    get_thresholds,
    ingest_manual,
    synthetic_status,
    toggle_synthetic,
    update_threshold,
)
from utils.formatting import METRIC_LABELS, metric_label
from utils.state import get_facility_id, get_facility_name, init_state

st.set_page_config(page_title="Admin | SFEID", layout="wide", page_icon="⚙️")
init_state()

facility_id   = get_facility_id()
facility_name = get_facility_name()

st.markdown(f"## ⚙️ Administrator Settings & Management — {facility_name}")
st.caption("Manage facility thresholds, toggle synthetic data feeds, enter manual readings, and view active sensors.")

st.divider()

# ── Tabbed Interface ───────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = tab1_thresholds, tab2_synthetic, tab3_manual, tab4_sensors = st.tabs([
    "🎛️ Metric Thresholds",
    "🔵 Synthetic Generator",
    "✏️ Manual Data Entry",
    "📡 Sensor Registry",
])

# ── Tab 1: Configurable Metric Thresholds ──────────────────────────────────────
with tab1_thresholds:
    st.subheader("🎛️ Configurable Facility Thresholds (Engineering College Baseline)")
    st.caption("Thresholds drive static anomaly detection, sub-score bounds, and AI recommendation rules.")

    thresholds = get_thresholds(facility_type_id=1)
    if thresholds:
        for t in thresholds:
            mt = t["metric_type"]
            label = metric_label(mt)
            unit  = t.get("unit", "")

            with st.expander(f"⚙️ {label} Thresholds ({unit})"):
                with st.form(f"thresh_form_{t['id']}"):
                    tc1, tc2, tc3, tc4 = st.columns(4)

                    with tc1:
                        w_low = st.number_input("Warn Low", value=float(t.get("warn_low") or 0.0), key=f"wl_{t['id']}")
                    with tc2:
                        w_high = st.number_input("Warn High", value=float(t.get("warn_high") or 0.0), key=f"wh_{t['id']}")
                    with tc3:
                        c_low = st.number_input("Critical Low", value=float(t.get("critical_low") or 0.0), key=f"cl_{t['id']}")
                    with tc4:
                        c_high = st.number_input("Critical High", value=float(t.get("critical_high") or 0.0), key=f"ch_{t['id']}")

                    notes = st.text_input("Notes / Reference Standard", value=t.get("notes") or "", key=f"n_{t['id']}")

                    if st.form_submit_button("💾 Save Thresholds"):
                        updates = {
                            "warn_low":      w_low or None,
                            "warn_high":     w_high or None,
                            "critical_low":  c_low or None,
                            "critical_high": c_high or None,
                            "notes":         notes or None,
                        }
                        update_threshold(t["id"], updates)
                        st.success(f"Updated thresholds for {label}!")
                        st.rerun()

# ── Tab 2: Synthetic Generator Controls ────────────────────────────────────────
with tab2_synthetic:
    st.subheader("🔵 Real-time Synthetic Data Simulator Controls")
    st.caption("Background APScheduler process feeding realistic sensor readings every 60 seconds.")

    syn_info = synthetic_status()
    is_running = syn_info.get("running", False)

    st.write("")
    sc1, sc2 = st.columns([1, 2])
    with sc1:
        st.markdown(f"**Current Status:** `{'RUNNING (Active)' if is_running else 'STOPPED (Idle)'}`")
        st.markdown(f"**Interval:** `{syn_info.get('interval_seconds', 60)} seconds`")
    with sc2:
        if is_running:
            if st.button("⏹️ Stop Synthetic Generator", use_container_width=True):
                toggle_synthetic(False)
                st.success("Synthetic generator stopped.")
                st.rerun()
        else:
            if st.button("▶️ Start Synthetic Generator", use_container_width=True):
                toggle_synthetic(True)
                st.success("Synthetic generator started.")
                st.rerun()

# ── Tab 3: Manual Data Entry ──────────────────────────────────────────────────
with tab3_manual:
    st.subheader("✏️ Manual Sensor Data Entry")
    st.caption("Manually record inspection or offline meter readings. Tagged as source='manual' in database.")

    with st.form("manual_entry_form"):
        mc1, mc2, mc3 = st.columns(3)
        with mc1:
            sel_m_label = st.selectbox("Select Metric", list(METRIC_LABELS.keys()), format_func=metric_label)
        with mc2:
            m_val = st.number_input("Observed Value", value=10.0, step=0.5)
        with mc3:
            m_zone = st.number_input("Zone ID (Optional)", value=1, min_value=1, max_value=6)

        m_notes = st.text_input("Entry Reason / Notes", value="Admin manual meter reading")

        if st.form_submit_button("📥 Submit Manual Reading"):
            res = ingest_manual(facility_id, sel_m_label, m_val, zone_id=m_zone)
            st.success(res.get("message", "Manual reading inserted!"))

# ── Tab 4: Active Sensor Registry ─────────────────────────────────────────────
with tab4_sensors:
    st.subheader("📡 Active Campus Sensor Registry")
    sensors = get_sensors(facility_id)
    if sensors:
        df_s = pd.DataFrame(sensors)
        st.dataframe(
            df_s[["id", "metric_type", "unit", "description", "mac_address", "is_active"]],
            use_container_width=True, hide_index=True
        )
    else:
        st.warning("No active sensors found in database.")

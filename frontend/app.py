"""
frontend/app.py — SFEID Streamlit entry point
Handles: password gate, sidebar navigation, facility selector, API base URL config.
"""

import streamlit as st

st.set_page_config(
    page_title="SFEID — Facility Intelligence Dashboard",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

from frontend.utils.state      import init_state, is_authenticated, set_authenticated
from frontend.utils.api_client import verify_password, get_facilities, api_status, synthetic_status

# ── Session state initialisation ─────────────────────────────────────────────
init_state()

# ── Password Gate ─────────────────────────────────────────────────────────────
if not is_authenticated():
    st.markdown(
        """
        <div style='text-align:center; padding: 60px 0 20px 0;'>
            <h1>🏛️ SFEID</h1>
            <h3>Sustainable Facility & Estate Intelligence Dashboard</h3>
            <p style='color:#aaa'>SFEID College of Engineering — Admin Access</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        pwd = st.text_input("Admin Password", type="password", label_visibility="visible")
        if st.button("🔓 Login", use_container_width=True):
            if verify_password(pwd):
                set_authenticated(True)
                st.rerun()
            else:
                st.error("❌ Incorrect password. Please try again.")
        st.caption("Default password: `sfeid2026` (change in `.env`)")
    st.stop()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🏛️ SFEID")
    st.caption("Facility & Estate Intelligence")
    st.divider()

    # Facility selector
    facilities = get_facilities()
    if facilities:
        fac_names = {f["name"]: f["id"] for f in facilities}
        sel_name  = st.selectbox("📍 Facility", list(fac_names.keys()))
        st.session_state.facility_id   = fac_names[sel_name]
        st.session_state.facility_name = sel_name
    else:
        st.warning("⚠️ Cannot reach API. Is the backend running?")

    st.divider()

    # API status indicator
    status = api_status()
    if status:
        llm = status.get("llm_enabled", False)
        st.session_state.llm_enabled = llm
        mode_label = "🤖 LLM-Enhanced" if llm else "📋 Rule-Based"
        st.caption(f"AI Mode: **{mode_label}**")
    else:
        st.caption("⚠️ Backend offline")

    # Synthetic data status
    syn = synthetic_status()
    if syn.get("running"):
        st.caption(f"🔵 Synthetic data: ON ({syn.get('interval_seconds', 60)}s)")
    else:
        st.caption("⚫ Synthetic data: OFF")

    st.divider()
    st.caption("📖 Navigation →")
    st.caption(
        "1 Dashboard · 2 Trends · 3 Anomalies\n"
        "4 Forecast · 5 AI Insights · 6 Priority\n"
        "7 Scenario Sim · 8 Score · 9 Chat · 10 Admin"
    )

    st.divider()
    if st.button("🚪 Logout", use_container_width=True):
        set_authenticated(False)
        st.rerun()

# ── Home content (shown when no page is selected) ─────────────────────────────
st.markdown(
    f"""
    ## 🏛️ Welcome to SFEID
    **Sustainable Facility & Estate Intelligence Dashboard**

    > **Facility:** {st.session_state.facility_name}

    Use the **sidebar** to navigate between dashboard pages.
    """,
)

col1, col2, col3 = st.columns(3)
with col1:
    st.info("📊 **Live Dashboard**\nReal-time KPI tiles and metric status across all zones.")
with col2:
    st.info("🤖 **AI Insights**\nRule-based recommendations — no API key needed.")
with col3:
    st.info("🔬 **What-If Simulator**\nModel energy and sustainability impact of changes.")

st.divider()
st.caption(
    "⚠️ Rows tagged **🔵 DEMO** are synthetic data for demonstration. "
    "**✏️ MANUAL** rows are admin-entered. **📡 LIVE** rows are from ESP32 sensors."
)

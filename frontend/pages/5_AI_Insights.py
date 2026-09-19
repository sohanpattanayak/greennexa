"""
frontend/pages/5_AI_Insights.py — AI-Generated Recommendations Page
"""

import json
import streamlit as st

from utils.api_client import (
    acknowledge_recommendation,
    ai_status,
    generate_recommendations,
    get_recommendations,
)
from utils.formatting import priority_tier
from utils.state import get_facility_id, get_facility_name, init_state
st.set_page_config(page_title="AI Insights | SFEID", layout="wide", page_icon="💡")
init_state()

facility_id   = get_facility_id()
facility_name = get_facility_name()

st.markdown(f"## 💡 AI Plain-Language Recommendations — {facility_name}")
st.caption(
    "Automated actionable insights and operational advice. "
    "Powered by a **deterministic rule engine** (always available offline), "
    "with optional **Gemini LLM enhancement** when configured."
)

# ── Header & Refresh Button ───────────────────────────────────────────────────
col1, col2 = st.columns([3, 1])

status_info = ai_status()
llm_enabled = status_info.get("llm_enabled", False)

with col1:
    if llm_enabled:
        st.info("🤖 **Mode:** LLM-Enhanced (Gemini 3.8 Flash active)")
    else:
        st.info("📋 **Mode:** Rule-Based Engine (Offline mode — no API key needed)")

with col2:
    if st.button("🔄 Generate Recommendations", use_container_width=True):
        with st.spinner("Analyzing campus metrics and anomalies..."):
            res = generate_recommendations(facility_id)
            st.success(f"Generated {res.get('generated', 0)} new recommendation(s).")
            st.rerun()

st.divider()

# ── Filter options ────────────────────────────────────────────────────────────
fcol1, fcol2 = st.columns(2)
with fcol1:
    cat_filter = st.selectbox("Category Filter", ["All", "energy", "air", "water", "waste", "occupancy"])
with fcol2:
    show_ack = st.checkbox("Show Acknowledged Recommendations", value=False)

recs = get_recommendations(facility_id, acknowledged=None if show_ack else False, limit=50)

if cat_filter != "All":
    recs = [r for r in recs if r["category"] == cat_filter]

if not recs:
    st.success(
        "✅ No pending recommendations found! "
        "Click **'Generate Recommendations'** to run the recommendation engine."
    )
    st.stop()

# ── Recommendations List ──────────────────────────────────────────────────────
st.subheader(f"📋 Operational Action Items ({len(recs)} Recommendations)")

for rec in recs:
    score = rec.get("priority_score", 50.0)
    tier, color = priority_tier(score)
    cat = rec.get("category", "general").upper()
    src = "🔵 LLM ENHANCED" if rec.get("source") == "llm" else "📋 RULE ENGINE"
    ack = rec.get("is_acknowledged", False)

    with st.expander(f"{tier} | [{cat}] {rec['title']} {' (✅ Acknowledged)' if ack else ''}"):
        rc1, rc2 = st.columns([3, 1])

        with rc1:
            st.markdown(f"**Description:** {rec.get('description', '')}")

            # Parse action items JSON
            actions_raw = rec.get("action_items_json")
            if actions_raw:
                try:
                    actions = json.loads(actions_raw)
                    if actions:
                        st.markdown("**Actionable Steps:**")
                        for step in actions:
                            st.markdown(f"- {step}")
                except Exception:
                    pass

        with rc2:
            st.markdown(f"**Priority Score:** <span style='color:{color}; font-weight:bold; font-size:1.2em;'>{score:.0f}/100</span>", unsafe_allow_html=True)
            st.markdown(f"**Source:** `{src}`")
            st.markdown(f"**Generated:** `{rec.get('generated_at', '')[:16].replace('T', ' ')}`")

            st.write("")
            if not ack:
                if st.button("✅ Acknowledge", key=f"ack_{rec['id']}", use_container_width=True):
                    acknowledge_recommendation(rec["id"])
                    st.success("Acknowledged!")
                    st.rerun()

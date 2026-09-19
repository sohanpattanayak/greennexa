"""
frontend/utils/state.py — Streamlit session state helpers
"""

import streamlit as st

DEFAULTS = {
    "authenticated":    False,
    "facility_id":      1,
    "facility_name":    "SFEID College of Engineering",
    "api_base_url":     "http://localhost:8000",
    "llm_enabled":      False,
    "chat_messages":    [],     # list of {"role": ..., "content": ...}
    "sim_result":       None,
    "last_refresh":     None,
}


def init_state():
    """Call at the top of every Streamlit page to ensure session state is initialised."""
    for key, default in DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = default


def set_facility(facility_id: int, facility_name: str):
    st.session_state.facility_id   = facility_id
    st.session_state.facility_name = facility_name


def get_facility_id() -> int:
    return st.session_state.get("facility_id", 1)


def get_facility_name() -> str:
    return st.session_state.get("facility_name", "SFEID College of Engineering")


def is_authenticated() -> bool:
    return st.session_state.get("authenticated", False)


def set_authenticated(value: bool):
    st.session_state.authenticated = value


def add_chat_message(role: str, content: str):
    st.session_state.chat_messages.append({"role": role, "content": content})


def clear_chat():
    st.session_state.chat_messages = []

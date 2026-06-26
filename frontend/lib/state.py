from __future__ import annotations

import streamlit as st

from api_client import ApiClient


def init_state() -> None:
    if "api" not in st.session_state:
        st.session_state.api = ApiClient()
    if "last_run" not in st.session_state:
        st.session_state.last_run = None
    if "review_filters" not in st.session_state:
        st.session_state.review_filters = {
            "field": None,
            "region": None,
            "status": None,
            "has_email": None,
        }


def get_api() -> ApiClient:
    return st.session_state.api

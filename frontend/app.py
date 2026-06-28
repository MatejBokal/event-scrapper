"""Confiva Lead Finder — entry point with sidebar navigation."""

from __future__ import annotations

import streamlit as st

from lib.constants import PAGE_DETAIL, PAGE_FIND, PAGE_MANUAL, PAGE_REVIEW
from lib.sidebar import render_global_sidebar
from lib.state import init_state

st.set_page_config(
    page_title="Lead Finder — Confiva",
    page_icon="📇",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_state()

if not render_global_sidebar():
    st.stop()

find_leads = st.Page(PAGE_FIND, title="Find leads", icon="🔍", default=True)
review_leads = st.Page(PAGE_REVIEW, title="Review leads", icon="📋")
manual_crawl = st.Page(PAGE_MANUAL, title="Manual crawl", icon="🛠️")
conference_detail = st.Page(
    PAGE_DETAIL,
    title="Conference detail",
    icon="📄",
    visibility="hidden",
)

pg = st.navigation(
    {
        "Search": [find_leads],
        "Leads": [review_leads, manual_crawl, conference_detail],
    },
    position="sidebar",
    expanded=True,
)

pg.run()

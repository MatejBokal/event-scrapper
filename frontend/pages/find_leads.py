from __future__ import annotations

from datetime import datetime

import streamlit as st

from lib.constants import PAGE_FIND, PAGE_REVIEW
from lib.nav import render_breadcrumbs, render_page_header
from lib.sidebar import api_ok
from lib.state import get_api
from options import FIELD_OPTIONS, MONTH_PICKER_HORIZON, REGION_OPTIONS


def _month_picker_options() -> dict[str, str]:
    options: dict[str, str] = {}
    year = datetime.now().year
    month = 1
    for _ in range(MONTH_PICKER_HORIZON):
        value = f"{year}-{month:02d}"
        label = datetime(year, month, 1).strftime("%B %Y")
        options[label] = value
        month += 1
        if month > 12:
            month = 1
            year += 1
    return options


def _default_month_labels(options: dict[str, str]) -> list[str]:
    now = datetime.now()
    defaults: list[str] = []
    year = now.year
    month = now.month
    for _ in range(3):
        value = f"{year}-{month:02d}"
        label = next((lbl for lbl, val in options.items() if val == value), None)
        if label:
            defaults.append(label)
        month += 1
        if month > 12:
            month = 1
            year += 1
    return defaults


render_breadcrumbs(("Find leads", None))
render_page_header(
    "Find leads",
    "Run search → crawl → extract. Results appear under Review leads and Manual crawl.",
)

if not api_ok():
    st.stop()

api = get_api()
month_options = _month_picker_options()
default_labels = [lbl for lbl in _default_month_labels(month_options) if lbl in month_options]

col1, col2 = st.columns(2)
with col1:
    field = st.selectbox("Field", FIELD_OPTIONS)
with col2:
    region = st.selectbox("Region", REGION_OPTIONS)

selected_labels = st.multiselect(
    "Months",
    options=list(month_options.keys()),
    default=default_labels,
    help="Events in these months (from January of the current year).",
)
selected_months = [month_options[label] for label in selected_labels]

col3, col4 = st.columns(2)
with col3:
    max_conferences = st.slider("Max conferences", min_value=1, max_value=20, value=10)
with col4:
    manual_url = st.text_input(
        "Manual official URL (optional)",
        placeholder="https://example.org/conference-2026",
    )

if st.button("Find leads", type="primary", use_container_width=True):
    if not selected_months:
        st.error("Select at least one month.")
    else:
        with st.spinner("Running pipeline — may take several minutes..."):
            try:
                result = api.run_full_pipeline(
                    field=field,
                    region=region,
                    selected_months=selected_months,
                    max_conferences=max_conferences,
                    manual_official_url=manual_url,
                )
                st.session_state.last_run = result
                st.success("Pipeline finished.")
                st.rerun()
            except Exception as exc:
                st.error(f"Pipeline failed: {exc}")

if st.session_state.last_run:
    run = st.session_state.last_run
    stats = run.get("stats") or {}
    st.divider()
    st.subheader("Last run")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Search hits", stats.get("search_hits", 0))
    m2.metric("Pages crawled", stats.get("pages_crawled", 0))
    m3.metric("Emails found", stats.get("emails_found", 0))
    m4.metric("Leads saved", stats.get("primary_leads_persisted", 0))
    m5.metric("Blocked sites", stats.get("sites_crawl_blocked", 0))
    st.caption(f"Run `{run.get('id')}` · status **{run.get('status')}**")
    if run.get("errors"):
        with st.expander("Errors / warnings"):
            for err in run["errors"]:
                st.write(err)
    llm_audit = stats.get("llm_audit") or []
    if llm_audit:
        with st.expander("LLM audit (Perplexity calls)"):
            for entry in llm_audit:
                status = "OK" if entry.get("success") else entry.get("skipped_reason") or "failed"
                st.markdown(
                    f"**{entry.get('conference_url', '—')}** — `{status}` "
                    f"({entry.get('duration_ms')} ms)"
                )
                if entry.get("pages_selected"):
                    st.caption("Pages: " + ", ".join(entry["pages_selected"]))
                if entry.get("organizers_found"):
                    st.caption(f"Organizers from LLM: {entry['organizers_found']}")
                if entry.get("conference_fields_filled"):
                    st.caption("Conference fields: " + ", ".join(entry["conference_fields_filled"]))
                if entry.get("usage"):
                    st.caption(f"Token usage: `{entry['usage']}`")
                if entry.get("error"):
                    st.error(entry["error"])
    if stats.get("llm_extraction_enabled"):
        st.caption("Detailed pipeline logs: `logs/app.log` in the repo root.")
    st.page_link(PAGE_REVIEW, label="Go to Review leads →", icon="📋")

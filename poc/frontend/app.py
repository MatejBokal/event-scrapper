"""Streamlit frontend for PoC v1.1 — Confiva lead generation."""

from __future__ import annotations

import sys
import sys
from datetime import datetime
from pathlib import Path

import streamlit as st

POC_ROOT = Path(__file__).resolve().parent.parent
if str(POC_ROOT) not in sys.path:
    sys.path.insert(0, str(POC_ROOT))

from backend.cloud_bootstrap import ensure_playwright_chromium
from backend.config import CONTACT_TYPES, DEFAULT_FIELD_SUGGESTIONS
from backend.exporter import (
    contacts_to_csv_bytes,
    export_filename,
    leads_to_csv_bytes,
    leads_to_json_bytes,
)
from backend.models import PipelineResult, SearchParams
from backend.pipeline import run_pipeline
from backend.regions import REGION_OPTIONS

st.set_page_config(
    page_title="Confiva Lead Finder — PoC",
    page_icon="📇",
    layout="wide",
)


@st.cache_resource(show_spinner="Preparing browser (first load only)...")
def _prepare_playwright() -> None:
    ensure_playwright_chromium()


if sys.platform == "linux":
    try:
        _prepare_playwright()
    except RuntimeError as exc:
        st.error(f"Browser setup failed: {exc}")
        st.stop()

st.title("Confiva Lead Finder")
st.caption(
    "PoC v1.1 — find conference organizer leads by field and region. "
    "One best contact per conference. Ready for export to your email tool."
)

if "pipeline_result" not in st.session_state:
    st.session_state.pipeline_result = None
if "progress_log" not in st.session_state:
    st.session_state.progress_log = []


def _default_start_month() -> str:
    return datetime.now().strftime("%Y-%m")


def _default_end_month() -> str:
    year = datetime.now().year + 1
    return f"{year}-03"


with st.form("search_form"):
    col1, col2 = st.columns(2)

    with col1:
        field = st.text_input(
            "Field / topic",
            value="Healthcare",
            help="Any topic works. Healthcare, pharma, security, IT, and AI are common.",
        )
        region = st.selectbox("Region", REGION_OPTIONS, index=REGION_OPTIONS.index("Slovenia"))
        contact_type = st.selectbox(
            "Contact focus",
            CONTACT_TYPES,
            index=0,
            help="Organizer is recommended for Confiva outreach.",
        )

    with col2:
        start_month = st.text_input("Start month (YYYY-MM)", value=_default_start_month())
        end_month = st.text_input("End month (YYYY-MM)", value=_default_end_month())
        max_conferences = st.slider("Max conferences", min_value=5, max_value=20, value=10)

    custom_region = ""
    if region == "Custom":
        custom_region = st.text_input(
            "Custom region / area / city",
            placeholder="e.g. DACH, Ljubljana, Bavaria",
        )

    manual_url = st.text_input(
        "Manual official URL (optional)",
        placeholder="https://example-conference.org",
    )

    submitted = st.form_submit_button("Find Leads", type="primary", use_container_width=True)

if submitted:
    params = SearchParams(
        field=field.strip(),
        region=region,
        start_month=start_month.strip(),
        end_month=end_month.strip(),
        contact_type=contact_type,
        max_conferences=max_conferences,
        manual_url=manual_url.strip(),
        custom_region=custom_region.strip(),
    )

    st.session_state.progress_log = []
    status = st.status("Running pipeline...", expanded=True)
    progress_placeholder = status.empty()

    def on_progress(stage: str, payload: dict) -> None:
        message = payload.get("message", stage)
        st.session_state.progress_log.append(f"[{stage}] {message}")
        progress_placeholder.write("\n".join(st.session_state.progress_log[-10:]))

    with st.spinner("Working..."):
        result = run_pipeline(params, on_progress=on_progress)

    st.session_state.pipeline_result = result

    if result.errors:
        for error in result.errors:
            if result.leads:
                st.warning(error)
            else:
                status.update(label="Finished with warnings", state="error")
                st.warning(error)
    elif result.leads:
        status.update(label="Leads found", state="complete")
    else:
        status.update(label="No leads found", state="complete")

result: PipelineResult | None = st.session_state.pipeline_result

if result:
    stats = result.stats
    m1, m2, m3, m4, m5, m6, m7 = st.columns(7)
    m1.metric("Queries", stats.queries_run)
    m2.metric("Search hits", stats.search_hits)
    m3.metric("Filtered out", stats.filtered_hits)
    m4.metric("Sites crawled", stats.sites_selected)
    m5.metric("From listings", stats.official_urls_from_listings)
    m6.metric("Leads", stats.leads_found)
    m7.metric("Raw emails", stats.emails_found)

    if result.leads:
        st.subheader("Organizer leads")
        st.dataframe(
            [
                {
                    "Conference": lead.conference_name or "—",
                    "Organizer": lead.organizer_name or "—",
                    "Email": lead.organizer_email,
                    "Quality": lead.contact_quality,
                    "Confidence": lead.confidence,
                    "URL": lead.conference_url,
                }
                for lead in result.leads
            ],
            use_container_width=True,
            hide_index=True,
        )

        with st.expander("Evidence snippets", expanded=False):
            for lead in result.leads:
                label = lead.organizer_name or lead.organizer_email
                st.markdown(f"**{label}** — {lead.source_url}")
                st.caption(lead.evidence_snippet)
                st.divider()

        col_csv, col_json = st.columns(2)
        with col_csv:
            st.download_button(
                label="Download leads CSV",
                data=leads_to_csv_bytes(result.leads),
                file_name=export_filename("csv"),
                mime="text/csv",
                use_container_width=True,
            )
        with col_json:
            st.download_button(
                label="Download leads JSON",
                data=leads_to_json_bytes(result.leads),
                file_name=export_filename("json"),
                mime="application/json",
                use_container_width=True,
            )
    else:
        st.info("No organizer leads found. Try Custom region, a manual URL, or a broader field.")

    with st.expander("Debug panel", expanded=False):
        st.markdown("#### Generated queries")
        if result.params:
            from backend.query_builder import build_queries

            for query in build_queries(result.params):
                st.write(query)

        st.markdown("#### Crawl targets (official sites)")
        if result.selected_sites:
            st.dataframe(
                [
                    {
                        "url": site.url,
                        "title": site.title,
                        "score": round(site.url_score, 1),
                        "source": site.source,
                        "discovered_from": site.discovered_from or "—",
                    }
                    for site in result.selected_sites
                ],
                use_container_width=True,
                hide_index=True,
            )

        st.markdown("#### Listing pages used for discovery")
        if result.listing_sources:
            st.dataframe(
                [
                    {
                        "url": site.url,
                        "title": site.title,
                        "score": round(site.url_score, 1),
                    }
                    for site in result.listing_sources
                ],
                use_container_width=True,
                hide_index=True,
            )

        st.markdown("#### Listing page warnings")
        if result.listing_warnings:
            for warning in result.listing_warnings:
                st.warning(warning)
            st.caption(
                "Some listing sites block automated access. Official sites from search "
                "are still crawled; install Playwright if you have not already."
            )

        st.markdown("#### Official URLs discovered via listings")
        if result.listing_discoveries:
            st.dataframe(
                [
                    {
                        "listing": discovery.listing_url,
                        "official_url": discovery.official_url,
                        "title": discovery.official_title,
                        "link_score": round(discovery.link_score, 1),
                    }
                    for discovery in result.listing_discoveries
                ],
                use_container_width=True,
                hide_index=True,
            )

        st.markdown("#### Filtered out (news/spam/stale)")
        if result.filtered_urls:
            st.dataframe(
                [
                    {"title": hit.title, "url": hit.url}
                    for hit in result.filtered_urls[:20]
                ],
                use_container_width=True,
                hide_index=True,
            )

        st.markdown("#### Skipped URLs (low score)")
        if result.skipped_urls:
            st.dataframe(
                [
                    {
                        "title": hit.title,
                        "url": hit.url,
                        "score": round(hit.url_score, 1),
                    }
                    for hit in result.skipped_urls[:20]
                ],
                use_container_width=True,
                hide_index=True,
            )

        if result.contacts:
            st.markdown("#### All raw contacts")
            st.download_button(
                label="Download raw contacts CSV",
                data=contacts_to_csv_bytes(result.contacts),
                file_name=export_filename("csv", prefix="confiva_raw_contacts"),
                mime="text/csv",
            )

else:
    st.info("Fill in the search form and click **Find Leads** to start.")
    st.write("Suggested fields:", ", ".join(DEFAULT_FIELD_SUGGESTIONS))

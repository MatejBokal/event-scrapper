from __future__ import annotations

import streamlit as st

from lib.constants import (
    BLOCK_REASON_LABELS,
    CONTACT_QUALITY_OPTIONS,
    PAGE_FIND,
    PAGE_MANUAL,
    PAGE_REVIEW,
    STATUS_OPTIONS,
)
from lib.nav import go_back_from_detail, render_breadcrumbs, render_page_header
from lib.sidebar import api_ok
from lib.state import get_api


def _block_reason_label(reason: str | None) -> str:
    if not reason:
        return "Unknown"
    return BLOCK_REASON_LABELS.get(reason, reason.replace("_", " "))


conference_id = st.query_params.get("conference")
if not conference_id:
    st.warning("No conference selected.")
    st.page_link(PAGE_REVIEW, label="Go to Review leads", icon="📋")
    st.stop()

return_page = st.session_state.get("detail_return_page", PAGE_REVIEW)
return_label = "Manual crawl" if return_page == PAGE_MANUAL else "Review leads"

if not api_ok():
    st.stop()

api = get_api()

try:
    conference = api.get_conference(conference_id)
except Exception as exc:
    st.error(f"Failed to load conference: {exc}")
    st.stop()

render_breadcrumbs(
    ("Find leads", PAGE_FIND),
    (return_label, return_page),
    (conference["name"][:48], None),
)

nav_cols = st.columns([1, 1, 6])
with nav_cols[0]:
    if st.button("← Back", use_container_width=True):
        go_back_from_detail()
with nav_cols[1]:
    st.link_button("Official site ↗", conference["official_url"], use_container_width=True)

render_page_header(conference["name"])

if conference.get("status") == "crawl_blocked":
    reason = _block_reason_label(conference.get("crawl_block_reason"))
    st.warning(
        f"**Auto-crawl blocked** — {reason}"
        + (f" (HTTP {conference['crawl_http_status']})" if conference.get("crawl_http_status") else "")
    )
    if conference.get("crawl_block_detail"):
        st.caption(conference["crawl_block_detail"])
    if st.button("Allow auto-crawl on next run"):
        api.retry_crawl(conference_id)
        st.success("Unblocked.")
        st.rerun()

action_cols = st.columns(3)
if action_cols[0].button("Mark verified", use_container_width=True):
    api.update_conference(conference_id, {"status": "verified"})
    st.success("Marked as verified.")
    st.rerun()
if action_cols[1].button("Needs review", use_container_width=True):
    api.update_conference(conference_id, {"status": "needs_review"})
    st.success("Marked as needs review.")
    st.rerun()
if action_cols[2].button("Mark rejected", use_container_width=True):
    api.update_conference(conference_id, {"status": "rejected"})
    st.success("Marked as rejected.")
    st.rerun()

tab_overview, tab_organizers, tab_evidence, tab_crawl = st.tabs(
    ["Overview", "Organizers", "Evidence", "Crawl history"]
)

with tab_overview:
    with st.form("conference_form"):
        name = st.text_input("Name", conference["name"])
        field = st.text_input("Field", conference.get("field") or "")
        region = st.text_input("Region", conference.get("region") or "")
        location = st.text_input("Location", conference.get("location") or "")
        month_year = st.text_input("Month / year", conference.get("month_year") or "")
        official_url = st.text_input("Official URL", conference["official_url"])
        status = st.selectbox(
            "Status",
            STATUS_OPTIONS,
            index=STATUS_OPTIONS.index(conference["status"])
            if conference["status"] in STATUS_OPTIONS
            else 0,
        )
        confidence = st.number_input(
            "Confidence score",
            min_value=0,
            max_value=100,
            value=int(conference.get("confidence_score") or 0),
        )
        if st.form_submit_button("Save conference", use_container_width=True):
            api.update_conference(
                conference_id,
                {
                    "name": name,
                    "field": field or None,
                    "region": region or None,
                    "location": location or None,
                    "month_year": month_year or None,
                    "official_url": official_url,
                    "status": status,
                    "confidence_score": confidence,
                },
            )
            st.success("Conference updated.")
            st.rerun()

with tab_organizers:
    organizers = conference.get("organizers") or []
    if not organizers:
        st.info("No organizers yet — add contacts manually after visiting the official site.")
    for org in organizers:
        label = f"{'⭐ Primary — ' if org.get('is_primary_lead') else ''}{org['email']}"
        with st.expander(label, expanded=org.get("is_primary_lead", False)):
            with st.form(f"org_form_{org['id']}"):
                email = st.text_input("Email", org["email"], key=f"email_{org['id']}")
                org_name = st.text_input("Name", org.get("name") or "", key=f"name_{org['id']}")
                role = st.text_input("Role", org.get("role") or "", key=f"role_{org['id']}")
                organization = st.text_input(
                    "Organization",
                    org.get("organization") or "",
                    key=f"org_{org['id']}",
                )
                quality = st.selectbox(
                    "Contact quality",
                    CONTACT_QUALITY_OPTIONS,
                    index=CONTACT_QUALITY_OPTIONS.index(org["contact_quality"])
                    if org.get("contact_quality") in CONTACT_QUALITY_OPTIONS
                    else 3,
                    key=f"quality_{org['id']}",
                )
                is_primary = st.checkbox(
                    "Primary lead for export",
                    value=bool(org.get("is_primary_lead")),
                    key=f"primary_{org['id']}",
                )
                org_confidence = st.number_input(
                    "Confidence",
                    min_value=0,
                    max_value=100,
                    value=int(org.get("confidence_score") or 0),
                    key=f"conf_{org['id']}",
                )
                if st.form_submit_button("Save organizer", use_container_width=True):
                    api.update_organizer(
                        org["id"],
                        {
                            "email": email,
                            "name": org_name or None,
                            "role": role or None,
                            "organization": organization or None,
                            "contact_quality": quality,
                            "is_primary_lead": is_primary,
                            "confidence_score": org_confidence,
                        },
                    )
                    st.success("Organizer updated.")
                    st.rerun()

with tab_evidence:
    evidence_rows = conference.get("evidence") or []
    if not evidence_rows:
        st.info("No evidence snippets stored.")
    for item in evidence_rows:
        st.markdown(f"**[{item.get('evidence_type') or 'evidence'}]({item['source_url']})**")
        if item.get("source_title"):
            st.caption(item["source_title"])
        st.text(item["extracted_text_snippet"])
        st.divider()

with tab_crawl:
    pages = conference.get("crawled_pages") or []
    if not pages:
        st.info("No crawled pages stored for this conference.")
    else:
        st.dataframe(
            [
                {
                    "url": page["url"],
                    "title": page.get("title"),
                    "type": page.get("page_type"),
                    "text_chars": page.get("text_length"),
                    "crawled_at": page.get("crawled_at"),
                }
                for page in pages
            ],
            use_container_width=True,
            hide_index=True,
        )

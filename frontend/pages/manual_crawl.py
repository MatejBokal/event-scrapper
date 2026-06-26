from __future__ import annotations

import streamlit as st

from lib.constants import BLOCK_REASON_LABELS, PAGE_FIND, PAGE_MANUAL, PAGE_REVIEW
from lib.nav import open_conference, render_breadcrumbs, render_page_header
from lib.sidebar import api_ok
from lib.state import get_api


def _block_reason_label(reason: str | None) -> str:
    if not reason:
        return "Unknown"
    return BLOCK_REASON_LABELS.get(reason, reason.replace("_", " "))


render_breadcrumbs(("Find leads", PAGE_FIND), ("Manual crawl", None))
render_page_header(
    "Manual crawl",
    "Sites that blocked automated crawling — open in your browser and add contacts manually.",
)

if not api_ok():
    st.stop()

api = get_api()

try:
    rows = api.list_conferences(status="crawl_blocked", limit=200)
except Exception as exc:
    st.error(f"Failed to load blocked sites: {exc}")
    st.stop()

if not rows:
    st.info("No blocked sites yet. They appear here when crawl gets 403 or returns no pages.")
    st.page_link(PAGE_FIND, label="Run a search →", icon="🔍")
    st.stop()

st.subheader(f"{len(rows)} sites need manual review")

for row in rows:
    reason = _block_reason_label(row.get("crawl_block_reason"))
    http_status = row.get("crawl_http_status")
    status_note = f"HTTP {http_status}" if http_status else reason

    with st.container(border=True):
        head = st.columns([5, 2, 2, 2])
        head[0].markdown(f"**{row['name']}**")
        head[0].caption(row["official_url"])
        head[1].write(row.get("field") or "—")
        head[2].write(row.get("region") or "—")
        head[3].write(status_note)

        actions = st.columns([1, 1, 4])
        if actions[0].button("Open detail", key=f"manual_open_{row['id']}", use_container_width=True):
            open_conference(row["id"], from_page=PAGE_MANUAL)
        if actions[1].button("Retry auto-crawl", key=f"retry_{row['id']}", use_container_width=True):
            try:
                api.retry_crawl(row["id"])
                st.success("Unblocked for next pipeline run.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
        actions[2].link_button("Open in browser ↗", row["official_url"], use_container_width=True)

st.divider()
st.page_link(PAGE_REVIEW, label="← Back to Review leads", icon="📋")

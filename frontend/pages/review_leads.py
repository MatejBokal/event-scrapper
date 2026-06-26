from __future__ import annotations

import streamlit as st

from lib.constants import PAGE_FIND, PAGE_REVIEW, STATUS_OPTIONS
from lib.nav import open_conference, render_breadcrumbs, render_page_header
from lib.sidebar import api_ok
from lib.state import get_api
from options import FIELD_OPTIONS, REGION_OPTIONS


def _load_filter_options(api):
    try:
        all_rows = api.list_conferences(limit=200)
    except Exception:
        all_rows = []
    fields = sorted({*FIELD_OPTIONS, *(r["field"] for r in all_rows if r.get("field"))})
    regions = sorted({*REGION_OPTIONS, *(r["region"] for r in all_rows if r.get("region"))})
    return fields, regions


render_breadcrumbs(("Find leads", PAGE_FIND), ("Review leads", None))
render_page_header("Review leads", "Browse, filter, and open conferences to edit contacts.")

if not api_ok():
    st.stop()

api = get_api()
fields, regions = _load_filter_options(api)

with st.expander("Filters", expanded=True):
    f1, f2, f3, f4 = st.columns(4)
    with f1:
        field_pick = st.selectbox("Field", ["(all)", *fields], key="review_filter_field")
    with f2:
        region_pick = st.selectbox("Region", ["(all)", *regions], key="review_filter_region")
    with f3:
        status_pick = st.selectbox("Status", ["(all)", *STATUS_OPTIONS], key="review_filter_status")
    with f4:
        has_email_label = st.selectbox(
            "Has primary email", ["(all)", "Yes", "No"], key="review_filter_email"
        )

field = None if field_pick == "(all)" else field_pick
region = None if region_pick == "(all)" else region_pick
status = None if status_pick == "(all)" else status_pick
has_email = None
if has_email_label == "Yes":
    has_email = True
elif has_email_label == "No":
    has_email = False

try:
    rows = api.list_conferences(
        field=field,
        region=region,
        status=status,
        has_email=has_email,
        limit=200,
    )
except Exception as exc:
    st.error(f"Failed to load conferences: {exc}")
    st.stop()

if not rows:
    st.info("No conferences match these filters.")
    st.page_link(PAGE_FIND, label="Run a search →", icon="🔍")
    st.stop()

st.subheader(f"{len(rows)} conferences")

for row in rows:
    with st.container(border=True):
        top = st.columns([5, 2, 2, 2, 1])
        top[0].markdown(f"**{row['name']}**")
        top[0].caption(row["official_url"])
        top[1].write(row.get("field") or "—")
        top[2].write(row.get("region") or "—")
        top[3].write(f"{row['status']} · {row.get('confidence_score', 0)}%")
        if top[4].button("Open", key=f"review_open_{row['id']}", use_container_width=True):
            open_conference(row["id"], from_page=PAGE_REVIEW)

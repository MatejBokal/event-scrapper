from __future__ import annotations

import streamlit as st

from lib.constants import PAGE_DETAIL, PAGE_FIND, PAGE_MANUAL, PAGE_REVIEW


def open_conference(conference_id: str, *, from_page: str = PAGE_REVIEW) -> None:
    st.session_state.detail_return_page = from_page
    st.query_params["conference"] = conference_id
    st.switch_page(PAGE_DETAIL)


def go_back_from_detail() -> None:
    return_page = st.session_state.pop("detail_return_page", PAGE_REVIEW)
    if "conference" in st.query_params:
        del st.query_params["conference"]
    st.switch_page(return_page)


def render_breadcrumbs(*crumbs: tuple[str, str | None]) -> None:
    """Each crumb is (label, page_path). None page_path = current page."""
    if not crumbs:
        return
    cols = st.columns(min(len(crumbs) * 2 - 1, 12) or 1)
    col_idx = 0
    for index, (label, page_path) in enumerate(crumbs):
        if index > 0:
            with cols[col_idx]:
                st.caption("›")
            col_idx += 1
        with cols[col_idx]:
            if page_path:
                st.page_link(page_path, label=label)
            else:
                st.markdown(f"**{label}**")
        col_idx += 1
    st.divider()


def render_page_header(title: str, caption: str | None = None) -> None:
    st.title(title)
    if caption:
        st.caption(caption)

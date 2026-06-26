from __future__ import annotations

from datetime import datetime

import streamlit as st

from api_client import base_url
from lib.state import get_api


def api_ok() -> bool:
    try:
        get_api().health()
        return True
    except Exception:
        return False


def render_global_sidebar() -> bool:
    """API status + export. Returns True if API is reachable."""
    with st.sidebar:
        st.markdown("### Confiva Lead Finder")
        st.caption(f"API `{base_url()}`")

        if not api_ok():
            st.error("API offline — start backend on port 8001")
            return False

        st.success("API connected")

        st.divider()
        st.markdown("**Quick export**")
        if st.button("Export leads (.xlsx)", use_container_width=True, key="sidebar_export"):
            try:
                content = get_api().export_leads_xlsx()
                st.download_button(
                    "Download Excel",
                    data=content,
                    file_name=f"confiva_leads_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
            except Exception as exc:
                st.error(f"Export failed: {exc}")

        st.divider()
        st.caption("Use the sidebar menu above to switch pages.")

    return True

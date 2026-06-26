"""Import PoC pipeline modules from poc/backend."""

from __future__ import annotations

import sys
from pathlib import Path

POC_ROOT = Path(__file__).resolve().parents[3] / "poc"
if str(POC_ROOT) not in sys.path:
    sys.path.insert(0, str(POC_ROOT))

from backend.confidence import apply_confidence  # noqa: E402
from backend.crawler import crawl_site, get_conference_name  # noqa: E402
from backend.domains import is_denylisted_domain, is_listing_domain, is_spam_domain  # noqa: E402
from backend.event_filter import filter_event_hits  # noqa: E402
from backend.extractor import extract_emails_from_pages  # noqa: E402
from backend.config import is_llm_extraction_enabled  # noqa: E402
from backend.geo_filter import apply_geo_scoring  # noqa: E402
from backend.lead_ranker import build_leads, classify_contact_quality  # noqa: E402
from backend.listing_discovery import expand_sites_via_listings  # noqa: E402
from backend.models import CrawledPage, CrawlSiteResult, SelectedSite  # noqa: E402
from backend.query_builder import build_queries  # noqa: E402
from backend.search_ddg import search_queries as ddg_search  # noqa: E402
from backend.url_scorer import select_sites  # noqa: E402
from backend.validator import validate_hits  # noqa: E402

__all__ = [
    "CrawledPage",
    "CrawlSiteResult",
    "SearchHit",
    "SearchParams",
    "SelectedSite",
    "build_queries",
    "ddg_search",
    "filter_event_hits",
    "apply_geo_scoring",
    "select_sites",
    "expand_sites_via_listings",
    "is_listing_domain",
    "is_spam_domain",
    "is_denylisted_domain",
    "crawl_site",
    "get_conference_name",
    "extract_emails_from_pages",
    "is_llm_extraction_enabled",
    "validate_hits",
    "apply_confidence",
    "build_leads",
    "classify_contact_quality",
]

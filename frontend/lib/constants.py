STATUS_OPTIONS = [
    "discovered",
    "official_site_found",
    "crawled",
    "extracted",
    "crawl_blocked",
    "needs_review",
    "verified",
    "rejected",
]

BLOCK_REASON_LABELS = {
    "http_403": "403 Forbidden (site blocked the bot)",
    "http_401": "401 Unauthorized",
    "http_429": "429 Too many requests",
    "fetch_failed": "Fetch failed",
    "empty": "No usable page content",
    "exception": "Crawler error",
}

CONTACT_QUALITY_OPTIONS = ["named_organizer", "role_email", "generic_info", "unknown"]

PAGE_FIND = "pages/find_leads.py"
PAGE_REVIEW = "pages/review_leads.py"
PAGE_MANUAL = "pages/manual_crawl.py"
PAGE_DETAIL = "pages/conference_detail.py"

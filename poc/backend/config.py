"""Configuration defaults for PoC v1.1 — Confiva lead generation."""

from __future__ import annotations

import os
from pathlib import Path


def _load_repo_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    repo_root = Path(__file__).resolve().parents[2]
    load_dotenv(repo_root / ".env")


_load_repo_dotenv()

from backend.app_logging import setup_logging  # noqa: E402

setup_logging()

MAX_QUERIES = 30
RESULTS_PER_QUERY = 15
MAX_CONFERENCE_SITES = 10
MAX_PAGES_PER_SITE = 10
MAX_CRAWL_DEPTH = 2
REQUEST_DELAY_SECONDS = 1.5
SITE_CRAWL_TIMEOUT_SECONDS = 120
ROBOTS_TIMEOUT_SECONDS = 10
EVIDENCE_SNIPPET_CHARS = 200
MIN_PAGE_TEXT_LENGTH = 100
MIN_URL_SCORE = 8

PLAYWRIGHT_TIMEOUT_MS = 30_000
PLAYWRIGHT_WAIT_MS = 1_500

JS_FRAMEWORK_MARKERS = (
    "__next_data__",
    "__nuxt",
    "data-reactroot",
    "ng-version",
    'id="root"',
    "id='root'",
    "__gatsby",
    "window.__initial_state__",
    "data-server-rendered",
)

SEARCH_TIMEOUT_SECONDS = 25
SEARCH_RETRY_DELAY_SECONDS = 2.0

# All ddgs text backends — aggregated on first attempt, then retried individually.
SEARCH_BACKENDS: list[str] = [
    "duckduckgo",
    "bing",
    "yahoo",
    "mojeek",
    "brave",
    "google",
    "yandex",
]
SEARCH_BACKENDS_AGGREGATED = ",".join(SEARCH_BACKENDS)

USER_AGENT = (
    "Mozilla/5.0 (compatible; ConferenceContactPoC/1.1; +local-dev)"
)

# Realistic browser UA for Playwright — listing sites often block bot-like agents.
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# Listing sites that block simple HTTP scraping — fetch with Playwright first.
LISTING_PLAYWRIGHT_FIRST_DOMAINS = [
    "10times.com",
    "eventbrite.com",
    "allconferences.com",
    "conferencealert.com",
]

# Listing / aggregator sites — discovery only; never extract contacts from these domains.
LISTING_DOMAINS = [
    "eventbrite.com",
    "meetup.com",
    "10times.com",
    "allconferences.com",
    "conferencealert.com",
    "conferenceindex.org",
    "conference-series.com",
    "conferenceseries.com",
    "internationalconferencealerts.com",
    "papercept.net",
]

LISTING_MAX_PER_RUN = 3
OFFICIAL_LINKS_PER_LISTING = 5
GATEWAY_PAGE_TIMEOUT_SECONDS = 60

# Hard-drop fake / SEO conference farms (event filter stage).
SPAM_DOMAINS = [
    "mindauthors.com",
    "healthssummit.com",
    "waset.org",
]

# Social, news, policy pages — never crawl for leads or follow as official targets.
AGGREGATOR_DENYLIST = [
    "wikidata.org",
    "wikipedia.org",
    "reddit.com",
    "linkedin.com",
    "facebook.com",
    "twitter.com",
    "x.com",
    "youtube.com",
    "instagram.com",
    "tiktok.com",
    "pinterest.com",
    "ungeneva.org",
    "efpia.eu",
    "mindauthors.com",
    "healthssummit.com",
    "waset.org",
]

# Ticket vendors — no organizer emails; crawls often hang on JS/anti-bot.
TICKET_VENDOR_DOMAINS = [
    "oeticket.com",
    "oeticket.at",
    "eventim.",
    "ticketmaster.",
    "adticket.",
    "universe.com",
    "fienta.com",
    "tickets.",
]

CONFERENCE_KEYWORDS = [
    "conference",
    "summit",
    "congress",
    "symposium",
    "workshop",
    "colloquium",
    "kongres",
    "konferenca",
    "konferenz",
    "event",
    "fair",
    "sejem",
    "messe",
]

PREFERRED_PATH_KEYWORDS = [
    "contact",
    "organizers",
    "organisers",
    "organizing",
    "organising",
    "about",
    "team",
    "committee",
    "registration",
    "sponsors",
    "sponsorship",
    "sponsor",
    "cfp",
    "call-for-papers",
    "call_for_papers",
    "exhibitors",
    "exhibition",
]

CONTACT_TYPE_KEYWORDS: dict[str, list[str]] = {
    "organizer": [
        "organizer",
        "organiser",
        "organizing",
        "organising",
        "event manager",
        "congress organiser",
        "congress organizer",
        "project manager",
        "pco",
    ],
    "committee": ["committee", "chair", "program"],
    "sponsorship": ["sponsor", "sponsorship", "partnership"],
    "exhibitor": ["exhibitor", "exhibition", "booth"],
    "cfp": ["cfp", "call for papers", "submission", "abstract"],
    "generic": ["contact", "info", "inquiry", "enquir"],
}

GENERIC_EMAIL_PREFIXES = ["info@", "contact@", "hello@", "office@", "mail@", "reception@"]

CONTACT_TYPES = ["organizer", "any", "committee"]

FIELD_OPTIONS = [
    "Healthcare",
    "Pharmaceuticals",
    "Security",
    "Cybersecurity",
    "IT",
    "AI",
]

DEFAULT_FIELD_SUGGESTIONS = FIELD_OPTIONS

# Phase 8 — Perplexity Sonar LLM extraction
LLM_MAX_PAGE_CHARS = 12_000
LLM_REQUEST_DELAY_SECONDS = 0.3
LLM_MAX_PAGES_PER_SITE = 3

LLM_PATH_KEYWORDS_ORGANIZER = (
    "contact",
    "organizers",
    "organisers",
    "organizing",
    "organising",
    "committee",
    "about",
    "team",
    "registration",
)

LLM_PATH_KEYWORDS_LOW_PRIORITY = (
    "sponsor",
    "sponsorship",
    "cfp",
    "call-for-papers",
    "call_for_papers",
    "exhibitor",
    "exhibitors",
    "exhibition",
    "abstract",
)


def get_perplexity_api_key() -> str | None:
    key = os.environ.get("PERPLEXITY_API_KEY", "").strip()
    return key or None


def get_perplexity_model() -> str:
    return os.environ.get("PERPLEXITY_MODEL", "sonar").strip() or "sonar"


def get_llm_max_pages_per_site() -> int:
    raw = os.environ.get("LLM_MAX_PAGES_PER_SITE", str(LLM_MAX_PAGES_PER_SITE)).strip()
    try:
        value = int(raw)
    except ValueError:
        return LLM_MAX_PAGES_PER_SITE
    return max(1, value)


def is_llm_extraction_enabled() -> bool:
    if not get_perplexity_api_key():
        return False
    flag = os.environ.get("EXTRACTION_USE_LLM", "").strip().lower()
    if flag in ("0", "false", "no"):
        return False
    return True

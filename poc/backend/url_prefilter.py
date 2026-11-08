"""Queue prefilter: hopeless hosts, paths, and file/endpoint URLs."""

from __future__ import annotations

from urllib.parse import urlparse

from backend.config import AGGREGATOR_DENYLIST
from backend.domains import is_denylisted_domain, is_spam_domain

# Exact hosts or suffixes (matched against www-stripped host).
HOPELESS_HOSTS: tuple[str, ...] = (
    "api.whatsapp.com",
    "wa.me",
    "whatsapp.com",
    "t.me",
    "telegram.me",
    "telegram.org",
    "calendar.google.com",
    "calendar.yahoo.com",
    "outlook.live.com",
    "outlook.office.com",
    "outlook.office365.com",
    "maps.google.com",
    "maps.app.goo.gl",
)

HOPELESS_HOST_SUBSTRINGS: tuple[str, ...] = (
    "maps.google.",
)

HOPELESS_PATH_MARKERS: tuple[str, ...] = (
    "/blog/",
    "/blogs/",
    "/news/",
    "/press/",
    "/article/",
    "/articles/",
    "/jobs/",
    "/careers/",
    "/career/",
    "/privacy",
    "/terms",
    "/cookie",
    "/login",
    "/signin",
    "/sign-in",
    "/account",
    "/wp-login",
)

HOPELESS_EXTENSIONS: tuple[str, ...] = (
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".svg",
    ".zip",
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
    ".mp4",
    ".mp3",
    ".webp",
    ".ics",
)


def _host_matches(host: str, pattern: str) -> bool:
    host = host.lower().removeprefix("www.")
    pattern = pattern.lower().removeprefix("www.")
    return host == pattern or host.endswith("." + pattern)


def classify_hopeless_url(url: str) -> str | None:
    """Return a reason code if the URL should not be crawled, else None."""
    if not url or not str(url).strip():
        return "hopeless_empty"

    raw = str(url).strip()
    lower = raw.lower()
    if lower.startswith(("mailto:", "tel:", "javascript:", "data:")):
        return "hopeless_scheme"

    parsed = urlparse(raw)
    host = (parsed.netloc or "").lower().removeprefix("www.")
    path = (parsed.path or "").lower()
    scheme = (parsed.scheme or "").lower()

    if scheme in {"mailto", "tel", "javascript", "data"}:
        return "hopeless_scheme"

    if is_spam_domain(raw) or is_denylisted_domain(raw):
        return "hopeless_host"

    if host.endswith("google.com") and "/calendar" in path:
        return "hopeless_host"
    if "goo.gl/maps" in lower or "/maps" in path and "google." in host:
        return "hopeless_host"

    for pattern in HOPELESS_HOSTS:
        if _host_matches(host, pattern):
            return "hopeless_host"
    for fragment in HOPELESS_HOST_SUBSTRINGS:
        if fragment in host:
            return "hopeless_host"
    for entry in AGGREGATOR_DENYLIST:
        if entry in host:
            return "hopeless_host"

    for marker in HOPELESS_PATH_MARKERS:
        if marker in path:
            return "hopeless_path"

    for ext in HOPELESS_EXTENSIONS:
        if path.endswith(ext):
            return "hopeless_file"

    return None


def is_hopeless_url(url: str) -> bool:
    return classify_hopeless_url(url) is not None

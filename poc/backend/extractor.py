"""Rule-based email extraction from crawled pages — no LLM."""

from __future__ import annotations

import re
from urllib.parse import unquote, urlparse

from bs4 import BeautifulSoup

from backend.config import (
    CONTACT_TYPE_KEYWORDS,
    EVIDENCE_SNIPPET_CHARS,
    GENERIC_EMAIL_PREFIXES,
    PREFERRED_PATH_KEYWORDS,
)
from backend.models import CrawledPage, RawEmailHit, SearchParams

EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
)

PATH_CONTACT_TYPES: dict[str, str] = {
    "sponsor": "sponsorship",
    "sponsorship": "sponsorship",
    "sponsors": "sponsorship",
    "exhibitor": "exhibitor",
    "exhibitors": "exhibitor",
    "exhibition": "exhibitor",
    "cfp": "cfp",
    "call-for-papers": "cfp",
    "call_for_papers": "cfp",
    "committee": "committee",
    "organizer": "organizer",
    "organisers": "organizer",
    "organizers": "organizer",
    "contact": "generic",
}


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _is_plausible_email(email: str) -> bool:
    lowered = email.lower()
    if any(bad in lowered for bad in (".png", ".jpg", ".gif", ".svg", "example.com", "email@")):
        return False
    if lowered.endswith((".js", ".css")):
        return False
    local, _, domain = lowered.partition("@")
    if not local or not domain or "." not in domain:
        return False
    return True


def _contact_type_from_path(path: str) -> str | None:
    path_lower = path.lower()
    for keyword, contact_type in PATH_CONTACT_TYPES.items():
        if keyword in path_lower:
            return contact_type
    return None


def _contact_type_from_context(context: str) -> str:
    context_lower = context.lower()
    best_type = "unknown"
    best_score = 0

    for contact_type, keywords in CONTACT_TYPE_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword in context_lower)
        if score > best_score:
            best_score = score
            best_type = contact_type

    if best_type == "generic" and best_score == 0:
        return "unknown"
    return best_type


def _evidence_snippet(text: str, email: str) -> str:
    if not text:
        return ""
    lower_text = text.lower()
    lower_email = email.lower()
    index = lower_text.find(lower_email)
    if index == -1:
        return text[:EVIDENCE_SNIPPET_CHARS].strip()

    half = EVIDENCE_SNIPPET_CHARS // 2
    start = max(0, index - half)
    end = min(len(text), index + len(email) + half)
    snippet = text[start:end].strip()
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    return snippet


def _context_window(text: str, email: str, window: int = 100) -> str:
    lower_text = text.lower()
    lower_email = email.lower()
    index = lower_text.find(lower_email)
    if index == -1:
        return text[: window * 2]
    start = max(0, index - window)
    end = min(len(text), index + len(email) + window)
    return text[start:end]


def _extract_mailto_emails(html: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    emails: list[str] = []
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if not href.lower().startswith("mailto:"):
            continue
        raw = href[7:].split("?")[0]
        email = _normalize_email(unquote(raw))
        if _is_plausible_email(email):
            emails.append(email)
    return emails


def _resolve_contact_type(
    path_type: str | None,
    context_type: str,
    email: str,
    preferred_contact_type: str,
) -> str:
    if any(email.startswith(prefix) for prefix in GENERIC_EMAIL_PREFIXES):
        if path_type:
            return path_type
        return "generic"

    if preferred_contact_type != "any":
        if context_type == preferred_contact_type or path_type == preferred_contact_type:
            return preferred_contact_type
        if path_type:
            return path_type
        if context_type != "unknown":
            return context_type
        return preferred_contact_type

    if path_type:
        return path_type
    if context_type != "unknown":
        return context_type
    return "unknown"


def extract_emails_from_pages(
    pages: list[CrawledPage],
    params: SearchParams,
    conference_name: str | None,
) -> list[RawEmailHit]:
    hits: list[RawEmailHit] = []
    seen: set[tuple[str, str]] = set()

    for page in pages:
        path_type = _contact_type_from_path(urlparse(page.url).path)
        text = page.extracted_text or ""

        sources: list[tuple[str, str]] = []

        if page.html:
            for email in _extract_mailto_emails(page.html):
                sources.append((email, "mailto"))

        for match in EMAIL_PATTERN.finditer(text):
            email = _normalize_email(match.group(0))
            if _is_plausible_email(email):
                sources.append((email, "regex"))

        for email, method in sources:
            key = (email, page.url)
            if key in seen:
                continue
            seen.add(key)

            context = _context_window(text, email)
            context_type = _contact_type_from_context(context)
            contact_type = _resolve_contact_type(
                path_type,
                context_type,
                email,
                params.contact_type,
            )

            extraction_method = method
            if method == "regex" and context_type != "unknown":
                extraction_method = "regex+keyword"

            hits.append(
                RawEmailHit(
                    email=email,
                    source_url=page.url,
                    page_title=page.title,
                    extracted_text=text,
                    extraction_method=extraction_method,
                    contact_type=contact_type,
                    conference_url=page.conference_url,
                    conference_name=conference_name,
                )
            )

    return hits

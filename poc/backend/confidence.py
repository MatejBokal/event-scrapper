"""Deterministic confidence scoring for contact rows."""

from __future__ import annotations

from urllib.parse import urlparse

from backend.config import GENERIC_EMAIL_PREFIXES, PREFERRED_PATH_KEYWORDS
from backend.domains import is_denylisted_domain, is_listing_domain
from backend.extractor import _contact_type_from_context, _context_window
from backend.models import ContactResult


def _domain(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def _is_aggregator(url: str) -> bool:
    return is_listing_domain(url) or is_denylisted_domain(url)


def _path_is_preferred(path: str) -> bool:
    path_lower = path.lower()
    return any(keyword in path_lower for keyword in PREFERRED_PATH_KEYWORDS)


def score_contact(contact: ContactResult, page_text: str = "") -> int:
    score = 0

    conference_domain = _domain(contact.conference_url)
    source_domain = _domain(contact.source_url)

    if conference_domain and conference_domain == source_domain:
        score += 40

    if _path_is_preferred(urlparse(contact.source_url).path):
        score += 20

    if page_text:
        context = _context_window(page_text, contact.email)
        inferred = _contact_type_from_context(context)
        if inferred == contact.contact_type and contact.contact_type != "unknown":
            score += 20
        elif inferred != "unknown":
            score += 10

    if contact.extraction_method == "mailto":
        score += 10

    if not _is_aggregator(contact.source_url):
        score += 10

    if any(contact.email.startswith(prefix) for prefix in GENERIC_EMAIL_PREFIXES):
        contact.contact_type = "generic"

    if _is_aggregator(contact.source_url):
        score = min(score, 20 if is_listing_domain(contact.source_url) else 50)

    return min(score, 100)


def apply_confidence(contacts: list[ContactResult], page_texts: dict[str, str]) -> list[ContactResult]:
    for contact in contacts:
        page_text = page_texts.get(contact.source_url, "")
        contact.confidence = score_contact(contact, page_text)
    return contacts

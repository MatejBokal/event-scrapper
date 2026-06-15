"""Validate extracted emails and deduplicate results."""

from __future__ import annotations

from backend.extractor import _evidence_snippet, _is_plausible_email, _normalize_email
from backend.models import ContactResult, RawEmailHit, SearchParams


def _email_in_text(email: str, text: str) -> bool:
    if not text:
        return False
    return email.lower() in text.lower()


def validate_hits(
    hits: list[RawEmailHit],
    params: SearchParams,
) -> list[ContactResult]:
    validated: list[ContactResult] = []
    seen: set[tuple[str, str]] = set()

    for hit in hits:
        email = _normalize_email(hit.email)
        if not _is_plausible_email(email):
            continue
        if not _email_in_text(email, hit.extracted_text):
            continue

        key = (email, hit.source_url)
        if key in seen:
            continue
        seen.add(key)

        snippet = _evidence_snippet(hit.extracted_text, email)
        if not snippet:
            continue

        validated.append(
            ContactResult(
                conference_name=hit.conference_name,
                conference_url=hit.conference_url,
                field=params.field,
                region=params.region,
                email=email,
                contact_type=hit.contact_type,
                source_url=hit.source_url,
                evidence_snippet=snippet,
                confidence=0,
                extraction_method=hit.extraction_method,
                page_title=hit.page_title,
            )
        )

    return validated

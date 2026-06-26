"""Rank organizer contacts and collapse to one lead per conference."""

from __future__ import annotations

import re

from backend.conference_metadata import enrich_lead_from_metadata, event_date_label
from backend.config import GENERIC_EMAIL_PREFIXES
from backend.models import ConferenceLlmMetadata, ContactResult, LeadResult, SearchParams

ORGANIZER_KEYWORDS = (
    "organizer",
    "organiser",
    "organizing",
    "organising",
    "event manager",
    "congress organiser",
    "congress organizer",
    "project manager",
    "direktor",
    "direktorica",
    "president",
    "chair",
    "pco",
    "kongres",
    "programme manager",
    "communications officer",
)

ROLE_EMAIL_PREFIXES = (
    "events@",
    "event@",
    "kongres@",
    "congress@",
    "organizer@",
    "organiser@",
    "office@",
)

NAME_PATTERN = re.compile(
    r"(?:^|[\n\r]|organizer|organiser|president|manager|chair|director|direktor)[:\s\-]*"
    r"([A-ZÀ-ÖØ-Þ][a-zà-ž]+(?:\s+[A-ZÀ-ÖØ-Þ][a-zà-ž]+){1,2})",
    re.IGNORECASE,
)

ROLE_PATTERN = re.compile(
    r"(?i)(organizer|organiser|event manager|congress organiser|congress organizer|"
    r"project manager|president|chair|direktor|programme manager|PCO)"
)


def _is_generic_email(email: str) -> bool:
    return any(email.startswith(prefix) for prefix in GENERIC_EMAIL_PREFIXES)


def _is_role_email(email: str) -> bool:
    return any(email.startswith(prefix) for prefix in ROLE_EMAIL_PREFIXES)


def _has_organizer_context(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in ORGANIZER_KEYWORDS)


def _extract_organizer_name(context: str) -> str | None:
    match = NAME_PATTERN.search(context)
    if match:
        name = match.group(1).strip()
        if len(name.split()) >= 2:
            return name
    return None


def _extract_organizer_role(context: str) -> str | None:
    match = ROLE_PATTERN.search(context)
    if match:
        return match.group(1).strip()
    return None


def classify_contact_quality(
    email: str,
    context: str,
    organizer_name: str | None,
) -> str:
    if organizer_name and _has_organizer_context(context):
        return "named_organizer"
    if _is_role_email(email) or (_has_organizer_context(context) and not _is_generic_email(email)):
        return "role_email"
    if _is_generic_email(email):
        return "generic_info"
    if _has_organizer_context(context):
        return "role_email"
    return "unknown"


def _contact_priority(lead: LeadResult) -> tuple[int, int, int]:
    quality_rank = {
        "named_organizer": 4,
        "role_email": 3,
        "unknown": 2,
        "generic_info": 1,
    }
    organizer_page = 1 if "organ" in lead.source_url.lower() or "contact" in lead.source_url.lower() else 0
    return (
        quality_rank.get(lead.contact_quality, 0),
        lead.confidence,
        organizer_page,
    )


def _should_skip_for_organizer_focus(contact: ContactResult) -> bool:
    path = contact.source_url.lower()
    if any(marker in path for marker in ("/sponsor", "/exhibitor", "/cfp", "/abstract")):
        if contact.contact_type not in ("organizer", "committee", "unknown"):
            return True
    return False


def build_leads(
    contacts: list[ContactResult],
    params: SearchParams,
    conference_metadata: dict[str, ConferenceLlmMetadata] | None = None,
) -> list[LeadResult]:
    metadata_by_url = conference_metadata or {}
    grouped: dict[str, list[ContactResult]] = {}
    for contact in contacts:
        if params.contact_type == "organizer" and _should_skip_for_organizer_focus(contact):
            continue
        grouped.setdefault(contact.conference_url.rstrip("/"), []).append(contact)

    leads: list[LeadResult] = []
    for conference_url, conference_contacts in grouped.items():
        meta = metadata_by_url.get(conference_url.rstrip("/"))
        candidates: list[LeadResult] = []
        for contact in conference_contacts:
            context = contact.evidence_snippet
            organizer_name = contact.organizer_name or _extract_organizer_name(context)
            organizer_role = contact.organizer_role or _extract_organizer_role(context)
            contact_quality = classify_contact_quality(contact.email, context, organizer_name)

            candidates.append(
                LeadResult(
                    conference_name=contact.conference_name or (meta.name if meta else None),
                    conference_url=contact.conference_url,
                    event_date=event_date_label(meta),
                    location=meta.location if meta else None,
                    field=contact.field,
                    region=contact.region,
                    organizer_name=organizer_name,
                    organizer_email=contact.email,
                    organizer_role=organizer_role,
                    contact_quality=contact_quality,
                    source_url=contact.source_url,
                    evidence_snippet=contact.evidence_snippet,
                    confidence=contact.confidence,
                    language=meta.language if meta else None,
                )
            )

        if not candidates:
            continue

        best = max(candidates, key=_contact_priority)
        leads.append(enrich_lead_from_metadata(best, meta))

    leads.sort(key=lambda lead: _contact_priority(lead), reverse=True)
    return leads

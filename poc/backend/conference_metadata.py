"""Apply LLM-parsed conference metadata to stored records and lead rows."""

from __future__ import annotations

from backend.models import ConferenceLlmMetadata, ContactResult, LeadResult


def event_date_label(metadata: ConferenceLlmMetadata | None) -> str | None:
    if metadata is None:
        return None
    if metadata.start_date:
        if metadata.end_date and metadata.end_date != metadata.start_date:
            return f"{metadata.start_date.isoformat()} – {metadata.end_date.isoformat()}"
        return metadata.start_date.isoformat()
    return metadata.month_year


def enrich_lead_from_metadata(lead: LeadResult, metadata: ConferenceLlmMetadata | None) -> LeadResult:
    if metadata is None:
        return lead
    if metadata.name:
        lead.conference_name = metadata.name
    if metadata.location:
        lead.location = metadata.location
    if metadata.language:
        lead.language = metadata.language
    event_date = event_date_label(metadata)
    if event_date:
        lead.event_date = event_date
    return lead


def enrich_contact_from_metadata(
    contact: ContactResult,
    metadata: ConferenceLlmMetadata | None,
) -> ContactResult:
    if metadata is None:
        return contact
    if metadata.name:
        contact.conference_name = metadata.name
    return contact

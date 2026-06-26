from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, joinedload

from app.models import Conference, CrawledPage, Organizer, SearchRun, SourceEvidence
from app.services.poc_bridge import (
    CrawledPage as PocCrawledPage,
    SearchParams,
    apply_confidence,
    build_leads,
    classify_contact_quality,
    extract_emails_from_pages,
    get_conference_name,
    is_listing_domain,
    is_llm_extraction_enabled,
    validate_hits,
)
from app.utils import normalize_official_url

EVIDENCE_SNIPPET_MAX = 500


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _apply_conference_metadata(conference: Conference, metadata) -> None:
    if metadata is None:
        return
    if metadata.name:
        conference.name = metadata.name
    if metadata.start_date:
        conference.start_date = metadata.start_date
    if metadata.end_date:
        conference.end_date = metadata.end_date
    if metadata.month_year:
        conference.month_year = metadata.month_year
    if metadata.location:
        conference.location = metadata.location
    if metadata.country:
        conference.country = metadata.country
    if metadata.description:
        conference.description = metadata.description
    if metadata.language:
        conference.language = metadata.language


def _db_page_to_poc(page: CrawledPage, conference_url: str) -> PocCrawledPage:
    return PocCrawledPage(
        url=page.url,
        title=page.title or "",
        page_type=page.page_type or "",
        extracted_text=page.extracted_text or "",
        conference_url=conference_url,
        html="",
    )


def _persist_organizer(
    db: Session,
    run: SearchRun,
    conference: Conference,
    contact,
    *,
    contact_quality: str | None,
    is_primary: bool,
) -> Organizer:
    organizer = Organizer(
        id=uuid.uuid4(),
        conference_id=conference.id,
        search_run_id=run.id,
        name=getattr(contact, "organizer_name", None),
        role=getattr(contact, "organizer_role", None),
        organization=getattr(contact, "organization", None),
        phone=getattr(contact, "phone", None),
        website=getattr(contact, "website", None),
        linkedin_url=getattr(contact, "linkedin_url", None),
        email=contact.email.strip().lower(),
        contact_type=contact.contact_type,
        contact_quality=contact_quality,
        is_primary_lead=is_primary,
        confidence_score=contact.confidence,
        extraction_method=contact.extraction_method,
    )
    db.add(organizer)
    db.flush()
    return organizer


def _persist_organizer_evidence(
    db: Session,
    run: SearchRun,
    conference: Conference,
    organizer: Organizer,
    contact,
) -> None:
    snippet = (contact.evidence_snippet or "")[:EVIDENCE_SNIPPET_MAX].strip()
    if not snippet:
        return
    db.add(
        SourceEvidence(
            id=uuid.uuid4(),
            conference_id=conference.id,
            organizer_id=organizer.id,
            search_run_id=run.id,
            source_url=contact.source_url,
            source_title=contact.page_title,
            extracted_text_snippet=snippet,
            evidence_type="email_extraction",
        )
    )


def execute_extract_run(db: Session, run: SearchRun) -> SearchRun:
    run = db.scalar(
        select(SearchRun).where(SearchRun.id == run.id).options(joinedload(SearchRun.results))
    )
    if run is None:
        raise ValueError("Search run not found")

    pages = list(
        db.scalars(select(CrawledPage).where(CrawledPage.search_run_id == run.id)).all()
    )
    if not pages:
        raise ValueError("Search run has no crawled pages — run crawl first")

    params = SearchParams(
        field=run.field,
        region=run.region,
        selected_months=tuple(run.selected_months),
        contact_type=run.contact_type,
        max_conferences=run.max_conferences,
        manual_official_url=run.manual_official_url or "",
    )

    errors = list(run.errors or [])
    run.status = "running"
    db.commit()
    db.refresh(run)

    db.execute(delete(Organizer).where(Organizer.search_run_id == run.id))

    pages_by_conference: dict[uuid.UUID, list[CrawledPage]] = {}
    for page in pages:
        pages_by_conference.setdefault(page.conference_id, []).append(page)

    all_contacts = []
    organizers_by_key: dict[tuple[uuid.UUID, str], Organizer] = {}
    conference_metadata_by_url: dict[str, object] = {}

    for conference_id, conference_pages in pages_by_conference.items():
        conference = db.get(Conference, conference_id)
        if conference is None:
            continue

        poc_pages = [_db_page_to_poc(page, conference.official_url) for page in conference_pages]
        conference_name = get_conference_name(poc_pages) or conference.name

        extract_result = extract_emails_from_pages(poc_pages, params, conference_name)
        if extract_result.conference_metadata:
            conference_metadata_by_url[conference.official_url.rstrip("/")] = (
                extract_result.conference_metadata
            )
            _apply_conference_metadata(conference, extract_result.conference_metadata)

        raw_hits = extract_result.hits
        contacts = validate_hits(raw_hits, params)
        contacts = [
            contact
            for contact in contacts
            if not is_listing_domain(contact.conference_url)
            and not is_listing_domain(contact.source_url)
        ]

        page_texts = {page.url: page.extracted_text or "" for page in poc_pages}
        contacts = apply_confidence(contacts, page_texts)
        all_contacts.extend(contacts)

        for contact in contacts:
            quality = classify_contact_quality(
                contact.email,
                contact.evidence_snippet,
                contact.organizer_name,
            )
            organizer = _persist_organizer(
                db,
                run,
                conference,
                contact,
                contact_quality=quality,
                is_primary=False,
            )
            _persist_organizer_evidence(db, run, conference, organizer, contact)
            organizers_by_key[(conference_id, contact.email.strip().lower())] = organizer

    leads = build_leads(all_contacts, params, conference_metadata_by_url)
    leads_persisted = 0

    for lead in leads:
        try:
            normalized = normalize_official_url(lead.conference_url)
        except ValueError:
            errors.append(f"Invalid lead conference URL: {lead.conference_url}")
            continue

        conference = db.scalar(
            select(Conference).where(Conference.official_url_normalized == normalized)
        )
        if conference is None:
            continue

        organizer = organizers_by_key.get((conference.id, lead.organizer_email.strip().lower()))
        if organizer is None:
            continue

        organizer.is_primary_lead = True
        organizer.name = lead.organizer_name
        organizer.role = lead.organizer_role
        organizer.contact_quality = lead.contact_quality
        organizer.confidence_score = lead.confidence
        conference.status = "extracted"
        conference.confidence_score = lead.confidence
        if lead.conference_name:
            conference.name = lead.conference_name
        leads_persisted += 1

    stats = dict(run.stats or {})
    stats.update(
        {
            "emails_found": len(all_contacts),
            "leads_found": len(leads),
            "primary_leads_persisted": leads_persisted,
            "llm_extraction_enabled": is_llm_extraction_enabled(),
        }
    )

    run.stats = stats
    run.errors = errors
    run.status = "failed" if leads_persisted == 0 and not all_contacts else "completed"
    run.finished_at = _utcnow()
    db.commit()
    db.refresh(run)
    return run

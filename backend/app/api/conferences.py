import uuid

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Conference, CrawledPage, Organizer, SourceEvidence
from app.schemas.conference import (
    ConferenceCreate,
    ConferenceDetail,
    ConferenceRead,
    ConferenceUpdate,
    CrawledPageSummary,
    EvidenceCreate,
    EvidenceRead,
    OrganizerCreate,
    OrganizerRead,
    OrganizerUpdate,
)
from app.utils import normalize_official_url

router = APIRouter(prefix="/conferences", tags=["conferences"])


def _get_conference_or_404(db: Session, conference_id: uuid.UUID) -> Conference:
    conference = db.get(Conference, conference_id)
    if conference is None:
        raise HTTPException(status_code=404, detail="Conference not found")
    return conference


@router.get("", response_model=list[ConferenceRead])
def list_conferences(
    field: str | None = None,
    region: str | None = None,
    status: str | None = None,
    has_email: bool | None = None,
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
) -> list[Conference]:
    query = select(Conference).order_by(Conference.created_at.desc()).limit(limit)
    if field:
        query = query.where(Conference.field == field)
    if region:
        query = query.where(Conference.region == region)
    if status:
        query = query.where(Conference.status == status)
    if has_email is True:
        query = query.where(
            Conference.id.in_(
                select(Organizer.conference_id).where(Organizer.is_primary_lead.is_(True))
            )
        )
    elif has_email is False:
        query = query.where(
            ~Conference.id.in_(
                select(Organizer.conference_id).where(Organizer.is_primary_lead.is_(True))
            )
        )
    return list(db.scalars(query).all())


@router.post("", response_model=ConferenceRead, status_code=201)
def create_conference(payload: ConferenceCreate, db: Session = Depends(get_db)) -> Conference:
    try:
        normalized = normalize_official_url(payload.official_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    conference = Conference(
        id=uuid.uuid4(),
        name=payload.name,
        field=payload.field,
        region=payload.region,
        start_date=payload.start_date,
        end_date=payload.end_date,
        month_year=payload.month_year,
        location=payload.location,
        country=payload.country,
        official_url=payload.official_url.strip(),
        official_url_normalized=normalized,
        description=payload.description,
        status=payload.status,
        confidence_score=payload.confidence_score,
    )
    db.add(conference)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Conference with this official URL already exists") from exc
    db.refresh(conference)
    return conference


def _crawled_page_summaries(db: Session, conference_id: uuid.UUID) -> list[CrawledPageSummary]:
    pages = db.scalars(
        select(CrawledPage)
        .where(CrawledPage.conference_id == conference_id)
        .order_by(CrawledPage.crawled_at.desc())
    ).all()
    return [
        CrawledPageSummary(
            id=page.id,
            url=page.url,
            title=page.title,
            page_type=page.page_type,
            text_length=len(page.extracted_text or ""),
            crawled_at=page.crawled_at,
        )
        for page in pages
    ]


@router.get("/{conference_id}", response_model=ConferenceDetail)
def get_conference(conference_id: uuid.UUID, db: Session = Depends(get_db)) -> ConferenceDetail:
    conference = db.scalar(
        select(Conference)
        .where(Conference.id == conference_id)
        .options(joinedload(Conference.organizers), joinedload(Conference.evidence))
    )
    if conference is None:
        raise HTTPException(status_code=404, detail="Conference not found")
    return ConferenceDetail(
        id=conference.id,
        name=conference.name,
        field=conference.field,
        region=conference.region,
        start_date=conference.start_date,
        end_date=conference.end_date,
        month_year=conference.month_year,
        location=conference.location,
        country=conference.country,
        language=conference.language,
        official_url=conference.official_url,
        official_url_normalized=conference.official_url_normalized,
        description=conference.description,
        status=conference.status,
        confidence_score=conference.confidence_score,
        crawl_block_reason=conference.crawl_block_reason,
        crawl_http_status=conference.crawl_http_status,
        crawl_block_detail=conference.crawl_block_detail,
        crawl_blocked_at=conference.crawl_blocked_at,
        created_at=conference.created_at,
        updated_at=conference.updated_at,
        organizers=conference.organizers,
        evidence=conference.evidence,
        crawled_pages=_crawled_page_summaries(db, conference_id),
    )


@router.patch("/{conference_id}", response_model=ConferenceRead)
def update_conference(
    conference_id: uuid.UUID,
    payload: ConferenceUpdate,
    db: Session = Depends(get_db),
) -> Conference:
    conference = _get_conference_or_404(db, conference_id)
    data = payload.model_dump(exclude_unset=True)

    if "official_url" in data and data["official_url"] is not None:
        try:
            conference.official_url = data["official_url"].strip()
            conference.official_url_normalized = normalize_official_url(data["official_url"])
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        del data["official_url"]

    for key, value in data.items():
        setattr(conference, key, value)

    if conference.status != "crawl_blocked":
        conference.crawl_block_reason = None
        conference.crawl_http_status = None
        conference.crawl_block_detail = None
        conference.crawl_blocked_at = None
    elif data.get("status") == "crawl_blocked" and conference.crawl_blocked_at is None:
        conference.crawl_blocked_at = datetime.now(timezone.utc)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Conference URL conflicts with existing record") from exc
    db.refresh(conference)
    return conference


def _add_evidence(
    db: Session,
    conference_id: uuid.UUID,
    organizer_id: uuid.UUID,
    payload: EvidenceCreate,
) -> SourceEvidence:
    evidence = SourceEvidence(
        id=uuid.uuid4(),
        conference_id=conference_id,
        organizer_id=organizer_id,
        source_url=payload.source_url.strip(),
        source_title=payload.source_title,
        extracted_text_snippet=payload.extracted_text_snippet.strip(),
        evidence_type=payload.evidence_type,
    )
    db.add(evidence)
    return evidence


@router.post("/{conference_id}/retry-crawl", response_model=ConferenceRead)
def retry_crawl_conference(conference_id: uuid.UUID, db: Session = Depends(get_db)) -> Conference:
    """Clear crawl block so the site is eligible for automated crawl on the next run."""
    conference = _get_conference_or_404(db, conference_id)
    conference.status = "discovered"
    conference.crawl_block_reason = None
    conference.crawl_http_status = None
    conference.crawl_block_detail = None
    conference.crawl_blocked_at = None
    db.commit()
    db.refresh(conference)
    return conference


@router.get("/{conference_id}/organizers", response_model=list[OrganizerRead])
def list_conference_organizers(
    conference_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> list[Organizer]:
    _get_conference_or_404(db, conference_id)
    return list(
        db.scalars(
            select(Organizer)
            .where(Organizer.conference_id == conference_id)
            .order_by(Organizer.is_primary_lead.desc(), Organizer.created_at.desc())
        ).all()
    )


@router.post("/{conference_id}/organizers", response_model=OrganizerRead, status_code=201)
def create_conference_organizer(
    conference_id: uuid.UUID,
    payload: OrganizerCreate,
    db: Session = Depends(get_db),
) -> Organizer:
    if payload.conference_id != conference_id:
        raise HTTPException(status_code=400, detail="conference_id in body must match URL")

    _get_conference_or_404(db, conference_id)

    if payload.is_primary_lead:
        for existing in db.scalars(
            select(Organizer).where(
                Organizer.conference_id == conference_id,
                Organizer.is_primary_lead.is_(True),
            )
        ).all():
            existing.is_primary_lead = False

    organizer = Organizer(
        id=uuid.uuid4(),
        conference_id=conference_id,
        name=payload.name,
        organization=payload.organization,
        role=payload.role,
        email=payload.email.strip().lower(),
        phone=payload.phone,
        website=payload.website,
        linkedin_url=payload.linkedin_url,
        contact_type=payload.contact_type,
        contact_quality=payload.contact_quality,
        is_primary_lead=payload.is_primary_lead,
        confidence_score=payload.confidence_score,
        extraction_method=payload.extraction_method,
    )
    db.add(organizer)
    db.flush()
    _add_evidence(db, conference_id, organizer.id, payload.evidence)
    db.commit()
    db.refresh(organizer)
    return organizer


@router.get("/{conference_id}/evidence", response_model=list[EvidenceRead])
def list_conference_evidence(
    conference_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> list[SourceEvidence]:
    _get_conference_or_404(db, conference_id)
    return list(
        db.scalars(
            select(SourceEvidence)
            .where(SourceEvidence.conference_id == conference_id)
            .order_by(SourceEvidence.extraction_date.desc())
        ).all()
    )

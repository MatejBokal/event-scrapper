import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.conferences import _add_evidence, _get_conference_or_404
from app.database import get_db
from app.models import Organizer, SourceEvidence
from app.schemas.conference import EvidenceCreate, EvidenceRead, OrganizerCreate, OrganizerRead, OrganizerUpdate

router = APIRouter(prefix="/organizers", tags=["organizers"])


@router.get("", response_model=list[OrganizerRead])
def list_organizers(
    conference_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
) -> list[Organizer]:
    query = select(Organizer).order_by(Organizer.created_at.desc())
    if conference_id:
        query = query.where(Organizer.conference_id == conference_id)
    return list(db.scalars(query).all())


@router.post("", response_model=OrganizerRead, status_code=201)
def create_organizer(payload: OrganizerCreate, db: Session = Depends(get_db)) -> Organizer:
    _get_conference_or_404(db, payload.conference_id)

    if payload.is_primary_lead:
        for existing in db.scalars(
            select(Organizer).where(
                Organizer.conference_id == payload.conference_id,
                Organizer.is_primary_lead.is_(True),
            )
        ).all():
            existing.is_primary_lead = False

    organizer = Organizer(
        id=uuid.uuid4(),
        conference_id=payload.conference_id,
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
    _add_evidence(db, payload.conference_id, organizer.id, payload.evidence)
    db.commit()
    db.refresh(organizer)
    return organizer


@router.patch("/{organizer_id}", response_model=OrganizerRead)
def update_organizer(
    organizer_id: uuid.UUID,
    payload: OrganizerUpdate,
    db: Session = Depends(get_db),
) -> Organizer:
    organizer = db.get(Organizer, organizer_id)
    if organizer is None:
        raise HTTPException(status_code=404, detail="Organizer not found")

    data = payload.model_dump(exclude_unset=True)
    if data.get("is_primary_lead"):
        for existing in db.scalars(
            select(Organizer).where(
                Organizer.conference_id == organizer.conference_id,
                Organizer.is_primary_lead.is_(True),
                Organizer.id != organizer_id,
            )
        ).all():
            existing.is_primary_lead = False

    if "email" in data and data["email"] is not None:
        data["email"] = data["email"].strip().lower()

    for key, value in data.items():
        setattr(organizer, key, value)

    db.commit()
    db.refresh(organizer)
    return organizer


@router.post("/{organizer_id}/evidence", response_model=EvidenceRead, status_code=201)
def add_organizer_evidence(
    organizer_id: uuid.UUID,
    payload: EvidenceCreate,
    db: Session = Depends(get_db),
) -> SourceEvidence:
    organizer = db.get(Organizer, organizer_id)
    if organizer is None:
        raise HTTPException(status_code=404, detail="Organizer not found")

    evidence = _add_evidence(db, organizer.conference_id, organizer.id, payload)
    db.commit()
    db.refresh(evidence)
    return evidence

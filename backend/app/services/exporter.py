from __future__ import annotations

from datetime import datetime
from io import BytesIO

from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Conference, Organizer, SourceEvidence

LEAD_EXPORT_FIELDS = [
    "conference_name",
    "conference_url",
    "event_date",
    "location",
    "field",
    "region",
    "organizer_name",
    "organizer_email",
    "organizer_role",
    "contact_quality",
    "source_url",
    "evidence_snippet",
    "confidence",
    "language",
]


def _event_date_label(conference: Conference) -> str | None:
    if conference.start_date:
        return conference.start_date.isoformat()
    return conference.month_year


def _primary_evidence(
    organizer: Organizer,
    evidence_by_organizer: dict,
) -> SourceEvidence | None:
    items = evidence_by_organizer.get(organizer.id, [])
    return items[0] if items else None


def fetch_lead_rows(db: Session) -> list[dict]:
    conferences = db.scalars(
        select(Conference).options(joinedload(Conference.organizers)).order_by(Conference.created_at.desc())
    ).unique().all()

    organizer_ids = [
        org.id for conference in conferences for org in conference.organizers if org.is_primary_lead
    ]
    if not organizer_ids:
        organizer_ids = [
            org.id
            for conference in conferences
            for org in sorted(conference.organizers, key=lambda o: o.confidence_score, reverse=True)[:1]
        ]

    evidence_rows = db.scalars(
        select(SourceEvidence).where(SourceEvidence.organizer_id.in_(organizer_ids))
    ).all() if organizer_ids else []

    evidence_by_organizer: dict = {}
    for row in evidence_rows:
        evidence_by_organizer.setdefault(row.organizer_id, []).append(row)

    leads: list[dict] = []
    seen_conferences: set = set()

    for conference in conferences:
        if conference.id in seen_conferences:
            continue
        primary = next((o for o in conference.organizers if o.is_primary_lead), None)
        if primary is None and conference.organizers:
            primary = max(conference.organizers, key=lambda o: o.confidence_score)
        if primary is None:
            continue

        seen_conferences.add(conference.id)
        evidence = _primary_evidence(primary, evidence_by_organizer)

        leads.append(
            {
                "conference_name": conference.name,
                "conference_url": conference.official_url,
                "event_date": _event_date_label(conference),
                "location": conference.location,
                "field": conference.field,
                "region": conference.region,
                "organizer_name": primary.name,
                "organizer_email": primary.email,
                "organizer_role": primary.role,
                "contact_quality": primary.contact_quality,
                "source_url": evidence.source_url if evidence else None,
                "evidence_snippet": evidence.extracted_text_snippet if evidence else None,
                "confidence": primary.confidence_score,
                "language": conference.language,
            }
        )

    return leads


def leads_to_xlsx_bytes(rows: list[dict]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Leads"
    sheet.append(LEAD_EXPORT_FIELDS)
    for row in rows:
        sheet.append([row.get(field) for field in LEAD_EXPORT_FIELDS])
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def export_filename(extension: str) -> str:
    return f"confiva_leads_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{extension}"

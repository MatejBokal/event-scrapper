"""CSV, JSON, and Excel export helpers."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from io import BytesIO, StringIO
from typing import Any

from backend.models import ContactResult, LeadResult

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

CONTACT_EXPORT_FIELDS = [
    "conference_name",
    "conference_url",
    "field",
    "region",
    "email",
    "contact_type",
    "source_url",
    "evidence_snippet",
    "confidence",
    "extraction_method",
    "page_title",
]


def leads_to_records(leads: list[LeadResult]) -> list[dict[str, Any]]:
    return [lead.to_dict() for lead in leads]


def contacts_to_records(contacts: list[ContactResult]) -> list[dict[str, Any]]:
    return [contact.to_dict() for contact in contacts]


def leads_to_json_bytes(leads: list[LeadResult]) -> bytes:
    payload = leads_to_records(leads)
    return json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")


def leads_to_csv_bytes(leads: list[LeadResult]) -> bytes:
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=LEAD_EXPORT_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for record in leads_to_records(leads):
        writer.writerow(record)
    return buffer.getvalue().encode("utf-8-sig")


def leads_to_xlsx_bytes(leads: list[LeadResult]) -> bytes:
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Leads"
    sheet.append(LEAD_EXPORT_FIELDS)

    for record in leads_to_records(leads):
        sheet.append([record.get(field) for field in LEAD_EXPORT_FIELDS])

    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def contacts_to_json_bytes(contacts: list[ContactResult]) -> bytes:
    payload = contacts_to_records(contacts)
    return json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")


def contacts_to_csv_bytes(contacts: list[ContactResult]) -> bytes:
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CONTACT_EXPORT_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for record in contacts_to_records(contacts):
        writer.writerow(record)
    return buffer.getvalue().encode("utf-8-sig")


def export_filename(extension: str, prefix: str = "confiva_leads") -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{timestamp}.{extension}"

"""Dual-sheet export for bulk list generation (conferences + leads)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# XML 1.0 chars openpyxl rejects (same range as openpyxl.cell.cell.ILLEGAL_CHARACTERS_RE).
_ILLEGAL_EXCEL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

CONFERENCE_FIELDS = [
    "country",
    "city",
    "field",
    "months",
    "conference_name",
    "conference_url",
    "search_title",
    "url_score",
    "has_email",
    "source",
    "event_date",
    "venue_city",
]

LEAD_FIELDS = [
    "country",
    "city",
    "field",
    "months",
    "conference_name",
    "conference_url",
    "event_date",
    "location",
    "organizer_name",
    "organizer_email",
    "organizer_role",
    "contact_quality",
    "source_url",
    "evidence_snippet",
    "confidence",
    "language",
]


def _excel_cell_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _ILLEGAL_EXCEL_CHARS.sub("", str(value))


def write_workbook(
    output_path: Path,
    conferences: list[dict[str, Any]],
    leads: list[dict[str, Any]],
) -> None:
    from openpyxl import Workbook

    output_path.parent.mkdir(parents=True, exist_ok=True)

    workbook = Workbook()
    conf_sheet = workbook.active
    conf_sheet.title = "Conferences"
    conf_sheet.append(CONFERENCE_FIELDS)
    for row in conferences:
        conf_sheet.append([_excel_cell_value(row.get(field)) for field in CONFERENCE_FIELDS])

    lead_sheet = workbook.create_sheet("Leads")
    lead_sheet.append(LEAD_FIELDS)
    for row in leads:
        lead_sheet.append([_excel_cell_value(row.get(field)) for field in LEAD_FIELDS])

    workbook.save(output_path)


def read_workbook(output_path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    from openpyxl import load_workbook

    if not output_path.exists():
        return [], []

    workbook = load_workbook(output_path, read_only=True, data_only=True)
    conferences: list[dict[str, Any]] = []
    leads: list[dict[str, Any]] = []

    if "Conferences" in workbook.sheetnames:
        sheet = workbook["Conferences"]
        rows = sheet.iter_rows(values_only=True)
        headers = [str(cell) if cell is not None else "" for cell in next(rows, ())]
        for row in rows:
            conferences.append(
                {headers[i]: row[i] for i in range(len(headers)) if i < len(row)}
            )

    if "Leads" in workbook.sheetnames:
        sheet = workbook["Leads"]
        rows = sheet.iter_rows(values_only=True)
        headers = [str(cell) if cell is not None else "" for cell in next(rows, ())]
        for row in rows:
            leads.append(
                {headers[i]: row[i] for i in range(len(headers)) if i < len(row)}
            )

    workbook.close()
    return conferences, leads

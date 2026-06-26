"""Offline tests for LLM JSON parsing and hit validation (no API calls)."""

from __future__ import annotations

import sys
from pathlib import Path

POC_ROOT = Path(__file__).resolve().parents[1] / "poc"
sys.path.insert(0, str(POC_ROOT))

from backend.llm_extractor import (  # noqa: E402
    _organizers_to_hits,
    _parse_conference_metadata,
    _parse_json_content,
    select_llm_pages,
)
from backend.models import CrawledPage, RawEmailHit, SearchParams  # noqa: E402


def test_parse_json_strips_fences() -> None:
    raw = '```json\n{"organizers": []}\n```'
    assert _parse_json_content(raw) == {"organizers": []}


def test_organizers_to_hits_requires_email_in_text() -> None:
    page_text = "Contact the organizing committee at events@example.org for details."
    page = CrawledPage(
        url="https://conf.example.org/contact",
        title="Contact",
        page_type="contact",
        extracted_text=page_text,
        conference_url="https://conf.example.org/",
    )
    params = SearchParams(field="Healthcare", region="Slovenia", selected_months=("2026-06",))
    data = {
        "conference": {"name": "Example Conf"},
        "organizers": [
            {
                "source_url": "https://conf.example.org/contact",
                "name": "Jane Doe",
                "role": "Event Manager",
                "organization": "Confiva PCO",
                "email": "events@example.org",
                "contact_type": "organizer",
                "evidence_text": "events@example.org",
            },
            {
                "source_url": "https://conf.example.org/contact",
                "name": "Fake Person",
                "email": "fake@not-in-page.com",
                "evidence_text": "fake@not-in-page.com",
            },
        ],
    }
    hits = _organizers_to_hits(data, {page.url: page}, params, None)
    assert len(hits) == 1
    assert hits[0].email == "events@example.org"
    assert hits[0].organizer_name == "Jane Doe"
    assert hits[0].organization == "Confiva PCO"
    assert hits[0].extraction_method == "llm"


def test_parse_conference_metadata_from_combined_text() -> None:
    combined = (
        "International Healthcare Congress 2026\n"
        "15–17 June 2026 in Ljubljana, Slovenia\n"
        "English conference website"
    )
    data = {
        "conference": {
            "name": "International Healthcare Congress 2026",
            "start_date": "2026-06-15",
            "end_date": "2026-06-17",
            "location": "Ljubljana",
            "country": "Slovenia",
            "language": "en",
        }
    }
    meta = _parse_conference_metadata(data, combined, None)
    assert meta is not None
    assert meta.name == "International Healthcare Congress 2026"
    assert meta.location == "Ljubljana"
    assert meta.country == "Slovenia"
    assert meta.language == "en"
    assert meta.month_year == "2026-06"


def test_select_llm_pages_prefers_contact_over_sponsors() -> None:
    params = SearchParams(field="Healthcare", region="Slovenia", selected_months=("2026-06",))
    text = (
        "Organizing committee contact details for the congress. "
        "Reach the event manager team for registration and programme questions."
    ) * 3
    pages = [
        CrawledPage(
            url="https://conf.example.org/sponsors",
            title="Sponsors",
            page_type="sponsors",
            extracted_text=text,
            conference_url="https://conf.example.org/",
        ),
        CrawledPage(
            url="https://conf.example.org/contact",
            title="Contact",
            page_type="contact",
            extracted_text=text,
            conference_url="https://conf.example.org/",
        ),
        CrawledPage(
            url="https://conf.example.org/program",
            title="Program",
            page_type="other",
            extracted_text="Schedule of talks and sessions only.",
            conference_url="https://conf.example.org/",
        ),
    ]
    selected = select_llm_pages(pages, [], params)
    assert len(selected) == 1
    assert selected[0].url.endswith("/contact")


def test_select_llm_pages_skips_when_regex_already_found_enough() -> None:
    params = SearchParams(field="Healthcare", region="Slovenia", selected_months=("2026-06",))
    page = CrawledPage(
        url="https://conf.example.org/program",
        title="Program",
        page_type="program",
        extracted_text="Schedule of talks and sessions only." * 20,
        conference_url="https://conf.example.org/",
    )
    regex_hits = [
        RawEmailHit(
            email="info@conf.example.org",
            source_url="https://conf.example.org/contact",
            page_title="Contact",
            extracted_text="info@conf.example.org",
            extraction_method="mailto",
            contact_type="organizer",
            conference_url="https://conf.example.org/",
        )
    ]
    assert select_llm_pages([page], regex_hits, params) == []


if __name__ == "__main__":
    test_parse_json_strips_fences()
    test_organizers_to_hits_requires_email_in_text()
    test_parse_conference_metadata_from_combined_text()
    test_select_llm_pages_prefers_contact_over_sponsors()
    test_select_llm_pages_skips_when_regex_already_found_enough()
    print("OK")

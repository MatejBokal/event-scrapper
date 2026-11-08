"""Unit tests for event date + city hard gate."""

from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "poc"))

from backend.event_presence import (  # noqa: E402
    assess_event_presence,
    extract_dates_from_text,
    extract_from_json_ld,
    extract_times_from_text,
    match_city_allowlist,
)
from backend.models import CrawledPage  # noqa: E402
from listgen.country_data import get_cities, get_city_allowlist  # noqa: E402


class EventPresenceTests(unittest.TestCase):
    def test_extract_iso_and_textual_dates(self) -> None:
        text = "Join us on 15 September 2026 in Zurich. Also 2026-10-03."
        dates = extract_dates_from_text(text)
        self.assertIn(date(2026, 9, 15), dates)
        self.assertIn(date(2026, 10, 3), dates)

    def test_year_only_is_not_enough(self) -> None:
        self.assertEqual(extract_dates_from_text("Conference 2026 in Basel"), [])

    def test_json_ld_event(self) -> None:
        html = """
        <html><head>
        <script type="application/ld+json">
        {
          "@type": "Event",
          "name": "Swiss AI Summit",
          "startDate": "2026-11-12T09:00:00+01:00",
          "location": {"@type": "Place", "address": {"addressLocality": "Bern"}}
        }
        </script>
        </head><body></body></html>
        """
        dates, locations, has_time = extract_from_json_ld(html)
        self.assertEqual(dates, [date(2026, 11, 12)])
        self.assertTrue(any("Bern" in loc for loc in locations))
        self.assertTrue(has_time)

    def test_time_detection(self) -> None:
        self.assertTrue(extract_times_from_text("Doors open 09:00"))
        self.assertTrue(extract_times_from_text("Starts at 9:30 a.m."))
        self.assertFalse(extract_times_from_text("Version 2026.10 release notes"))

    def test_city_allowlist_aliases(self) -> None:
        cities = ["Zurich", "Zürich", "Geneva", "Basel"]
        self.assertEqual(match_city_allowlist("Welcome to Zürich 2026", cities), "Zürich")
        self.assertIsNone(match_city_allowlist("Private chauffeur service", cities))

    def test_hard_gate_requires_both(self) -> None:
        allow = ["Zurich", "Basel", "Bern"]
        pages = [
            CrawledPage(
                url="https://example.com/conf",
                title="AI Summit",
                page_type="home",
                extracted_text="The AI Summit takes place on 20 October 2026 in Zurich.",
                conference_url="https://example.com/conf",
                html="",
            )
        ]
        ok = assess_event_presence(pages, allow)
        self.assertTrue(ok.passes)
        self.assertEqual(ok.event_date, date(2026, 10, 20))
        self.assertEqual(ok.matched_city, "Zurich")
        self.assertFalse(ok.has_time)

        no_date = [
            CrawledPage(
                url="https://example.com/about",
                title="About us Zurich",
                page_type="about",
                extracted_text="We are based in Zurich and love events.",
                conference_url="https://example.com/about",
            )
        ]
        bad = assess_event_presence(no_date, allow)
        self.assertFalse(bad.passes)
        self.assertEqual(bad.reason, "missing_date")

        no_city = [
            CrawledPage(
                url="https://example.com/berlin",
                title="Security Essen",
                page_type="home",
                extracted_text="Security fair on 12 November 2026 in Essen.",
                conference_url="https://example.com/berlin",
            )
        ]
        bad2 = assess_event_presence(no_city, allow)
        self.assertFalse(bad2.passes)
        self.assertEqual(bad2.reason, "missing_city")

    def test_date_and_time_can_be_on_different_pages(self) -> None:
        allow = ["Zurich", "Basel"]
        pages = [
            CrawledPage(
                url="https://example.com/",
                title="Home",
                page_type="home",
                extracted_text="Welcome to our conference in Zurich.",
                conference_url="https://example.com/",
            ),
            CrawledPage(
                url="https://example.com/agenda",
                title="Agenda",
                page_type="agenda",
                extracted_text="Day 1 — 14 September 2026. Opening at 09:30.",
                conference_url="https://example.com/",
            ),
            CrawledPage(
                url="https://example.com/contact",
                title="Contact",
                page_type="contact",
                extracted_text="Organizer: events@example.com",
                conference_url="https://example.com/",
            ),
        ]
        presence = assess_event_presence(pages, allow)
        self.assertTrue(presence.passes)
        self.assertEqual(presence.event_date, date(2026, 9, 14))
        self.assertEqual(presence.matched_city, "Zurich")
        self.assertTrue(presence.has_time)

    def test_switzerland_allowlist_expanded(self) -> None:
        search_cities = get_cities("Switzerland")
        allow = get_city_allowlist("Switzerland")
        self.assertEqual(len(search_cities), 10)
        self.assertGreater(len(allow), 40)
        self.assertTrue({"Davos", "Zermatt", "Zürich"} <= set(allow))


if __name__ == "__main__":
    unittest.main()

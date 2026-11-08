"""Tests for hopeless URL prefilter and event keyword gate."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "poc"))

from backend.event_keyword_gate import (  # noqa: E402
    assess_keyword_gate,
    site_root_url,
    text_has_event_keyword,
)
from backend.event_keywords import event_keywords_for_region  # noqa: E402
from backend.models import CrawledPage  # noqa: E402
from backend.url_prefilter import classify_hopeless_url  # noqa: E402
from listgen.country_data import get_event_keywords  # noqa: E402
from listgen.skip_log import SkipLog  # noqa: E402


class UrlPrefilterTests(unittest.TestCase):
    def test_hopeless_hosts_and_schemes(self) -> None:
        self.assertEqual(classify_hopeless_url("https://api.whatsapp.com/send?phone=1"), "hopeless_host")
        self.assertEqual(classify_hopeless_url("https://t.me/share/url"), "hopeless_host")
        self.assertEqual(
            classify_hopeless_url("https://calendar.google.com/calendar/event"),
            "hopeless_host",
        )
        self.assertEqual(classify_hopeless_url("mailto:a@b.com"), "hopeless_scheme")

    def test_hopeless_path_and_file(self) -> None:
        self.assertEqual(classify_hopeless_url("https://example.ch/blog/post"), "hopeless_path")
        self.assertEqual(classify_hopeless_url("https://example.ch/jobs/open"), "hopeless_path")
        self.assertEqual(classify_hopeless_url("https://example.ch/agenda.pdf"), "hopeless_file")
        self.assertIsNone(classify_hopeless_url("https://cloudnativeday.ch/"))


class KeywordGateTests(unittest.TestCase):
    def test_site_root(self) -> None:
        self.assertEqual(site_root_url("https://example.ch/events/ai"), "https://example.ch/")

    def test_language_pack_includes_en_and_native(self) -> None:
        keywords = get_event_keywords("Switzerland")
        folded = {k.casefold() for k in keywords}
        self.assertIn("conference", folded)
        self.assertTrue({"konferenz", "kongress", "congrès", "congress"} & folded)

    def test_keyword_or_json_ld(self) -> None:
        keywords = event_keywords_for_region("Switzerland")
        bare = [
            CrawledPage(
                url="https://corp.ch/",
                title="About us",
                page_type="home",
                extracted_text="We sell software in Zurich.",
                conference_url="https://corp.ch/",
                html="<html><body>We sell software</body></html>",
            )
        ]
        self.assertFalse(assess_keyword_gate(bare, keywords).passes)

        with_keyword = [
            CrawledPage(
                url="https://corp.ch/",
                title="Home",
                page_type="home",
                extracted_text="Welcome",
                conference_url="https://corp.ch/",
            ),
            CrawledPage(
                url="https://corp.ch/events/ai",
                title="AI Konferenz 2026",
                page_type="event",
                extracted_text="Join our Konferenz in Basel.",
                conference_url="https://corp.ch/events/ai",
            ),
        ]
        ok = assess_keyword_gate(with_keyword, keywords)
        self.assertTrue(ok.passes)
        self.assertEqual(ok.reason, "ok_keyword")

        json_ld = [
            CrawledPage(
                url="https://corp.ch/x",
                title="X",
                page_type="home",
                extracted_text="Welcome to our company",
                conference_url="https://corp.ch/x",
                html="""
                <script type="application/ld+json">
                {"@type":"Event","name":"Secret","startDate":"2026-11-01"}
                </script>
                """,
            )
        ]
        jd = assess_keyword_gate(json_ld, keywords)
        self.assertTrue(jd.passes)
        self.assertTrue(jd.via_json_ld)

    def test_word_boundary(self) -> None:
        self.assertIsNone(text_has_event_keyword("preventative care", ["event"]))
        self.assertEqual(text_has_event_keyword("annual event in Bern", ["event"]), "event")


class SkipLogTests(unittest.TestCase):
    def test_append_and_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "skip.jsonl"
            log = SkipLog(path, run_id="test")
            log.log(stage="queue_skip", decision="dont_crawl", reason="hopeless_host", url="https://t.me/x")
            log.log(stage="keyword_gate", decision="dont_crawl", reason="missing_event_keyword", url="https://a.ch/")
            self.assertTrue(path.exists())
            lines = path.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 2)
            summary = "\n".join(log.summary_lines())
            self.assertIn("queue_skip/hopeless_host", summary)


if __name__ == "__main__":
    unittest.main()

"""Tests for same-run domain memory / one URL per domain."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "poc"))

from backend.models import SelectedSite  # noqa: E402
from listgen.domain_memory import DomainMemory, looks_like_mill_or_listing  # noqa: E402
from listgen.links_export import DedupedCrawlTarget, TaskContext, build_crawl_queue  # noqa: E402


class DomainMemoryTests(unittest.TestCase):
    def test_mill_pattern(self) -> None:
        self.assertTrue(looks_like_mill_or_listing("http://biofora.org/Conference/10682/ICC"))
        self.assertTrue(looks_like_mill_or_listing("https://swiss-congress.ch/conferences/ilmac"))
        self.assertFalse(looks_like_mill_or_listing("https://cloudnativeday.ch/"))

    def test_same_run_skips_second_url_on_domain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            memory = DomainMemory(Path(tmp) / "denylist.json")
            first = "https://example-conf.ch/ai-2026"
            second = "https://example-conf.ch/contact"
            self.assertIsNone(memory.should_skip(first))
            memory.mark_crawled(first)
            reason = memory.should_skip(second)
            self.assertIsNotNone(reason)
            self.assertEqual(reason, "domain_already_crawled")

    def test_presence_fail_denylists_for_future(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "denylist.json"
            memory = DomainMemory(path)
            memory.deny("https://junk.ch/page", reason="missing_date")
            self.assertTrue(path.exists())
            again = DomainMemory(path)
            self.assertTrue(again.is_denied("https://www.junk.ch/other"))

    def test_queue_keeps_best_url_per_domain(self) -> None:
        ctx = TaskContext(
            country="Switzerland",
            city="Zurich",
            field="AI",
            months_label="2026-09",
            selected_months=("2026-09",),
            task_key="Switzerland|Zurich|AI|2026-09",
            region_name="Switzerland",
        )
        rows = [
            {
                "link_type": "crawl_target",
                "crawl_status": "pending",
                "url": "https://event.ch/weak",
                "title": "weak",
                "snippet": "",
                "url_score": "20",
                "found_in_tasks": ctx.task_key,
                "parent_url": "",
            },
            {
                "link_type": "crawl_target",
                "crawl_status": "pending",
                "url": "https://event.ch/strong",
                "title": "strong",
                "snippet": "",
                "url_score": "90",
                "found_in_tasks": ctx.task_key,
                "parent_url": "",
            },
            {
                "link_type": "crawl_target",
                "crawl_status": "pending",
                "url": "https://other.ch/only",
                "title": "other",
                "snippet": "",
                "url_score": "50",
                "found_in_tasks": ctx.task_key,
                "parent_url": "",
            },
        ]
        queue = build_crawl_queue(rows, {ctx.task_key: ctx}, one_url_per_domain=True)
        urls = {item.site.url for item in queue}
        self.assertEqual(urls, {"https://event.ch/strong", "https://other.ch/only"})


if __name__ == "__main__":
    unittest.main()

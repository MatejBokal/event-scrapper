#!/usr/bin/env python3
"""Phase 5 smoke test: full pipeline execute + export."""

from __future__ import annotations

import sys

import httpx

BASE = "http://127.0.0.1:8001"


def main() -> int:
    with httpx.Client(base_url=BASE, timeout=900.0) as client:
        print("Creating search run (search only)...")
        create = client.post(
            "/api/search-runs",
            json={
                "field": "Healthcare",
                "region": "Slovenia",
                "selected_months": ["2026-06"],
                "max_conferences": 3,
                "manual_official_url": "https://www.slo-heart.org/simpozij/attr-cm-ljubljana-2026",
                "execute_search": True,
                "execute_crawl": False,
                "execute_extract": False,
            },
        )
        if create.status_code != 201:
            print(f"FAIL: create -> {create.status_code} {create.text}")
            return 1

        run_id = create.json()["id"]
        hits = create.json().get("stats", {}).get("search_hits", 0)
        print(f"OK: search run {run_id} with {hits} hits")

        if hits < 1:
            print("FAIL: no search hits to continue pipeline")
            return 1

        print("Executing full pipeline (crawl + extract, may take several minutes)...")
        execute = client.post(f"/api/search-runs/{run_id}/execute")
        if execute.status_code != 200:
            print(f"FAIL: execute -> {execute.status_code} {execute.text}")
            return 1

        body = execute.json()
        stats = body.get("stats", {})
        print(
            f"OK: execute status={body['status']} "
            f"pages={stats.get('pages_crawled', 0)} "
            f"emails={stats.get('emails_found', 0)} "
            f"leads={stats.get('primary_leads_persisted', 0)}"
        )

        if stats.get("pages_crawled", 0) < 1:
            print("FAIL: no pages crawled")
            return 1

        print("Checking export endpoint...")
        export = client.get("/api/export/leads.xlsx")
        if export.status_code != 200:
            print(f"FAIL: export -> {export.status_code}")
            return 1

        if len(export.content) < 100:
            print("FAIL: export file too small")
            return 1

        print(f"OK: export returned {len(export.content)} bytes")

    print("\nPhase 5 smoke test passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

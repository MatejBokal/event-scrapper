#!/usr/bin/env python3
"""Phase 4 smoke test: crawl targets + pages persisted."""

from __future__ import annotations

import sys

import httpx

BASE = "http://127.0.0.1:8001"


def main() -> int:
    with httpx.Client(base_url=BASE, timeout=600.0) as client:
        print("Creating search run with live search...")
        create = client.post(
            "/api/search-runs",
            json={
                "field": "Healthcare",
                "region": "Slovenia",
                "selected_months": ["2026-06"],
                "max_conferences": 3,
                "execute_search": True,
            },
        )
        if create.status_code != 201:
            print(f"FAIL: create -> {create.status_code} {create.text}")
            return 1

        run_id = create.json()["id"]
        hits = create.json().get("stats", {}).get("search_hits", 0)
        print(f"OK: search run {run_id} with {hits} hits")

        print("Crawling selected sites (may take several minutes)...")
        crawl = client.post(f"/api/search-runs/{run_id}/crawl")
        if crawl.status_code != 200:
            print(f"FAIL: crawl -> {crawl.status_code} {crawl.text}")
            return 1

        body = crawl.json()
        stats = body.get("stats", {})
        targets = len(body.get("crawl_targets", []))
        pages = len(body.get("crawled_pages", []))
        print(
            f"OK: crawl status={body['status']} "
            f"targets={targets} pages={pages} "
            f"conferences={stats.get('conferences_upserted', 0)}"
        )

        if targets < 1:
            print("FAIL: no crawl targets stored")
            return 1
        if pages < 1:
            print("FAIL: no crawled pages stored")
            return 1

    print("\nPhase 4 smoke test passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

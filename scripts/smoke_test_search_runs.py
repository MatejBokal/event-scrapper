#!/usr/bin/env python3
"""Phase 3 smoke test: search runs persisted to Supabase."""

from __future__ import annotations

import sys

import httpx

BASE = "http://127.0.0.1:8001"


def main() -> int:
    with httpx.Client(base_url=BASE, timeout=300.0) as client:
        # Fast path: queries only (no DuckDuckGo)
        response = client.post(
            "/api/search-runs",
            json={
                "field": "Healthcare",
                "region": "Slovenia",
                "selected_months": ["2026-06"],
                "max_conferences": 5,
                "execute_search": False,
            },
        )
        if response.status_code != 201:
            print(f"FAIL: create (queries only) -> {response.status_code} {response.text}")
            return 1

        run = response.json()
        run_id = run["id"]
        if len(run.get("queries", [])) < 1:
            print("FAIL: no queries stored")
            return 1
        print(f"OK: queries-only run {run_id} ({len(run['queries'])} queries)")

        # Full path: real search (may take 1-3 minutes)
        print("Running live search (execute_search=true)...")
        live = client.post(
            "/api/search-runs",
            json={
                "field": "Healthcare",
                "region": "Slovenia",
                "selected_months": ["2026-06"],
                "max_conferences": 5,
                "execute_search": True,
            },
        )
        if live.status_code != 201:
            print(f"FAIL: live search -> {live.status_code} {live.text}")
            return 1

        live_run = live.json()
        hits = live_run.get("stats", {}).get("search_hits", 0)
        print(f"OK: live run {live_run['id']} status={live_run['status']} hits={hits}")

        detail = client.get(f"/api/search-runs/{live_run['id']}")
        if detail.status_code != 200:
            print(f"FAIL: get detail -> {detail.status_code}")
            return 1
        if len(detail.json().get("results", [])) != hits:
            print("FAIL: results count mismatch")
            return 1
        print(f"OK: GET detail with {hits} raw hits")

    print("\nPhase 3 smoke test passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

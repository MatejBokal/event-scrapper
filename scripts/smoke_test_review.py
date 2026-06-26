#!/usr/bin/env python3
"""Phase 6 smoke test: review API filters + conference detail."""

from __future__ import annotations

import sys

import httpx

BASE = "http://127.0.0.1:8001"


def main() -> int:
    with httpx.Client(base_url=BASE, timeout=30.0) as client:
        health = client.get("/health")
        if health.status_code != 200:
            print(f"FAIL: health -> {health.status_code}")
            return 1
        print("OK: API health")

        conferences = client.get("/api/conferences", params={"limit": 5})
        if conferences.status_code != 200:
            print(f"FAIL: list conferences -> {conferences.status_code}")
            return 1
        rows = conferences.json()
        print(f"OK: {len(rows)} conferences in sample list")

        filtered = client.get("/api/conferences", params={"has_email": True, "limit": 5})
        if filtered.status_code != 200:
            print(f"FAIL: has_email filter -> {filtered.status_code}")
            return 1
        print(f"OK: has_email filter returned {len(filtered.json())} rows")

        if rows:
            detail = client.get(f"/api/conferences/{rows[0]['id']}")
            if detail.status_code != 200:
                print(f"FAIL: detail -> {detail.status_code}")
                return 1
            body = detail.json()
            if "crawled_pages" not in body:
                print("FAIL: detail missing crawled_pages")
                return 1
            print(
                f"OK: detail organizers={len(body.get('organizers', []))} "
                f"evidence={len(body.get('evidence', []))} "
                f"pages={len(body.get('crawled_pages', []))}"
            )

    print("\nPhase 6 API smoke test passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

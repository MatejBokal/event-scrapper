#!/usr/bin/env python3
"""Phase 2 smoke test: create conferences, organizers, export Excel."""

from __future__ import annotations

import sys
import uuid

import httpx

BASE = "http://127.0.0.1:8001"
SUFFIX = uuid.uuid4().hex[:8]


def main() -> int:
    with httpx.Client(base_url=BASE, timeout=30.0) as client:
        health = client.get("/health")
        if health.status_code != 200:
            print(f"FAIL: /health -> {health.status_code}")
            return 1
        print("OK: /health")

        conferences = []
        for index in (1, 2):
            response = client.post(
                "/api/conferences",
                json={
                    "name": f"Test Health Summit {index} {SUFFIX}",
                    "official_url": f"https://example-{SUFFIX}-{index}.org/conference",
                    "field": "Healthcare",
                    "region": "Slovenia",
                    "location": "Ljubljana",
                    "status": "needs_review",
                    "confidence_score": 70 + index,
                },
            )
            if response.status_code != 201:
                print(f"FAIL: create conference {index} -> {response.status_code} {response.text}")
                return 1
            conferences.append(response.json())
            print(f"OK: created conference {conferences[-1]['id']}")

        for conference in conferences:
            response = client.post(
                f"/api/conferences/{conference['id']}/organizers",
                json={
                    "conference_id": conference["id"],
                    "email": f"organizer-{SUFFIX}@{conference['id'][:8]}.example.org",
                    "name": "Jane Organizer",
                    "role": "Event Manager",
                    "contact_quality": "named_organizer",
                    "is_primary_lead": True,
                    "confidence_score": 85,
                    "evidence": {
                        "source_url": conference["official_url"] + "/contact",
                        "extracted_text_snippet": (
                            f"Contact event manager Jane Organizer at "
                            f"organizer-{SUFFIX}@{conference['id'][:8]}.example.org"
                        ),
                        "evidence_type": "contact_page",
                    },
                },
            )
            if response.status_code != 201:
                print(f"FAIL: create organizer -> {response.status_code} {response.text}")
                return 1
            print(f"OK: organizer for {conference['id']}")

        export_response = client.get("/api/export/leads.xlsx")
        if export_response.status_code != 200:
            print(f"FAIL: export -> {export_response.status_code}")
            return 1
        if len(export_response.content) < 1000:
            print("FAIL: export file too small")
            return 1
        print(f"OK: export leads.xlsx ({len(export_response.content)} bytes)")

    print("\nPhase 2 smoke test passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Verify Phase 1 tables exist after migration."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXPECTED = (
    "search_runs",
    "search_queries",
    "search_results",
    "crawl_targets",
    "crawled_pages",
    "conferences",
    "organizers",
    "source_evidence",
)


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, raw = line.partition("=")
        values[key.strip()] = raw.strip().strip('"').strip("'")
    return values


def main() -> int:
    import psycopg2

    database_url = load_env(ROOT / ".env").get("DATABASE_URL")
    if not database_url:
        print("FAIL: DATABASE_URL missing")
        return 1

    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                select table_name
                from information_schema.tables
                where table_schema = 'public'
                  and table_name = any(%s)
                order by table_name
                """,
                (list(EXPECTED),),
            )
            found = {row[0] for row in cur.fetchall()}
    finally:
        conn.close()

    missing = [name for name in EXPECTED if name not in found]
    if missing:
        print("FAIL: missing tables:", ", ".join(missing))
        return 1

    for name in EXPECTED:
        print(f"OK: public.{name}")
    print("Phase 1 schema verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Apply SQL files in supabase/migrations/ using DATABASE_URL from .env."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = ROOT / "supabase" / "migrations"


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, raw = line.partition("=")
        values[key.strip()] = raw.strip().strip('"').strip("'")
    return values


def main() -> int:
    try:
        import psycopg2
    except ImportError:
        print("FAIL: pip install psycopg2-binary")
        return 1

    env = load_env(ROOT / ".env")
    database_url = env.get("DATABASE_URL")
    if not database_url:
        print("FAIL: DATABASE_URL missing in .env")
        return 1

    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not migration_files:
        print(f"FAIL: no migrations in {MIGRATIONS_DIR}")
        return 1

    conn = psycopg2.connect(database_url)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                create table if not exists public.schema_migrations (
                  filename text primary key,
                  applied_at timestamptz not null default now()
                )
                """
            )
            for path in migration_files:
                cur.execute(
                    "select 1 from public.schema_migrations where filename = %s",
                    (path.name,),
                )
                if cur.fetchone():
                    print(f"SKIP: {path.name} (already applied)")
                    continue

                sql = path.read_text(encoding="utf-8")
                print(f"APPLY: {path.name}")
                cur.execute(sql)
                cur.execute(
                    "insert into public.schema_migrations (filename) values (%s)",
                    (path.name,),
                )
    finally:
        conn.close()

    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

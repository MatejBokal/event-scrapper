#!/usr/bin/env python3
"""Smoke-test Supabase credentials from repo-root .env (no secrets printed)."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, raw = line.partition("=")
        values[key.strip()] = raw.strip().strip('"').strip("'")
    return values


def project_ref_from_url(url: str) -> str | None:
    match = re.match(r"https://([^.]+)\.supabase\.co", url.strip())
    return match.group(1) if match else None


def check_required(env: dict[str, str]) -> list[str]:
    missing = []
    for key in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "DATABASE_URL"):
        if not env.get(key):
            missing.append(key)
    return missing


def test_rest_api(url: str, service_role: str) -> tuple[bool, str]:
    try:
        import requests
    except ImportError:
        return False, "requests not installed (pip install requests)"

    try:
        response = requests.get(
            f"{url.rstrip('/')}/rest/v1/",
            headers={
                "apikey": service_role,
                "Authorization": f"Bearer {service_role}",
            },
            timeout=20,
        )
    except requests.RequestException as exc:
        return False, f"HTTP request failed: {exc}"

    if response.status_code in (200, 401, 404):
        # 200 = OK; 401/404 on root still means host + key reached Supabase
        if response.status_code == 401:
            return False, "REST API returned 401 — check SUPABASE_SERVICE_ROLE_KEY"
        return True, f"REST API reachable (HTTP {response.status_code})"
    return False, f"REST API unexpected status {response.status_code}"


def test_postgres(database_url: str) -> tuple[bool, str]:
    try:
        import psycopg2
    except ImportError:
        return False, "psycopg2 not installed (pip install psycopg2-binary)"

    try:
        conn = psycopg2.connect(database_url, connect_timeout=20)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        finally:
            conn.close()
    except Exception as exc:
        return False, f"Postgres connection failed: {exc}"

    host = urlparse(database_url).hostname or "?"
    return True, f"Postgres OK (host: {host})"


def main() -> int:
    env_path = ROOT / ".env"
    env = load_env(env_path)

    print(f"Loading: {env_path}")
    missing = check_required(env)
    if missing:
        print("FAIL — missing or empty:", ", ".join(missing))
        return 1

    ref = project_ref_from_url(env["SUPABASE_URL"])
    if ref:
        print(f"Project ref (from URL): {ref}")
    else:
        print("WARN — SUPABASE_URL does not look like https://<ref>.supabase.co")

    if ref == "uujppgapwgmmjjbpxkva":
        print("WARN — this ref is 'oddo'; use your Event Organiser project instead")

    ok_api, msg_api = test_rest_api(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    print(("OK" if ok_api else "FAIL") + f" — {msg_api}")

    ok_db, msg_db = test_postgres(env["DATABASE_URL"])
    print(("OK" if ok_db else "FAIL") + f" — {msg_db}")

    if ok_api and ok_db:
        print("\nAll checks passed.")
        return 0

    print("\nFix .env and try again. Common issues:")
    print("  - Wrong project URL / service role key")
    print("  - DATABASE_URL password wrong or needs URL-encoding (@ as %40)")
    print("  - Use pooler host from Dashboard → Database → Connection string")
    return 1


if __name__ == "__main__":
    sys.exit(main())

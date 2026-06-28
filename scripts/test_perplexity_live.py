"""Live smoke test for Perplexity Sonar API (requires PERPLEXITY_API_KEY in .env)."""

from __future__ import annotations

import sys
from pathlib import Path

POC_ROOT = Path(__file__).resolve().parents[1] / "poc"
sys.path.insert(0, str(POC_ROOT))

from backend.config import (  # noqa: E402
    get_perplexity_api_key,
    get_perplexity_model,
    is_llm_extraction_enabled,
)
from backend.llm_extractor import _call_perplexity_for_site  # noqa: E402


def main() -> int:
    key = get_perplexity_api_key()
    if not key:
        print("FAIL: PERPLEXITY_API_KEY is not set in repo-root .env")
        return 1

    print(f"API key: present ({key[:8]}…)")
    print(f"Model: {get_perplexity_model()}")
    print(f"LLM extraction enabled: {is_llm_extraction_enabled()}")

    sample_pages = (
        "--- PAGE: https://example.org/contact ---\n"
        "Contact the organizing committee at events@example.org for registration."
    )

    try:
        data, raw_body = _call_perplexity_for_site("https://example.org/", sample_pages)
    except Exception as exc:
        print(f"FAIL: Perplexity API call failed — {exc}")
        return 1

    organizers = data.get("organizers") or []
    conference = data.get("conference") or {}
    print("OK: Perplexity returned valid JSON")
    print(f"  conference keys: {list(conference.keys()) if isinstance(conference, dict) else '—'}")
    print(f"  organizers count: {len(organizers) if isinstance(organizers, list) else 0}")
    if raw_body.get("usage"):
        print(f"  token usage: {raw_body['usage']}")
    if organizers and isinstance(organizers[0], dict):
        print(f"  first organizer email: {organizers[0].get('email')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

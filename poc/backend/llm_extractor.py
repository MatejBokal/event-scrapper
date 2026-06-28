"""Perplexity Sonar LLM extraction from crawled page text — no web search."""

from __future__ import annotations

import json
import logging
import re
import time
from collections import defaultdict
from datetime import date, datetime
from typing import Any
from urllib.parse import urlparse

import httpx

from backend.app_logging import get_logger, llm_debug_enabled
from backend.config import (
    CONTACT_TYPE_KEYWORDS,
    LLM_MAX_PAGE_CHARS,
    LLM_PATH_KEYWORDS_LOW_PRIORITY,
    LLM_PATH_KEYWORDS_ORGANIZER,
    MIN_PAGE_TEXT_LENGTH,
    get_llm_max_pages_per_site,
    get_perplexity_api_key,
    get_perplexity_model,
    is_llm_extraction_enabled,
)
from backend.extractor import (
    _evidence_snippet,
    _is_plausible_email,
    _normalize_email,
)
from backend.models import ConferenceLlmMetadata, CrawledPage, RawEmailHit, SearchParams

logger = get_logger("llm")

PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"

SYSTEM_PROMPT = """You extract structured conference and organizer contact information from official conference website text.

Rules:
- Only extract information that appears in the provided PAGE sections.
- Do not invent names, dates, emails, organizations, or roles.
- If a value is not present, return null.
- Prefer official organizer, committee, and general event contact emails.
- For every organizer with an email, set source_url to the PAGE URL where the email appears.
- For every organizer with an email, include evidence_text: a short verbatim quote containing the email.
- Return valid JSON only, no markdown fences or commentary."""

SITE_PROMPT_TEMPLATE = """CONFERENCE_URL:
{conference_url}

PAGES:
{pages_block}

Return JSON in this structure:
{{
  "conference": {{
    "name": null,
    "start_date": null,
    "end_date": null,
    "location": null,
    "country": null,
    "description": null,
    "language": null
  }},
  "organizers": [
    {{
      "source_url": null,
      "name": null,
      "organization": null,
      "role": null,
      "email": null,
      "phone": null,
      "website": null,
      "linkedin_url": null,
      "contact_type": null,
      "evidence_text": null
    }}
  ]
}}"""

_CONTACT_TYPE_ALIASES = {
    "organizer": "organizer",
    "organiser": "organizer",
    "organizing": "organizer",
    "organising": "organizer",
    "committee": "committee",
    "pco": "organizer",
    "sponsorship": "sponsorship",
    "sponsor": "sponsorship",
    "exhibitor": "exhibitor",
    "cfp": "cfp",
    "generic": "generic",
    "contact": "generic",
}


def _organizer_text_keywords() -> tuple[str, ...]:
    keywords: list[str] = []
    for group in ("organizer", "committee", "generic"):
        keywords.extend(CONTACT_TYPE_KEYWORDS.get(group, []))
    return tuple(keywords)


def _llm_page_score(
    page: CrawledPage,
    params: SearchParams,
    regex_hit_count: int,
) -> int:
    path = urlparse(page.url).path.lower()
    page_type = (page.page_type or "").lower()
    text_lower = (page.extracted_text or "").lower()
    score = 0

    for index, keyword in enumerate(LLM_PATH_KEYWORDS_ORGANIZER):
        if keyword in path or keyword == page_type:
            score += 60 - (index * 3)

    if params.contact_type in ("organizer", "committee"):
        for keyword in LLM_PATH_KEYWORDS_LOW_PRIORITY:
            if keyword in path or keyword == page_type:
                score -= 35

    for keyword in _organizer_text_keywords():
        if keyword in text_lower:
            score += 4

    if regex_hit_count:
        score += 20
    elif score > 0:
        score += 25

    if path in ("", "/"):
        score += 3

    return score


def select_llm_pages(
    pages: list[CrawledPage],
    regex_hits: list[RawEmailHit],
    params: SearchParams,
) -> list[CrawledPage]:
    """Pick the highest-value pages for a Perplexity call (default: top 3 per site)."""
    if not pages:
        return []

    hits_by_url: dict[str, int] = defaultdict(int)
    for hit in regex_hits:
        hits_by_url[hit.source_url] += 1

    scored: list[tuple[int, CrawledPage]] = []
    for page in pages:
        text = (page.extracted_text or "").strip()
        if len(text) < MIN_PAGE_TEXT_LENGTH:
            continue
        score = _llm_page_score(page, params, hits_by_url.get(page.url, 0))
        scored.append((score, page))

    if not scored:
        return []

    scored.sort(key=lambda item: item[0], reverse=True)
    limit = get_llm_max_pages_per_site()
    promising = [page for score, page in scored if score > 0][:limit]

    if promising:
        return promising

    if not regex_hits:
        return [scored[0][1]]

    return []


def _parse_json_content(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("LLM response is not a JSON object")
    return parsed


def _normalize_contact_type(raw: str | None, preferred: str) -> str:
    if not raw:
        return preferred if preferred != "any" else "unknown"
    normalized = _CONTACT_TYPE_ALIASES.get(raw.strip().lower())
    if normalized:
        return normalized
    lowered = raw.strip().lower()
    if lowered in _CONTACT_TYPE_ALIASES.values():
        return lowered
    return preferred if preferred != "any" else "unknown"


def _clean_optional_str(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _text_in_source(value: str, source_text: str) -> bool:
    if not value or not source_text:
        return False
    return value.lower() in source_text.lower()


def _parse_optional_date(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(cleaned[:10] if fmt == "%Y-%m-%d" else cleaned, fmt).date()
        except ValueError:
            continue
    try:
        return date.fromisoformat(cleaned[:10])
    except ValueError:
        return None


def _combine_selected_pages(selected: list[CrawledPage]) -> tuple[str, dict[str, CrawledPage]]:
    per_page_budget = max(2000, LLM_MAX_PAGE_CHARS // max(1, len(selected)))
    pages_by_url: dict[str, CrawledPage] = {}
    blocks: list[str] = []
    for page in selected:
        pages_by_url[page.url] = page
        text = (page.extracted_text or "").strip()[:per_page_budget]
        blocks.append(f"--- PAGE: {page.url} ---\n{text}")
    return "\n\n".join(blocks), pages_by_url


def _parse_conference_metadata(
    data: dict[str, Any],
    combined_text: str,
    fallback_name: str | None,
) -> ConferenceLlmMetadata | None:
    block = data.get("conference")
    if not isinstance(block, dict):
        return None

    name = _clean_optional_str(block.get("name"))
    if name and not _text_in_source(name, combined_text):
        name = fallback_name

    location = _clean_optional_str(block.get("location"))
    if location and not _text_in_source(location, combined_text):
        location = None

    country = _clean_optional_str(block.get("country"))
    if country and not _text_in_source(country, combined_text):
        country = None

    description = _clean_optional_str(block.get("description"))
    if description and len(description) > 80 and not _text_in_source(description[:80], combined_text):
        description = None

    language = _clean_optional_str(block.get("language"))

    start_date = _parse_optional_date(block.get("start_date"))
    end_date = _parse_optional_date(block.get("end_date"))
    month_year = start_date.strftime("%Y-%m") if start_date else None

    if not any((name, start_date, end_date, location, country, description, language)):
        return None

    return ConferenceLlmMetadata(
        name=name or fallback_name,
        start_date=start_date,
        end_date=end_date,
        month_year=month_year,
        location=location,
        country=country,
        description=description,
        language=language,
    )


def _resolve_page_for_organizer(
    row: dict[str, Any],
    email: str,
    pages_by_url: dict[str, CrawledPage],
) -> CrawledPage | None:
    source_url = _clean_optional_str(row.get("source_url"))
    if source_url and source_url in pages_by_url:
        page = pages_by_url[source_url]
        if email.lower() in (page.extracted_text or "").lower():
            return page

    for page in pages_by_url.values():
        if email.lower() in (page.extracted_text or "").lower():
            return page
    return None


def _metadata_filled_fields(metadata: ConferenceLlmMetadata | None) -> list[str]:
    if metadata is None:
        return []
    fields: list[str] = []
    if metadata.name:
        fields.append("name")
    if metadata.start_date:
        fields.append("start_date")
    if metadata.end_date:
        fields.append("end_date")
    if metadata.month_year:
        fields.append("month_year")
    if metadata.location:
        fields.append("location")
    if metadata.country:
        fields.append("country")
    if metadata.description:
        fields.append("description")
    if metadata.language:
        fields.append("language")
    return fields


def _audit_base(conference_url: str) -> dict[str, Any]:
    return {
        "conference_url": conference_url,
        "pages_selected": [],
        "success": False,
        "skipped_reason": None,
        "organizers_found": 0,
        "conference_fields_filled": [],
        "model": get_perplexity_model(),
        "duration_ms": None,
        "usage": None,
        "error": None,
    }


def _call_perplexity_for_site(conference_url: str, pages_block: str) -> tuple[dict[str, Any], dict[str, Any]]:
    api_key = get_perplexity_api_key()
    if not api_key:
        raise RuntimeError("PERPLEXITY_API_KEY is not set")

    payload = {
        "model": get_perplexity_model(),
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": SITE_PROMPT_TEMPLATE.format(
                    conference_url=conference_url,
                    pages_block=pages_block[:LLM_MAX_PAGE_CHARS],
                ),
            },
        ],
        "temperature": 0.1,
        "disable_search": True,
    }

    with httpx.Client(timeout=90.0) as client:
        response = client.post(
            PERPLEXITY_API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        body = response.json()

    choices = body.get("choices") or []
    if not choices:
        raise ValueError("Perplexity response has no choices")
    content = choices[0].get("message", {}).get("content", "")
    if not content:
        raise ValueError("Perplexity response has empty content")

    if llm_debug_enabled():
        logger.debug(
            "LLM raw response for %s (first 800 chars): %s",
            conference_url,
            content[:800],
        )

    return _parse_json_content(content), body


def _organizers_to_hits(
    data: dict[str, Any],
    pages_by_url: dict[str, CrawledPage],
    params: SearchParams,
    conference_name: str | None,
) -> list[RawEmailHit]:
    organizers = data.get("organizers") or []
    if not isinstance(organizers, list):
        return []

    resolved_name = conference_name
    conference_block = data.get("conference") if isinstance(data.get("conference"), dict) else {}
    if isinstance(conference_block, dict):
        llm_name = _clean_optional_str(conference_block.get("name"))
        if llm_name:
            resolved_name = llm_name

    hits: list[RawEmailHit] = []
    seen: set[tuple[str, str]] = set()

    for row in organizers:
        if not isinstance(row, dict):
            continue
        raw_email = row.get("email")
        if not raw_email or not isinstance(raw_email, str):
            continue

        email = _normalize_email(raw_email)
        if not _is_plausible_email(email):
            continue

        page = _resolve_page_for_organizer(row, email, pages_by_url)
        if page is None:
            continue

        page_text = page.extracted_text or ""
        key = (email, page.url)
        if key in seen:
            continue

        evidence = _clean_optional_str(row.get("evidence_text"))
        if evidence and not _text_in_source(evidence, page_text):
            evidence = _evidence_snippet(page_text, email)
        if not evidence:
            evidence = _evidence_snippet(page_text, email)
        if not evidence:
            continue

        seen.add(key)
        contact_type = _normalize_contact_type(
            row.get("contact_type") if isinstance(row.get("contact_type"), str) else None,
            params.contact_type,
        )

        hits.append(
            RawEmailHit(
                email=email,
                source_url=page.url,
                page_title=page.title,
                extracted_text=page_text,
                extraction_method="llm",
                contact_type=contact_type,
                conference_url=page.conference_url,
                conference_name=resolved_name,
                organizer_name=_clean_optional_str(row.get("name")),
                organizer_role=_clean_optional_str(row.get("role")),
                organization=_clean_optional_str(row.get("organization")),
                phone=_clean_optional_str(row.get("phone")),
                website=_clean_optional_str(row.get("website")),
                linkedin_url=_clean_optional_str(row.get("linkedin_url")),
            )
        )

    return hits


def extract_llm_for_site(
    pages: list[CrawledPage],
    regex_hits: list[RawEmailHit],
    params: SearchParams,
    conference_name: str | None,
) -> tuple[list[RawEmailHit], ConferenceLlmMetadata | None, dict[str, Any]]:
    """One Perplexity call per conference site on the most promising pages."""
    conference_url = pages[0].conference_url if pages else ""
    audit = _audit_base(conference_url)

    if not is_llm_extraction_enabled():
        audit["skipped_reason"] = "llm_disabled"
        logger.info("LLM skipped for %s: disabled", conference_url or "(no pages)")
        return [], None, audit

    selected = select_llm_pages(pages, regex_hits, params)
    audit["pages_selected"] = [page.url for page in selected]

    if not selected:
        audit["skipped_reason"] = (
            "no_promising_pages" if regex_hits else "no_eligible_pages_or_hail_mary"
        )
        logger.info(
            "LLM skipped for %s: %s (regex_hits=%d)",
            conference_url,
            audit["skipped_reason"],
            len(regex_hits),
        )
        return [], None, audit

    pages_block, pages_by_url = _combine_selected_pages(selected)
    conference_url = selected[0].conference_url
    audit["conference_url"] = conference_url

    logger.info(
        "LLM call for %s — pages=%s",
        conference_url,
        ", ".join(audit["pages_selected"]),
    )

    started = time.perf_counter()
    try:
        data, raw_body = _call_perplexity_for_site(conference_url, pages_block)
    except Exception as exc:
        audit["error"] = str(exc)
        audit["duration_ms"] = int((time.perf_counter() - started) * 1000)
        logger.warning(
            "LLM extraction failed for %s after %sms: %s",
            conference_url,
            audit["duration_ms"],
            exc,
        )
        return [], None, audit

    audit["duration_ms"] = int((time.perf_counter() - started) * 1000)
    audit["usage"] = raw_body.get("usage")

    combined_text = pages_block
    metadata = _parse_conference_metadata(data, combined_text, conference_name)
    hits = _organizers_to_hits(data, pages_by_url, params, conference_name)

    audit["success"] = True
    audit["organizers_found"] = len(hits)
    audit["conference_fields_filled"] = _metadata_filled_fields(metadata)

    logger.info(
        "LLM OK for %s — %sms, organizers=%d, conference_fields=%s, usage=%s",
        conference_url,
        audit["duration_ms"],
        len(hits),
        audit["conference_fields_filled"] or "none",
        audit["usage"],
    )
    return hits, metadata, audit

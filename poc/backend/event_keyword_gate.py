"""Keyword gate: start page or site root must look like an event (or JSON-LD Event)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from backend.event_presence import extract_from_json_ld
from backend.models import CrawledPage


@dataclass(frozen=True)
class KeywordGateResult:
    passes: bool
    reason: str
    matched_keyword: str | None = None
    via_json_ld: bool = False


def site_root_url(url: str) -> str:
    parsed = urlparse(url)
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc
    if not netloc:
        return url
    return f"{scheme}://{netloc}/"


def _html_h1_text(html: str) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, "lxml")
    parts = [tag.get_text(" ", strip=True) for tag in soup.find_all("h1")]
    return "\n".join(parts)


def _page_corpus(page: CrawledPage) -> str:
    parts: list[str] = []
    if page.title:
        parts.append(page.title)
    parts.append(_html_h1_text(page.html or ""))
    if page.extracted_text:
        # Prefer head of body — enough for keyword, less footer noise.
        parts.append(page.extracted_text[:4000])
    return "\n".join(parts)


def _has_json_ld_event(pages: list[CrawledPage]) -> bool:
    for page in pages:
        dates, _locs, _has_time = extract_from_json_ld(page.html or "")
        if dates:
            return True
        # extract_from_json_ld only returns Event-typed nodes' dates; also accept type-only.
        if page.html and re.search(
            r'("@type"\s*:\s*"Event"|@type["\']?\s*:\s*["\']Event)',
            page.html,
            re.IGNORECASE,
        ):
            return True
    return False


def text_has_event_keyword(text: str, keywords: list[str] | tuple[str, ...]) -> str | None:
    if not text or not keywords:
        return None
    haystack = text.casefold()
    # Longer keywords first (e.g. "call for papers" if ever added).
    ordered = sorted({k.strip() for k in keywords if k and k.strip()}, key=len, reverse=True)
    for keyword in ordered:
        needle = keyword.casefold()
        pattern = re.compile(rf"(?<!\w){re.escape(needle)}(?!\w)", re.IGNORECASE)
        if pattern.search(haystack):
            return keyword
    return None


def assess_keyword_gate(
    pages: list[CrawledPage],
    keywords: list[str] | tuple[str, ...],
) -> KeywordGateResult:
    if not pages:
        return KeywordGateResult(False, "no_pages")

    if _has_json_ld_event(pages):
        return KeywordGateResult(True, "ok_json_ld", via_json_ld=True)

    combined = "\n".join(_page_corpus(page) for page in pages)
    matched = text_has_event_keyword(combined, keywords)
    if matched:
        return KeywordGateResult(True, "ok_keyword", matched_keyword=matched)
    return KeywordGateResult(False, "missing_event_keyword")

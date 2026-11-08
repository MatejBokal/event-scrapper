"""Hard gate: require a real event date and a country-allowlisted city on the page."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable

from bs4 import BeautifulSoup

from backend.models import CrawledPage

_MONTHS: dict[str, int] = {
    "january": 1,
    "jan": 1,
    "januar": 1,
    "janvier": 1,
    "february": 2,
    "feb": 2,
    "februar": 2,
    "février": 2,
    "fevrier": 2,
    "march": 3,
    "mar": 3,
    "märz": 3,
    "maerz": 3,
    "mars": 3,
    "april": 4,
    "apr": 4,
    "avril": 4,
    "may": 5,
    "mai": 5,
    "june": 6,
    "jun": 6,
    "juni": 6,
    "juin": 6,
    "july": 7,
    "jul": 7,
    "juli": 7,
    "juillet": 7,
    "august": 8,
    "aug": 8,
    "août": 8,
    "aout": 8,
    "september": 9,
    "sep": 9,
    "sept": 9,
    "septembre": 9,
    "october": 10,
    "oct": 10,
    "oktober": 10,
    "octobre": 10,
    "november": 11,
    "nov": 11,
    "novembre": 11,
    "december": 12,
    "dec": 12,
    "dezember": 12,
    "décembre": 12,
    "decembre": 12,
}

_MONTH_ALT = "|".join(sorted(_MONTHS.keys(), key=len, reverse=True))

# Day-level dates only — year/month alone is not enough.
_DATE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})(?:[Tt ]\d{2}:\d{2})?"),
    re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](20\d{2})\b"),
    # Multi-day ranges like 14-16 September 2026 (ASCII hyphen only; avoid "Day 1 — 14 September").
    re.compile(
        rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s*-\s*(\d{{1,2}})(?:st|nd|rd|th)?\s+"
        rf"({_MONTH_ALT})\.?\s+(20\d{{2}})\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({_MONTH_ALT})\.?\s+(20\d{{2}})\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\b({_MONTH_ALT})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:,)?\s+(20\d{{2}})\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\b(\d{{1,2}})\.\s*({_MONTH_ALT})\.?\s+(20\d{{2}})\b",
        re.IGNORECASE,
    ),
]

# Clock times anywhere on the site (bonus signal, not required).
_TIME_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b([01]?\d|2[0-3])[:.]([0-5]\d)\s*(?:h|hrs|hours|uhr|u\.?)?\b", re.IGNORECASE),
    re.compile(r"\b([01]?\d|2[0-3])[:.]([0-5]\d)\s*[-–—]\s*([01]?\d|2[0-3])[:.]([0-5]\d)\b"),
    re.compile(r"\b(1[0-2]|0?[1-9])[:.]([0-5]\d)\s*(a\.?m\.?|p\.?m\.?)\b", re.IGNORECASE),
    re.compile(r"\b(1[0-2]|0?[1-9])\s*(a\.?m\.?|p\.?m\.?)\b", re.IGNORECASE),
    re.compile(r"[Tt]([01]\d|2[0-3]):([0-5]\d)"),
    re.compile(r"\bdoors?\s+open\b", re.IGNORECASE),
    re.compile(r"\bregistration\s+opens?\b", re.IGNORECASE),
]

# Confidence bump when any crawled page shows a clock time.
TIME_PRESENCE_BONUS = 15


@dataclass(frozen=True)
class EventPresence:
    event_date: date | None
    matched_city: str | None
    reason: str = ""
    has_time: bool = False

    @property
    def passes(self) -> bool:
        return self.event_date is not None and self.matched_city is not None


def _date_window() -> tuple[date, date]:
    today = date.today()
    return today - timedelta(days=60), today + timedelta(days=365 * 3)


def _valid_date(year: int, month: int, day: int) -> date | None:
    try:
        value = date(year, month, day)
    except ValueError:
        return None
    lo, hi = _date_window()
    if value < lo or value > hi:
        return None
    return value


def _parse_iso_like(year: str, month: str, day: str) -> date | None:
    return _valid_date(int(year), int(month), int(day))


def _parse_dmy(day: str, month: str, year: str) -> date | None:
    return _valid_date(int(year), int(month), int(day))


def extract_dates_from_text(text: str) -> list[date]:
    if not text:
        return []
    found: list[date] = []
    seen: set[date] = set()

    for match in _DATE_PATTERNS[0].finditer(text):
        parsed = _parse_iso_like(match.group(1), match.group(2), match.group(3))
        if parsed and parsed not in seen:
            seen.add(parsed)
            found.append(parsed)

    for match in _DATE_PATTERNS[1].finditer(text):
        first, second, year = match.group(1), match.group(2), match.group(3)
        # Prefer DMY (EU); fall back to MDY when day would be invalid.
        parsed = _parse_dmy(first, second, year)
        if parsed is None and int(first) <= 12:
            parsed = _valid_date(int(year), int(first), int(second))
        if parsed and parsed not in seen:
            seen.add(parsed)
            found.append(parsed)

    # 14-16 September 2026 → use the first day of the range
    for match in _DATE_PATTERNS[2].finditer(text):
        day_s, _end_day, month_s, year_s = match.groups()
        month = _MONTHS.get(month_s.lower())
        if not month:
            continue
        parsed = _valid_date(int(year_s), month, int(day_s))
        if parsed and parsed not in seen:
            seen.add(parsed)
            found.append(parsed)

    for pattern in _DATE_PATTERNS[3:]:
        for match in pattern.finditer(text):
            groups = match.groups()
            if groups[0].isdigit():
                day_s, month_s, year_s = groups[0], groups[1], groups[2]
            else:
                month_s, day_s, year_s = groups[0], groups[1], groups[2]
            month = _MONTHS.get(month_s.lower())
            if not month:
                continue
            parsed = _valid_date(int(year_s), month, int(day_s))
            if parsed and parsed not in seen:
                seen.add(parsed)
                found.append(parsed)

    return found


def _iter_json_ld_nodes(payload: object) -> Iterable[dict]:
    if isinstance(payload, dict):
        if "@graph" in payload and isinstance(payload["@graph"], list):
            for item in payload["@graph"]:
                yield from _iter_json_ld_nodes(item)
        else:
            yield payload
            for value in payload.values():
                yield from _iter_json_ld_nodes(value)
    elif isinstance(payload, list):
        for item in payload:
            yield from _iter_json_ld_nodes(item)


def _types_of(node: dict) -> set[str]:
    raw = node.get("@type")
    if isinstance(raw, str):
        return {raw.lower()}
    if isinstance(raw, list):
        return {str(item).lower() for item in raw}
    return set()


def _parse_json_ld_date(value: object) -> date | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    match = re.match(r"(20\d{2})-(\d{2})-(\d{2})", raw)
    if match:
        return _parse_iso_like(match.group(1), match.group(2), match.group(3))
    return None


def _location_text(node: object) -> str:
    if isinstance(node, str):
        return node
    if not isinstance(node, dict):
        return ""
    parts: list[str] = []
    for key in ("name", "addressLocality", "addressRegion", "streetAddress"):
        value = node.get(key)
        if isinstance(value, str):
            parts.append(value)
    address = node.get("address")
    if isinstance(address, (dict, str)):
        parts.append(_location_text(address))
    return " ".join(parts)


def extract_times_from_text(text: str) -> bool:
    if not text:
        return False
    return any(pattern.search(text) for pattern in _TIME_PATTERNS)


def _html_visible_text(html: str) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    chunks: list[str] = []
    for node in soup.find_all(attrs={"datetime": True}):
        value = node.get("datetime")
        if isinstance(value, str) and value.strip():
            chunks.append(value.strip())
    chunks.append(soup.get_text(" ", strip=True))
    return "\n".join(chunks)


def extract_from_json_ld(html: str) -> tuple[list[date], list[str], bool]:
    if not html:
        return [], [], False
    soup = BeautifulSoup(html, "lxml")
    dates: list[date] = []
    locations: list[str] = []
    seen_dates: set[date] = set()
    has_time = False

    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string or script.get_text() or ""
        if not raw.strip():
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for node in _iter_json_ld_nodes(payload):
            types = _types_of(node)
            event_types = {
                "event",
                "businessevent",
                "educationevent",
                "socialevent",
                "exhibitionevent",
            }
            if not types.intersection(event_types):
                continue
            start = None
            start_raw = None
            for key, value in node.items():
                if key.lower() == "startdate":
                    start_raw = value
                    start = _parse_json_ld_date(value)
                    break
            if isinstance(start_raw, str) and re.search(r"[Tt ]\d{2}:\d{2}", start_raw):
                has_time = True
            if start and start not in seen_dates:
                seen_dates.add(start)
                dates.append(start)
            loc = _location_text(node.get("location"))
            if loc:
                locations.append(loc)

    return dates, locations, has_time


def match_city_allowlist(text: str, cities: Iterable[str]) -> str | None:
    if not text:
        return None
    haystack = text.casefold()
    # Longer names first so "Sankt Gallen" wins over "Gallen" if both listed.
    ordered = sorted({c.strip() for c in cities if c and c.strip()}, key=len, reverse=True)
    for city in ordered:
        needle = city.casefold()
        pattern = re.compile(rf"(?<!\w){re.escape(needle)}(?!\w)", re.IGNORECASE)
        if pattern.search(haystack):
            return city
    return None


def _page_corpus(page: CrawledPage) -> str:
    """All text available on one crawled page (date/hour may be anywhere)."""
    parts: list[str] = []
    if page.title:
        parts.append(page.title)
    if page.extracted_text:
        parts.append(page.extracted_text)
    html_text = _html_visible_text(page.html or "")
    if html_text:
        parts.append(html_text)
    return "\n".join(parts)


def _combined_page_text(pages: list[CrawledPage]) -> str:
    return "\n".join(_page_corpus(page) for page in pages)


def assess_event_presence(
    pages: list[CrawledPage],
    city_allowlist: Iterable[str],
) -> EventPresence:
    """Scan every crawled page of the site for date, city, and optional hour."""
    allowlist = [c for c in city_allowlist if c and str(c).strip()]
    if not pages:
        return EventPresence(None, None, "no_pages", has_time=False)

    dates: list[date] = []
    json_ld_locations: list[str] = []
    has_time = False

    for page in pages:
        page_dates, page_locs, page_has_time = extract_from_json_ld(page.html or "")
        dates.extend(page_dates)
        json_ld_locations.extend(page_locs)
        has_time = has_time or page_has_time

        corpus = _page_corpus(page)
        dates.extend(extract_dates_from_text(corpus))
        has_time = has_time or extract_times_from_text(corpus)

    event_date = min(dates) if dates else None

    combined = _combined_page_text(pages)
    if json_ld_locations:
        combined = "\n".join(json_ld_locations) + "\n" + combined

    matched_city = match_city_allowlist(combined, allowlist) if allowlist else None

    if event_date is None and matched_city is None:
        return EventPresence(None, None, "missing_date_and_city", has_time=has_time)
    if event_date is None:
        return EventPresence(None, matched_city, "missing_date", has_time=has_time)
    if matched_city is None:
        return EventPresence(event_date, None, "missing_city", has_time=has_time)
    return EventPresence(event_date, matched_city, "ok", has_time=has_time)

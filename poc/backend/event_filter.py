"""Filter out non-event pages and stale results."""

from __future__ import annotations

import re
from datetime import datetime

from backend.domains import is_spam_domain as is_spam_domain_url
from backend.models import SearchHit, SearchParams

NEWS_URL_MARKERS = (
    "/blog/",
    "/news/",
    "/article/",
    "/articles/",
    "/meeting-summary/",
    "/press/",
    "/media/",
    "/the-efpia-view/",
    "/view/blog",
)

NEWS_TITLE_MARKERS = (
    "guest blog",
    "blog article",
    "meeting summary",
    "welcome slovenia",
    "experts of the committee",
    "read more",
)

YEAR_PATTERN = re.compile(r"\b(20\d{2})\b")


def _years_in_text(text: str) -> set[int]:
    return {int(match.group(1)) for match in YEAR_PATTERN.finditer(text)}


def _target_years(params: SearchParams) -> set[int]:
    years: set[int] = set()
    for month in params.selected_months:
        if month and "-" in month:
            try:
                years.add(int(month.split("-")[0]))
            except ValueError:
                continue
    if not years:
        years.add(datetime.now().year)
        years.add(datetime.now().year + 1)
    return years


def is_news_or_article(hit: SearchHit) -> bool:
    url_lower = hit.url.lower()
    title_lower = hit.title.lower()

    if any(marker in url_lower for marker in NEWS_URL_MARKERS):
        return True
    if any(marker in title_lower for marker in NEWS_TITLE_MARKERS):
        return True
    return False


def is_spam_domain(hit: SearchHit) -> bool:
    return is_spam_domain_url(hit.url)


def is_stale_event(hit: SearchHit, params: SearchParams) -> bool:
    target_years = _target_years(params)
    min_year = min(target_years) - 1
    max_year = max(target_years) + 1

    combined = f"{hit.url} {hit.title} {hit.snippet}"
    years = _years_in_text(combined)

    if not years:
        return False

    if all(year < min_year for year in years):
        return True
    if all(year > max_year + 1 for year in years):
        return True
    return False


def is_likely_event_page(hit: SearchHit, params: SearchParams) -> bool:
    if is_news_or_article(hit):
        return False
    if is_spam_domain(hit):
        return False
    if is_stale_event(hit, params):
        return False
    return True


def filter_event_hits(hits: list[SearchHit], params: SearchParams) -> tuple[list[SearchHit], list[SearchHit]]:
    kept: list[SearchHit] = []
    rejected: list[SearchHit] = []

    for hit in hits:
        if is_likely_event_page(hit, params):
            kept.append(hit)
        else:
            rejected.append(hit)

    return kept, rejected

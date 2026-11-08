"""Rank search results and pick likely official conference sites."""

from __future__ import annotations

from urllib.parse import urlparse

from backend.config import CONFERENCE_KEYWORDS, MIN_URL_SCORE
from backend.domains import is_denylisted_domain, is_listing_domain
from backend.models import SearchHit, SearchParams, SelectedSite
from backend.regions import get_region_profile


def _domain(url: str) -> str:
    parsed = urlparse(url)
    return (parsed.netloc or "").lower().removeprefix("www.")


def _field_tokens(field: str) -> list[str]:
    tokens = []
    for part in field.lower().replace(",", " ").replace("/", " ").split():
        cleaned = part.strip()
        if len(cleaned) >= 3:
            tokens.append(cleaned)
    return tokens


def score_hit(hit: SearchHit, params: SearchParams) -> float:
    url_lower = hit.url.lower()
    title_lower = hit.title.lower()
    snippet_lower = hit.snippet.lower()
    combined = f"{url_lower} {title_lower} {snippet_lower}"

    score = 0.0

    if is_denylisted_domain(hit.url):
        score -= 80
    elif is_listing_domain(hit.url):
        score += 12

    year = params.start_month.split("-")[0] if params.start_month else ""
    if year and year in combined:
        score += 15

    for token in _field_tokens(params.field):
        if token in combined:
            score += 8

    for keyword in CONFERENCE_KEYWORDS:
        if keyword in combined:
            score += 10
            break

    path = urlparse(hit.url).path.lower()
    if any(k in path for k in ("conference", "summit", "event", "kongres", "konferenc")):
        score += 10

    score += max(0, 6 - hit.rank)
    return score


def rank_hits(hits: list[SearchHit], params: SearchParams) -> list[SearchHit]:
    seen_urls: set[str] = set()
    ranked: list[SearchHit] = []

    for hit in hits:
        normalized_url = hit.url.rstrip("/")
        if normalized_url in seen_urls:
            continue
        seen_urls.add(normalized_url)

        scored = SearchHit(
            title=hit.title,
            url=hit.url,
            snippet=hit.snippet,
            source_query=hit.source_query,
            rank=hit.rank,
            url_score=score_hit(hit, params),
        )
        ranked.append(scored)

    ranked.sort(key=lambda h: h.url_score, reverse=True)
    return ranked


def _min_score_for_region(params: SearchParams) -> float:
    profile = get_region_profile(params.region, params.custom_region)
    if profile.key in ("worldwide", "europe", "asia"):
        return 0
    return MIN_URL_SCORE


def select_sites(
    hits: list[SearchHit],
    params: SearchParams,
) -> tuple[list[SelectedSite], list[SearchHit]]:
    ranked = rank_hits(hits, params)
    selected: list[SelectedSite] = []
    skipped: list[SearchHit] = []
    min_score = _min_score_for_region(params)
    unlimited = params.max_conferences <= 0

    for hit in ranked:
        if not unlimited and len(selected) >= params.max_conferences:
            skipped.append(hit)
            continue

        if hit.url_score < min_score and not is_listing_domain(hit.url):
            skipped.append(hit)
            continue

        if any(s.url.rstrip("/") == hit.url.rstrip("/") for s in selected):
            continue

        selected.append(
            SelectedSite(
                url=hit.url,
                title=hit.title,
                url_score=hit.url_score,
                snippet=hit.snippet,
                source="listing" if is_listing_domain(hit.url) else "search",
            )
        )

    return selected, skipped

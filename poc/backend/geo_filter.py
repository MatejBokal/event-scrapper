"""Geo relevance scoring for search hits."""

from __future__ import annotations

from urllib.parse import urlparse

from backend.models import SearchHit, SearchParams
from backend.regions import RegionProfile, get_region_profile


def _combined_text(hit: SearchHit) -> str:
    return f"{hit.url} {hit.title} {hit.snippet}".lower()


def _domain(url: str) -> str:
    return urlparse(url).netloc.lower()


def geo_score(hit: SearchHit, profile: RegionProfile, params: SearchParams) -> float:
    text = _combined_text(hit)
    domain = _domain(hit.url)
    score = 0.0

    for country in profile.country_names:
        if country and country in text:
            score += 12

    city_targets = list(profile.cities)
    if params.target_city.strip():
        city_targets = [params.target_city.strip(), *city_targets]

    for city in city_targets:
        if city.lower() in text:
            score += 15

    for tld in profile.tlds:
        if domain.endswith(tld) or tld.strip(".") in domain:
            score += 20

    for prefix in profile.phone_prefixes:
        if prefix in text:
            score += 8

    if profile.display_name.lower() != "worldwide" and profile.display_name.lower() in text:
        score += 8

    for negative in profile.negative_locations:
        if negative in text or negative in domain:
            score -= 18

    if params.custom_region and params.region == "Custom":
        custom = params.custom_region.lower()
        if custom in text:
            score += 15

    return score


def apply_geo_scoring(
    hits: list[SearchHit],
    params: SearchParams,
) -> list[SearchHit]:
    profile = get_region_profile(params.region, params.custom_region)
    scored: list[SearchHit] = []

    for hit in hits:
        bonus = geo_score(hit, profile, params)
        scored.append(
            SearchHit(
                title=hit.title,
                url=hit.url,
                snippet=hit.snippet,
                source_query=hit.source_query,
                rank=hit.rank,
                url_score=hit.url_score + bonus,
            )
        )

    return scored

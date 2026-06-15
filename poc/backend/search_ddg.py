"""DuckDuckGo search wrapper — free, no API key."""

from __future__ import annotations

import time

from backend.config import (
    REQUEST_DELAY_SECONDS,
    RESULTS_PER_QUERY,
    SEARCH_BACKENDS,
    SEARCH_BACKENDS_AGGREGATED,
    SEARCH_RETRY_DELAY_SECONDS,
    SEARCH_TIMEOUT_SECONDS,
)
from backend.models import SearchHit, SearchParams
from backend.regions import get_region_profile


def _get_ddgs():
    try:
        from ddgs import DDGS

        return DDGS
    except ImportError:
        from duckduckgo_search import DDGS

        return DDGS


def _parse_results(results: list[dict], query: str) -> list[SearchHit]:
    hits: list[SearchHit] = []
    if not results:
        return hits

    for rank, item in enumerate(results, start=1):
        url = item.get("href") or item.get("url") or ""
        title = item.get("title") or ""
        snippet = item.get("body") or item.get("snippet") or ""
        if not url:
            continue
        hits.append(
            SearchHit(
                title=title.strip(),
                url=url.strip(),
                snippet=snippet.strip(),
                source_query=query,
                rank=rank,
            )
        )
    return hits


def _run_search(ddgs, query: str, search_region: str, backend: str) -> list[SearchHit]:
    results = ddgs.text(
        query,
        max_results=RESULTS_PER_QUERY,
        backend=backend,
        region=search_region,
    )
    return _parse_results(results, query)


def _search_one_query(ddgs, query: str, search_region: str) -> list[SearchHit]:
    last_error: Exception | None = None

    # First try: query all backends at once for maximum coverage.
    try:
        hits = _run_search(ddgs, query, search_region, SEARCH_BACKENDS_AGGREGATED)
        if hits:
            return hits
    except Exception as exc:
        last_error = exc

    # Fallback: try each backend individually (including Yahoo).
    for index, backend in enumerate(SEARCH_BACKENDS):
        try:
            hits = _run_search(ddgs, query, search_region, backend)
            if hits:
                return hits
        except Exception as exc:
            last_error = exc
            if index < len(SEARCH_BACKENDS) - 1:
                time.sleep(SEARCH_RETRY_DELAY_SECONDS)

    if last_error:
        raise last_error
    return []


def search_queries(
    queries: list[str],
    params: SearchParams | None = None,
) -> tuple[list[SearchHit], list[str]]:
    DDGS = _get_ddgs()
    hits: list[SearchHit] = []
    errors: list[str] = []

    profile = get_region_profile(
        params.region if params else "Worldwide",
        params.custom_region if params else "",
    )
    search_region = profile.search_region

    with DDGS(timeout=SEARCH_TIMEOUT_SECONDS) as ddgs:
        for query_index, query in enumerate(queries):
            if query_index > 0:
                time.sleep(REQUEST_DELAY_SECONDS)

            try:
                query_hits = _search_one_query(ddgs, query, search_region)
                hits.extend(query_hits)
            except Exception as exc:
                errors.append(f"Query '{query}' failed after retries: {exc}")

    return hits, errors

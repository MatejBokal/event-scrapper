"""Resolve official conference URLs from listing / ticket gateway pages."""

from __future__ import annotations

import concurrent.futures
import json
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from backend.config import (
    CONFERENCE_KEYWORDS,
    GATEWAY_PAGE_TIMEOUT_SECONDS,
    LISTING_MAX_PER_RUN,
    OFFICIAL_LINKS_PER_LISTING,
)
from backend.crawler import _open_playwright_session, fetch_gateway_page, fetch_single_page
from backend.playwright_fetcher import PlaywrightSession
from backend.domains import (
    domain,
    is_blocked_outbound_domain,
    is_gateway_domain,
    is_ticket_vendor_domain,
)
from backend.models import ListingDiscovery, SearchParams, SelectedSite
from backend.regions import get_region_profile

SKIP_EXTENSIONS = (
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".svg",
    ".zip",
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
    ".mp4",
    ".mp3",
)

OFFICIAL_LINK_MARKERS = (
    "official website",
    "official site",
    "visit website",
    "conference website",
    "event website",
    "organizer website",
    "organiser website",
    "learn more",
    "register now",
    "book now",
    "zur website",
    "offizielle website",
    "veranstalter",
    "mehr informationen",
    "event information",
    "organizer info",
)


def _field_tokens(field: str) -> list[str]:
    tokens: list[str] = []
    for part in field.lower().replace(",", " ").replace("/", " ").split():
        cleaned = part.strip()
        if len(cleaned) >= 3:
            tokens.append(cleaned)
    return tokens


def _normalize_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") or "/"
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def _score_official_candidate(
    url: str,
    anchor_text: str,
    params: SearchParams,
) -> float:
    profile = get_region_profile(params.region, params.custom_region)
    url_lower = url.lower()
    text_lower = anchor_text.lower()
    combined = f"{url_lower} {text_lower}"
    score = 0.0

    for keyword in CONFERENCE_KEYWORDS:
        if keyword in combined:
            score += 12
            break

    for token in _field_tokens(params.field):
        if token in combined:
            score += 8

    year = params.start_month.split("-")[0] if params.start_month else ""
    if year and year in combined:
        score += 10

    host = domain(url)
    for tld in profile.tlds:
        if host.endswith(tld) or tld.strip(".") in host:
            score += 18
            break

    for city in profile.cities:
        if city.lower() in combined:
            score += 10

    for country in profile.country_names:
        if country and country.lower() in combined:
            score += 6

    path = urlparse(url).path.lower()
    if any(k in path for k in ("conference", "summit", "event", "kongres", "konferenc")):
        score += 8

    if any(marker in text_lower for marker in OFFICIAL_LINK_MARKERS):
        score += 14

    if re.search(r"\b(20\d{2})\b", combined):
        score += 6

    return score


def _fetch_gateway_html(
    url: str,
    playwright: PlaywrightSession | None = None,
) -> tuple[str, str]:
    """Light fetch with a hard timeout so ticket pages cannot hang the run."""
    _ = playwright  # gateway resolution uses HTTP-only fetch_gateway_page
    timeout = max(15, int(GATEWAY_PAGE_TIMEOUT_SECONDS))
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(fetch_gateway_page, url)
    try:
        return future.result(timeout=timeout)
    except Exception:
        return url, ""
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _collect_json_ld_urls(data: object, urls: list[str]) -> None:
    if isinstance(data, dict):
        for key in ("url", "sameAs"):
            value = data.get(key)
            if isinstance(value, str) and value.startswith("http"):
                urls.append(value)
        organizer = data.get("organizer")
        if isinstance(organizer, dict):
            org_url = organizer.get("url")
            if isinstance(org_url, str) and org_url.startswith("http"):
                urls.append(org_url)
        for value in data.values():
            _collect_json_ld_urls(value, urls)
    elif isinstance(data, list):
        for item in data:
            _collect_json_ld_urls(item, urls)


def _extract_structured_urls(
    html: str,
    page_url: str,
    params: SearchParams,
) -> list[tuple[str, str, float]]:
    soup = BeautifulSoup(html, "lxml")
    candidates: dict[str, tuple[str, float]] = {}

    for tag in soup.find_all("meta"):
        prop = (tag.get("property") or tag.get("name") or "").lower()
        if prop not in ("og:url", "twitter:url"):
            continue
        content = (tag.get("content") or "").strip()
        if not content.startswith("http"):
            continue
        if is_blocked_outbound_domain(content) or domain(content) == domain(page_url):
            continue
        score = _score_official_candidate(content, "", params)
        if score >= 8:
            candidates[_normalize_url(content)] = ("", score)

    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string or script.get_text() or ""
        if not raw.strip():
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        structured_urls: list[str] = []
        _collect_json_ld_urls(payload, structured_urls)
        for candidate_url in structured_urls:
            if is_blocked_outbound_domain(candidate_url) or domain(candidate_url) == domain(page_url):
                continue
            score = _score_official_candidate(candidate_url, "", params)
            if score >= 8:
                normalized = _normalize_url(candidate_url)
                existing = candidates.get(normalized)
                if existing is None or score > existing[1]:
                    candidates[normalized] = ("", score)

    return [(url, title, score) for url, (title, score) in candidates.items()]


def extract_official_urls(
    html: str,
    listing_url: str,
    params: SearchParams,
) -> list[tuple[str, str, float]]:
    soup = BeautifulSoup(html, "lxml")
    listing_host = domain(listing_url)
    candidates: dict[str, tuple[str, float]] = {}

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue

        absolute = urljoin(listing_url, href)
        parsed = urlparse(absolute)
        if parsed.scheme not in ("http", "https"):
            continue

        path_lower = parsed.path.lower()
        if any(path_lower.endswith(ext) for ext in SKIP_EXTENSIONS):
            continue

        if domain(absolute) == listing_host:
            continue

        if is_blocked_outbound_domain(absolute):
            continue

        anchor_text = anchor.get_text(" ", strip=True)
        link_score = _score_official_candidate(absolute, anchor_text, params)
        if link_score < 8:
            continue

        normalized = _normalize_url(absolute)
        title = anchor_text or parsed.netloc
        existing = candidates.get(normalized)
        if existing is None or link_score > existing[1]:
            candidates[normalized] = (title, link_score)

    ranked = sorted(
        ((url, title, score) for url, (title, score) in candidates.items()),
        key=lambda item: item[2],
        reverse=True,
    )
    structured = _extract_structured_urls(html, listing_url, params)
    merged: dict[str, tuple[str, float]] = {
        url: (title, score) for url, title, score in ranked
    }
    for url, title, score in structured:
        existing = merged.get(url)
        if existing is None or score > existing[1]:
            merged[url] = (title or existing[0] if existing else "", score)
    final_ranked = sorted(
        ((url, title, score) for url, (title, score) in merged.items()),
        key=lambda item: item[2],
        reverse=True,
    )
    return final_ranked[:OFFICIAL_LINKS_PER_LISTING]


def resolve_gateway_site(
    site: SelectedSite,
    params: SearchParams,
    playwright: PlaywrightSession | None = None,
) -> tuple[list[SelectedSite], list[ListingDiscovery]]:
    final_url, html = _fetch_gateway_html(site.url, playwright=playwright)
    if not html:
        return [], []

    source_kind = "ticket" if is_ticket_vendor_domain(site.url) else "listing"
    discoveries: list[ListingDiscovery] = []
    official_sites: list[SelectedSite] = []

    for official_url, title, link_score in extract_official_urls(html, final_url, params):
        discoveries.append(
            ListingDiscovery(
                listing_url=site.url,
                listing_title=site.title,
                official_url=official_url,
                official_title=title,
                link_score=link_score,
            )
        )
        official_sites.append(
            SelectedSite(
                url=official_url,
                title=title or site.title,
                url_score=site.url_score + link_score,
                snippet=f"Discovered via {source_kind}: {site.url}",
                source=source_kind,
                discovered_from=site.url,
            )
        )

    return official_sites, discoveries


def resolve_listing_site(
    site: SelectedSite,
    params: SearchParams,
    playwright: PlaywrightSession | None = None,
) -> tuple[list[SelectedSite], list[ListingDiscovery]]:
    """Backward-compatible alias for resolve_gateway_site."""
    return resolve_gateway_site(site, params, playwright=playwright)


def expand_sites_via_listings(
    sites: list[SelectedSite],
    params: SearchParams,
) -> tuple[list[SelectedSite], list[SelectedSite], list[ListingDiscovery], list[str]]:
    """Split gateway pages (listings, ticket vendors) from official sites and resolve outbound URLs."""
    crawl_targets: list[SelectedSite] = []
    listing_sources: list[SelectedSite] = []
    discoveries: list[ListingDiscovery] = []
    errors: list[str] = []

    for site in sites:
        if is_gateway_domain(site.url):
            listing_sources.append(site)
        else:
            crawl_targets.append(site)

    gateways_processed = 0
    playwright = _open_playwright_session()
    try:
        for gateway in listing_sources:
            if gateways_processed >= LISTING_MAX_PER_RUN:
                break
            gateways_processed += 1

            kind = "ticket page" if is_ticket_vendor_domain(gateway.url) else "listing page"
            try:
                official_sites, found = resolve_gateway_site(gateway, params, playwright)
                discoveries.extend(found)
                crawl_targets.extend(official_sites)
            except Exception as exc:
                errors.append(f"Could not read {kind} {gateway.url}: {exc}")
    finally:
        if playwright is not None:
            playwright.close()

    deduped: list[SelectedSite] = []
    seen_urls: set[str] = set()
    for site in crawl_targets:
        normalized = site.url.rstrip("/")
        if normalized in seen_urls:
            continue
        seen_urls.add(normalized)
        deduped.append(site)

    if params.max_conferences > 0 and len(deduped) > params.max_conferences:
        deduped = deduped[: params.max_conferences]

    return deduped, listing_sources, discoveries, errors

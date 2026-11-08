"""Orchestrate the full PoC v1.1 Confiva lead generation pipeline."""

from __future__ import annotations

from urllib.parse import urlparse

from backend.confidence import apply_confidence
from backend.crawler import crawl_site, get_conference_name, probe_page
from backend.domains import (
    is_denylisted_domain,
    is_gateway_domain,
    is_listing_domain,
    is_skip_crawl_domain,
    is_spam_domain,
    is_ticket_vendor_domain,
)
from backend.event_filter import filter_event_hits
from backend.event_keyword_gate import assess_keyword_gate, site_root_url
from backend.event_keywords import event_keywords_for_region
from backend.event_presence import EventPresence, TIME_PRESENCE_BONUS, assess_event_presence
from backend.extractor import extract_emails_from_pages
from backend.geo_filter import apply_geo_scoring
from backend.lead_ranker import build_leads
from backend.config import LISTING_MAX_PER_RUN
from backend.app_logging import get_logger
from backend.listing_discovery import expand_sites_via_listings
from backend.models import (
    ConferenceLlmMetadata,
    ContactResult,
    CrawledPage,
    PipelineResult,
    PipelineStats,
    ProgressCallback,
    SearchParams,
    SelectedSite,
)
from backend.query_builder import build_queries
from backend.regions import get_region_profile
from backend.search_ddg import search_queries
from backend.url_prefilter import classify_hopeless_url
from backend.url_scorer import select_sites

log = get_logger("pipeline")
from backend.validator import validate_hits


def _emit(callback: ProgressCallback | None, stage: str, payload: dict) -> None:
    if callback:
        callback(stage, payload)


def _normalize_manual_url(raw: str) -> str | None:
    cleaned = raw.strip()
    if not cleaned:
        return None
    if not cleaned.startswith(("http://", "https://")):
        cleaned = f"https://{cleaned}"
    parsed = urlparse(cleaned)
    if not parsed.netloc:
        return None
    path = parsed.path.rstrip("/") or "/"
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def _manual_selected_site(raw: str) -> tuple[SelectedSite | None, str | None]:
    normalized = _normalize_manual_url(raw)
    if not normalized:
        return None, None
    if is_spam_domain(normalized) or is_denylisted_domain(normalized):
        return None, f"Manual URL blocked (spam/denylist): {normalized}"
    return (
        SelectedSite(
            url=normalized,
            title="Manual official URL",
            url_score=999.0,
            snippet="",
            source="manual",
        ),
        None,
    )


def _prepend_manual_site(
    crawl_targets: list[SelectedSite],
    manual_site: SelectedSite,
) -> list[SelectedSite]:
    normalized = manual_site.url.rstrip("/")
    without_dup = [site for site in crawl_targets if site.url.rstrip("/") != normalized]
    return [manual_site, *without_dup]


def run_pipeline(
    params: SearchParams,
    on_progress: ProgressCallback | None = None,
) -> PipelineResult:
    result = PipelineResult(params=params)

    try:
        log.info(
            "PoC pipeline started — field=%s region=%s months=%s",
            params.field,
            params.region,
            params.selected_months,
        )
        manual_site, manual_error = _manual_selected_site(params.manual_official_url)
        if manual_error:
            result.errors.append(manual_error)

        queries = build_queries(params)
        _emit(
            on_progress,
            "searching",
            {"message": "Running localized web search...", "queries": queries},
        )

        search_hits, search_errors = search_queries(queries, params)
        result.stats.queries_run = len(queries)
        result.raw_search_hits = list(search_hits)
        for error in search_errors:
            result.errors.append(error)

        if not search_hits and not manual_site:
            if search_errors:
                result.errors.append(
                    "All search queries failed. Check your internet connection and try again."
                )
            else:
                result.errors.append(
                    "Search returned no results. Try broader terms, more months, "
                    "or paste a manual official URL."
                )
            return result

        if search_hits:
            filtered_hits, filtered_out = filter_event_hits(search_hits, params)
            result.filtered_urls = filtered_out
            result.stats.filtered_hits = len(filtered_out)

            geo_scored = apply_geo_scoring(filtered_hits, params)
            result.search_hits = geo_scored
            result.stats.search_hits = len(geo_scored)

            _emit(
                on_progress,
                "scoring",
                {
                    "message": "Scoring and selecting conference sites...",
                    "hits": len(geo_scored),
                    "filtered_out": len(filtered_out),
                },
            )

            selected, skipped = select_sites(geo_scored, params)
            result.skipped_urls = skipped
        else:
            result.stats.search_hits = 0
            selected = []
            _emit(
                on_progress,
                "scoring",
                {"message": "Skipping site selection — using manual official URL only."},
            )

        if manual_site and is_gateway_domain(manual_site.url):
            selected = _prepend_manual_site(selected, manual_site)

        _emit(
            on_progress,
            "listing_discovery",
            {
                "message": "Resolving official URLs from listing and ticket pages...",
                "listing_candidates": sum(1 for site in selected if is_listing_domain(site.url)),
                "ticket_candidates": sum(1 for site in selected if is_ticket_vendor_domain(site.url)),
            },
        )

        crawl_targets, listing_sources, discoveries, listing_errors = expand_sites_via_listings(
            selected,
            params,
        )
        if manual_site and not is_gateway_domain(manual_site.url):
            crawl_targets = _prepend_manual_site(crawl_targets, manual_site)

        result.selected_sites = crawl_targets
        result.listing_sources = listing_sources
        result.listing_discoveries = discoveries
        result.listing_warnings = listing_errors
        result.stats.sites_selected = len(crawl_targets)
        result.stats.listing_pages_processed = min(len(listing_sources), LISTING_MAX_PER_RUN)
        result.stats.official_urls_from_listings = len(discoveries)

        if not crawl_targets:
            result.errors.append(
                "No official conference sites to crawl. Listing pages may not have linked "
                "to official sites — try a different region, more months, or a manual official URL."
            )
            return result

        crawl_result = run_crawl_phase(crawl_targets, params, on_progress=on_progress)
        result.crawled_pages = crawl_result.crawled_pages
        result.pages_without_emails = crawl_result.pages_without_emails
        result.contacts = crawl_result.contacts
        result.leads = crawl_result.leads
        result.stats.pages_crawled = crawl_result.stats.pages_crawled
        result.stats.emails_found = crawl_result.stats.emails_found
        result.stats.leads_found = crawl_result.stats.leads_found
        result.stats.pages_without_emails = crawl_result.stats.pages_without_emails
        result.errors.extend(crawl_result.errors)

        log.info(
            "PoC pipeline finished — leads=%d emails=%d pages=%d",
            result.stats.leads_found,
            result.stats.emails_found,
            result.stats.pages_crawled,
        )

        _emit(
            on_progress,
            "done",
            {
                "message": "Pipeline complete.",
                "leads_found": result.stats.leads_found,
            },
        )

    except Exception as exc:
        result.errors.append(str(exc))
        log.exception("PoC pipeline failed: %s", exc)
        _emit(on_progress, "error", {"message": str(exc)})

    return result


def run_discovery(
    params: SearchParams,
    on_progress: ProgressCallback | None = None,
) -> PipelineResult:
    """Search, score, and resolve listing pages — no crawling."""
    result = PipelineResult(params=params)

    try:
        log.info(
            "PoC discovery started — field=%s region=%s months=%s",
            params.field,
            params.region,
            params.selected_months,
        )
        manual_site, manual_error = _manual_selected_site(params.manual_official_url)
        if manual_error:
            result.errors.append(manual_error)

        queries = build_queries(params)
        _emit(
            on_progress,
            "searching",
            {"message": "Running localized web search...", "queries": queries},
        )

        search_hits, search_errors = search_queries(queries, params)
        result.stats.queries_run = len(queries)
        result.raw_search_hits = list(search_hits)
        for error in search_errors:
            result.errors.append(error)

        if not search_hits and not manual_site:
            if search_errors:
                result.errors.append(
                    "All search queries failed. Check your internet connection and try again."
                )
            else:
                result.errors.append("Search returned no results.")
            return result

        if search_hits:
            filtered_hits, filtered_out = filter_event_hits(search_hits, params)
            result.filtered_urls = filtered_out
            result.stats.filtered_hits = len(filtered_out)

            geo_scored = apply_geo_scoring(filtered_hits, params)
            result.search_hits = geo_scored
            result.stats.search_hits = len(geo_scored)

            _emit(
                on_progress,
                "scoring",
                {
                    "message": "Scoring and selecting conference sites...",
                    "hits": len(geo_scored),
                    "filtered_out": len(filtered_out),
                },
            )

            selected, skipped = select_sites(geo_scored, params)
            result.skipped_urls = skipped
        else:
            result.stats.search_hits = 0
            selected = []
            _emit(
                on_progress,
                "scoring",
                {"message": "Skipping site selection — using manual official URL only."},
            )

        if manual_site and is_gateway_domain(manual_site.url):
            selected = _prepend_manual_site(selected, manual_site)

        _emit(
            on_progress,
            "listing_discovery",
            {
                "message": "Resolving official URLs from listing and ticket pages...",
                "listing_candidates": sum(1 for site in selected if is_listing_domain(site.url)),
                "ticket_candidates": sum(1 for site in selected if is_ticket_vendor_domain(site.url)),
            },
        )

        crawl_targets, listing_sources, discoveries, listing_errors = expand_sites_via_listings(
            selected,
            params,
        )
        if manual_site and not is_gateway_domain(manual_site.url):
            crawl_targets = _prepend_manual_site(crawl_targets, manual_site)

        result.selected_sites = crawl_targets
        result.listing_sources = listing_sources
        result.listing_discoveries = discoveries
        result.listing_warnings = listing_errors
        result.stats.sites_selected = len(crawl_targets)
        result.stats.listing_pages_processed = min(len(listing_sources), LISTING_MAX_PER_RUN)
        result.stats.official_urls_from_listings = len(discoveries)

        if not crawl_targets:
            result.errors.append(
                "No official conference sites to crawl. Listing pages may not have linked "
                "to official sites — try a different region, more months, or a manual official URL."
            )

        _emit(
            on_progress,
            "discovery_done",
            {
                "message": "Discovery complete.",
                "crawl_targets": len(crawl_targets),
                "search_hits": len(result.search_hits),
            },
        )

    except Exception as exc:
        result.errors.append(str(exc))
        log.exception("PoC discovery failed: %s", exc)
        _emit(on_progress, "error", {"message": str(exc)})

    return result


def _city_allowlist_for_params(params: SearchParams) -> list[str]:
    if params.city_allowlist:
        return list(params.city_allowlist)
    profile = get_region_profile(params.region, params.custom_region)
    cities = list(profile.cities)
    if params.target_city.strip():
        cities = [params.target_city.strip(), *cities]
    return cities


def _event_keywords_for_params(params: SearchParams) -> list[str]:
    if params.event_keywords:
        return list(params.event_keywords)
    return event_keywords_for_region(params.region, params.custom_region)


def _probe_start_and_root(site: SelectedSite) -> list[CrawledPage]:
    pages: list[CrawledPage] = []
    start = probe_page(site.url, conference_url=site.url)
    if start is not None:
        pages.append(start)
    root = site_root_url(site.url)
    if root.rstrip("/") != site.url.rstrip("/"):
        root_page = probe_page(root, conference_url=site.url)
        if root_page is not None:
            pages.append(root_page)
    return pages


def _merge_presence_metadata(
    existing: ConferenceLlmMetadata | None,
    presence: EventPresence,
) -> ConferenceLlmMetadata:
    meta = existing or ConferenceLlmMetadata()
    if presence.event_date and not meta.start_date:
        meta.start_date = presence.event_date
        meta.month_year = presence.event_date.strftime("%Y-%m")
    if presence.matched_city and not meta.location:
        meta.location = presence.matched_city
    return meta


def run_crawl_phase(
    crawl_targets: list[SelectedSite],
    params: SearchParams,
    on_progress: ProgressCallback | None = None,
) -> PipelineResult:
    """Crawl official conference sites and extract leads."""
    result = PipelineResult(params=params)
    all_contacts: list[ContactResult] = []
    all_crawled_pages = []
    pages_without_emails = []
    conference_metadata_by_url: dict[str, object] = {}
    city_allowlist = _city_allowlist_for_params(params)
    event_keywords = _event_keywords_for_params(params)

    if not crawl_targets:
        result.errors.append("No crawl targets provided.")
        return result

    try:
        for index, site in enumerate(crawl_targets, start=1):
            _emit(
                on_progress,
                "crawling",
                {
                    "message": f"Crawling site {index}/{len(crawl_targets)}...",
                    "current_site": site.url,
                    "sites_done": index - 1,
                    "sites_total": len(crawl_targets),
                },
            )

            if is_skip_crawl_domain(site.url):
                continue

            hopeless = classify_hopeless_url(site.url)
            if hopeless:
                log.info("Skipping %s — hopeless URL (%s)", site.url, hopeless)
                _emit(
                    on_progress,
                    "queue_skip",
                    {
                        "message": f"Skipped {site.url}: {hopeless}",
                        "url": site.url,
                        "reason": hopeless,
                        "decision": "dont_crawl",
                    },
                )
                continue

            probe_pages = _probe_start_and_root(site)
            keyword = assess_keyword_gate(probe_pages, event_keywords)
            if not keyword.passes:
                log.info(
                    "Skipping %s — keyword gate failed (%s)",
                    site.url,
                    keyword.reason,
                )
                _emit(
                    on_progress,
                    "keyword_rejected",
                    {
                        "message": f"Skipped {site.url}: {keyword.reason}",
                        "url": site.url,
                        "reason": keyword.reason,
                        "decision": "dont_crawl",
                    },
                )
                continue

            try:
                pages = crawl_site(site).pages
            except Exception as exc:
                result.errors.append(f"Crawl failed for {site.url}: {exc}")
                continue

            if not pages and probe_pages:
                pages = probe_pages

            all_crawled_pages.extend(pages)
            result.stats.pages_crawled += len(pages)

            presence = assess_event_presence(pages, city_allowlist)
            if not presence.passes:
                log.info(
                    "Skipping %s — event presence failed (%s)",
                    site.url,
                    presence.reason,
                )
                _emit(
                    on_progress,
                    "presence_rejected",
                    {
                        "message": (
                            f"Skipped {site.url}: needs page date + city "
                            f"({presence.reason})"
                        ),
                        "url": site.url,
                        "reason": presence.reason,
                        "decision": "drop_lead",
                    },
                )
                continue

            conference_name = get_conference_name(pages) or site.title
            extract_result = extract_emails_from_pages(pages, params, conference_name)
            metadata = _merge_presence_metadata(extract_result.conference_metadata, presence)
            conference_metadata_by_url[site.url.rstrip("/")] = metadata
            contacts = validate_hits(extract_result.hits, params)
            contacts = [
                contact
                for contact in contacts
                if not is_gateway_domain(contact.conference_url)
                and not is_gateway_domain(contact.source_url)
            ]

            page_texts = {page.url: page.extracted_text for page in pages}
            contacts = apply_confidence(contacts, page_texts)
            if presence.has_time:
                for contact in contacts:
                    contact.confidence = min(100, contact.confidence + TIME_PRESENCE_BONUS)

            if not contacts:
                pages_without_emails.extend(pages)

            all_contacts.extend(contacts)

        result.crawled_pages = all_crawled_pages
        result.pages_without_emails = pages_without_emails
        result.contacts = all_contacts
        result.leads = build_leads(all_contacts, params, conference_metadata_by_url)
        result.stats.emails_found = len(all_contacts)
        result.stats.leads_found = len(result.leads)
        result.stats.pages_without_emails = len(pages_without_emails)

    except Exception as exc:
        result.errors.append(str(exc))
        log.exception("PoC crawl phase failed: %s", exc)
        _emit(on_progress, "error", {"message": str(exc)})

    return result

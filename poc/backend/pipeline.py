"""Orchestrate the full PoC v1.1 Confiva lead generation pipeline."""

from __future__ import annotations

from backend.confidence import apply_confidence
from backend.crawler import crawl_site, get_conference_name
from backend.domains import is_listing_domain
from backend.event_filter import filter_event_hits
from backend.extractor import extract_emails_from_pages
from backend.geo_filter import apply_geo_scoring
from backend.lead_ranker import build_leads
from backend.config import LISTING_MAX_PER_RUN
from backend.listing_discovery import expand_sites_via_listings
from backend.models import (
    ContactResult,
    PipelineResult,
    PipelineStats,
    ProgressCallback,
    SearchHit,
    SearchParams,
)
from backend.query_builder import build_queries
from backend.search_ddg import search_queries
from backend.url_scorer import select_sites
from backend.validator import validate_hits


def _emit(callback: ProgressCallback | None, stage: str, payload: dict) -> None:
    if callback:
        callback(stage, payload)


def run_pipeline(
    params: SearchParams,
    on_progress: ProgressCallback | None = None,
) -> PipelineResult:
    result = PipelineResult(params=params)
    all_contacts: list[ContactResult] = []
    all_crawled_pages = []
    pages_without_emails = []

    try:
        queries = build_queries(params)
        _emit(
            on_progress,
            "searching",
            {"message": "Running localized web search...", "queries": queries},
        )

        if params.manual_url.strip():
            search_hits: list[SearchHit] = []
            search_errors: list[str] = []
        else:
            search_hits, search_errors = search_queries(queries, params)
            result.stats.queries_run = len(queries)
            for error in search_errors:
                result.errors.append(error)

        if not search_hits and not params.manual_url.strip():
            if search_errors:
                result.errors.append(
                    "All search queries failed. Check your internet connection and try again, "
                    "or paste a manual official URL."
                )
            else:
                result.errors.append("Search returned no results. Try broader terms or a manual URL.")
            return result

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

        selected, skipped = select_sites(
            geo_scored,
            params,
            manual_url=params.manual_url,
        )
        result.skipped_urls = skipped

        _emit(
            on_progress,
            "listing_discovery",
            {
                "message": "Resolving official URLs from listing pages...",
                "listing_candidates": sum(1 for site in selected if is_listing_domain(site.url)),
            },
        )

        crawl_targets, listing_sources, discoveries, listing_errors = expand_sites_via_listings(
            selected,
            params,
        )
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
                "to official sites — try a manual URL, Custom region, or broader search terms."
            )
            return result

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

            if is_listing_domain(site.url):
                continue

            try:
                pages = crawl_site(site)
            except Exception as exc:
                result.errors.append(f"Crawl failed for {site.url}: {exc}")
                continue

            all_crawled_pages.extend(pages)
            result.stats.pages_crawled += len(pages)

            conference_name = get_conference_name(pages) or site.title
            raw_hits = extract_emails_from_pages(pages, params, conference_name)
            contacts = validate_hits(raw_hits, params)
            contacts = [
                contact
                for contact in contacts
                if not is_listing_domain(contact.conference_url)
                and not is_listing_domain(contact.source_url)
            ]

            page_texts = {page.url: page.extracted_text for page in pages}
            contacts = apply_confidence(contacts, page_texts)

            if not contacts:
                pages_without_emails.extend(pages)

            all_contacts.extend(contacts)

        result.crawled_pages = all_crawled_pages
        result.pages_without_emails = pages_without_emails
        result.contacts = all_contacts
        result.leads = build_leads(all_contacts, params)
        result.stats.emails_found = len(all_contacts)
        result.stats.leads_found = len(result.leads)
        result.stats.pages_without_emails = len(pages_without_emails)

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
        _emit(on_progress, "error", {"message": str(exc)})

    return result

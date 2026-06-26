from __future__ import annotations

import uuid
from datetime import datetime, timezone

from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Conference, CrawledPage, CrawlTarget, SearchResult, SearchRun, SourceEvidence
from app.services.poc_bridge import (
    CrawlSiteResult,
    SearchHit,
    SearchParams,
    SelectedSite,
    apply_geo_scoring,
    crawl_site,
    expand_sites_via_listings,
    filter_event_hits,
    get_conference_name,
    is_denylisted_domain,
    is_listing_domain,
    is_spam_domain,
    select_sites,
)
from app.utils import normalize_official_url

EVIDENCE_SNIPPET_MAX = 500


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


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


def _prepend_manual_site(targets: list[SelectedSite], manual_site: SelectedSite) -> list[SelectedSite]:
    normalized = manual_site.url.rstrip("/")
    without_dup = [site for site in targets if site.url.rstrip("/") != normalized]
    return [manual_site, *without_dup]


def _hits_from_results(results: list[SearchResult]) -> list[SearchHit]:
    return [
        SearchHit(
            title=row.title or "",
            url=row.url,
            snippet=row.snippet or "",
            source_query=row.source_query or "",
            rank=row.rank or 0,
            url_score=float(row.url_score) if row.url_score is not None else 0.0,
        )
        for row in results
    ]


def _upsert_conference(
    db: Session,
    run: SearchRun,
    site: SelectedSite,
    pages,
) -> Conference:
    normalized = normalize_official_url(site.url)
    conference = db.scalar(
        select(Conference).where(Conference.official_url_normalized == normalized)
    )
    name = get_conference_name(pages) or site.title or normalized

    if conference is None:
        conference = Conference(
            id=uuid.uuid4(),
            name=name,
            field=run.field,
            region=run.region,
            official_url=site.url,
            official_url_normalized=normalized,
            status="crawled",
            first_seen_run_id=run.id,
        )
        db.add(conference)
    else:
        conference.name = name or conference.name
        conference.field = run.field
        conference.region = run.region
        conference.status = "crawled"
        conference.crawl_block_reason = None
        conference.crawl_http_status = None
        conference.crawl_block_detail = None
        conference.crawl_blocked_at = None
        if conference.first_seen_run_id is None:
            conference.first_seen_run_id = run.id

    db.flush()
    return conference


def _upsert_crawl_blocked(
    db: Session,
    run: SearchRun,
    site: SelectedSite,
    result: CrawlSiteResult,
) -> Conference:
    normalized = normalize_official_url(site.url)
    conference = db.scalar(
        select(Conference).where(Conference.official_url_normalized == normalized)
    )
    name = site.title or normalized
    reason = result.block_reason or "empty"
    detail = result.error_message

    if conference is None:
        conference = Conference(
            id=uuid.uuid4(),
            name=name,
            field=run.field,
            region=run.region,
            official_url=site.url,
            official_url_normalized=normalized,
            status="crawl_blocked",
            crawl_block_reason=reason,
            crawl_http_status=result.http_status,
            crawl_block_detail=detail,
            crawl_blocked_at=_utcnow(),
            first_seen_run_id=run.id,
        )
        db.add(conference)
    else:
        conference.name = name or conference.name
        conference.field = run.field
        conference.region = run.region
        conference.status = "crawl_blocked"
        conference.crawl_block_reason = reason
        conference.crawl_http_status = result.http_status
        conference.crawl_block_detail = detail
        conference.crawl_blocked_at = _utcnow()

    db.flush()
    return conference


def _is_crawl_blocked(db: Session, url: str) -> bool:
    try:
        normalized = normalize_official_url(url)
    except ValueError:
        return False
    conference = db.scalar(
        select(Conference).where(Conference.official_url_normalized == normalized)
    )
    return conference is not None and conference.status == "crawl_blocked"


def _persist_crawl_target(
    db: Session,
    run_id: uuid.UUID,
    site: SelectedSite,
    conference_id: uuid.UUID | None = None,
) -> CrawlTarget:
    target = CrawlTarget(
        id=uuid.uuid4(),
        search_run_id=run_id,
        conference_id=conference_id,
        url=site.url,
        title=site.title,
        source=site.source,
        discovered_from=site.discovered_from or None,
        url_score=site.url_score,
    )
    db.add(target)
    return target


def _persist_crawled_page(
    db: Session,
    run_id: uuid.UUID,
    conference_id: uuid.UUID,
    page,
) -> CrawledPage:
    crawled = CrawledPage(
        id=uuid.uuid4(),
        conference_id=conference_id,
        search_run_id=run_id,
        url=page.url,
        title=page.title,
        page_type=page.page_type,
        extracted_text=page.extracted_text,
    )
    db.add(crawled)

    snippet = (page.extracted_text or "")[:EVIDENCE_SNIPPET_MAX].strip()
    if snippet:
        db.add(
            SourceEvidence(
                id=uuid.uuid4(),
                conference_id=conference_id,
                search_run_id=run_id,
                source_url=page.url,
                source_title=page.title,
                extracted_text_snippet=snippet,
                evidence_type=page.page_type or "crawled_page",
            )
        )

    return crawled


def _fallback_official_sites(geo_scored: list[SearchHit], limit: int) -> list[SelectedSite]:
    seen: set[str] = set()
    sites: list[SelectedSite] = []

    for hit in sorted(geo_scored, key=lambda h: h.url_score, reverse=True):
        if is_listing_domain(hit.url):
            continue
        try:
            normalized = normalize_official_url(hit.url)
        except ValueError:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        sites.append(
            SelectedSite(
                url=hit.url,
                title=hit.title,
                url_score=hit.url_score,
                snippet=hit.snippet,
                source="search",
            )
        )
        if len(sites) >= limit:
            break

    return sites


def _link_targets_to_conference(
    db: Session,
    run_id: uuid.UUID,
    site_url: str,
    conference_id: uuid.UUID,
) -> None:
    for target in db.scalars(
        select(CrawlTarget).where(
            CrawlTarget.search_run_id == run_id,
            CrawlTarget.url == site_url,
        )
    ).all():
        target.conference_id = conference_id


def _crawl_and_persist_site(
    db: Session,
    run: SearchRun,
    site: SelectedSite,
    errors: list[str],
    *,
    force: bool = False,
) -> tuple[int, int, int, int]:
    """Returns (pages_crawled, conferences_upserted, sites_blocked, sites_skipped)."""
    if is_listing_domain(site.url):
        _persist_crawl_target(db, run.id, site)
        return 0, 0, 0, 0

    if not force and _is_crawl_blocked(db, site.url):
        _persist_crawl_target(db, run.id, site)
        errors.append(f"Skipped crawl (previously blocked): {site.url}")
        return 0, 0, 0, 1

    _persist_crawl_target(db, run.id, site)

    try:
        result = crawl_site(site)
    except Exception as exc:
        errors.append(f"Crawl failed for {site.url}: {exc}")
        blocked = _upsert_crawl_blocked(
            db,
            run,
            site,
            CrawlSiteResult(block_reason="exception", error_message=str(exc)),
        )
        _link_targets_to_conference(db, run.id, site.url, blocked.id)
        return 0, 0, 1, 0

    if result.blocked:
        blocked = _upsert_crawl_blocked(db, run, site, result)
        _link_targets_to_conference(db, run.id, site.url, blocked.id)
        label = result.http_status or result.block_reason
        errors.append(f"Crawl blocked ({label}): {site.url}")
        return 0, 0, 1, 0

    if not result.pages:
        return 0, 0, 0, 0

    conference = _upsert_conference(db, run, site, result.pages)
    _link_targets_to_conference(db, run.id, site.url, conference.id)

    pages_crawled = 0
    for page in result.pages:
        _persist_crawled_page(db, run.id, conference.id, page)
        pages_crawled += 1

    return pages_crawled, 1, 0, 0


def execute_crawl_run(db: Session, run: SearchRun) -> SearchRun:
    run = db.scalar(
        select(SearchRun).where(SearchRun.id == run.id).options(joinedload(SearchRun.results))
    )
    if run is None:
        raise ValueError("Search run not found")
    if not run.results:
        raise ValueError("Search run has no results — run search first")

    params = SearchParams(
        field=run.field,
        region=run.region,
        selected_months=tuple(run.selected_months),
        contact_type=run.contact_type,
        max_conferences=run.max_conferences,
        manual_official_url=run.manual_official_url or "",
    )

    errors = list(run.errors or [])
    manual_site, manual_error = _manual_selected_site(params.manual_official_url)
    if manual_error:
        errors.append(manual_error)

    run.status = "running"
    db.commit()
    db.refresh(run)

    raw_hits = _hits_from_results(run.results)
    filtered_hits, _filtered_out = filter_event_hits(raw_hits, params)
    geo_scored = apply_geo_scoring(filtered_hits, params)
    selected, _skipped = select_sites(geo_scored, params)

    if manual_site and is_listing_domain(manual_site.url):
        selected = _prepend_manual_site(selected, manual_site)

    crawl_targets, listing_sources, _discoveries, listing_errors = expand_sites_via_listings(
        selected,
        params,
    )
    errors.extend(listing_errors)

    for listing in listing_sources:
        _persist_crawl_target(db, run.id, listing)

    if manual_site and not is_listing_domain(manual_site.url):
        crawl_targets = _prepend_manual_site(crawl_targets, manual_site)

    if not crawl_targets:
        crawl_targets = _fallback_official_sites(geo_scored, params.max_conferences)
        if crawl_targets:
            errors.append(
                "Listing discovery found no official URLs; used top non-listing search hits instead"
            )

    if not crawl_targets:
        errors.append("No official conference sites to crawl")
        run.status = "failed"
        run.errors = errors
        run.finished_at = _utcnow()
        db.commit()
        db.refresh(run)
        return run

    pages_crawled = 0
    conferences_upserted = 0
    sites_blocked = 0
    sites_skipped = 0
    tried_urls: set[str] = set()
    manual_normalized = None
    if manual_site:
        try:
            manual_normalized = normalize_official_url(manual_site.url)
        except ValueError:
            manual_normalized = None

    for site in crawl_targets:
        tried_urls.add(site.url.rstrip("/"))
        force = False
        if manual_normalized:
            try:
                force = normalize_official_url(site.url) == manual_normalized
            except ValueError:
                force = False
        crawled, upserted, blocked, skipped = _crawl_and_persist_site(
            db, run, site, errors, force=force
        )
        pages_crawled += crawled
        conferences_upserted += upserted
        sites_blocked += blocked
        sites_skipped += skipped

    if pages_crawled == 0:
        retry_targets = [
            site
            for site in _fallback_official_sites(geo_scored, params.max_conferences)
            if site.url.rstrip("/") not in tried_urls
        ]
        if retry_targets:
            errors.append(
                "First crawl pass returned no pages; retrying with alternate non-listing search hits"
            )
            for site in retry_targets:
                tried_urls.add(site.url.rstrip("/"))
                crawled, upserted, blocked, skipped = _crawl_and_persist_site(
                    db, run, site, errors
                )
                pages_crawled += crawled
                conferences_upserted += upserted
                sites_blocked += blocked
                sites_skipped += skipped
                if pages_crawled > 0:
                    break

    stats = dict(run.stats or {})
    stats.update(
        {
            "sites_selected": len(crawl_targets),
            "pages_crawled": pages_crawled,
            "conferences_upserted": conferences_upserted,
            "sites_crawl_blocked": sites_blocked,
            "sites_skipped_blocked": sites_skipped,
        }
    )

    run.stats = stats
    run.errors = errors
    run.status = "failed" if pages_crawled == 0 and errors else "completed"
    run.finished_at = _utcnow()
    db.commit()
    db.refresh(run)
    return run

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import CrawledPage, SearchQuery, SearchResult, SearchRun
from app.schemas.search_run import CrawledPageRead, SearchRunDetail
from app.services.poc_bridge import SearchParams, build_queries, ddg_search


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_search_run_record(
    db: Session,
    params: SearchParams,
) -> SearchRun:
    run = SearchRun(
        id=uuid.uuid4(),
        field=params.field,
        region=params.region,
        selected_months=list(params.selected_months),
        contact_type=params.contact_type,
        max_conferences=params.max_conferences,
        manual_official_url=params.manual_official_url or None,
        status="pending",
        stats={},
        errors=[],
    )
    db.add(run)
    db.flush()
    return run


def persist_queries(db: Session, run_id: uuid.UUID, queries: list[str]) -> None:
    for index, query_text in enumerate(queries):
        db.add(
            SearchQuery(
                id=uuid.uuid4(),
                search_run_id=run_id,
                query_text=query_text,
                order_index=index,
            )
        )


def persist_raw_hits(db: Session, run_id: uuid.UUID, hits) -> int:
    for hit in hits:
        db.add(
            SearchResult(
                id=uuid.uuid4(),
                search_run_id=run_id,
                title=hit.title,
                url=hit.url,
                snippet=hit.snippet,
                source_query=hit.source_query,
                rank=hit.rank,
                url_score=getattr(hit, "url_score", None) or None,
                filter_status="raw",
            )
        )
    return len(hits)


def execute_search_run(db: Session, run: SearchRun, *, execute_search: bool = True) -> SearchRun:
    params = SearchParams(
        field=run.field,
        region=run.region,
        selected_months=tuple(run.selected_months),
        contact_type=run.contact_type,
        max_conferences=run.max_conferences,
        manual_official_url=run.manual_official_url or "",
    )

    run.status = "running"
    db.commit()
    db.refresh(run)

    queries = build_queries(params)
    persist_queries(db, run.id, queries)

    if not execute_search:
        run.status = "pending"
        run.stats = {"queries_run": len(queries), "search_hits": 0}
        run.errors = []
        db.commit()
        db.refresh(run)
        return run

    errors: list[str] = []
    hit_count = 0
    status = "completed"

    try:
        hits, search_errors = ddg_search(queries, params)
        errors.extend(search_errors)
        hit_count = persist_raw_hits(db, run.id, hits)
        if hit_count == 0 and errors:
            status = "failed"
    except Exception as exc:
        errors.append(str(exc))
        status = "failed"

    run.status = status
    run.stats = {"queries_run": len(queries), "search_hits": hit_count}
    run.errors = errors
    run.finished_at = _utcnow()
    db.commit()
    db.refresh(run)
    return run


def get_search_run_detail(db: Session, run_id: uuid.UUID) -> SearchRun | None:
    return db.scalar(
        select(SearchRun)
        .where(SearchRun.id == run_id)
        .options(
            joinedload(SearchRun.queries),
            joinedload(SearchRun.results),
            joinedload(SearchRun.crawl_targets),
        )
    )


def build_search_run_detail(db: Session, run: SearchRun) -> SearchRunDetail:
    crawled_pages = db.scalars(
        select(CrawledPage)
        .where(CrawledPage.search_run_id == run.id)
        .order_by(CrawledPage.crawled_at.desc())
    ).all()

    page_reads = [
        CrawledPageRead(
            id=page.id,
            conference_id=page.conference_id,
            url=page.url,
            title=page.title,
            page_type=page.page_type,
            text_length=len(page.extracted_text or ""),
            crawled_at=page.crawled_at,
        )
        for page in crawled_pages
    ]

    return SearchRunDetail(
        id=run.id,
        field=run.field,
        region=run.region,
        selected_months=run.selected_months,
        contact_type=run.contact_type,
        max_conferences=run.max_conferences,
        manual_official_url=run.manual_official_url,
        status=run.status,
        stats=run.stats,
        errors=run.errors,
        created_at=run.created_at,
        finished_at=run.finished_at,
        queries=run.queries,
        results=run.results,
        crawl_targets=run.crawl_targets,
        crawled_pages=page_reads,
    )

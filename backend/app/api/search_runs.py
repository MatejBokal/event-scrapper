import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import SearchRun
from app.schemas.search_run import SearchRunCreate, SearchRunDetail, SearchRunRead
from app.services.crawl_run import execute_crawl_run
from app.services.extract_run import execute_extract_run
from app.services.pipeline_run import execute_full_pipeline
from app.services.poc_bridge import SearchParams
from app.services.search_run import (
    build_search_run_detail,
    create_search_run_record,
    execute_search_run,
    get_search_run_detail,
)

router = APIRouter(prefix="/search-runs", tags=["search-runs"])


@router.get("", response_model=list[SearchRunRead])
def list_search_runs(
    limit: int = Query(default=20, le=100),
    db: Session = Depends(get_db),
) -> list[SearchRun]:
    return list(
        db.scalars(select(SearchRun).order_by(SearchRun.created_at.desc()).limit(limit)).all()
    )


@router.post("", response_model=SearchRunDetail, status_code=201)
def create_search_run(
    payload: SearchRunCreate,
    db: Session = Depends(get_db),
) -> SearchRunDetail:
    params = SearchParams(
        field=payload.field,
        region=payload.region,
        selected_months=tuple(payload.selected_months),
        contact_type=payload.contact_type,
        max_conferences=payload.max_conferences,
        manual_official_url=payload.manual_official_url.strip(),
    )
    run = create_search_run_record(db, params)
    db.commit()
    db.refresh(run)

    run = execute_search_run(db, run, execute_search=payload.execute_search)
    db.refresh(run)

    if payload.execute_crawl or payload.execute_extract:
        if not run.results:
            raise HTTPException(
                status_code=400,
                detail="Search produced no results — cannot crawl or extract",
            )

    if payload.execute_crawl:
        try:
            run = execute_crawl_run(db, run)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    if payload.execute_extract:
        try:
            run = execute_extract_run(db, run)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    loaded = get_search_run_detail(db, run.id)
    if loaded is None:
        raise HTTPException(status_code=500, detail="Search run not found after create")
    return build_search_run_detail(db, loaded)


@router.get("/{run_id}", response_model=SearchRunDetail)
def get_search_run(run_id: uuid.UUID, db: Session = Depends(get_db)) -> SearchRunDetail:
    run = get_search_run_detail(db, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Search run not found")
    return build_search_run_detail(db, run)


@router.post("/{run_id}/crawl", response_model=SearchRunDetail)
def crawl_search_run(run_id: uuid.UUID, db: Session = Depends(get_db)) -> SearchRunDetail:
    run = db.get(SearchRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Search run not found")
    if not run.results:
        raise HTTPException(status_code=400, detail="Run has no search results — execute search first")

    try:
        run = execute_crawl_run(db, run)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    loaded = get_search_run_detail(db, run.id)
    if loaded is None:
        raise HTTPException(status_code=500, detail="Search run not found after crawl")
    return build_search_run_detail(db, loaded)


@router.post("/{run_id}/extract", response_model=SearchRunDetail)
def extract_search_run(run_id: uuid.UUID, db: Session = Depends(get_db)) -> SearchRunDetail:
    run = db.get(SearchRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Search run not found")

    try:
        run = execute_extract_run(db, run)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    loaded = get_search_run_detail(db, run.id)
    if loaded is None:
        raise HTTPException(status_code=500, detail="Search run not found after extract")
    return build_search_run_detail(db, loaded)


@router.post("/{run_id}/execute", response_model=SearchRunDetail)
def execute_search_run_pipeline(run_id: uuid.UUID, db: Session = Depends(get_db)) -> SearchRunDetail:
    run = db.get(SearchRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Search run not found")

    try:
        run = execute_full_pipeline(db, run)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    loaded = get_search_run_detail(db, run.id)
    if loaded is None:
        raise HTTPException(status_code=500, detail="Search run not found after execute")
    return build_search_run_detail(db, loaded)

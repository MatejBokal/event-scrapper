from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import SearchRun
from app.services.crawl_run import execute_crawl_run
from app.services.extract_run import execute_extract_run
from app.services.search_run import execute_search_run


def execute_full_pipeline(db: Session, run: SearchRun) -> SearchRun:
    if not run.results:
        run = execute_search_run(db, run, execute_search=True)
        if not run.results:
            return run

    run = execute_crawl_run(db, run)
    pages_crawled = (run.stats or {}).get("pages_crawled", 0)
    if pages_crawled < 1:
        return run

    return execute_extract_run(db, run)

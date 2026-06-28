from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.models import SearchRun
from app.services.crawl_run import execute_crawl_run
from app.services.extract_run import execute_extract_run
from app.services.poc_bridge import setup_logging
from app.services.search_run import execute_search_run

setup_logging()
log = logging.getLogger("leadfinder.pipeline")


def execute_full_pipeline(db: Session, run: SearchRun) -> SearchRun:
    log.info("Pipeline started for run %s", run.id)
    if not run.results:
        run = execute_search_run(db, run, execute_search=True)
        if not run.results:
            log.warning("Pipeline stopped for run %s — no search results", run.id)
            return run

    run = execute_crawl_run(db, run)
    pages_crawled = (run.stats or {}).get("pages_crawled", 0)
    if pages_crawled < 1:
        log.warning("Pipeline stopped for run %s — no pages crawled", run.id)
        return run

    run = execute_extract_run(db, run)
    log.info("Pipeline finished for run %s — status=%s", run.id, run.status)
    return run

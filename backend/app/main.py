from __future__ import annotations

import sys
from pathlib import Path

POC_ROOT = Path(__file__).resolve().parents[2] / "poc"
if str(POC_ROOT) not in sys.path:
    sys.path.insert(0, str(POC_ROOT))

from backend.app_logging import setup_logging  # noqa: E402

setup_logging()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import conferences, export, organizers, search_runs

app = FastAPI(
    title="Conference Organizer Lead Finder API",
    version="0.8.0",
    description="MVP Phase 8 — Perplexity LLM extraction on crawled page text",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8501",
        "http://localhost:8501",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(conferences.router, prefix="/api")
app.include_router(organizers.router, prefix="/api")
app.include_router(export.router, prefix="/api")
app.include_router(search_runs.router, prefix="/api")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

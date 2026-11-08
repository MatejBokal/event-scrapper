"""Load listgen settings.json and apply overrides to poc/backend config."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


LISTGEN_ROOT = Path(__file__).resolve().parent
DEFAULT_SETTINGS_PATH = LISTGEN_ROOT / "settings.json"


def load_settings(path: Path | None = None) -> dict[str, Any]:
    settings_path = path or DEFAULT_SETTINGS_PATH
    with settings_path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _repo_root() -> Path:
    return LISTGEN_ROOT.parent


def _apply_months_mode(settings: dict[str, Any]) -> None:
    """Configure query_builder month sampling: sampled | all | per_task."""
    import backend.query_builder as qb

    mode = str(settings.get("months_mode", "sampled")).strip().lower()
    month_list = settings.get("months", [])
    n_months = max(len(month_list), 1)

    if mode == "all":
        qb.MONTH_QUERY_SAMPLE_SIZE = n_months
        qb.MONTH_QUERY_SLOTS = max(6, n_months * 2)
    elif mode == "per_task":
        qb.MONTH_QUERY_SAMPLE_SIZE = 1
        qb.MONTH_QUERY_SLOTS = 6
    else:
        qb.MONTH_QUERY_SAMPLE_SIZE = 3
        qb.MONTH_QUERY_SLOTS = 6


def get_months_mode(settings: dict[str, Any]) -> str:
    return str(settings.get("months_mode", "sampled")).strip().lower()


def get_run_mode(settings: dict[str, Any]) -> str:
    """full = discovery + crawl; links_only = discovery/search only."""
    return str(settings.get("run_mode", "full")).strip().lower()


def get_query_mode(settings: dict[str, Any]) -> str:
    """sampled = PoC rotation; exhaustive = all language × synonym × month × city combos."""
    if get_run_mode(settings) == "links_only":
        return "exhaustive"
    search = settings.get("search", {})
    return str(search.get("query_mode", "sampled")).strip().lower()


def _apply_query_mode(settings: dict[str, Any]) -> None:
    import backend.query_builder as qb

    qb.EXHAUSTIVE_QUERIES = get_query_mode(settings) == "exhaustive"
    extra = settings.get("search", {}).get("extra_event_synonyms", {})
    qb.EXTRA_EVENT_SYNONYMS = {str(k): list(v) for k, v in extra.items()} if extra else {}
    organizer = settings.get("search", {}).get("include_organizer_queries")
    if organizer is not None:
        qb.INCLUDE_ORGANIZER_QUERIES = bool(organizer)


def month_batches(settings: dict[str, Any]) -> list[tuple[tuple[str, ...], str]]:
    """Return (selected_months, label) batches for task scheduling."""
    months = tuple(settings.get("months", []))
    mode = get_months_mode(settings)

    if mode == "per_task":
        return [((month,), month) for month in months]
    label = ",".join(months)
    return [(months, label)]


def apply_settings(settings: dict[str, Any]) -> None:
    import backend.config as config

    search = settings.get("search", {})
    crawl = settings.get("crawl", {})
    extraction = settings.get("extraction", {})

    max_queries = int(search.get("max_queries", 0))
    config.MAX_QUERIES = 9999 if max_queries <= 0 else max_queries

    results_per_query = int(search.get("results_per_query", config.RESULTS_PER_QUERY))
    config.RESULTS_PER_QUERY = max(1, results_per_query)

    delay = search.get("request_delay_seconds")
    if delay is not None:
        config.REQUEST_DELAY_SECONDS = float(delay)

    max_pages = crawl.get("max_pages_per_site")
    if max_pages is not None:
        config.MAX_PAGES_PER_SITE = max(1, int(max_pages))

    max_depth = crawl.get("max_crawl_depth")
    if max_depth is not None:
        config.MAX_CRAWL_DEPTH = max(1, int(max_depth))

    listing_max = crawl.get("listing_max_per_run")
    if listing_max is not None:
        config.LISTING_MAX_PER_RUN = max(1, int(listing_max))

    site_timeout = crawl.get("site_timeout_seconds")
    if site_timeout is not None:
        config.SITE_CRAWL_TIMEOUT_SECONDS = max(30, int(site_timeout))

    if not extraction.get("use_llm", False):
        config.is_llm_extraction_enabled = lambda: False  # type: ignore[method-assign]

    _apply_months_mode(settings)
    _apply_query_mode(settings)

    output_file = settings.get("output", {}).get("file", "listgen/output/results.xlsx")
    if not Path(output_file).is_absolute():
        settings.setdefault("output", {})["file"] = str(_repo_root() / output_file)

    checkpoint = settings.get("output", {}).get("checkpoint", "listgen/output/checkpoint.json")
    if not Path(checkpoint).is_absolute():
        settings.setdefault("output", {})["checkpoint"] = str(_repo_root() / checkpoint)

    links_file = settings.get("output", {}).get("links_file", "listgen/output/links.csv")
    if not Path(links_file).is_absolute():
        settings.setdefault("output", {})["links_file"] = str(_repo_root() / links_file)

    deduped_file = settings.get("output", {}).get("links_deduped_file", "listgen/output/links_deduped.csv")
    if not Path(deduped_file).is_absolute():
        settings.setdefault("output", {})["links_deduped_file"] = str(_repo_root() / deduped_file)

    test_links = settings.get("output", {}).get("test_links_file", "listgen/output/test_links.csv")
    if not Path(test_links).is_absolute():
        settings.setdefault("output", {})["test_links_file"] = str(_repo_root() / test_links)

    test_deduped = settings.get("output", {}).get(
        "test_links_deduped_file", "listgen/output/test_links_deduped.csv"
    )
    if not Path(test_deduped).is_absolute():
        settings.setdefault("output", {})["test_links_deduped_file"] = str(_repo_root() / test_deduped)

    skip_log = settings.get("output", {}).get("skip_log_file", "listgen/output/skip_log.jsonl")
    if not Path(skip_log).is_absolute():
        settings.setdefault("output", {})["skip_log_file"] = str(_repo_root() / skip_log)


def setup_poc_path() -> None:
    import sys

    poc_root = _repo_root() / "poc"
    poc_str = str(poc_root)
    if poc_str not in sys.path:
        sys.path.insert(0, poc_str)

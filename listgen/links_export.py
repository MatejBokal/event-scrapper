"""Incremental CSV export for discovered and crawled links, with deduplication."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from backend.domains import domain, is_listing_domain, is_skip_crawl_queue_url, is_ticket_vendor_domain
from backend.models import CrawledPage, PipelineResult, SelectedSite
from backend.url_prefilter import classify_hopeless_url

LINK_FIELDS = [
    "country",
    "city",
    "field",
    "months",
    "task_key",
    "link_type",
    "url",
    "title",
    "snippet",
    "source_query",
    "url_score",
    "parent_url",
    "rank",
]

DEDUPED_EXTRA_FIELDS = [
    "found_in_tasks",
    "found_fields",
    "found_cities",
    "crawl_status",
]

CRAWL_QUEUE_TYPES = ("crawl_target", "listing_official", "ticket_official", "ticket_page")

LINK_TYPE_PRIORITY = {
    "crawl_target": 5,
    "listing_official": 4,
    "ticket_official": 4,
    "ticket_page": 3,
    "listing_page": 3,
    "search_result": 2,
    "crawled_page": 1,
}


def normalize_link_url(url: str) -> str:
    cleaned = url.strip()
    if not cleaned:
        return ""
    parsed = urlparse(cleaned)
    if not parsed.netloc:
        return cleaned.rstrip("/").lower()
    path = parsed.path.rstrip("/") or ""
    return f"{parsed.scheme}://{parsed.netloc.lower()}{path}"


def _score_value(row: dict[str, Any]) -> float:
    raw = row.get("url_score", "")
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


def _append_csv_value(existing: str, value: str) -> str:
    value = value.strip()
    if not value:
        return existing
    parts = [part.strip() for part in existing.split(";") if part.strip()]
    if value in parts:
        return ";".join(parts)
    parts.append(value)
    return ";".join(parts)


def dedupe_link_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per URL; merge task/field/city context from duplicates."""
    by_url: dict[str, dict[str, Any]] = {}

    for row in rows:
        url_key = normalize_link_url(row.get("url", ""))
        if not url_key:
            continue

        existing = by_url.get(url_key)
        if existing is None:
            merged = dict(row)
            merged["found_in_tasks"] = str(row.get("task_key", ""))
            merged["found_fields"] = str(row.get("field", ""))
            merged["found_cities"] = str(row.get("city", ""))
            merged["crawl_status"] = row.get("crawl_status", "pending")
            by_url[url_key] = merged
            continue

        existing["found_in_tasks"] = _append_csv_value(
            str(existing.get("found_in_tasks", "")), str(row.get("task_key", ""))
        )
        existing["found_fields"] = _append_csv_value(
            str(existing.get("found_fields", "")), str(row.get("field", ""))
        )
        existing["found_cities"] = _append_csv_value(
            str(existing.get("found_cities", "")), str(row.get("city", ""))
        )

        if _score_value(row) > _score_value(existing):
            for key in ("title", "snippet", "source_query", "url_score", "parent_url", "rank"):
                if row.get(key) not in (None, ""):
                    existing[key] = row[key]

        row_priority = LINK_TYPE_PRIORITY.get(str(row.get("link_type", "")), 0)
        existing_priority = LINK_TYPE_PRIORITY.get(str(existing.get("link_type", "")), 0)
        if row_priority > existing_priority:
            existing["link_type"] = row.get("link_type", existing.get("link_type"))

    deduped = list(by_url.values())
    deduped.sort(key=lambda row: (-_score_value(row), row.get("url", "")))
    return deduped


def read_links_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_csv_header(path: Path) -> list[str]:
    if not path.exists() or path.stat().st_size == 0:
        return list(LINK_FIELDS)
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        row = next(reader, None)
    return list(row) if row else list(LINK_FIELDS)


def read_all_links_csv(base_path: Path) -> list[dict[str, Any]]:
    from listgen.run_files import list_parts

    rows: list[dict[str, Any]] = []
    for part in list_parts(base_path):
        rows.extend(read_links_csv(part))
    return rows


def write_links_csv(path: Path, rows: list[dict[str, Any]], *, fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    names = fieldnames or _fieldnames_for_rows(rows)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=names, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _fieldnames_for_rows(rows: list[dict[str, Any]]) -> list[str]:
    names = list(LINK_FIELDS)
    for row in rows:
        for key in row:
            if key not in names:
                names.append(key)
    for extra in DEDUPED_EXTRA_FIELDS:
        if extra not in names:
            names.append(extra)
    for extra in ("conference_name", "page_type", "text_length", "has_email"):
        if any(extra in row for row in rows) and extra not in names:
            names.append(extra)
    return names


def rebuild_deduped_links(
    raw_path: Path,
    deduped_path: Path,
    *,
    crawled_url_keys: set[str] | None = None,
    use_cached_deduped: bool = False,
) -> list[dict[str, Any]]:
    crawled = crawled_url_keys or set()

    if use_cached_deduped and deduped_path.exists() and deduped_path.stat().st_size > 0:
        return update_deduped_crawl_status(deduped_path, crawled)

    deduped = dedupe_link_rows(read_all_links_csv(raw_path))

    existing_status: dict[str, str] = {}
    if deduped_path.exists():
        for row in read_links_csv(deduped_path):
            url_key = normalize_link_url(row.get("url", ""))
            status = row.get("crawl_status", "")
            if url_key and status:
                existing_status[url_key] = str(status)

    for row in deduped:
        url_key = normalize_link_url(row.get("url", ""))
        if url_key in crawled:
            row["crawl_status"] = "crawled"
        elif url_key in existing_status:
            row["crawl_status"] = existing_status[url_key]

    write_links_csv(deduped_path, deduped)
    return deduped


def update_deduped_crawl_status(
    deduped_path: Path,
    crawled_url_keys: set[str],
) -> list[dict[str, Any]]:
    """Fast path: update crawl_status on the existing deduped file only."""
    rows = read_links_csv(deduped_path)
    if not rows:
        return rows

    changed = False
    for row in rows:
        url_key = normalize_link_url(row.get("url", ""))
        if url_key in crawled_url_keys and row.get("crawl_status") != "crawled":
            row["crawl_status"] = "crawled"
            changed = True

    if changed:
        write_links_csv(deduped_path, rows)
    return rows


def load_deduped_for_crawl(deduped_path: Path) -> list[dict[str, Any]]:
    if not deduped_path.exists() or deduped_path.stat().st_size == 0:
        return []
    return read_links_csv(deduped_path)


def _base_row(
    *,
    country: str,
    city: str,
    field: str,
    months_label: str,
    task_key: str,
    link_type: str,
    url: str,
    title: str = "",
    snippet: str = "",
    source_query: str = "",
    url_score: float | int | None = None,
    parent_url: str = "",
    rank: int | None = None,
) -> dict[str, Any]:
    return {
        "country": country,
        "city": city,
        "field": field,
        "months": months_label,
        "task_key": task_key,
        "link_type": link_type,
        "url": url,
        "title": title,
        "snippet": snippet,
        "source_query": source_query,
        "url_score": url_score if url_score is not None else "",
        "parent_url": parent_url,
        "rank": rank if rank is not None else "",
    }


def rows_from_discovery(
    result: PipelineResult,
    *,
    country: str,
    city: str,
    field: str,
    months_label: str,
    task_key: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    def add(link_type: str, url: str, **kwargs: Any) -> None:
        normalized = normalize_link_url(url)
        if not normalized:
            return
        key = (link_type, normalized)
        if key in seen:
            return
        seen.add(key)
        rows.append(
            _base_row(
                country=country,
                city=city,
                field=field,
                months_label=months_label,
                task_key=task_key,
                link_type=link_type,
                url=url,
                **kwargs,
            )
        )

    for hit in result.search_hits:
        add(
            "search_result",
            hit.url,
            title=hit.title,
            snippet=hit.snippet,
            source_query=hit.source_query,
            url_score=hit.url_score,
            rank=hit.rank,
        )

    for site in result.listing_sources:
        link_type = "ticket_page" if is_ticket_vendor_domain(site.url) else "listing_page"
        add(
            link_type,
            site.url,
            title=site.title,
            snippet=site.snippet,
            url_score=site.url_score,
            parent_url=site.discovered_from,
        )

    for discovery in result.listing_discoveries:
        link_type = (
            "ticket_official"
            if is_ticket_vendor_domain(discovery.listing_url)
            else "listing_official"
        )
        add(
            link_type,
            discovery.official_url,
            title=discovery.official_title,
            url_score=discovery.link_score,
            parent_url=discovery.listing_url,
        )

    for site in result.selected_sites:
        add(
            "crawl_target",
            site.url,
            title=site.title,
            snippet=site.snippet,
            url_score=site.url_score,
            parent_url=site.discovered_from,
        )

    return rows


def rows_from_crawl(
    pages: list[CrawledPage],
    *,
    conference_name: str,
    lead_source_urls: set[str],
    found_in_tasks: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    for page in pages:
        normalized = normalize_link_url(page.url)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        rows.append(
            {
                "link_type": "crawled_page",
                "url": page.url,
                "title": page.title,
                "snippet": "",
                "source_query": "",
                "url_score": "",
                "parent_url": page.conference_url,
                "rank": "",
                "found_in_tasks": found_in_tasks,
                "crawl_status": "crawled",
                "conference_name": conference_name,
                "page_type": page.page_type,
                "text_length": len(page.extracted_text or ""),
                "has_email": page.url.rstrip("/") in lead_source_urls,
            }
        )

    return rows


def append_links_csv(
    base_path: Path,
    rows: list[dict[str, Any]],
    *,
    max_bytes: int | None = None,
) -> Path | None:
    if not rows:
        return None

    from listgen.run_files import DEFAULT_MAX_FILE_BYTES, active_append_path, list_parts

    limit = max_bytes if max_bytes is not None else DEFAULT_MAX_FILE_BYTES
    before_parts = list_parts(base_path)
    before_latest = before_parts[-1] if before_parts else None
    target = active_append_path(base_path, limit)
    rotated = before_latest is not None and target != before_latest

    target.parent.mkdir(parents=True, exist_ok=True)
    write_header = not target.exists() or target.stat().st_size == 0
    fieldnames = _fieldnames_for_rows(rows)
    if not write_header:
        for name in _read_csv_header(target):
            if name not in fieldnames:
                fieldnames.append(name)

    with target.open("a", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerows(rows)
    return target if rotated else None


def site_to_dict(site: SelectedSite) -> dict[str, Any]:
    return {
        "url": site.url,
        "title": site.title,
        "url_score": site.url_score,
        "snippet": site.snippet,
        "source": site.source,
        "discovered_from": site.discovered_from,
    }


def site_from_dict(data: dict[str, Any]) -> SelectedSite:
    return SelectedSite(
        url=data["url"],
        title=data.get("title", ""),
        url_score=float(data.get("url_score", 0)),
        snippet=data.get("snippet", ""),
        source=data.get("source", "search"),
        discovered_from=data.get("discovered_from", ""),
    )


@dataclass
class TaskContext:
    country: str
    city: str
    field: str
    months_label: str
    selected_months: tuple[str, ...]
    task_key: str
    region_name: str


@dataclass
class DedupedCrawlTarget:
    site: SelectedSite
    tasks: list[TaskContext] = field(default_factory=list)
    url_key: str = ""
    found_in_tasks: str = ""


def _parse_task_keys(found_in_tasks: str) -> list[str]:
    return [part.strip() for part in found_in_tasks.split(";") if part.strip()]


def build_crawl_queue(
    deduped_rows: list[dict[str, Any]],
    task_contexts: dict[str, TaskContext],
    *,
    domain_memory: Any | None = None,
    one_url_per_domain: bool = True,
) -> list[DedupedCrawlTarget]:
    queue: list[DedupedCrawlTarget] = []

    for row in deduped_rows:
        if row.get("link_type") not in CRAWL_QUEUE_TYPES:
            continue
        if row.get("crawl_status") == "crawled":
            continue

        url = row.get("url", "")
        if not url or is_skip_crawl_queue_url(url):
            continue
        if classify_hopeless_url(url):
            continue
        if domain_memory is not None and domain_memory.should_skip(url):
            continue

        url_key = normalize_link_url(url)
        found_in_tasks = str(row.get("found_in_tasks", "") or row.get("task_key", ""))
        task_keys = _parse_task_keys(found_in_tasks)
        contexts = [task_contexts[key] for key in task_keys if key in task_contexts]
        if not contexts and row.get("task_key") in task_contexts:
            contexts = [task_contexts[str(row["task_key"])]]

        site = SelectedSite(
            url=url,
            title=str(row.get("title", "")),
            url_score=_score_value(row),
            snippet=str(row.get("snippet", "")),
            source="deduped",
            discovered_from=str(row.get("parent_url", "")),
        )
        queue.append(
            DedupedCrawlTarget(
                site=site,
                tasks=contexts,
                url_key=url_key,
                found_in_tasks=found_in_tasks,
            )
        )

    if one_url_per_domain:
        best_by_host: dict[str, DedupedCrawlTarget] = {}
        for target in queue:
            host = domain(target.site.url)
            if not host:
                continue
            existing = best_by_host.get(host)
            if existing is None or target.site.url_score > existing.site.url_score:
                best_by_host[host] = target
        queue = list(best_by_host.values())

    queue.sort(key=lambda item: (-item.site.url_score, item.url_key))
    return queue


def primary_task(target: DedupedCrawlTarget) -> TaskContext | None:
    if not target.tasks:
        return None
    return target.tasks[0]

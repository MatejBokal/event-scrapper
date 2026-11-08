"""Append-only crawl queue and done log for O(1)-style resume."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from backend.models import SelectedSite

from listgen.links_export import DedupedCrawlTarget, TaskContext, normalize_link_url


@dataclass(frozen=True)
class JournalPaths:
    queue: Path
    done_log: Path
    conferences_jsonl: Path
    leads_jsonl: Path


def journal_paths_for_checkpoint(checkpoint_base: Path) -> JournalPaths:
    stem = checkpoint_base.stem
    run_id = stem.removeprefix("checkpoint_") if stem.startswith("checkpoint_") else stem
    parent = checkpoint_base.parent
    return JournalPaths(
        queue=parent / f"crawl_queue_{run_id}.jsonl",
        done_log=parent / f"crawl_done_{run_id}.log",
        conferences_jsonl=parent / f"results_conferences_{run_id}.jsonl",
        leads_jsonl=parent / f"results_leads_{run_id}.jsonl",
    )


def journal_paths_payload(paths: JournalPaths) -> dict[str, str]:
    return {
        "queue": str(paths.queue),
        "done_log": str(paths.done_log),
        "conferences_jsonl": str(paths.conferences_jsonl),
        "leads_jsonl": str(paths.leads_jsonl),
    }


def journal_paths_from_payload(payload: dict[str, Any]) -> JournalPaths | None:
    journal = payload.get("journal")
    if not isinstance(journal, dict):
        return None
    required = ("queue", "done_log", "conferences_jsonl", "leads_jsonl")
    if not all(journal.get(key) for key in required):
        return None
    return JournalPaths(
        queue=Path(journal["queue"]),
        done_log=Path(journal["done_log"]),
        conferences_jsonl=Path(journal["conferences_jsonl"]),
        leads_jsonl=Path(journal["leads_jsonl"]),
    )


def target_to_record(target: DedupedCrawlTarget) -> dict[str, Any]:
    return {
        "url_key": target.url_key,
        "url": target.site.url,
        "title": target.site.title,
        "url_score": target.site.url_score,
        "snippet": target.site.snippet,
        "found_in_tasks": target.found_in_tasks,
        "tasks": [
            {
                "country": task.country,
                "city": task.city,
                "field": task.field,
                "months_label": task.months_label,
                "selected_months": list(task.selected_months),
                "task_key": task.task_key,
                "region_name": task.region_name,
            }
            for task in target.tasks
        ],
    }


def record_to_target(record: dict[str, Any]) -> DedupedCrawlTarget:
    site = SelectedSite(
        url=record["url"],
        title=str(record.get("title", "")),
        url_score=float(record.get("url_score", 0)),
        snippet=str(record.get("snippet", "")),
        source="deduped",
        discovered_from="",
    )
    tasks = [
        TaskContext(
            country=task["country"],
            city=task["city"],
            field=task["field"],
            months_label=task["months_label"],
            selected_months=tuple(task["selected_months"]),
            task_key=task["task_key"],
            region_name=task["region_name"],
        )
        for task in record.get("tasks", [])
    ]
    return DedupedCrawlTarget(
        site=site,
        tasks=tasks,
        url_key=str(record.get("url_key") or normalize_link_url(record["url"])),
        found_in_tasks=str(record.get("found_in_tasks", "")),
    )


def write_crawl_queue(paths: JournalPaths, targets: list[DedupedCrawlTarget]) -> None:
    paths.queue.parent.mkdir(parents=True, exist_ok=True)
    with paths.queue.open("w", encoding="utf-8") as handle:
        for target in targets:
            handle.write(json.dumps(target_to_record(target), ensure_ascii=False))
            handle.write("\n")


def count_lines(path: Path) -> int:
    if not path.exists() or path.stat().st_size == 0:
        return 0
    count = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            count += chunk.count(b"\n")
    return count


def load_done_set(paths: JournalPaths, *, legacy_urls: list[str] | None = None) -> set[str]:
    if paths.done_log.exists() and paths.done_log.stat().st_size > 0:
        done: set[str] = set()
        with paths.done_log.open(encoding="utf-8") as handle:
            for line in handle:
                key = normalize_link_url(line.strip())
                if key:
                    done.add(key)
        return done

    if not legacy_urls:
        return set()

    paths.done_log.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    with paths.done_log.open("w", encoding="utf-8") as handle:
        for url in legacy_urls:
            key = normalize_link_url(url.strip())
            if not key:
                continue
            done.add(key)
            handle.write(f"{key}\n")
    return done


def append_done(paths: JournalPaths, url_key: str) -> None:
    key = normalize_link_url(url_key)
    if not key:
        return
    paths.done_log.parent.mkdir(parents=True, exist_ok=True)
    with paths.done_log.open("a", encoding="utf-8") as handle:
        handle.write(f"{key}\n")


def iter_pending_targets(
    paths: JournalPaths,
    done_keys: set[str],
) -> Iterator[DedupedCrawlTarget]:
    if not paths.queue.exists():
        return

    with paths.queue.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            target = record_to_target(record)
            if target.url_key in done_keys:
                continue
            yield target


def count_pending(paths: JournalPaths, done_keys: set[str]) -> int:
    return sum(1 for _ in iter_pending_targets(paths, done_keys))

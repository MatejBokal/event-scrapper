"""Append-only JSONL results — no need to reload full Excel on resume."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from listgen.crawl_journal import JournalPaths, count_lines
from listgen.export import CONFERENCE_FIELDS, LEAD_FIELDS, write_workbook
from listgen.results_dedup import (
    ResultDedupIndex,
    dedupe_conferences,
    dedupe_leads,
)


def append_conferences(paths: JournalPaths, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    paths.conferences_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with paths.conferences_jsonl.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False))
            handle.write("\n")


def append_leads(paths: JournalPaths, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    paths.leads_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with paths.leads_jsonl.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False))
            handle.write("\n")


def iter_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_workbook_from_journal(
    paths: JournalPaths,
    output_path: Path,
    *,
    extra_conferences: list[dict[str, Any]] | None = None,
    extra_leads: list[dict[str, Any]] | None = None,
) -> None:
    conferences = iter_jsonl(paths.conferences_jsonl)
    leads = iter_jsonl(paths.leads_jsonl)
    if extra_conferences:
        conferences.extend(extra_conferences)
    if extra_leads:
        leads.extend(extra_leads)
    write_workbook(
        output_path,
        dedupe_conferences(conferences),
        dedupe_leads(leads),
    )


def load_result_dedup_index(paths: JournalPaths) -> ResultDedupIndex:
    return ResultDedupIndex.from_jsonl_rows(
        iter_jsonl(paths.conferences_jsonl),
        iter_jsonl(paths.leads_jsonl),
    )


def journal_result_counts(paths: JournalPaths) -> tuple[int, int]:
    return count_lines(paths.conferences_jsonl), count_lines(paths.leads_jsonl)


def migrate_workbook_to_journal(paths: JournalPaths, output_path: Path) -> tuple[int, int]:
    """One-time copy from xlsx into JSONL if journal files are empty."""
    conf_count, lead_count = journal_result_counts(paths)
    if conf_count or lead_count or not output_path.exists():
        return conf_count, lead_count

    from listgen.export import read_workbook

    conferences, leads = read_workbook(output_path)
    append_conferences(paths, conferences)
    append_leads(paths, leads)
    return len(conferences), len(leads)

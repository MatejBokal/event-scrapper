"""Deduplicate conference and lead result rows (one row per domain / email)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from listgen.links_export import normalize_link_url

try:
    from backend.domains import domain, is_gateway_domain
except ImportError:
    from poc.backend.domains import domain, is_gateway_domain  # type: ignore[no-redef]

CONFERENCE_MERGE_FIELDS = (
    "country",
    "city",
    "field",
    "months",
    "conference_url",
    "conference_name",
)
LEAD_MERGE_FIELDS = (
    "country",
    "city",
    "field",
    "months",
    "conference_url",
    "conference_name",
    "source_url",
)


def _append_semicolon(existing: str, value: str) -> str:
    value = value.strip()
    if not value:
        return existing
    parts = [part.strip() for part in existing.split(";") if part.strip()]
    if value in parts:
        return ";".join(parts)
    parts.append(value)
    return ";".join(parts)


def conference_dedup_key(row: dict[str, Any]) -> str:
    url = normalize_link_url(str(row.get("conference_url", "")))
    if not url:
        return ""
    if is_gateway_domain(url):
        return f"url:{url}"
    host = domain(url)
    return f"domain:{host}" if host else ""


def lead_dedup_key(row: dict[str, Any]) -> tuple[str, ...]:
    email = str(row.get("organizer_email", "")).strip().lower()
    if email:
        return ("email", email)
    organizer = str(row.get("organizer_name", "")).strip().lower()
    source_url = normalize_link_url(str(row.get("source_url", "")))
    return ("person", organizer, source_url)


def _score_value(row: dict[str, Any]) -> float:
    raw = row.get("url_score", row.get("confidence", 0))
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


def _merge_conference_row(existing: dict[str, Any], row: dict[str, Any]) -> None:
    for field in CONFERENCE_MERGE_FIELDS:
        existing[field] = _append_semicolon(str(existing.get(field, "")), str(row.get(field, "")))
    if bool(row.get("has_email")):
        existing["has_email"] = True
    if _score_value(row) > _score_value(existing):
        for field in ("search_title", "url_score", "source"):
            if row.get(field) not in (None, ""):
                existing[field] = row[field]


def _merge_lead_row(existing: dict[str, Any], row: dict[str, Any]) -> None:
    for field in LEAD_MERGE_FIELDS:
        existing[field] = _append_semicolon(str(existing.get(field, "")), str(row.get(field, "")))
    if _score_value(row) > _score_value(existing):
        for field in (
            "event_date",
            "location",
            "organizer_name",
            "organizer_role",
            "contact_quality",
            "evidence_snippet",
            "confidence",
            "language",
        ):
            if row.get(field) not in (None, ""):
                existing[field] = row[field]


def dedupe_conferences(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = conference_dedup_key(row)
        if not key:
            continue
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = dict(row)
        else:
            _merge_conference_row(existing, row)
    return list(by_key.values())


def dedupe_leads(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[tuple[str, ...], dict[str, Any]] = {}
    for row in rows:
        key = lead_dedup_key(row)
        if key in (("email", ""), ("person", "", "")):
            continue
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = dict(row)
        else:
            _merge_lead_row(existing, row)
    return list(by_key.values())


class ResultDedupIndex:
    """Tracks seen result keys so new crawl output does not duplicate prior rows."""

    def __init__(self) -> None:
        self._conference_keys: set[str] = set()
        self._lead_keys: set[tuple[str, ...]] = set()

    @classmethod
    def from_jsonl_rows(
        cls,
        conferences: list[dict[str, Any]],
        leads: list[dict[str, Any]],
    ) -> ResultDedupIndex:
        index = cls()
        for row in conferences:
            key = conference_dedup_key(row)
            if key:
                index._conference_keys.add(key)
        for row in leads:
            key = lead_dedup_key(row)
            if key not in (("email", ""), ("person", "", "")):
                index._lead_keys.add(key)
        return index

    @property
    def conference_count(self) -> int:
        return len(self._conference_keys)

    @property
    def lead_count(self) -> int:
        return len(self._lead_keys)

    def filter_new_conferences(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        merged_batch = dedupe_conferences(rows)
        accepted: list[dict[str, Any]] = []
        for row in merged_batch:
            key = conference_dedup_key(row)
            if not key or key in self._conference_keys:
                continue
            self._conference_keys.add(key)
            accepted.append(row)
        return accepted

    def filter_new_leads(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        merged_batch = dedupe_leads(rows)
        accepted: list[dict[str, Any]] = []
        for row in merged_batch:
            key = lead_dedup_key(row)
            if key in (("email", ""), ("person", "", "")) or key in self._lead_keys:
                continue
            self._lead_keys.add(key)
            accepted.append(row)
        return accepted


def merge_conferences(
    existing: list[dict[str, Any]],
    new_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return dedupe_conferences([*existing, *new_rows])


def merge_leads(
    existing: list[dict[str, Any]],
    new_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return dedupe_leads([*existing, *new_rows])


@dataclass
class DedupeStats:
    raw_lines: int = 0
    dropped_no_key: int = 0
    unique_count: int = 0

    @property
    def duplicates_merged(self) -> int:
        return max(0, self.raw_lines - self.dropped_no_key - self.unique_count)


def _ingest_conference(by_key: dict[str, dict[str, Any]], row: dict[str, Any], stats: DedupeStats) -> None:
    stats.raw_lines += 1
    key = conference_dedup_key(row)
    if not key:
        stats.dropped_no_key += 1
        return
    existing = by_key.get(key)
    if existing is None:
        by_key[key] = dict(row)
    else:
        _merge_conference_row(existing, row)


def _ingest_lead(by_key: dict[tuple[str, ...], dict[str, Any]], row: dict[str, Any], stats: DedupeStats) -> None:
    stats.raw_lines += 1
    key = lead_dedup_key(row)
    if key in (("email", ""), ("person", "", "")):
        stats.dropped_no_key += 1
        return
    existing = by_key.get(key)
    if existing is None:
        by_key[key] = dict(row)
    else:
        _merge_lead_row(existing, row)


def dedupe_conferences_iter(rows: Iterator[dict[str, Any]]) -> tuple[list[dict[str, Any]], DedupeStats]:
    stats = DedupeStats()
    by_key: dict[str, dict[str, Any]] = {}
    for row in rows:
        _ingest_conference(by_key, row, stats)
    stats.unique_count = len(by_key)
    return list(by_key.values()), stats


def dedupe_leads_iter(rows: Iterator[dict[str, Any]]) -> tuple[list[dict[str, Any]], DedupeStats]:
    stats = DedupeStats()
    by_key: dict[tuple[str, ...], dict[str, Any]] = {}
    for row in rows:
        _ingest_lead(by_key, row, stats)
    stats.unique_count = len(by_key)
    return list(by_key.values()), stats


def iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    if not path.exists() or path.stat().st_size == 0:
        return iter(())
    def _read() -> Iterator[dict[str, Any]]:
        with path.open(encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid JSON on line {line_no} of {path}: {exc}") from exc
    return _read()


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False))
            handle.write("\n")

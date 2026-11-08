"""Rotate large run output files into numbered parts that share a run base name."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

DEFAULT_MAX_FILE_BYTES = 20 * 1024 * 1024

_PART_STEM_RE = re.compile(r"_part(\d+)$")


def max_file_bytes(settings: dict[str, Any]) -> int:
    raw = settings.get("output", {}).get("max_file_bytes", DEFAULT_MAX_FILE_BYTES)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_MAX_FILE_BYTES
    return max(value, 1024 * 1024)


def part_path(base: Path, part_num: int) -> Path:
    """Part 1 uses the base path unchanged; part 2+ adds ``_partN`` before the suffix."""
    if part_num <= 1:
        return base
    return base.with_name(f"{base.stem}_part{part_num}{base.suffix}")


def part_number(path: Path) -> int:
    match = _PART_STEM_RE.search(path.stem)
    if not match:
        return 1
    return int(match.group(1))


def list_parts(base: Path) -> list[Path]:
    """Return existing parts in order (base file first, then _part2, _part3, …)."""
    parts: list[Path] = []
    if base.exists():
        parts.append(base)
    n = 2
    while True:
        candidate = part_path(base, n)
        if candidate.exists():
            parts.append(candidate)
            n += 1
        else:
            break
    return parts


def quarantine_trailing_corrupt_parts(base: Path) -> list[Path]:
    """Rename unreadable trailing parts so ``list_parts`` stops before them."""
    quarantined: list[Path] = []
    while True:
        parts = list_parts(base)
        if not parts:
            return quarantined
        latest = parts[-1]
        try:
            with latest.open(encoding="utf-8") as handle:
                json.load(handle)
            return quarantined
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            dest = latest.with_name(latest.name + ".corrupt")
            n = 1
            while dest.exists():
                dest = latest.with_name(f"{latest.name}.corrupt{n}")
                n += 1
            latest.rename(dest)
            quarantined.append(dest)


def load_latest_checkpoint_part(base: Path) -> dict[str, Any] | None:
    """Load only the newest readable checkpoint part (for lightweight resume)."""
    quarantine_trailing_corrupt_parts(base)
    parts = list_parts(base)
    if not parts:
        return None
    with parts[-1].open(encoding="utf-8") as handle:
        return json.load(handle)


def active_append_path(base: Path, max_bytes: int) -> Path:
    """Path for the next append write; opens a new part when the latest file is full."""
    existing = list_parts(base)
    if not existing:
        return base
    latest = existing[-1]
    if latest.stat().st_size >= max_bytes:
        return part_path(base, len(existing) + 1)
    return latest


def active_write_path(base: Path, max_bytes: int) -> Path:
    """Path for the next full-file write (same rule as append)."""
    return active_append_path(base, max_bytes)


def format_part_group(base: Path) -> str:
    parts = list_parts(base)
    if not parts:
        return base.name
    if len(parts) == 1:
        return parts[0].name
    return f"{base.name} (+{len(parts) - 1} parts)"


def _merge_checkpoint_chunk(merged: dict[str, Any], chunk: dict[str, Any]) -> None:
    for key in ("discovery_completed", "crawl_completed_urls"):
        existing = set(merged.get(key, []))
        existing.update(chunk.get(key, []))
        merged[key] = sorted(existing)

    targets = chunk.get("crawl_targets_by_task") or {}
    if targets:
        merged.setdefault("crawl_targets_by_task", {}).update(targets)

    merged["conferences"] = merged.get("conferences", []) + list(chunk.get("conferences", []))
    merged["leads"] = merged.get("leads", []) + list(chunk.get("leads", []))


def load_checkpoint_all(base: Path, *, empty: dict[str, Any]) -> dict[str, Any]:
    parts = list_parts(base)
    if not parts:
        return dict(empty)

    merged = dict(empty)
    for part in parts:
        with part.open(encoding="utf-8") as handle:
            chunk = json.load(handle)
        for key in empty:
            chunk.setdefault(key, empty[key])
        if chunk.get("crawl_completed") and not chunk.get("crawl_completed_urls"):
            chunk["crawl_completed_urls"] = []
        _merge_checkpoint_chunk(merged, chunk)
    return merged


class RotatingCheckpoint:
    """Write checkpoint JSON in parts; part 1 keeps the original base filename."""

    def __init__(self, base_path: Path, max_bytes: int) -> None:
        self.base_path = base_path
        self.max_bytes = max_bytes
        self._part_start_conf_count = 0
        self._part_start_lead_count = 0
        self._force_new_part = False

    def _sync_part_start_from_disk(self) -> None:
        parts = list_parts(self.base_path)
        if len(parts) <= 1:
            self._part_start_conf_count = 0
            self._part_start_lead_count = 0
            return

        prior = load_checkpoint_all(self.base_path, empty=_checkpoint_empty())
        # Count conferences/leads stored in all parts except the latest.
        latest = parts[-1]
        with latest.open(encoding="utf-8") as handle:
            latest_chunk = json.load(handle)
        self._part_start_conf_count = len(prior.get("conferences", [])) - len(
            latest_chunk.get("conferences", [])
        )
        self._part_start_lead_count = len(prior.get("leads", [])) - len(latest_chunk.get("leads", []))

    def prepare_lightweight_resume(self) -> None:
        """Next save writes a fresh part so we don't clobber disk-only conference rows."""
        quarantine_trailing_corrupt_parts(self.base_path)
        self._part_start_conf_count = 0
        self._part_start_lead_count = 0
        self._force_new_part = True

    def load(self, *, empty: dict[str, Any]) -> dict[str, Any]:
        quarantine_trailing_corrupt_parts(self.base_path)
        state = load_checkpoint_all(self.base_path, empty=empty)
        self._sync_part_start_from_disk()
        return state

    def init_empty(self, *, empty: dict[str, Any]) -> dict[str, Any]:
        self._part_start_conf_count = 0
        self._part_start_lead_count = 0
        self._force_new_part = False
        self._write_part(self.base_path, empty)
        save_crawl_progress(self.base_path, empty)
        return dict(empty)

    def save(self, state: dict[str, Any], *, drop_targets: bool = False) -> Path | None:
        parts_before = list_parts(self.base_path)
        latest_before = parts_before[-1] if parts_before else None
        if self._force_new_part:
            target = part_path(self.base_path, len(parts_before) + 1)
            self._force_new_part = False
        else:
            target = active_write_path(self.base_path, self.max_bytes)
        rotated = latest_before is not None and target != latest_before

        if rotated:
            self._part_start_conf_count = len(state.get("conferences", []))
            self._part_start_lead_count = len(state.get("leads", []))

        payload: dict[str, Any] = dict(state)
        if drop_targets:
            payload["crawl_targets_by_task"] = {}

        if part_number(target) > 1:
            payload = {
                "discovery_completed": state.get("discovery_completed", []),
                "crawl_completed_urls": state.get("crawl_completed_urls", []),
                "crawl_targets_by_task": payload.get("crawl_targets_by_task", {}),
                "conferences": list(state.get("conferences", []))[self._part_start_conf_count :],
                "leads": list(state.get("leads", []))[self._part_start_lead_count :],
            }

        self._write_part(target, payload)
        save_crawl_progress(self.base_path, state)
        return target if rotated else None

    def save_progress_only(
        self,
        state: dict[str, Any],
        *,
        journal: dict[str, str] | None = None,
        crawl_done_count: int | None = None,
        conferences_total: int | None = None,
        leads_total: int | None = None,
    ) -> None:
        save_crawl_progress(
            self.base_path,
            state,
            journal=journal,
            crawl_done_count=crawl_done_count,
            conferences_total=conferences_total,
            leads_total=leads_total,
        )

    def _write_part(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)


def _checkpoint_empty() -> dict[str, Any]:
    return {
        "discovery_completed": [],
        "crawl_completed_urls": [],
        "crawl_targets_by_task": {},
        "conferences": [],
        "leads": [],
    }


def progress_sidecar_path(checkpoint_base: Path) -> Path:
    return checkpoint_base.with_name(f"{checkpoint_base.stem}_progress{checkpoint_base.suffix}")


def save_crawl_progress(
    checkpoint_base: Path,
    state: dict[str, Any],
    *,
    journal: dict[str, str] | None = None,
    crawl_done_count: int | None = None,
    conferences_total: int | None = None,
    leads_total: int | None = None,
) -> None:
    """Small file for fast resume — counts and paths, not full result payloads."""
    path = progress_sidecar_path(checkpoint_base)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "discovery_completed": state.get("discovery_completed", []),
        "crawl_done_count": crawl_done_count
        if crawl_done_count is not None
        else len(state.get("crawl_completed_urls", [])),
        "conferences_total": conferences_total
        if conferences_total is not None
        else len(state.get("conferences", [])),
        "leads_total": leads_total
        if leads_total is not None
        else len(state.get("leads", [])),
    }
    if journal:
        payload["journal"] = journal
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def load_crawl_progress(checkpoint_base: Path) -> dict[str, Any] | None:
    path = progress_sidecar_path(checkpoint_base)
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    # Backward compat: old progress files stored the full URL list.
    if "crawl_completed_urls" in data and "crawl_done_count" not in data:
        data["crawl_done_count"] = len(data.get("crawl_completed_urls", []))
    return data

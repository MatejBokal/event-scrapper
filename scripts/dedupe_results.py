#!/usr/bin/env python3
"""One-off deduplication of listgen conference/lead JSONL results."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
for _path in (_REPO_ROOT, _REPO_ROOT / "poc"):
    _path_str = str(_path)
    if _path_str not in sys.path:
        sys.path.insert(0, _path_str)

from listgen.crawl_journal import journal_paths_for_checkpoint
from listgen.export import write_workbook
from listgen.run_files import load_crawl_progress, progress_sidecar_path, save_crawl_progress
from listgen.results_dedup import (
    DedupeStats,
    dedupe_conferences_iter,
    dedupe_leads_iter,
    iter_jsonl,
    write_jsonl,
)


def _default_latest_run_path() -> Path:
    return _REPO_ROOT / "listgen" / "output" / "latest_run.json"


def _load_latest_run(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"latest_run.json not found: {path}")
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _resolve_run_paths(run_id: str, output_dir: Path) -> dict[str, Path]:
    checkpoint = output_dir / f"checkpoint_{run_id}.json"
    journal = journal_paths_for_checkpoint(checkpoint)
    return {
        "checkpoint": checkpoint,
        "progress": progress_sidecar_path(checkpoint),
        "conferences_in": journal.conferences_jsonl,
        "leads_in": journal.leads_jsonl,
        "xlsx_in": output_dir / f"results_{run_id}.xlsx",
        "conferences_out": output_dir / f"results_conferences_{run_id}_deduped.jsonl",
        "leads_out": output_dir / f"results_leads_{run_id}_deduped.jsonl",
        "xlsx_out": output_dir / f"results_{run_id}_deduped.xlsx",
    }


def _latest_backup(path: Path) -> Path | None:
    matches = list(path.parent.glob(f"{path.name}.bak-*"))
    if not matches:
        return None
    return max(matches, key=lambda candidate: candidate.stat().st_size)


def _input_path(path: Path, *, from_backup: bool) -> Path:
    if not from_backup:
        return path
    backup = _latest_backup(path)
    if backup is None:
        return path
    print(f"Using backup source: {backup}")
    return backup


def _print_stats(label: str, stats: DedupeStats) -> None:
    print(
        f"{label}: {stats.raw_lines} raw lines -> {stats.unique_count} unique "
        f"({stats.duplicates_merged} merged, {stats.dropped_no_key} dropped with no key)"
    )


def _backup(path: Path, stamp: str) -> Path | None:
    if not path.exists():
        return None
    backup = path.with_name(f"{path.name}.bak-{stamp}")
    shutil.copy2(path, backup)
    return backup


def _install_deduped(paths: dict[str, Path], stamp: str) -> None:
    for key in ("conferences_in", "leads_in", "xlsx_in"):
        src = paths[key]
        backup = _backup(src, stamp)
        if backup:
            print(f"Backup: {backup}")

    shutil.copy2(paths["conferences_out"], paths["conferences_in"])
    shutil.copy2(paths["leads_out"], paths["leads_in"])
    shutil.copy2(paths["xlsx_out"], paths["xlsx_in"])
    print(f"Installed deduped files over:\n  {paths['conferences_in']}\n  {paths['leads_in']}\n  {paths['xlsx_in']}")


def _update_progress(paths: dict[str, Path], conf_count: int, lead_count: int) -> None:
    checkpoint = paths["checkpoint"]
    progress = load_crawl_progress(checkpoint) or {}
    state = {
        "discovery_completed": progress.get("discovery_completed", []),
        "crawl_completed_urls": progress.get("crawl_completed_urls", []),
    }
    journal = progress.get("journal")
    crawl_done_count = progress.get(
        "crawl_done_count",
        len(progress.get("crawl_completed_urls", [])),
    )
    save_crawl_progress(
        checkpoint,
        state,
        journal=journal if isinstance(journal, dict) else None,
        crawl_done_count=crawl_done_count,
        conferences_total=conf_count,
        leads_total=lead_count,
    )
    print(
        f"Updated progress sidecar: {paths['progress']} "
        f"(conferences_total={conf_count}, leads_total={lead_count})"
    )


def run(
    *,
    run_id: str,
    output_dir: Path,
    dry_run: bool,
    apply: bool,
    install: bool,
    from_backup: bool,
) -> int:
    paths = _resolve_run_paths(run_id, output_dir)

    if not paths["conferences_in"].exists() and not paths["leads_in"].exists():
        raise SystemExit(
            f"No results JSONL found for run {run_id} in {output_dir}"
        )

    conf_in = _input_path(paths["conferences_in"], from_backup=from_backup)
    lead_in = _input_path(paths["leads_in"], from_backup=from_backup)

    print(f"Run id: {run_id}")
    print(f"Input conferences: {conf_in}")
    print(f"Input leads:       {lead_in}")

    conferences, conf_stats = dedupe_conferences_iter(iter_jsonl(conf_in))
    leads, lead_stats = dedupe_leads_iter(iter_jsonl(lead_in))

    print()
    _print_stats("Conferences", conf_stats)
    _print_stats("Leads", lead_stats)
    print()

    if dry_run and not apply:
        print("Dry run only — no files written.")
        print(f"Would write:\n  {paths['conferences_out']}\n  {paths['leads_out']}\n  {paths['xlsx_out']}")
        if install:
            print("Would also replace live results files (with backup).")
        return 0

    if not apply:
        print("Nothing to do. Use --dry-run to preview or --apply to write deduped files.")
        return 0

    write_jsonl(paths["conferences_out"], conferences)
    write_jsonl(paths["leads_out"], leads)
    write_workbook(paths["xlsx_out"], conferences, leads)
    print(f"Wrote deduped JSONL + Excel:\n  {paths['conferences_out']}\n  {paths['leads_out']}\n  {paths['xlsx_out']}")

    if install:
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
        _install_deduped(paths, stamp)
        _update_progress(paths, conf_stats.unique_count, lead_stats.unique_count)
        print("\nDone. Resume crawling with: python -m listgen")
    else:
        print(
            "\nDeduped files written alongside originals. "
            "Re-run with --apply --install to replace live results (backs up first)."
        )

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Deduplicate listgen conference/lead JSONL results into new files.",
    )
    parser.add_argument(
        "--run-id",
        help="Run stamp (default: read from listgen/output/latest_run.json)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_REPO_ROOT / "listgen" / "output",
        help="Directory containing results JSONL files",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show before/after counts only",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write deduped JSONL and Excel files",
    )
    parser.add_argument(
        "--from-backup",
        action="store_true",
        help="Read from latest .bak-* files (richer merge for leads)",
    )
    parser.add_argument(
        "--install",
        action="store_true",
        help="With --apply: backup and replace live results files + update progress",
    )
    args = parser.parse_args()

    run_id = args.run_id
    if not run_id:
        latest = _load_latest_run(_default_latest_run_path())
        run_id = str(latest.get("run_stamp", "")).strip()
        if not run_id:
            raise SystemExit("Could not resolve run id from latest_run.json; pass --run-id")

    if args.install and not args.apply:
        raise SystemExit("--install requires --apply")

    if not args.dry_run and not args.apply:
        args.dry_run = True

    return run(
        run_id=run_id,
        output_dir=args.output_dir,
        dry_run=args.dry_run,
        apply=args.apply,
        install=args.install,
        from_backup=args.from_backup,
    )


if __name__ == "__main__":
    raise SystemExit(main())

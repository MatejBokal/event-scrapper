"""Bulk list-generation runner — discovery, deduplicated links, then global crawl."""

from __future__ import annotations

from dataclasses import dataclass

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.crawler import get_conference_name
from backend.domains import is_gateway_domain
from backend.event_presence import assess_event_presence
from backend.listing_discovery import resolve_gateway_site
from backend.models import LeadResult, PipelineResult, SearchParams
from backend.pipeline import run_crawl_phase, run_discovery
from backend.url_prefilter import classify_hopeless_url

from listgen.country_data import get_cities, get_city_allowlist, get_event_keywords, get_region_profile_for_country
from listgen.domain_memory import DomainMemory, looks_like_mill_or_listing
from listgen.skip_log import SkipLog, resolve_skip_log_path
from listgen.crawl_journal import (
    JournalPaths,
    append_done,
    count_pending,
    iter_pending_targets,
    journal_paths_for_checkpoint,
    journal_paths_payload,
    journal_paths_from_payload,
    load_done_set,
    write_crawl_queue,
)
from listgen.export import write_workbook
from listgen.links_export import (
    TaskContext,
    append_links_csv,
    build_crawl_queue,
    primary_task,
    rebuild_deduped_links,
    rows_from_crawl,
    rows_from_discovery,
    site_to_dict,
    update_deduped_crawl_status,
)
from listgen.run_files import (
    RotatingCheckpoint,
    format_part_group,
    load_crawl_progress,
    load_latest_checkpoint_part,
    max_file_bytes,
    save_crawl_progress,
)
from listgen.results_journal import (
    append_conferences,
    append_leads,
    journal_result_counts,
    load_result_dedup_index,
    migrate_workbook_to_journal,
    write_workbook_from_journal,
)
from listgen.results_dedup import ResultDedupIndex, merge_conferences, merge_leads
from listgen.settings_loader import get_months_mode, get_query_mode, get_run_mode, month_batches


def _task_key(country: str, city: str, field: str, months_label: str) -> str:
    return f"{country}|{city}|{field}|{months_label}"


def _empty_checkpoint() -> dict[str, Any]:
    return {
        "discovery_completed": [],
        "crawl_completed_urls": [],
        "crawl_targets_by_task": {},
        "conferences": [],
        "leads": [],
    }


@dataclass
class CrawlResume:
    journal: JournalPaths
    done_keys: set[str]
    conferences_total: int
    leads_total: int


def _init_run_state(
    checkpoint: RotatingCheckpoint,
    *,
    resume: bool,
    total_tasks: int,
    output_path: Path,
    current_task_keys: set[str],
) -> tuple[dict[str, Any], CrawlResume | None]:
    empty = _empty_checkpoint()
    if not resume or not list_parts_exists(checkpoint.base_path):
        return checkpoint.init_empty(empty=empty), None

    progress = load_crawl_progress(checkpoint.base_path)
    journal = journal_paths_from_payload(progress) if progress else None
    if journal is None:
        journal = journal_paths_for_checkpoint(checkpoint.base_path)

    if progress is None:
        print("Loading checkpoint (building progress index)...", flush=True)
        state = checkpoint.load(empty=empty)
        save_crawl_progress(checkpoint.base_path, state, journal=journal_paths_payload(journal))
        return state, None

    discovery_done = set(progress.get("discovery_completed", []))
    discovery_done_current = discovery_done & current_task_keys
    discovery_incomplete = len(discovery_done_current) < len(current_task_keys)

    # Mid-discovery: seed from the tiny progress sidecar + latest part only.
    # Loading every checkpoint part can be multi‑GB and blocks resume.
    if discovery_incomplete:
        print(
            f"Resuming discovery from progress "
            f"({len(discovery_done_current)}/{len(current_task_keys)} tasks for this run)...",
            flush=True,
        )
        latest = load_latest_checkpoint_part(checkpoint.base_path) or {}
        state = dict(empty)
        state["discovery_completed"] = list(progress.get("discovery_completed", []))
        state["crawl_completed_urls"] = list(
            latest.get("crawl_completed_urls")
            or progress.get("crawl_completed_urls")
            or []
        )
        if isinstance(latest.get("domain_memory"), dict):
            state["domain_memory"] = latest["domain_memory"]
        checkpoint.prepare_lightweight_resume()
        return state, None

    print("Resuming crawl (journal — tail only)...", flush=True)
    legacy_urls = progress.get("crawl_completed_urls")
    if not legacy_urls:
        latest = load_latest_checkpoint_part(checkpoint.base_path) or {}
        legacy_urls = latest.get("crawl_completed_urls")
    done_keys = load_done_set(journal, legacy_urls=legacy_urls)

    conf_total, lead_total = journal_result_counts(journal)
    if conf_total == 0 and lead_total == 0 and output_path.exists():
        print("Copying existing workbook into results journal (one-time)...", flush=True)
        conf_total, lead_total = migrate_workbook_to_journal(journal, output_path)

    state = dict(empty)
    state["discovery_completed"] = progress["discovery_completed"]
    state["crawl_completed_urls"] = sorted(done_keys)
    state["crawl_targets_by_task"] = {}
    state["conferences"] = []
    state["leads"] = []

    return state, CrawlResume(
        journal=journal,
        done_keys=done_keys,
        conferences_total=conf_total or int(progress.get("conferences_total", 0)),
        leads_total=lead_total or int(progress.get("leads_total", 0)),
    )


def list_parts_exists(base_path: Path) -> bool:
    from listgen.run_files import list_parts

    return bool(list_parts(base_path))


def _notify_rotation(label: str, path: Path) -> None:
    print(f"  rotated {label} -> {path.name}", flush=True)


def _domain_memory_from_settings(
    settings: dict[str, Any],
    repo_root: Path,
    state: dict[str, Any],
) -> DomainMemory:
    crawl_cfg = settings.get("crawl", {}) if isinstance(settings.get("crawl"), dict) else {}
    denylist_raw = str(
        crawl_cfg.get("domain_denylist_file") or "listgen/output/domain_denylist.json"
    )
    denylist_path = Path(denylist_raw)
    if not denylist_path.is_absolute():
        denylist_path = repo_root / denylist_path
    memory = DomainMemory(denylist_path)
    memory.load_state(state.get("domain_memory"))
    memory.hydrate_from_completed_urls(state.get("crawl_completed_urls") or [])
    return memory


def _persist_domain_memory(state: dict[str, Any], memory: DomainMemory) -> None:
    state["domain_memory"] = memory.to_state()


def _journal_mark_site_done(
    *,
    checkpoint: RotatingCheckpoint,
    journal_paths: JournalPaths,
    state: dict[str, Any],
    target: Any,
    done_keys: set[str],
    conf_total: int,
    lead_total: int,
) -> None:
    append_done(journal_paths, target.url_key)
    done_keys.add(target.url_key)
    state["crawl_completed_urls"] = sorted(done_keys)
    checkpoint.save_progress_only(
        state,
        journal=journal_paths_payload(journal_paths),
        crawl_done_count=len(done_keys),
        conferences_total=conf_total,
        leads_total=lead_total,
    )


def _mark_target_done(
    *,
    crawl_resume: Any,
    checkpoint: RotatingCheckpoint,
    journal_paths: JournalPaths,
    state: dict[str, Any],
    target: Any,
    done_keys: set[str],
    crawl_done_urls: set[str],
    conf_total: int,
    lead_total: int,
    memory: DomainMemory,
) -> None:
    memory.mark_crawled(target.site.url)
    _persist_domain_memory(state, memory)
    if crawl_resume is not None:
        _journal_mark_site_done(
            checkpoint=checkpoint,
            journal_paths=journal_paths,
            state=state,
            target=target,
            done_keys=done_keys,
            conf_total=conf_total,
            lead_total=lead_total,
        )
    else:
        crawl_done_urls.add(target.url_key)
        state["crawl_completed_urls"] = sorted(crawl_done_urls)


def _lead_to_row(
    lead: LeadResult,
    *,
    country: str,
    city: str,
    field: str,
    months_label: str,
) -> dict[str, Any]:
    row = lead.to_dict()
    row["country"] = country
    row["city"] = city
    row["field"] = field
    row["months"] = months_label
    return row


def _conferences_from_crawl(
    *,
    site_url: str,
    site_title: str,
    site_score: float,
    site_source: str,
    pages: list,
    country: str,
    city: str,
    field: str,
    months_label: str,
    has_email: bool,
    event_date: str | None = None,
    venue_city: str | None = None,
) -> dict[str, Any]:
    conference_name = get_conference_name(pages) or site_title
    return {
        "country": country,
        "city": city,
        "field": field,
        "months": months_label,
        "conference_name": conference_name,
        "conference_url": site_url,
        "search_title": site_title,
        "url_score": site_score,
        "has_email": has_email,
        "source": site_source,
        "event_date": event_date,
        "venue_city": venue_city,
    }


def _print_progress(stage: str, payload: dict[str, Any]) -> None:
    message = payload.get("message", stage)
    print(f"[{stage}] {message}", flush=True)


def _make_progress_logger(
    skip_log: SkipLog,
    *,
    country: str = "",
    city: str = "",
    field: str = "",
    task_key: str = "",
):
    stage_map = {
        "queue_skip": ("queue_skip", "dont_crawl"),
        "keyword_rejected": ("keyword_gate", "dont_crawl"),
        "presence_rejected": ("presence_gate", "drop_lead"),
    }

    def _on_progress(stage: str, payload: dict[str, Any]) -> None:
        _print_progress(stage, payload)
        mapped = stage_map.get(stage)
        if not mapped:
            return
        log_stage, default_decision = mapped
        skip_log.log(
            stage=log_stage,
            decision=str(payload.get("decision") or default_decision),
            reason=str(payload.get("reason") or stage),
            detail=str(payload.get("message") or ""),
            url=str(payload.get("url") or ""),
            country=country,
            city=city,
            field=field,
            task_key=task_key,
        )

    return _on_progress


def _resolve_test_run(settings: dict[str, Any], argv: list[str]) -> tuple[bool, str]:
    test_cfg = settings.get("test_run", {})
    if isinstance(test_cfg, bool):
        enabled = test_cfg
        city = settings.get("test_city", "")
    else:
        enabled = bool(test_cfg.get("enabled", False))
        city = str(test_cfg.get("city", "") or settings.get("test_city", ""))

    args = list(argv)
    if "--test" in args:
        enabled = True
        idx = args.index("--test")
        if idx + 1 < len(args) and not args[idx + 1].startswith("-"):
            city = args[idx + 1]
    return enabled, city.strip()


def _resolve_run_mode(settings: dict[str, Any], argv: list[str]) -> str:
    if "--links-only" in argv:
        return "links_only"
    return get_run_mode(settings)


def _apply_cli_overrides(settings: dict[str, Any], argv: list[str]) -> None:
    if "--links-only" in argv:
        settings["run_mode"] = "links_only"


def _parse_settings_path(argv: list[str]) -> tuple[Path, list[str]]:
    from listgen.settings_loader import DEFAULT_SETTINGS_PATH

    args = [a for a in argv if a not in ("--test", "--links-only")]
    if "--test" in argv:
        idx = argv.index("--test")
        if idx + 1 < len(argv) and not argv[idx + 1].startswith("-") and not argv[idx + 1].endswith(".json"):
            drop = argv[idx + 1]
            args = [a for a in args if a != drop]

    if not args:
        return DEFAULT_SETTINGS_PATH, argv
    candidate = Path(args[0])
    if candidate.suffix == ".json":
        return candidate, argv
    return DEFAULT_SETTINGS_PATH, argv


def _run_stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def _stamp_path(path: Path, stamp: str) -> Path:
    return path.with_name(f"{path.stem}_{stamp}{path.suffix}")


def _latest_run_path(settings: dict[str, Any], *, test_run: bool) -> Path:
    from listgen.settings_loader import LISTGEN_ROOT

    output_cfg = settings.get("output", {})
    name = "test_latest_run.json" if test_run else "latest_run.json"
    configured = output_cfg.get("latest_run_file" if not test_run else "test_latest_run_file")
    path = Path(configured) if configured else LISTGEN_ROOT / "output" / name
    if not path.is_absolute():
        path = LISTGEN_ROOT.parent / path
    return path


def _load_latest_run(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _save_latest_run(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def _paths_from_latest_run(record: dict[str, Any]) -> tuple[Path, Path, Path, Path]:
    return (
        Path(record["output"]),
        Path(record["checkpoint"]),
        Path(record["links_file"]),
        Path(record["links_deduped_file"]),
    )


def _resolve_paths(
    settings: dict[str, Any],
    *,
    test_run: bool,
    resume: bool,
) -> tuple[Path, Path, Path, Path, str | None]:
    from listgen.settings_loader import LISTGEN_ROOT

    repo_root = LISTGEN_ROOT.parent
    output_cfg = settings.get("output", {})

    if test_run:
        test_cfg = settings.get("test_run", {})
        test_cfg_dict = test_cfg if isinstance(test_cfg, dict) else {}
        output_path = Path(
            test_cfg_dict.get("output_file")
            or output_cfg.get("test_file")
            or "listgen/output/test_results.xlsx"
        )
        checkpoint_path = Path(
            test_cfg_dict.get("checkpoint")
            or output_cfg.get("test_checkpoint")
            or "listgen/output/test_checkpoint.json"
        )
        links_path = Path(
            test_cfg_dict.get("links_file")
            or output_cfg.get("test_links_file")
            or "listgen/output/test_links.csv"
        )
        deduped_path = Path(
            test_cfg_dict.get("links_deduped_file")
            or output_cfg.get("test_links_deduped_file")
            or "listgen/output/test_links_deduped.csv"
        )
    else:
        output_path = Path(output_cfg["file"])
        checkpoint_path = Path(output_cfg["checkpoint"])
        links_path = Path(output_cfg.get("links_file", "listgen/output/links.csv"))
        deduped_path = Path(output_cfg.get("links_deduped_file", "listgen/output/links_deduped.csv"))

    if not output_path.is_absolute():
        output_path = repo_root / output_path
    if not checkpoint_path.is_absolute():
        checkpoint_path = repo_root / checkpoint_path
    if not links_path.is_absolute():
        links_path = repo_root / links_path
    if not deduped_path.is_absolute():
        deduped_path = repo_root / deduped_path

    base_paths = (output_path, checkpoint_path, links_path, deduped_path)

    if resume:
        latest = _load_latest_run(_latest_run_path(settings, test_run=test_run))
        if latest and latest.get("test_run", False) == test_run:
            return (*_paths_from_latest_run(latest), latest.get("run_stamp"))
        return (*base_paths, None)

    stamp = _run_stamp()
    stamped = tuple(_stamp_path(path, stamp) for path in base_paths)
    record = {
        "run_stamp": stamp,
        "test_run": test_run,
        "output": str(stamped[0]),
        "checkpoint": str(stamped[1]),
        "links_file": str(stamped[2]),
        "links_deduped_file": str(stamped[3]),
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    _save_latest_run(_latest_run_path(settings, test_run=test_run), record)
    return (*stamped, stamp)


def _build_tasks(
    settings: dict[str, Any],
    *,
    test_run: bool,
    test_city: str,
) -> list[tuple[str, str, str, tuple[str, ...], str]]:
    tasks: list[tuple[str, str, str, tuple[str, ...], str]] = []
    for country in settings["countries"]:
        for city in get_cities(country, test_run=test_run, test_city=test_city):
            for field in settings["fields"]:
                for selected_months, months_label in month_batches(settings):
                    tasks.append((country, city, field, selected_months, months_label))
    return tasks


def _build_task_contexts(
    tasks: list[tuple[str, str, str, tuple[str, ...], str]],
) -> dict[str, TaskContext]:
    contexts: dict[str, TaskContext] = {}
    for country, city, field, selected_months, months_label in tasks:
        key = _task_key(country, city, field, months_label)
        profile = get_region_profile_for_country(country)
        contexts[key] = TaskContext(
            country=country,
            city=city,
            field=field,
            months_label=months_label,
            selected_months=selected_months,
            task_key=key,
            region_name=profile.display_name,
        )
    return contexts


def run_bulk(
    settings: dict[str, Any],
    *,
    test_run: bool = False,
    test_city: str = "",
    links_only: bool = False,
) -> Path:
    max_conferences = int(settings.get("max_conferences_per_run", 0))
    contact_type = settings.get("contact_type", "any")
    resume = bool(settings.get("resume", True))
    run_mode = "links_only" if links_only else get_run_mode(settings)
    query_mode = get_query_mode(settings)

    output_path, checkpoint_path, links_path, deduped_path, run_stamp = _resolve_paths(
        settings, test_run=test_run, resume=resume
    )
    file_limit = max_file_bytes(settings)
    checkpoint = RotatingCheckpoint(checkpoint_path, file_limit)
    tasks = _build_tasks(settings, test_run=test_run, test_city=test_city)
    task_contexts = _build_task_contexts(tasks)
    total = len(tasks)

    mode = "TEST" if test_run else "FULL"
    city_note = f", city={test_city or '(first)'}" if test_run else ""
    months_mode = get_months_mode(settings)
    print(
        f"Listgen [{mode}]: {total} discovery tasks "
        f"({len(settings['countries'])} countries, months_mode={months_mode}, "
        f"run_mode={run_mode}, query_mode={query_mode}{city_note})",
        flush=True,
    )
    print(f"Raw links: {format_part_group(links_path)}", flush=True)
    print(f"Deduped links: {deduped_path}", flush=True)
    if run_mode != "links_only":
        print(f"Results: {output_path}", flush=True)
    print(f"Checkpoint: {format_part_group(checkpoint_path)}", flush=True)
    if run_stamp:
        label = "resuming" if resume else "new output files"
        print(f"Run id: {run_stamp} ({label})", flush=True)
    if run_mode == "links_only":
        print("Crawl phase: SKIPPED (links_only)", flush=True)

    current_task_keys = {
        _task_key(country, city, field, months_label)
        for country, city, field, _months, months_label in tasks
    }
    had_checkpoint = list_parts_exists(checkpoint_path)
    state, crawl_resume = _init_run_state(
        checkpoint,
        resume=resume,
        total_tasks=total,
        output_path=output_path,
        current_task_keys=current_task_keys,
    )
    journal_paths = (
        crawl_resume.journal if crawl_resume else journal_paths_for_checkpoint(checkpoint_path)
    )
    discovery_done = set(state.get("discovery_completed", []))
    crawl_done_urls = set(state.get("crawl_completed_urls", []))
    targets_by_task: dict[str, list[dict[str, Any]]] = state.get("crawl_targets_by_task", {})
    discovery_done_current = discovery_done & current_task_keys
    discovery_complete = len(discovery_done_current) >= total
    if resume and had_checkpoint:
        print(
            f"Checkpoint: resuming ({len(discovery_done_current)}/{total} discovery tasks "
            f"for this run, {len(crawl_done_urls)} crawled URLs)",
            flush=True,
        )
    elif not resume:
        print("Checkpoint: starting fresh", flush=True)
    use_cached_deduped = discovery_complete and deduped_path.exists()
    workbook_every = max(1, int(settings.get("output", {}).get("workbook_save_every", 5)))
    from listgen.settings_loader import LISTGEN_ROOT

    crawl_cfg = settings.get("crawl", {}) if isinstance(settings.get("crawl"), dict) else {}
    one_url_per_domain = bool(crawl_cfg.get("one_url_per_domain", True))
    domain_memory = _domain_memory_from_settings(settings, LISTGEN_ROOT.parent, state)
    _persist_domain_memory(state, domain_memory)
    print(
        f"Domain memory: {len(domain_memory.crawled_hosts)} crawled hosts, "
        f"{len(domain_memory.denied_hosts)} denylisted "
        f"(one_url_per_domain={one_url_per_domain})",
        flush=True,
    )
    skip_log = SkipLog(
        resolve_skip_log_path(settings, LISTGEN_ROOT.parent, run_stamp=run_stamp or ""),
        run_id=run_stamp or "",
    )
    print(f"Skip log: {skip_log.path}", flush=True)

    # --- Phase 1: discovery ---
    if discovery_complete:
        print(f"\n=== Phase 1: Discovery (skipped — {total}/{total} done) ===", flush=True)
    else:
        print(f"\n=== Phase 1: Discovery ({total} tasks) ===", flush=True)
    for index, (country, city, field, selected_months, months_label) in enumerate(tasks, start=1):
        if discovery_complete:
            break
        key = _task_key(country, city, field, months_label)
        if key in discovery_done:
            print(f"[discovery {index}/{total}] skip {key}", flush=True)
            continue

        profile = get_region_profile_for_country(country)
        print(f"[discovery {index}/{total}] {country} / {city} / {field} / {months_label}", flush=True)

        params = SearchParams(
            field=field,
            region=profile.display_name,
            selected_months=selected_months,
            contact_type=contact_type,
            max_conferences=max_conferences,
            target_city=city,
        )

        result = run_discovery(params, on_progress=_print_progress)
        link_rows = rows_from_discovery(
            result,
            country=country,
            city=city,
            field=field,
            months_label=months_label,
            task_key=key,
        )
        rotated = append_links_csv(links_path, link_rows, max_bytes=file_limit)
        if rotated:
            _notify_rotation("links", rotated)

        targets_by_task[key] = [site_to_dict(site) for site in result.selected_sites]
        discovery_done.add(key)
        discovery_done_current.add(key)
        state["discovery_completed"] = sorted(discovery_done)
        state["crawl_targets_by_task"] = targets_by_task
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        drop_targets = len(discovery_done_current) >= total
        rotated_ckpt = checkpoint.save(state, drop_targets=drop_targets)
        if rotated_ckpt:
            _notify_rotation("checkpoint", rotated_ckpt)

        deduped = rebuild_deduped_links(
            links_path, deduped_path, crawled_url_keys=crawl_done_urls, use_cached_deduped=False
        )
        crawl_pending = len(
            build_crawl_queue(
                deduped,
                task_contexts,
                domain_memory=domain_memory,
                one_url_per_domain=one_url_per_domain,
            )
        )

        if result.errors:
            for error in result.errors:
                print(f"  warning: {error}", flush=True)
        print(
            f"  +{len(link_rows)} raw links | deduped: {len(deduped)} urls | crawl queue: {crawl_pending}",
            flush=True,
        )

    if discovery_complete and crawl_resume is not None and journal_paths.queue.exists():
        pending_count = count_pending(journal_paths, crawl_resume.done_keys)
        print(
            f"\nPhase 1 complete. Crawl queue journal ready ({pending_count} sites pending).",
            flush=True,
        )
        crawl_queue: list[Any] = []
    elif use_cached_deduped:
        print("Using cached deduped links (fast)...", flush=True)
        deduped_rows = update_deduped_crawl_status(deduped_path, crawl_done_urls)
        crawl_queue = build_crawl_queue(
            deduped_rows,
            task_contexts,
            domain_memory=domain_memory,
            one_url_per_domain=one_url_per_domain,
        )
        if run_mode != "links_only" and not journal_paths.queue.exists():
            print("Writing crawl queue journal (one-time)...", flush=True)
            write_crawl_queue(journal_paths, crawl_queue)
        print(
            f"\nPhase 1 complete. {len(deduped_rows)} unique URLs"
            + (f", {len(crawl_queue)} sites to crawl (deduplicated)." if run_mode != "links_only" else "."),
            flush=True,
        )
    else:
        print("Rebuilding deduped links from raw files...", flush=True)
        deduped_rows = rebuild_deduped_links(
            links_path, deduped_path, crawled_url_keys=crawl_done_urls, use_cached_deduped=False
        )
        crawl_queue = build_crawl_queue(
            deduped_rows,
            task_contexts,
            domain_memory=domain_memory,
            one_url_per_domain=one_url_per_domain,
        )
        if run_mode != "links_only" and not journal_paths.queue.exists():
            print("Writing crawl queue journal (one-time)...", flush=True)
            write_crawl_queue(journal_paths, crawl_queue)
        print(
            f"\nPhase 1 complete. {len(deduped_rows)} unique URLs"
            + (f", {len(crawl_queue)} sites to crawl (deduplicated)." if run_mode != "links_only" else "."),
            flush=True,
        )

    if run_mode == "links_only":
        print(f"\nDone (links_only). Deduped links: {deduped_path}", flush=True)
        print(f"Raw links: {links_path}", flush=True)
        return deduped_path

    result_dedup: ResultDedupIndex | None = None

    # --- Phase 2: global deduplicated crawl ---
    if crawl_resume is not None:
        print("Loading result dedup index...", flush=True)
        result_dedup = load_result_dedup_index(journal_paths)
        done_keys = crawl_resume.done_keys
        conf_total = result_dedup.conference_count
        lead_total = result_dedup.lead_count
        pending_count = count_pending(journal_paths, done_keys)
        print(
            f"\n=== Phase 2: Crawl ({pending_count} remaining, {len(done_keys)} already done, journal) ===",
            flush=True,
        )
        crawl_iter: Any = iter_pending_targets(journal_paths, done_keys)
        crawl_total = pending_count
    else:
        done_keys = crawl_done_urls
        conf_total = len(state.get("conferences", []))
        lead_total = len(state.get("leads", []))
        already_crawled = len(crawl_done_urls)
        print(
            f"\n=== Phase 2: Crawl ({len(crawl_queue)} remaining, {already_crawled} already done) ===",
            flush=True,
        )
        crawl_iter = crawl_queue
        crawl_total = len(crawl_queue)

    for index, target in enumerate(crawl_iter, start=1):
        if crawl_resume is None and target.url_key in crawl_done_urls:
            print(f"[crawl {index}/{crawl_total}] skip {target.site.url}", flush=True)
            continue

        task = primary_task(target)
        if task is None:
            print(f"[crawl {index}/{crawl_total}] skip {target.site.url} (no task context)", flush=True)
            continue

        skip_reason = domain_memory.should_skip(target.site.url)
        if skip_reason and not is_gateway_domain(target.site.url):
            print(
                f"[crawl {index}/{crawl_total}] skip {target.site.url} — {skip_reason}",
                flush=True,
            )
            skip_log.log(
                stage="domain_memory",
                decision="dont_crawl",
                reason=skip_reason,
                detail=f"host={target.site.url}",
                url=target.site.url,
                country=task.country,
                city=task.city,
                field=task.field,
                task_key=task.task_key,
            )
            _mark_target_done(
                crawl_resume=crawl_resume,
                checkpoint=checkpoint,
                journal_paths=journal_paths,
                state=state,
                target=target,
                done_keys=done_keys,
                crawl_done_urls=crawl_done_urls,
                conf_total=conf_total,
                lead_total=lead_total,
                memory=domain_memory,
            )
            continue

        hopeless = classify_hopeless_url(target.site.url)
        if hopeless and not is_gateway_domain(target.site.url):
            print(
                f"[crawl {index}/{crawl_total}] skip {target.site.url} — {hopeless}",
                flush=True,
            )
            skip_log.log(
                stage="queue_skip",
                decision="dont_crawl",
                reason=hopeless,
                detail="hopeless URL prefilter",
                url=target.site.url,
                country=task.country,
                city=task.city,
                field=task.field,
                task_key=task.task_key,
            )
            _mark_target_done(
                crawl_resume=crawl_resume,
                checkpoint=checkpoint,
                journal_paths=journal_paths,
                state=state,
                target=target,
                done_keys=done_keys,
                crawl_done_urls=crawl_done_urls,
                conf_total=conf_total,
                lead_total=lead_total,
                memory=domain_memory,
            )
            continue

        if is_gateway_domain(target.site.url):
            print(
                f"[crawl {index}/{crawl_total}] gateway {target.site.url} "
                f"({len(target.tasks)} tasks: {target.found_in_tasks})",
                flush=True,
            )
            params = SearchParams(
                field=task.field,
                region=task.region_name,
                selected_months=task.selected_months,
                contact_type=contact_type,
                max_conferences=max_conferences,
                target_city=task.city,
                city_allowlist=tuple(get_city_allowlist(task.country)),
                event_keywords=tuple(get_event_keywords(task.country)),
            )
            print("  resolving official URL from gateway page...", flush=True)
            try:
                official_sites, discoveries = resolve_gateway_site(target.site, params)
            except Exception as exc:
                print(f"  gateway resolution failed ({exc}) — marking done and continuing", flush=True)
                if crawl_resume is not None:
                    _journal_mark_site_done(
                        checkpoint=checkpoint,
                        journal_paths=journal_paths,
                        state=state,
                        target=target,
                        done_keys=done_keys,
                        conf_total=conf_total,
                        lead_total=lead_total,
                    )
                else:
                    crawl_done_urls.add(target.url_key)
                continue
            if discoveries:
                print(f"  found {len(discoveries)} official URL(s)", flush=True)
            if not official_sites:
                print("  no official URL found — marking done and continuing", flush=True)
                if crawl_resume is not None:
                    _journal_mark_site_done(
                        checkpoint=checkpoint,
                        journal_paths=journal_paths,
                        state=state,
                        target=target,
                        done_keys=done_keys,
                        conf_total=conf_total,
                        lead_total=lead_total,
                    )
                else:
                    crawl_done_urls.add(target.url_key)
                continue
            crawl_targets_for_site = official_sites
        else:
            print(
                f"[crawl {index}/{crawl_total}] {target.site.url} "
                f"({len(target.tasks)} tasks: {target.found_in_tasks})",
                flush=True,
            )

            params = SearchParams(
                field=task.field,
                region=task.region_name,
                selected_months=task.selected_months,
                contact_type=contact_type,
                max_conferences=max_conferences,
                target_city=task.city,
                city_allowlist=tuple(get_city_allowlist(task.country)),
                event_keywords=tuple(get_event_keywords(task.country)),
            )
            crawl_targets_for_site = [target.site]

        on_progress = _make_progress_logger(
            skip_log,
            country=task.country,
            city=task.city,
            field=task.field,
            task_key=task.task_key,
        )
        crawl_result = run_crawl_phase(crawl_targets_for_site, params, on_progress=on_progress)
        if crawl_result.errors:
            for error in crawl_result.errors:
                print(f"  warning: {error}", flush=True)
        if not crawl_result.crawled_pages:
            print("  no pages kept after gates — marking done and continuing", flush=True)
            _mark_target_done(
                crawl_resume=crawl_resume,
                checkpoint=checkpoint,
                journal_paths=journal_paths,
                state=state,
                target=target,
                done_keys=done_keys,
                crawl_done_urls=crawl_done_urls,
                conf_total=conf_total,
                lead_total=lead_total,
                memory=domain_memory,
            )
            continue

        lead_source_urls = {contact.source_url.rstrip("/") for contact in crawl_result.contacts}
        result_site = crawl_targets_for_site[0] if crawl_targets_for_site else target.site
        conference_name = get_conference_name(crawl_result.crawled_pages) or result_site.title
        site_has_email = bool(crawl_result.leads)

        crawled_link_rows = rows_from_crawl(
            crawl_result.crawled_pages,
            conference_name=conference_name,
            lead_source_urls=lead_source_urls,
            found_in_tasks=target.found_in_tasks,
        )
        rotated = append_links_csv(links_path, crawled_link_rows, max_bytes=file_limit)
        if rotated:
            _notify_rotation("links", rotated)

        site_key = result_site.url.rstrip("/")
        site_pages = [
            page
            for page in crawl_result.crawled_pages
            if page.conference_url.rstrip("/") == site_key
        ] or list(crawl_result.crawled_pages)
        presence = assess_event_presence(site_pages, get_city_allowlist(task.country))
        if not presence.passes:
            print(
                f"  skip export — needs page date + city ({presence.reason})",
                flush=True,
            )
            skip_log.log(
                stage="presence_gate",
                decision="drop_lead",
                reason=presence.reason,
                detail="missing date and/or allowlisted city on crawled pages",
                url=result_site.url,
                country=task.country,
                city=task.city,
                field=task.field,
                task_key=task.task_key,
            )
            # Same-run only: don't revisit this host. Persist denylist for clear mills only.
            if looks_like_mill_or_listing(result_site.url):
                domain_memory.deny(result_site.url, reason=presence.reason)
            _mark_target_done(
                crawl_resume=crawl_resume,
                checkpoint=checkpoint,
                journal_paths=journal_paths,
                state=state,
                target=target,
                done_keys=done_keys,
                crawl_done_urls=crawl_done_urls,
                conf_total=conf_total,
                lead_total=lead_total,
                memory=domain_memory,
            )
            continue

        # First crawl of this domain already followed same-domain pages — don't revisit.
        for site in crawl_targets_for_site:
            domain_memory.mark_crawled(site.url)
        domain_memory.mark_crawled(target.site.url)
        _persist_domain_memory(state, domain_memory)

        event_date_label = presence.event_date.isoformat() if presence.event_date else None
        venue_city = presence.matched_city

        conf_rows: list[dict[str, Any]] = []
        lead_rows: list[dict[str, Any]] = []
        for task_ctx in target.tasks:
            conf_rows.append(
                _conferences_from_crawl(
                    site_url=result_site.url,
                    site_title=result_site.title,
                    site_score=result_site.url_score,
                    site_source=result_site.source or target.site.source,
                    pages=site_pages,
                    country=task_ctx.country,
                    city=task_ctx.city,
                    field=task_ctx.field,
                    months_label=task_ctx.months_label,
                    has_email=site_has_email,
                    event_date=event_date_label,
                    venue_city=venue_city,
                )
            )
            for lead in crawl_result.leads:
                row = _lead_to_row(
                    lead,
                    country=task_ctx.country,
                    city=task_ctx.city,
                    field=task_ctx.field,
                    months_label=task_ctx.months_label,
                )
                if not row.get("event_date"):
                    row["event_date"] = event_date_label
                if not row.get("location"):
                    row["location"] = venue_city
                lead_rows.append(row)

        if crawl_resume is not None:
            new_conf_rows = result_dedup.filter_new_conferences(conf_rows)
            new_lead_rows = result_dedup.filter_new_leads(lead_rows)
            added_conf = len(new_conf_rows)
            added_lead = len(new_lead_rows)
            append_conferences(journal_paths, new_conf_rows)
            append_leads(journal_paths, new_lead_rows)
            conf_total = result_dedup.conference_count
            lead_total = result_dedup.lead_count
            append_done(journal_paths, target.url_key)
            done_keys.add(target.url_key)
            state["crawl_completed_urls"] = sorted(done_keys)
            checkpoint.save_progress_only(
                state,
                journal=journal_paths_payload(journal_paths),
                crawl_done_count=len(done_keys),
                conferences_total=conf_total,
                leads_total=lead_total,
            )
            if index % workbook_every == 0:
                write_workbook_from_journal(journal_paths, output_path)
        else:
            prev_conf = len(state.get("conferences", []))
            prev_lead = len(state.get("leads", []))
            state["conferences"] = merge_conferences(state.get("conferences", []), conf_rows)
            state["leads"] = merge_leads(state.get("leads", []), lead_rows)
            conf_total = len(state["conferences"])
            lead_total = len(state["leads"])
            added_conf = conf_total - prev_conf
            added_lead = lead_total - prev_lead

            crawl_done_urls.add(target.url_key)
            state["crawl_completed_urls"] = sorted(crawl_done_urls)
            state["updated_at"] = datetime.now(timezone.utc).isoformat()

            if use_cached_deduped:
                update_deduped_crawl_status(deduped_path, crawl_done_urls)
            else:
                rebuild_deduped_links(
                    links_path,
                    deduped_path,
                    crawled_url_keys=crawl_done_urls,
                    use_cached_deduped=False,
                )

            rotated_ckpt = checkpoint.save(state, drop_targets=True)
            if rotated_ckpt:
                _notify_rotation("checkpoint", rotated_ckpt)
            if index % workbook_every == 0 or index == crawl_total:
                write_workbook(output_path, state["conferences"], state["leads"])

        state["updated_at"] = datetime.now(timezone.utc).isoformat()

        if crawl_result.errors:
            for error in crawl_result.errors:
                print(f"  warning: {error}", flush=True)
        print(
            f"  +{added_conf} conference rows, +{added_lead} lead rows, "
            f"+{len(crawled_link_rows)} crawled pages "
            f"(unique totals: {conf_total}, {lead_total})",
            flush=True,
        )

    if crawl_resume is not None:
        write_workbook_from_journal(journal_paths, output_path)
    else:
        write_workbook(output_path, state["conferences"], state["leads"])
    for line in skip_log.summary_lines():
        print(line, flush=True)
    print(f"\nDone. Results: {output_path}", flush=True)
    print(f"Raw links: {links_path}", flush=True)
    print(f"Deduped links: {deduped_path}", flush=True)
    return output_path


def main(argv: list[str] | None = None) -> int:
    from listgen.settings_loader import apply_settings, load_settings, setup_poc_path

    setup_poc_path()

    raw_args = argv if argv is not None else sys.argv[1:]
    settings_path, _ = _parse_settings_path(raw_args)
    settings = load_settings(settings_path)
    _apply_cli_overrides(settings, raw_args)
    apply_settings(settings)

    test_run, test_city = _resolve_test_run(settings, raw_args)
    links_only = _resolve_run_mode(settings, raw_args) == "links_only"
    run_bulk(settings, test_run=test_run, test_city=test_city, links_only=links_only)
    return 0

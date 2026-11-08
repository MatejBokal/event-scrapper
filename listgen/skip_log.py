"""Append-only skip/drop audit log for listgen crawl decisions."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


@dataclass
class SkipEvent:
    ts: str
    run_id: str
    stage: str
    decision: str
    reason: str
    detail: str = ""
    url: str = ""
    host: str = ""
    country: str = ""
    city: str = ""
    field: str = ""
    task_key: str = ""


class SkipLog:
    def __init__(self, path: Path, *, run_id: str = "") -> None:
        self.path = path
        self.run_id = run_id
        self._counts: Counter[tuple[str, str]] = Counter()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(
        self,
        *,
        stage: str,
        decision: str,
        reason: str,
        detail: str = "",
        url: str = "",
        country: str = "",
        city: str = "",
        field: str = "",
        task_key: str = "",
    ) -> None:
        host = ""
        if url:
            try:
                host = urlparse(url).netloc.lower().removeprefix("www.")
            except Exception:
                host = ""
        event = SkipEvent(
            ts=datetime.now(timezone.utc).isoformat(),
            run_id=self.run_id,
            stage=stage,
            decision=decision,
            reason=reason,
            detail=detail,
            url=url,
            host=host,
            country=country,
            city=city,
            field=field,
            task_key=task_key,
        )
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")
        self._counts[(stage, reason)] += 1

    def summary_lines(self) -> list[str]:
        if not self._counts:
            return ["skip log: (no skips)"]
        lines = [f"skip log: {self.path}"]
        for (stage, reason), count in sorted(self._counts.items(), key=lambda x: (-x[1], x[0])):
            lines.append(f"  {count:4d}  {stage}/{reason}")
        return lines


def resolve_skip_log_path(
    settings: dict[str, Any],
    repo_root: Path,
    *,
    run_stamp: str = "",
) -> Path:
    output = settings.get("output", {}) if isinstance(settings.get("output"), dict) else {}
    raw = str(output.get("skip_log_file") or "listgen/output/skip_log.jsonl")
    path = Path(raw)
    if not path.is_absolute():
        path = repo_root / path
    if run_stamp and path.name == "skip_log.jsonl":
        path = path.with_name(f"skip_log_{run_stamp}.jsonl")
    elif run_stamp and "{run}" in str(path):
        path = Path(str(path).replace("{run}", run_stamp))
    return path

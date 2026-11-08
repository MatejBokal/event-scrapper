"""Same-run domain memory + persistent denylist for junk/listing hosts."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from backend.domains import domain as host_of

# Path/host smells for conference mills and calendars (learned from exports).
_MILL_HOST_MARKERS = (
    "biofora",
    "sciencefora",
    "researchforum",
    "researchleague",
    "academicresearch",
    "conferenceresearch",
    "academicsera",
    "conferencealert",
    "allconference",
    "annualcongress",
    "swiss-congress",
    "tradefairdates",
    "conferencelists",
    "happeningnext",
    "eventseye",
    "10times",
)

_MILL_PATH_RE = re.compile(
    r"/conference/\d+/|/events-list/|/conferences/?$",
    re.IGNORECASE,
)


def registrable_host(url: str) -> str:
    """Hostname used for one-crawl-per-domain (www-stripped)."""
    return host_of(url)


def looks_like_mill_or_listing(url: str) -> bool:
    host = registrable_host(url)
    if any(marker in host for marker in _MILL_HOST_MARKERS):
        return True
    path = urlparse(url).path or ""
    return bool(_MILL_PATH_RE.search(path))


class DomainMemory:
    """Tracks domains crawled this run and a durable denylist for future runs."""

    def __init__(self, denylist_path: Path) -> None:
        self.denylist_path = denylist_path
        self.crawled_hosts: set[str] = set()
        self.denied_hosts: set[str] = set()
        self._load_denylist()

    def _load_denylist(self) -> None:
        if not self.denylist_path.exists():
            return
        try:
            payload = json.loads(self.denylist_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        hosts = payload.get("hosts") if isinstance(payload, dict) else payload
        if isinstance(hosts, list):
            self.denied_hosts = {str(h).lower().removeprefix("www.") for h in hosts if h}

    def save_denylist(self) -> None:
        self.denylist_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "hosts": sorted(self.denied_hosts),
            "count": len(self.denied_hosts),
        }
        self.denylist_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def hydrate_from_completed_urls(self, urls: list[str] | set[str]) -> None:
        for url in urls:
            host = registrable_host(url)
            if host:
                self.crawled_hosts.add(host)

    def is_denied(self, url: str) -> bool:
        host = registrable_host(url)
        return bool(host) and host in self.denied_hosts

    def already_crawled(self, url: str) -> bool:
        host = registrable_host(url)
        return bool(host) and host in self.crawled_hosts

    def should_skip(self, url: str) -> str | None:
        """Return skip reason code, or None if the URL may be crawled."""
        host = registrable_host(url)
        if not host:
            return None
        if host in self.denied_hosts:
            return "denylisted_domain"
        if host in self.crawled_hosts:
            return "domain_already_crawled"
        if looks_like_mill_or_listing(url):
            self.deny(url, reason="mill_pattern")
            return "mill_pattern"
        return None

    def mark_crawled(self, url: str) -> None:
        host = registrable_host(url)
        if host:
            self.crawled_hosts.add(host)

    def deny(self, url: str, *, reason: str = "") -> None:
        host = registrable_host(url)
        if not host:
            return
        self.denied_hosts.add(host)
        self.crawled_hosts.add(host)
        self.save_denylist()
        _ = reason

    def to_state(self) -> dict[str, Any]:
        return {
            "crawled_hosts": sorted(self.crawled_hosts),
            "denied_hosts": sorted(self.denied_hosts),
        }

    def load_state(self, payload: dict[str, Any] | None) -> None:
        if not payload:
            return
        for host in payload.get("crawled_hosts") or []:
            self.crawled_hosts.add(str(host).lower().removeprefix("www."))
        for host in payload.get("denied_hosts") or []:
            self.denied_hosts.add(str(host).lower().removeprefix("www."))

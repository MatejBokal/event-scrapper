"""Headless browser fetch for JavaScript-rendered conference pages."""

from __future__ import annotations

from urllib.parse import urlparse

from backend.config import (
    BROWSER_USER_AGENT,
    LISTING_PLAYWRIGHT_FIRST_DOMAINS,
    PLAYWRIGHT_TIMEOUT_MS,
    PLAYWRIGHT_WAIT_MS,
)

_playwright_domains: set[str] = set()


def _host(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def remember_js_domain(url: str) -> None:
    host = _host(url)
    if host:
        _playwright_domains.add(host)


def domain_prefers_playwright(url: str) -> bool:
    return _host(url) in _playwright_domains


def listing_domain_prefers_playwright(url: str) -> bool:
    host = _host(url)
    return any(listing in host for listing in LISTING_PLAYWRIGHT_FIRST_DOMAINS)


def reset_playwright_domain_cache() -> None:
    _playwright_domains.clear()


class PlaywrightSession:
    """Reuse one browser per crawl run."""

    def __init__(self) -> None:
        self._playwright = None
        self._browser = None

    def fetch(self, url: str) -> tuple[str, str]:
        from playwright.sync_api import sync_playwright

        if self._browser is None:
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=True)

        page = self._browser.new_page(user_agent=BROWSER_USER_AGENT, locale="en-US")
        try:
            page.set_extra_http_headers({"Accept-Language": "en-US,en;q=0.9"})
            page.goto(url, wait_until="domcontentloaded", timeout=PLAYWRIGHT_TIMEOUT_MS)
            page.wait_for_timeout(PLAYWRIGHT_WAIT_MS)
            return page.url, page.content()
        finally:
            page.close()

    def close(self) -> None:
        if self._browser is not None:
            self._browser.close()
            self._browser = None
        if self._playwright is not None:
            self._playwright.stop()
            self._playwright = None

    def __enter__(self) -> PlaywrightSession:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

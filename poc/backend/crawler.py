"""Fetch and parse conference pages on the same domain."""

from __future__ import annotations

import concurrent.futures
import time
from collections import deque
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from requests import HTTPError
import trafilatura
from bs4 import BeautifulSoup

from backend.config import (
    JS_FRAMEWORK_MARKERS,
    GATEWAY_PAGE_TIMEOUT_SECONDS,
    MAX_CRAWL_DEPTH,
    MAX_PAGES_PER_SITE,
    MIN_PAGE_TEXT_LENGTH,
    PREFERRED_PATH_KEYWORDS,
    REQUEST_DELAY_SECONDS,
    ROBOTS_TIMEOUT_SECONDS,
    SITE_CRAWL_TIMEOUT_SECONDS,
    USER_AGENT,
)
from backend.models import CrawledPage, CrawlSiteResult, SelectedSite
from backend.playwright_fetcher import (
    PlaywrightSession,
    domain_prefers_playwright,
    listing_domain_prefers_playwright,
    remember_js_domain,
)


def _normalize_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") or "/"
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def _same_domain(base: str, candidate: str) -> bool:
    base_netloc = urlparse(base).netloc.lower().removeprefix("www.")
    candidate_netloc = urlparse(candidate).netloc.lower().removeprefix("www.")
    return base_netloc == candidate_netloc


def _path_priority(path: str) -> int:
    path_lower = path.lower()
    for index, keyword in enumerate(PREFERRED_PATH_KEYWORDS):
        if keyword in path_lower:
            return len(PREFERRED_PATH_KEYWORDS) - index
    return 0


def _guess_page_type(path: str) -> str:
    path_lower = path.lower()
    for keyword in PREFERRED_PATH_KEYWORDS:
        if keyword in path_lower:
            return keyword
    return "other"


def _can_fetch(robots: RobotFileParser | None, url: str) -> bool:
    if robots is None:
        return True
    try:
        return robots.can_fetch(USER_AGENT, url)
    except Exception:
        return True


def _load_robots(base_url: str) -> RobotFileParser | None:
    parsed = urlparse(base_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    parser = RobotFileParser()
    try:
        response = requests.get(
            robots_url,
            timeout=ROBOTS_TIMEOUT_SECONDS,
            headers={"User-Agent": USER_AGENT},
        )
        if response.status_code >= 400:
            return None
        parser.parse(response.text.splitlines())
        return parser
    except Exception:
        return None


def _open_playwright_session() -> PlaywrightSession | None:
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401

        return PlaywrightSession()
    except ImportError:
        return None


def _fetch_html_http(url: str, session: requests.Session, *, timeout: int = 20) -> tuple[str, str]:
    response = session.get(url, timeout=timeout)
    response.raise_for_status()
    content_type = response.headers.get("Content-Type", "")
    if "text" not in content_type and "html" not in content_type:
        return url, ""
    return url, response.text


def _body_text_length(html: str) -> int:
    soup = BeautifulSoup(html, "lxml")
    body = soup.find("body")
    if not body:
        return 0
    return len(body.get_text(strip=True))


def _looks_like_js_shell(html: str) -> bool:
    lower = html.lower()
    if not any(marker in lower for marker in JS_FRAMEWORK_MARKERS):
        return False
    return _body_text_length(html) < MIN_PAGE_TEXT_LENGTH


def _needs_playwright(html: str, text: str, url: str) -> bool:
    if domain_prefers_playwright(url):
        return True
    stripped = text.strip()
    if len(stripped) < MIN_PAGE_TEXT_LENGTH:
        return True
    if _looks_like_js_shell(html):
        return True
    if "mailto:" not in html.lower() and len(stripped) < MIN_PAGE_TEXT_LENGTH * 2:
        if _body_text_length(html) < MIN_PAGE_TEXT_LENGTH:
            return True
    return False


def _fetch_page_html(
    url: str,
    session: requests.Session,
    playwright: PlaywrightSession | None,
) -> tuple[str, str]:
    if (
        playwright is not None
        and (domain_prefers_playwright(url) or listing_domain_prefers_playwright(url))
    ):
        try:
            final_url, html = playwright.fetch(url)
            remember_js_domain(final_url)
            return final_url, html
        except Exception:
            pass

    try:
        final_url, html = _fetch_html_http(url, session)
    except HTTPError as exc:
        if playwright is not None and exc.response is not None and exc.response.status_code in (
            401,
            403,
            429,
        ):
            try:
                final_url, html = playwright.fetch(url)
                remember_js_domain(final_url)
                return final_url, html
            except Exception:
                raise
        raise
    if not html:
        if playwright is not None:
            try:
                final_url, html = playwright.fetch(url)
                remember_js_domain(final_url)
            except Exception:
                return final_url, ""
        return final_url, html

    text = _extract_text(html)
    if playwright is not None and _needs_playwright(html, text, final_url):
        try:
            final_url, rendered = playwright.fetch(url)
            remember_js_domain(final_url)
            return final_url, rendered
        except Exception:
            pass

    return final_url, html


def _extract_title(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        return og_title["content"].strip()
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True)
    return ""


def _extract_text(html: str) -> str:
    text = trafilatura.extract(html, include_comments=False, include_tables=True)
    if text and len(text.strip()) >= MIN_PAGE_TEXT_LENGTH:
        return text.strip()

    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)


def _discover_links(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    links: list[str] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        absolute = urljoin(base_url, href)
        parsed = urlparse(absolute)
        if parsed.scheme not in ("http", "https"):
            continue
        if not _same_domain(base_url, absolute):
            continue
        normalized = _normalize_url(absolute)
        if normalized not in seen:
            seen.add(normalized)
            links.append(normalized)
    links.sort(key=lambda link: _path_priority(urlparse(link).path), reverse=True)
    return links


def fetch_single_page(
    url: str,
    playwright: PlaywrightSession | None = None,
) -> tuple[str, str]:
    """Fetch one page (HTTP with optional Playwright fallback). Used for listing discovery."""
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    owns_playwright = playwright is None
    active_playwright = playwright or _open_playwright_session()
    try:
        return _fetch_page_html(url, session, active_playwright)
    finally:
        if owns_playwright and active_playwright is not None:
            active_playwright.close()


def probe_page(url: str, *, conference_url: str = "") -> CrawledPage | None:
    """Fetch one page into a CrawledPage for keyword/presence probes. Returns None on failure."""
    try:
        final_url, html = fetch_single_page(url)
    except Exception:
        return None
    if not html:
        return None
    return CrawledPage(
        url=final_url or url,
        title=_extract_title(html),
        page_type="probe",
        extracted_text=_extract_text(html),
        conference_url=conference_url or url,
        html=html,
    )


def fetch_gateway_page(url: str) -> tuple[str, str]:
    """HTTP-only gateway fetch for listing/ticket pages. Never raises."""
    http_timeout = min(15, max(5, int(GATEWAY_PAGE_TIMEOUT_SECONDS)))
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    try:
        return _fetch_html_http(url, session, timeout=http_timeout)
    except Exception:
        return url, ""


def crawl_site(site: SelectedSite) -> CrawlSiteResult:
    timeout = max(30, int(SITE_CRAWL_TIMEOUT_SECONDS))
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(_crawl_site_impl, site)
    try:
        return future.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        return CrawlSiteResult(
            pages=[],
            block_reason="timeout",
            error_message=f"site crawl exceeded {timeout}s",
        )
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _crawl_site_impl(site: SelectedSite) -> CrawlSiteResult:
    start_url = _normalize_url(site.url)
    robots = _load_robots(start_url)
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    queue: deque[tuple[str, int]] = deque([(start_url, 0)])
    visited: set[str] = set()
    pages: list[CrawledPage] = []
    first_failure_status: int | None = None
    first_failure_message: str | None = None

    playwright = None
    try:
        while queue and len(pages) < MAX_PAGES_PER_SITE:
            url, depth = queue.popleft()
            if url in visited:
                continue
            visited.add(url)

            if not _can_fetch(robots, url):
                continue

            time.sleep(REQUEST_DELAY_SECONDS)

            try:
                if playwright is None and (
                    domain_prefers_playwright(url)
                    or listing_domain_prefers_playwright(url)
                ):
                    playwright = _open_playwright_session()
                final_url, html = _fetch_page_html(url, session, playwright)
                text = _extract_text(html) if html else ""
                if playwright is None and html and _needs_playwright(html, text, final_url):
                    playwright = _open_playwright_session()
                    if playwright is not None:
                        final_url, html = playwright.fetch(url)
                        remember_js_domain(final_url)
            except HTTPError as exc:
                if first_failure_message is None:
                    first_failure_status = exc.response.status_code if exc.response is not None else None
                    first_failure_message = str(exc)
                continue
            except Exception as exc:
                if first_failure_message is None:
                    first_failure_message = str(exc)
                continue

            if not html:
                if first_failure_message is None:
                    first_failure_message = "empty response"
                continue

            text = _extract_text(html)
            path = urlparse(final_url).path

            pages.append(
                CrawledPage(
                    url=final_url,
                    title=_extract_title(html),
                    page_type=_guess_page_type(path),
                    extracted_text=text,
                    conference_url=start_url,
                    html=html,
                )
            )

            if depth < MAX_CRAWL_DEPTH:
                for link in _discover_links(html, final_url):
                    if link not in visited:
                        queue.append((link, depth + 1))
    finally:
        if playwright is not None:
            playwright.close()

    if pages:
        return CrawlSiteResult(pages=pages)

    if first_failure_status == 403:
        reason = "http_403"
    elif first_failure_status == 401:
        reason = "http_401"
    elif first_failure_status == 429:
        reason = "http_429"
    elif first_failure_status is not None:
        reason = f"http_{first_failure_status}"
    elif first_failure_message:
        reason = "fetch_failed"
    else:
        reason = "empty"

    return CrawlSiteResult(
        pages=[],
        block_reason=reason,
        http_status=first_failure_status,
        error_message=first_failure_message,
    )


def get_conference_name(pages: list[CrawledPage]) -> str | None:
    for page in pages:
        if page.title:
            return page.title
    return None

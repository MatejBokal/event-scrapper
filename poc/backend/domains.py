"""Shared domain classification helpers."""

from __future__ import annotations

from urllib.parse import urlparse

from backend.config import AGGREGATOR_DENYLIST, LISTING_DOMAINS, SPAM_DOMAINS, TICKET_VENDOR_DOMAINS


def domain(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def _matches_domain_list(url: str, entries: list[str] | tuple[str, ...]) -> bool:
    host = domain(url)
    for entry in entries:
        if entry.endswith("*"):
            if host.startswith(entry.removesuffix("*")):
                return True
        elif entry in host:
            return True
    return False


def is_listing_domain(url: str) -> bool:
    return _matches_domain_list(url, LISTING_DOMAINS)


def is_spam_domain(url: str) -> bool:
    return _matches_domain_list(url, SPAM_DOMAINS)


def is_denylisted_domain(url: str) -> bool:
    return _matches_domain_list(url, AGGREGATOR_DENYLIST)


def is_ticket_vendor_domain(url: str) -> bool:
    return _matches_domain_list(url, TICKET_VENDOR_DOMAINS)


def is_gateway_domain(url: str) -> bool:
    """Listing or ticket pages that link to official conference sites."""
    return is_listing_domain(url) or is_ticket_vendor_domain(url)


def is_skip_crawl_domain(url: str) -> bool:
    """Domains we should not full-crawl directly (use gateway resolution first)."""
    return is_gateway_domain(url) or is_blocked_outbound_domain(url)


def is_skip_crawl_queue_url(url: str) -> bool:
    """URLs to omit from the crawl queue (listing pages resolved at discovery)."""
    if is_listing_domain(url):
        return True
    return is_spam_domain(url) or is_denylisted_domain(url)


def is_blocked_outbound_domain(url: str) -> bool:
    """Domains we never treat as official conference targets."""
    return (
        is_listing_domain(url)
        or is_ticket_vendor_domain(url)
        or is_spam_domain(url)
        or is_denylisted_domain(url)
    )

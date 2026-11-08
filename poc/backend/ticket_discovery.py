"""Resolve official conference URLs from ticket vendor pages (oeticket, Eventim, etc.)."""

from __future__ import annotations

from backend.domains import is_ticket_vendor_domain
from backend.listing_discovery import (
    expand_sites_via_listings,
    resolve_gateway_site,
)
from backend.models import ListingDiscovery, SearchParams, SelectedSite
from backend.playwright_fetcher import PlaywrightSession


def resolve_ticket_site(
    site: SelectedSite,
    params: SearchParams,
    playwright: PlaywrightSession | None = None,
) -> tuple[list[SelectedSite], list[ListingDiscovery]]:
    """Light-fetch a ticket page and extract official conference URLs."""
    if not is_ticket_vendor_domain(site.url):
        return [], []
    return resolve_gateway_site(site, params, playwright=playwright)


def expand_sites_via_tickets(
    sites: list[SelectedSite],
    params: SearchParams,
) -> tuple[list[SelectedSite], list[SelectedSite], list[ListingDiscovery], list[str]]:
    """Same gateway expansion as listings — ticket vendors share the listing pipeline."""
    return expand_sites_via_listings(sites, params)

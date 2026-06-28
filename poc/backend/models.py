from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable, Literal


ProgressCallback = Callable[[str, dict[str, Any]], None]

ExtractionMethod = Literal["mailto", "regex", "regex+keyword", "llm"]


@dataclass
class SearchParams:
    field: str
    region: str
    selected_months: tuple[str, ...]
    contact_type: str = "organizer"
    max_conferences: int = 10
    custom_region: str = ""
    manual_official_url: str = ""

    @property
    def start_month(self) -> str:
        return min(self.selected_months) if self.selected_months else ""

    @property
    def end_month(self) -> str:
        return max(self.selected_months) if self.selected_months else ""


@dataclass
class SearchHit:
    title: str
    url: str
    snippet: str
    source_query: str
    rank: int
    url_score: float = 0.0


@dataclass
class SelectedSite:
    url: str
    title: str
    url_score: float
    snippet: str = ""
    source: str = "search"
    discovered_from: str = ""


@dataclass
class ListingDiscovery:
    listing_url: str
    listing_title: str
    official_url: str
    official_title: str
    link_score: float


@dataclass
class CrawledPage:
    url: str
    title: str
    page_type: str
    extracted_text: str
    conference_url: str
    html: str = ""


@dataclass
class CrawlSiteResult:
    pages: list[CrawledPage] = field(default_factory=list)
    block_reason: str | None = None
    http_status: int | None = None
    error_message: str | None = None

    @property
    def blocked(self) -> bool:
        return bool(self.block_reason) and not self.pages


@dataclass
class RawEmailHit:
    email: str
    source_url: str
    page_title: str | None
    extracted_text: str
    extraction_method: ExtractionMethod
    contact_type: str
    conference_url: str
    conference_name: str | None = None
    organizer_name: str | None = None
    organizer_role: str | None = None
    organization: str | None = None
    phone: str | None = None
    website: str | None = None
    linkedin_url: str | None = None


@dataclass
class ConferenceLlmMetadata:
    name: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    month_year: str | None = None
    location: str | None = None
    country: str | None = None
    description: str | None = None
    language: str | None = None


@dataclass
class ExtractEmailsResult:
    hits: list[RawEmailHit]
    conference_metadata: ConferenceLlmMetadata | None = None
    llm_audit: dict[str, Any] | None = None


@dataclass
class ContactResult:
    conference_name: str | None
    conference_url: str
    field: str
    region: str
    email: str
    contact_type: str
    source_url: str
    evidence_snippet: str
    confidence: int
    extraction_method: str
    page_title: str | None
    organizer_name: str | None = None
    organizer_role: str | None = None
    organization: str | None = None
    phone: str | None = None
    website: str | None = None
    linkedin_url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "conference_name": self.conference_name,
            "conference_url": self.conference_url,
            "field": self.field,
            "region": self.region,
            "email": self.email,
            "contact_type": self.contact_type,
            "source_url": self.source_url,
            "evidence_snippet": self.evidence_snippet,
            "confidence": self.confidence,
            "extraction_method": self.extraction_method,
            "page_title": self.page_title,
            "organizer_name": self.organizer_name,
            "organizer_role": self.organizer_role,
            "organization": self.organization,
            "phone": self.phone,
            "website": self.website,
            "linkedin_url": self.linkedin_url,
        }


@dataclass
class LeadResult:
    conference_name: str | None
    conference_url: str
    event_date: str | None
    location: str | None
    field: str
    region: str
    organizer_name: str | None
    organizer_email: str
    organizer_role: str | None
    contact_quality: str
    source_url: str
    evidence_snippet: str
    confidence: int
    language: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "conference_name": self.conference_name,
            "conference_url": self.conference_url,
            "event_date": self.event_date,
            "location": self.location,
            "field": self.field,
            "region": self.region,
            "organizer_name": self.organizer_name,
            "organizer_email": self.organizer_email,
            "organizer_role": self.organizer_role,
            "contact_quality": self.contact_quality,
            "source_url": self.source_url,
            "evidence_snippet": self.evidence_snippet,
            "confidence": self.confidence,
            "language": self.language,
        }


@dataclass
class PipelineStats:
    queries_run: int = 0
    search_hits: int = 0
    sites_selected: int = 0
    pages_crawled: int = 0
    emails_found: int = 0
    leads_found: int = 0
    pages_without_emails: int = 0
    filtered_hits: int = 0
    listing_pages_processed: int = 0
    official_urls_from_listings: int = 0


@dataclass
class PipelineResult:
    params: SearchParams
    leads: list[LeadResult] = field(default_factory=list)
    contacts: list[ContactResult] = field(default_factory=list)
    raw_search_hits: list[SearchHit] = field(default_factory=list)
    search_hits: list[SearchHit] = field(default_factory=list)
    selected_sites: list[SelectedSite] = field(default_factory=list)
    listing_sources: list[SelectedSite] = field(default_factory=list)
    listing_discoveries: list[ListingDiscovery] = field(default_factory=list)
    listing_warnings: list[str] = field(default_factory=list)
    skipped_urls: list[SearchHit] = field(default_factory=list)
    filtered_urls: list[SearchHit] = field(default_factory=list)
    crawled_pages: list[CrawledPage] = field(default_factory=list)
    pages_without_emails: list[CrawledPage] = field(default_factory=list)
    stats: PipelineStats = field(default_factory=PipelineStats)
    errors: list[str] = field(default_factory=list)

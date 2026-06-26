from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EvidenceCreate(BaseModel):
    source_url: str
    extracted_text_snippet: str = Field(min_length=1)
    source_title: str | None = None
    evidence_type: str | None = "contact_page"


class EvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    conference_id: UUID
    organizer_id: UUID | None
    source_url: str
    source_title: str | None
    extracted_text_snippet: str
    evidence_type: str | None
    extraction_date: datetime


class ConferenceCreate(BaseModel):
    name: str
    official_url: str
    field: str | None = None
    region: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    month_year: str | None = None
    location: str | None = None
    country: str | None = None
    description: str | None = None
    language: str | None = None
    status: str = "discovered"
    confidence_score: int = 0


class ConferenceUpdate(BaseModel):
    name: str | None = None
    official_url: str | None = None
    field: str | None = None
    region: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    month_year: str | None = None
    location: str | None = None
    country: str | None = None
    description: str | None = None
    language: str | None = None
    status: str | None = None
    confidence_score: int | None = None
    crawl_block_reason: str | None = None
    crawl_http_status: int | None = None
    crawl_block_detail: str | None = None


class ConferenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    field: str | None
    region: str | None
    start_date: date | None
    end_date: date | None
    month_year: str | None
    location: str | None
    country: str | None
    language: str | None
    official_url: str
    official_url_normalized: str
    description: str | None
    status: str
    confidence_score: int
    crawl_block_reason: str | None = None
    crawl_http_status: int | None = None
    crawl_block_detail: str | None = None
    crawl_blocked_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class CrawledPageSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    url: str
    title: str | None
    page_type: str | None
    text_length: int
    crawled_at: datetime


class ConferenceDetail(ConferenceRead):
    organizers: list["OrganizerRead"] = []
    evidence: list[EvidenceRead] = []
    crawled_pages: list[CrawledPageSummary] = []


class OrganizerCreate(BaseModel):
    conference_id: UUID
    email: str
    name: str | None = None
    organization: str | None = None
    role: str | None = None
    phone: str | None = None
    website: str | None = None
    linkedin_url: str | None = None
    contact_type: str = "organizer"
    contact_quality: str | None = None
    is_primary_lead: bool = False
    confidence_score: int = 0
    extraction_method: str | None = "manual"
    evidence: EvidenceCreate


class OrganizerUpdate(BaseModel):
    email: str | None = None
    name: str | None = None
    organization: str | None = None
    role: str | None = None
    phone: str | None = None
    website: str | None = None
    linkedin_url: str | None = None
    contact_type: str | None = None
    contact_quality: str | None = None
    is_primary_lead: bool | None = None
    confidence_score: int | None = None
    extraction_method: str | None = None


class OrganizerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    conference_id: UUID
    name: str | None
    organization: str | None
    role: str | None
    email: str
    phone: str | None
    website: str | None
    linkedin_url: str | None
    contact_type: str
    contact_quality: str | None
    is_primary_lead: bool
    confidence_score: int
    extraction_method: str | None
    created_at: datetime


ConferenceDetail.model_rebuild()

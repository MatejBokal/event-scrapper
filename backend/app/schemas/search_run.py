from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SearchRunCreate(BaseModel):
    field: str
    region: str
    selected_months: list[str] = Field(min_length=1)
    contact_type: str = "organizer"
    max_conferences: int = Field(default=10, ge=1, le=20)
    manual_official_url: str = ""
    execute_search: bool = True
    execute_crawl: bool = False
    execute_extract: bool = False


class SearchQueryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    query_text: str
    order_index: int


class SearchResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str | None
    url: str
    snippet: str | None
    source_query: str | None
    rank: int | None
    url_score: float | None
    filter_status: str | None


class CrawlTargetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    conference_id: UUID | None
    url: str
    title: str | None
    source: str | None
    discovered_from: str | None
    url_score: float | None


class CrawledPageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    conference_id: UUID
    url: str
    title: str | None
    page_type: str | None
    text_length: int
    crawled_at: datetime


class SearchRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    field: str
    region: str
    selected_months: list[str]
    contact_type: str
    max_conferences: int
    manual_official_url: str | None
    status: str
    stats: dict
    errors: list
    created_at: datetime
    finished_at: datetime | None


class SearchRunDetail(SearchRunRead):
    queries: list[SearchQueryRead] = []
    results: list[SearchResultRead] = []
    crawl_targets: list[CrawlTargetRead] = []
    crawled_pages: list[CrawledPageRead] = []

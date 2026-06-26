import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SearchRun(Base):
    __tablename__ = "search_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    field: Mapped[str] = mapped_column(Text, nullable=False)
    region: Mapped[str] = mapped_column(Text, nullable=False)
    selected_months: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    contact_type: Mapped[str] = mapped_column(Text, nullable=False, default="organizer")
    max_conferences: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    manual_official_url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    stats: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    errors: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    queries: Mapped[list["SearchQuery"]] = relationship(back_populates="search_run")
    results: Mapped[list["SearchResult"]] = relationship(back_populates="search_run")
    crawl_targets: Mapped[list["CrawlTarget"]] = relationship(back_populates="search_run")


class SearchQuery(Base):
    __tablename__ = "search_queries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    search_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("search_runs.id", ondelete="CASCADE"), nullable=False
    )
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)

    search_run: Mapped["SearchRun"] = relationship(back_populates="queries")


class SearchResult(Base):
    __tablename__ = "search_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    search_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("search_runs.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    snippet: Mapped[str | None] = mapped_column(Text)
    source_query: Mapped[str | None] = mapped_column(Text)
    rank: Mapped[int | None] = mapped_column(Integer)
    url_score: Mapped[float | None] = mapped_column(Numeric)
    filter_status: Mapped[str | None] = mapped_column(Text)

    search_run: Mapped["SearchRun"] = relationship(back_populates="results")


class CrawlTarget(Base):
    __tablename__ = "crawl_targets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    search_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("search_runs.id", ondelete="CASCADE"), nullable=False
    )
    conference_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conferences.id", ondelete="SET NULL")
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(Text)
    discovered_from: Mapped[str | None] = mapped_column(Text)
    url_score: Mapped[float | None] = mapped_column(Numeric)

    search_run: Mapped["SearchRun"] = relationship(back_populates="crawl_targets")
    conference: Mapped["Conference | None"] = relationship(back_populates="crawl_targets")


class CrawledPage(Base):
    __tablename__ = "crawled_pages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    conference_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conferences.id", ondelete="CASCADE"), nullable=False
    )
    search_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("search_runs.id", ondelete="SET NULL")
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    page_type: Mapped[str | None] = mapped_column(Text)
    extracted_text: Mapped[str | None] = mapped_column(Text)
    crawled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    conference: Mapped["Conference"] = relationship(back_populates="crawled_pages")


class Conference(Base):
    __tablename__ = "conferences"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    field: Mapped[str | None] = mapped_column(Text)
    region: Mapped[str | None] = mapped_column(Text)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    month_year: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(Text)
    official_url: Mapped[str] = mapped_column(Text, nullable=False)
    official_url_normalized: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="discovered")
    confidence_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    crawl_block_reason: Mapped[str | None] = mapped_column(Text)
    crawl_http_status: Mapped[int | None] = mapped_column(Integer)
    crawl_block_detail: Mapped[str | None] = mapped_column(Text)
    crawl_blocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_seen_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("search_runs.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    organizers: Mapped[list["Organizer"]] = relationship(back_populates="conference")
    evidence: Mapped[list["SourceEvidence"]] = relationship(back_populates="conference")
    crawl_targets: Mapped[list["CrawlTarget"]] = relationship(back_populates="conference")
    crawled_pages: Mapped[list["CrawledPage"]] = relationship(back_populates="conference")


class Organizer(Base):
    __tablename__ = "organizers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    conference_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conferences.id", ondelete="CASCADE"), nullable=False
    )
    search_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("search_runs.id", ondelete="SET NULL")
    )
    name: Mapped[str | None] = mapped_column(Text)
    organization: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str | None] = mapped_column(Text)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str | None] = mapped_column(Text)
    website: Mapped[str | None] = mapped_column(Text)
    linkedin_url: Mapped[str | None] = mapped_column(Text)
    contact_type: Mapped[str] = mapped_column(Text, nullable=False, default="organizer")
    contact_quality: Mapped[str | None] = mapped_column(Text)
    is_primary_lead: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    confidence_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    extraction_method: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    conference: Mapped["Conference"] = relationship(back_populates="organizers")
    evidence: Mapped[list["SourceEvidence"]] = relationship(back_populates="organizer")


class SourceEvidence(Base):
    __tablename__ = "source_evidence"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    conference_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conferences.id", ondelete="CASCADE"), nullable=False
    )
    organizer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizers.id", ondelete="SET NULL")
    )
    search_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("search_runs.id", ondelete="SET NULL")
    )
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_title: Mapped[str | None] = mapped_column(Text)
    extracted_text_snippet: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_type: Mapped[str | None] = mapped_column(Text)
    extraction_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    conference: Mapped["Conference"] = relationship(back_populates="evidence")
    organizer: Mapped["Organizer | None"] = relationship(back_populates="evidence")

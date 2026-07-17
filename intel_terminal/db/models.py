"""SQLAlchemy models for the financial intelligence terminal."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models import Base


class Article(Base):
    """Normalized news article after fetch + dedup."""

    __tablename__ = "intel_articles"
    __table_args__ = (
        UniqueConstraint("url_hash", name="uq_intel_articles_url_hash"),
        Index("ix_intel_articles_published", "published_at"),
        Index("ix_intel_articles_category_score", "category", "relevance_score"),
        Index("ix_intel_articles_region", "region"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    url_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    source: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_fetch_status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")
    category: Mapped[str] = mapped_column(String(60), nullable=False, default="Uncategorized", index=True)
    relevance_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    region: Mapped[str] = mapped_column(String(20), nullable=False, default="global")
    language: Mapped[str | None] = mapped_column(String(12), nullable=True)
    is_paywalled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dedup_cluster_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    mention_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    vietnam_macro_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    vietnam_banking_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    vietnam_wealth_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    raw_metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    summaries: Mapped[list["ArticleSummary"]] = relationship(
        back_populates="article", cascade="all, delete-orphan", lazy="selectin"
    )
    bookmarks: Mapped[list["ArticleBookmark"]] = relationship(
        back_populates="article", cascade="all, delete-orphan", lazy="selectin"
    )


class ArticleSummary(Base):
    """Cached LLM output per article and agent type."""

    __tablename__ = "intel_article_summaries"
    __table_args__ = (
        UniqueConstraint("article_id", "agent_type", "model", name="uq_intel_summary_article_agent_model"),
        Index("ix_intel_summary_agent", "agent_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("intel_articles.id", ondelete="CASCADE"), index=True)
    agent_type: Mapped[str] = mapped_column(String(40), nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str] = mapped_column(String(80), nullable=False)
    summary_json: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    article: Mapped["Article"] = relationship(back_populates="summaries")


class ArticleBookmark(Base):
    __tablename__ = "intel_article_bookmarks"
    __table_args__ = (UniqueConstraint("article_id", name="uq_intel_bookmark_article"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("intel_articles.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    article: Mapped["Article"] = relationship(back_populates="bookmarks")


class DailyNewspaper(Base):
    """One structured daily report (Bloomberg-style newspaper)."""

    __tablename__ = "intel_daily_newspapers"
    __table_args__ = (UniqueConstraint("report_date", name="uq_intel_newspaper_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    market_regime: Mapped[str] = mapped_column(String(20), nullable=False, default="Neutral")
    content_json: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class PipelineRun(Base):
    """Audit log for ingest / analyze runs."""

    __tablename__ = "intel_pipeline_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    articles_fetched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    articles_new: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    articles_deduped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    errors_json: Mapped[str | None] = mapped_column(Text, nullable=True)

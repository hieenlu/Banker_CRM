"""News / newspaper schemas."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

from api.schemas.common import ORMModel


class ArticleOut(ORMModel):
    id: int
    url: str
    title: str
    source: str
    published_at: datetime | None = None
    fetched_at: datetime
    category: str
    relevance_score: float
    region: str
    language: str | None = None
    is_paywalled: bool = False
    mention_count: int = 1
    vietnam_macro_score: float = 0.0
    vietnam_banking_score: float = 0.0
    vietnam_wealth_score: float = 0.0
    bookmarked: bool = False

    @classmethod
    def from_orm_row(cls, row, *, bookmarked: bool = False) -> "ArticleOut":
        return cls(
            id=row.id,
            url=row.url,
            title=row.title,
            source=row.source,
            published_at=row.published_at,
            fetched_at=row.fetched_at,
            category=row.category,
            relevance_score=float(row.relevance_score or 0),
            region=row.region,
            language=row.language,
            is_paywalled=bool(row.is_paywalled),
            mention_count=int(row.mention_count or 1),
            vietnam_macro_score=float(row.vietnam_macro_score or 0),
            vietnam_banking_score=float(row.vietnam_banking_score or 0),
            vietnam_wealth_score=float(row.vietnam_wealth_score or 0),
            bookmarked=bookmarked,
        )


class ArticleDetailOut(ArticleOut):
    body_text: str | None = None
    body_fetch_status: str = "pending"
    canonical_url: str | None = None
    url_hash: str
    dedup_cluster_id: str | None = None

    @classmethod
    def from_orm_row(cls, row, *, bookmarked: bool = False) -> "ArticleDetailOut":
        base = ArticleOut.from_orm_row(row, bookmarked=bookmarked)
        return cls(
            **base.model_dump(),
            body_text=row.body_text,
            body_fetch_status=row.body_fetch_status,
            canonical_url=row.canonical_url,
            url_hash=row.url_hash,
            dedup_cluster_id=row.dedup_cluster_id,
        )


class BookmarkOut(BaseModel):
    id: int
    article_id: int
    created_at: datetime
    article: ArticleOut | None = None


class BookmarkCreate(BaseModel):
    article_id: int


class NewspaperOut(BaseModel):
    id: int
    report_date: date
    market_regime: str
    content: dict[str, Any]
    provider: str
    model: str
    created_at: datetime

    @classmethod
    def from_orm_row(cls, row) -> "NewspaperOut":
        try:
            content = json.loads(row.content_json or "{}")
        except Exception:
            content = {"raw": row.content_json}
        if not isinstance(content, dict):
            content = {"value": content}
        return cls(
            id=row.id,
            report_date=row.report_date,
            market_regime=row.market_regime,
            content=content,
            provider=row.provider,
            model=row.model,
            created_at=row.created_at,
        )


class NewsQuery(BaseModel):
    q: str | None = None
    region: str | None = None
    category: str | None = None
    sort: str = Field(default="latest", pattern="^(latest|relevance)$")
    vietnam_focus: bool = False
    max_age_hours: int | None = 336
    page: int = 1
    page_size: int = 25


class XFeedItemOut(BaseModel):
    headline: str
    source: str
    date: str = ""
    link: str
    handle: str = ""
    tags: list[str] = Field(default_factory=list)

    @classmethod
    def from_cache_item(cls, item: dict[str, Any]) -> "XFeedItemOut":
        handle = str(item.get("handle") or "").strip().lstrip("@")
        source = str(item.get("source") or "")
        if not handle and source.startswith("X @"):
            handle = source[3:].strip()
        tags = item.get("tags") or []
        if not isinstance(tags, list):
            tags = []
        return cls(
            headline=str(item.get("headline") or ""),
            source=source or (f"X @{handle}" if handle else "X"),
            date=str(item.get("date") or ""),
            link=str(item.get("link") or ""),
            handle=handle,
            tags=[str(t) for t in tags if t],
        )


class XFeedsOut(BaseModel):
    items: list[XFeedItemOut]
    fetched_at: datetime | None = None
    profiles: list[str]
    cache_key: str


class XFeedsRefreshOut(BaseModel):
    count: int
    items: list[XFeedItemOut]
    fetched_at: datetime
    profiles: list[str]
    errors: list[str] = Field(default_factory=list)

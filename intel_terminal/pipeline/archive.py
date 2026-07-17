"""Archive retention — keep recent news; cap older archive at N articles."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import and_, delete, desc, func, or_, select
from sqlalchemy.orm import Session

from intel_terminal.db.models import Article, ArticleBookmark, ArticleSummary

# Stories newer than this stay in Dashboard / Latest and are never auto-pruned.
ARCHIVE_FRESH_DAYS = 14
# Max older articles retained in Archive (newest-of-old kept; rest deleted).
ARCHIVE_KEEP_LIMIT = 50


@dataclass(frozen=True)
class PruneResult:
    deleted: int
    archive_remaining: int
    fresh_remaining: int


def _fresh_cutoff(*, fresh_days: int = ARCHIVE_FRESH_DAYS) -> datetime:
    return datetime.utcnow() - timedelta(days=fresh_days)


def _archive_where(cutoff: datetime):
    """SQLAlchemy filter: article is older than the fresh window."""
    return or_(
        and_(Article.published_at.is_not(None), Article.published_at < cutoff),
        and_(Article.published_at.is_(None), Article.fetched_at < cutoff),
    )


def _fresh_where(cutoff: datetime):
    return or_(
        Article.published_at >= cutoff,
        and_(Article.published_at.is_(None), Article.fetched_at >= cutoff),
    )


def _order_newest():
    return (
        desc(func.coalesce(Article.published_at, Article.fetched_at)),
        desc(Article.fetched_at),
    )


def count_archive_articles(
    session: Session,
    *,
    fresh_days: int = ARCHIVE_FRESH_DAYS,
) -> int:
    cutoff = _fresh_cutoff(fresh_days=fresh_days)
    return int(
        session.execute(select(func.count()).select_from(Article).where(_archive_where(cutoff))).scalar_one()
        or 0
    )


def list_archive_articles(
    session: Session,
    *,
    limit: int = ARCHIVE_KEEP_LIMIT,
    fresh_days: int = ARCHIVE_FRESH_DAYS,
    region: str | None = None,
) -> list[Article]:
    """Newest-first archive rows (older than the fresh window)."""
    cutoff = _fresh_cutoff(fresh_days=fresh_days)
    q = select(Article).where(_archive_where(cutoff)).order_by(*_order_newest()).limit(limit)
    if region:
        q = q.where(Article.region == region)
    return list(session.execute(q).scalars().all())


def prune_archive_articles(
    session: Session,
    *,
    keep: int = ARCHIVE_KEEP_LIMIT,
    fresh_days: int = ARCHIVE_FRESH_DAYS,
) -> PruneResult:
    """
    Keep all fresh articles; among older ones keep only the newest `keep`.
    Deletes the rest (summaries/bookmarks cleared first for SQLite FK safety).
    """
    cutoff = _fresh_cutoff(fresh_days=fresh_days)
    archive_ids = list(
        session.execute(
            select(Article.id).where(_archive_where(cutoff)).order_by(*_order_newest())
        )
        .scalars()
        .all()
    )
    keep_ids = set(archive_ids[: max(0, keep)])
    delete_ids = [i for i in archive_ids if i not in keep_ids]

    deleted = 0
    if delete_ids:
        session.execute(delete(ArticleSummary).where(ArticleSummary.article_id.in_(delete_ids)))
        session.execute(delete(ArticleBookmark).where(ArticleBookmark.article_id.in_(delete_ids)))
        result = session.execute(delete(Article).where(Article.id.in_(delete_ids)))
        deleted = int(result.rowcount or 0)
        session.flush()

    fresh_count = int(
        session.execute(select(func.count()).select_from(Article).where(_fresh_where(cutoff))).scalar_one()
        or 0
    )
    archive_left = int(
        session.execute(select(func.count()).select_from(Article).where(_archive_where(cutoff))).scalar_one()
        or 0
    )
    return PruneResult(deleted=deleted, archive_remaining=archive_left, fresh_remaining=fresh_count)


def delete_all_archive_articles(
    session: Session,
    *,
    fresh_days: int = ARCHIVE_FRESH_DAYS,
) -> int:
    """Manually wipe the entire archive (fresh window untouched)."""
    cutoff = _fresh_cutoff(fresh_days=fresh_days)
    ids = list(session.execute(select(Article.id).where(_archive_where(cutoff))).scalars().all())
    if not ids:
        return 0
    session.execute(delete(ArticleSummary).where(ArticleSummary.article_id.in_(ids)))
    session.execute(delete(ArticleBookmark).where(ArticleBookmark.article_id.in_(ids)))
    result = session.execute(delete(Article).where(Article.id.in_(ids)))
    session.flush()
    return int(result.rowcount or 0)


def delete_article_by_id(session: Session, article_id: int) -> bool:
    row = session.get(Article, article_id)
    if row is None:
        return False
    session.delete(row)
    session.flush()
    return True

"""News list, article detail, bookmarks, daily newspaper."""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import desc, func, or_, select

from api.deps import CurrentUser, DbSession
from api.schemas.common import Message, Page, paginate
from api.schemas.news import (
    ArticleDetailOut,
    ArticleOut,
    BookmarkCreate,
    BookmarkOut,
    NewspaperOut,
    XFeedItemOut,
    XFeedsOut,
    XFeedsRefreshOut,
)
from api.schemas.portfolio_view import NewsRefreshOut
from intel_terminal.db.models import Article, ArticleBookmark, DailyNewspaper
from intel_terminal.db.repository import get_newspaper_for_date
from intel_terminal.pipeline.analyze import top_articles
from intel_terminal.pipeline.ingest import run_ingest_pipeline
from models import NewsCache
from scraper import (
    X_FEEDS_CACHE_KEY,
    X_PROFILES_DEFAULT,
    get_cached_news,
    scrape_x_analyst_feeds,
    upsert_cached_news,
)
from utils import keywords_hash

news_router = APIRouter(prefix="/news", tags=["news"])
newspaper_router = APIRouter(prefix="/newspaper", tags=["newspaper"])


def _bookmarked_ids(session, article_ids: list[int]) -> set[int]:
    if not article_ids:
        return set()
    rows = session.execute(
        select(ArticleBookmark.article_id).where(ArticleBookmark.article_id.in_(article_ids))
    ).scalars()
    return set(rows)


@news_router.post("/refresh", response_model=NewsRefreshOut)
def refresh_news(
    session: DbSession,
    _user: CurrentUser,
    region: str | None = Query(None, pattern="^(vietnam|global|crypto)$"),
) -> NewsRefreshOut:
    """Run the intel ingest pipeline (same as Streamlit Refresh News)."""
    result = run_ingest_pipeline(
        session,
        region=region,
        fetch_bodies=False,
        classify_after=True,
    )
    return NewsRefreshOut(
        status=result.status,
        fetched=int(result.articles_fetched or 0),
        new_count=int(result.articles_new or 0),
        deduped=int(result.articles_deduped or 0),
        classified=int(result.articles_classified or 0),
        errors=list(result.errors or []),
    )


@news_router.get("/x-feeds", response_model=XFeedsOut)
def get_x_feeds(session: DbSession, _user: CurrentUser) -> XFeedsOut:
    """Return cached X analyst posts (same NewsCache key as Streamlit Refresh X)."""
    cached = get_cached_news(session, X_FEEDS_CACHE_KEY)
    k_hash = keywords_hash(X_FEEDS_CACHE_KEY)
    row = session.execute(select(NewsCache).where(NewsCache.keywords_hash == k_hash)).scalar_one_or_none()
    items = [XFeedItemOut.from_cache_item(item) for item in cached if isinstance(item, dict)]
    items = [item for item in items if item.headline and item.link]
    return XFeedsOut(
        items=items,
        fetched_at=row.fetched_at if row else None,
        profiles=list(X_PROFILES_DEFAULT),
        cache_key=X_FEEDS_CACHE_KEY,
    )


@news_router.post("/x-feeds/refresh", response_model=XFeedsRefreshOut)
def refresh_x_feeds(
    session: DbSession,
    _user: CurrentUser,
    limit_per_profile: int = Query(12, ge=1, le=30),
) -> XFeedsRefreshOut:
    """Scrape @KobeissiLetter / @citrini and upsert the X analyst NewsCache."""
    try:
        results = scrape_x_analyst_feeds(
            list(X_PROFILES_DEFAULT),
            limit_per_profile=limit_per_profile,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not fetch X feeds: {exc}",
        ) from exc

    upsert_cached_news(session, X_FEEDS_CACHE_KEY, results)
    session.flush()
    items = [XFeedItemOut.from_cache_item(item) for item in results if isinstance(item, dict)]
    return XFeedsRefreshOut(
        count=len(items),
        items=items,
        fetched_at=datetime.utcnow(),
        profiles=list(X_PROFILES_DEFAULT),
        errors=[],
    )


@news_router.get("/articles", response_model=Page[ArticleOut])
def list_articles(
    session: DbSession,
    _user: CurrentUser,
    q: str | None = None,
    region: str | None = None,
    category: str | None = None,
    sort: str = Query("latest", pattern="^(latest|relevance)$"),
    vietnam_focus: bool = False,
    max_age_hours: int | None = Query(336, ge=1, le=24 * 90),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
) -> Page[ArticleOut]:
    # Fetch a ranked window, then paginate in-memory for consistent filters.
    fetch_limit = min(500, max(page * page_size, page_size * 3))
    if q and q.strip():
        term = f"%{q.strip()}%"
        filters = [or_(Article.title.ilike(term), Article.body_text.ilike(term))]
        if region:
            filters.append(Article.region == region)
        if category:
            filters.append(Article.category == category)
        count = int(
            session.execute(select(func.count()).select_from(Article).where(*filters)).scalar_one()
            or 0
        )
        page, page_size, pages = paginate(count, page, page_size)
        stmt = (
            select(Article)
            .where(*filters)
            .order_by(desc(func.coalesce(Article.published_at, Article.fetched_at)))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = list(session.execute(stmt).scalars().all())
    else:
        ranked = top_articles(
            session,
            limit=fetch_limit,
            region=region,
            category=category,
            vietnam_focus=vietnam_focus,
            max_age_hours=max_age_hours,
            sort=sort,
        )
        total = len(ranked)
        page, page_size, pages = paginate(total, page, page_size)
        start = (page - 1) * page_size
        rows = ranked[start : start + page_size]
        count = total

    marks = _bookmarked_ids(session, [r.id for r in rows])
    return Page(
        items=[ArticleOut.from_orm_row(r, bookmarked=r.id in marks) for r in rows],
        page=page,
        page_size=page_size,
        total=count,
        pages=pages,
    )


@news_router.get("/articles/{article_id}", response_model=ArticleDetailOut)
def get_article(article_id: int, session: DbSession, _user: CurrentUser) -> ArticleDetailOut:
    row = session.get(Article, article_id)
    if not row:
        raise HTTPException(status_code=404, detail="Article not found")
    marked = bool(
        session.execute(
            select(ArticleBookmark.id).where(ArticleBookmark.article_id == article_id).limit(1)
        ).scalar_one_or_none()
    )
    return ArticleDetailOut.from_orm_row(row, bookmarked=marked)


@news_router.get("/bookmarks", response_model=Page[BookmarkOut])
def list_bookmarks(
    session: DbSession,
    _user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
) -> Page[BookmarkOut]:
    total = int(session.execute(select(func.count()).select_from(ArticleBookmark)).scalar_one() or 0)
    page, page_size, pages = paginate(total, page, page_size)
    rows = list(
        session.execute(
            select(ArticleBookmark)
            .order_by(desc(ArticleBookmark.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    items: list[BookmarkOut] = []
    for bm in rows:
        article = session.get(Article, bm.article_id)
        items.append(
            BookmarkOut(
                id=bm.id,
                article_id=bm.article_id,
                created_at=bm.created_at,
                article=ArticleOut.from_orm_row(article, bookmarked=True) if article else None,
            )
        )
    return Page(items=items, page=page, page_size=page_size, total=total, pages=pages)


@news_router.post("/bookmarks", response_model=BookmarkOut, status_code=status.HTTP_201_CREATED)
def create_bookmark(
    body: BookmarkCreate, session: DbSession, _user: CurrentUser
) -> BookmarkOut:
    article = session.get(Article, body.article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    existing = session.execute(
        select(ArticleBookmark).where(ArticleBookmark.article_id == body.article_id)
    ).scalar_one_or_none()
    if existing:
        return BookmarkOut(
            id=existing.id,
            article_id=existing.article_id,
            created_at=existing.created_at,
            article=ArticleOut.from_orm_row(article, bookmarked=True),
        )
    row = ArticleBookmark(article_id=body.article_id, created_at=datetime.utcnow())
    session.add(row)
    session.flush()
    return BookmarkOut(
        id=row.id,
        article_id=row.article_id,
        created_at=row.created_at,
        article=ArticleOut.from_orm_row(article, bookmarked=True),
    )


@news_router.delete("/bookmarks/{article_id}", response_model=Message)
def delete_bookmark(article_id: int, session: DbSession, _user: CurrentUser) -> Message:
    row = session.execute(
        select(ArticleBookmark).where(ArticleBookmark.article_id == article_id)
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Bookmark not found")
    session.delete(row)
    session.flush()
    return Message(detail="Bookmark removed")


@newspaper_router.get("/today", response_model=NewspaperOut)
def newspaper_today(session: DbSession, _user: CurrentUser) -> NewspaperOut:
    row = get_newspaper_for_date(session, datetime.utcnow().date())
    if not row:
        raise HTTPException(status_code=404, detail="No newspaper for today")
    return NewspaperOut.from_orm_row(row)


@newspaper_router.get("", response_model=Page[NewspaperOut])
def list_newspapers(
    session: DbSession,
    _user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> Page[NewspaperOut]:
    total = int(session.execute(select(func.count()).select_from(DailyNewspaper)).scalar_one() or 0)
    page, page_size, pages = paginate(total, page, page_size)
    rows = list(
        session.execute(
            select(DailyNewspaper)
            .order_by(desc(DailyNewspaper.report_date))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return Page(
        items=[NewspaperOut.from_orm_row(r) for r in rows],
        page=page,
        page_size=page_size,
        total=total,
        pages=pages,
    )


@newspaper_router.get("/{report_date}", response_model=NewspaperOut)
def newspaper_by_date(
    report_date: date, session: DbSession, _user: CurrentUser
) -> NewspaperOut:
    row = get_newspaper_for_date(session, report_date)
    if not row:
        raise HTTPException(status_code=404, detail="Newspaper not found")
    return NewspaperOut.from_orm_row(row)

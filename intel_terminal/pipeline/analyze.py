"""Classify, rank, and score Vietnam relevance for stored articles."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session

from intel_terminal.config import load_config
from intel_terminal.db.models import Article
from intel_terminal.pipeline.classify import classify_text
from intel_terminal.pipeline.rank import compute_relevance_score
from intel_terminal.pipeline.vietnam import score_vietnam_relevance

logger = logging.getLogger(__name__)


@dataclass
class AnalyzeResult:
    articles_processed: int
    articles_updated: int
    above_min_relevance: int
    errors: list[str] = field(default_factory=list)


def analyze_article(article: Article) -> bool:
    """Apply classification + scores in-place. Returns True if fields changed."""
    classification = classify_text(
        article.title,
        article.body_text,
        source=article.source,
        region=article.region,
    )
    vietnam = score_vietnam_relevance(
        article.title,
        article.body_text,
        source=article.source,
        region=article.region,
        category=classification.category,
    )
    relevance = compute_relevance_score(article, classification, vietnam)

    meta: dict = {}
    if article.raw_metadata_json:
        try:
            meta = json.loads(article.raw_metadata_json)
        except Exception:
            meta = {}
    meta["classification"] = {
        "category": classification.category,
        "confidence": classification.confidence,
        "matched_terms": list(classification.matched_terms),
        "analyzed_at": datetime.utcnow().isoformat(),
    }

    changed = (
        article.category != classification.category
        or abs(article.relevance_score - relevance) > 1e-6
        or abs(article.vietnam_macro_score - vietnam.macro) > 1e-6
        or abs(article.vietnam_banking_score - vietnam.banking) > 1e-6
        or abs(article.vietnam_wealth_score - vietnam.wealth) > 1e-6
    )

    article.category = classification.category
    article.relevance_score = relevance
    article.vietnam_macro_score = vietnam.macro
    article.vietnam_banking_score = vietnam.banking
    article.vietnam_wealth_score = vietnam.wealth
    article.raw_metadata_json = json.dumps(meta, ensure_ascii=False)

    return changed


def run_analyze_pipeline(
    session: Session,
    *,
    limit: int = 300,
    only_unclassified: bool = False,
    hours_back: int | None = 168,
) -> AnalyzeResult:
    """
    Re-classify and re-rank recent articles.

    only_unclassified: skip articles already categorized (not Uncategorized).
    hours_back: limit to articles fetched/published within N hours (None = all).
    """
    cfg = load_config()
    q = select(Article).order_by(desc(Article.fetched_at))

    if only_unclassified:
        q = q.where(Article.category == "Uncategorized")
    if hours_back is not None:
        cutoff = datetime.utcnow() - timedelta(hours=hours_back)
        q = q.where(or_(Article.fetched_at >= cutoff, Article.published_at >= cutoff))

    articles = list(session.execute(q.limit(limit)).scalars().all())
    seen_ids = {a.id for a in articles if a.id is not None}

    # Re-score stale high-score rows so old headlines stop dominating the UI
    # after recency decays (their scores were frozen when they were fresh).
    if hours_back is not None:
        stale_q = (
            select(Article)
            .where(Article.relevance_score >= cfg.pipeline.min_relevance_score)
            .order_by(desc(Article.relevance_score))
            .limit(min(150, limit))
        )
        if seen_ids:
            stale_q = stale_q.where(Article.id.notin_(seen_ids))
        articles.extend(list(session.execute(stale_q).scalars().all()))

    updated = 0
    above_min = 0
    errors: list[str] = []

    for article in articles:
        try:
            if analyze_article(article):
                updated += 1
            if article.relevance_score >= cfg.pipeline.min_relevance_score:
                above_min += 1
        except Exception as exc:
            errors.append(f"article {article.id}: {exc}")
            logger.warning("Analyze failed for article %s", article.id, exc_info=True)

    session.flush()

    return AnalyzeResult(
        articles_processed=len(articles),
        articles_updated=updated,
        above_min_relevance=above_min,
        errors=errors,
    )


def _recency_cutoff(max_age_hours: int | None) -> datetime | None:
    if max_age_hours is None:
        return None
    return datetime.utcnow() - timedelta(hours=max_age_hours)


def top_articles(
    session: Session,
    *,
    limit: int = 30,
    region: str | None = None,
    category: str | None = None,
    min_relevance: float | None = None,
    vietnam_focus: bool = False,
    max_age_hours: int | None = 168,
    sort: str = "relevance",
) -> list[Article]:
    """
    Ranked feed for UI / agents.

    max_age_hours: only articles published or fetched within this window (default 7 days).
    sort: 'relevance' (score then date) or 'latest' (newest first).
    """
    cfg = load_config()
    floor = min_relevance if min_relevance is not None else cfg.pipeline.min_relevance_score

    q = select(Article)
    if floor > 0 and sort != "latest":
        q = q.where(Article.relevance_score >= floor)
    if region:
        q = q.where(Article.region == region)
    if category:
        q = q.where(Article.category == category)

    cutoff = _recency_cutoff(max_age_hours)
    if cutoff is not None:
        q = q.where(or_(Article.published_at >= cutoff, Article.fetched_at >= cutoff))

    if sort == "latest":
        # Prefer publish time; fall back to fetch time for feeds with null published_at
        q = q.order_by(
            desc(func.coalesce(Article.published_at, Article.fetched_at)),
            desc(Article.fetched_at),
        )
    elif vietnam_focus:
        vn_sum = Article.vietnam_macro_score + Article.vietnam_banking_score + Article.vietnam_wealth_score
        q = q.order_by(
            desc(vn_sum),
            desc(Article.relevance_score),
            desc(func.coalesce(Article.published_at, Article.fetched_at)),
        )
    else:
        q = q.order_by(
            desc(Article.relevance_score),
            desc(func.coalesce(Article.published_at, Article.fetched_at)),
        )
    q = q.limit(limit)

    return list(session.execute(q).scalars().all())

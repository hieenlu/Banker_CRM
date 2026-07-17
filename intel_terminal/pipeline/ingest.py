"""Orchestrate: fetch → normalize → dedup → persist."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from intel_terminal.config import load_config
from intel_terminal.db.repository import finish_pipeline_run, start_pipeline_run, upsert_article_draft
from intel_terminal.pipeline.analyze import run_analyze_pipeline
from intel_terminal.pipeline.body_fetcher import fetch_article_body
from intel_terminal.pipeline.dedup import deduplicate_drafts
from intel_terminal.pipeline.normalize import ArticleDraft, normalize_feed_entry
from intel_terminal.sources.feeds import FeedSource, all_feeds, feeds_by_region
from intel_terminal.sources.rss_fetcher import fetch_all_feeds_sync

logger = logging.getLogger(__name__)


@dataclass
class IngestResult:
    run_id: int
    status: str
    articles_fetched: int
    articles_new: int
    articles_deduped: int
    articles_classified: int = 0
    articles_pruned: int = 0
    errors: list[str] = field(default_factory=list)


def _normalize_all(
    feed_results: list[tuple[FeedSource, list[dict], str | None]],
) -> tuple[list[ArticleDraft], list[str]]:
    drafts: list[ArticleDraft] = []
    errors: list[str] = []
    for feed, entries, err in feed_results:
        if err:
            errors.append(f"{feed.key}: {err}")
            continue
        if not entries:
            errors.append(f"{feed.key}: empty feed")
            continue
        for entry in entries:
            draft = normalize_feed_entry(entry, feed)
            if draft:
                drafts.append(draft)
    return drafts, errors


def _cap_drafts_fairly(drafts: list[ArticleDraft], limit: int) -> list[ArticleDraft]:
    """
    Cap drafts without starving Vietnam.

    When ingesting all regions, ~40% of the budget is reserved for Vietnam so
    global/crypto feeds cannot push local headlines out of the run.
    """
    if len(drafts) <= limit:
        return drafts

    vietnam = [d for d in drafts if d.region == "vietnam"]
    other = [d for d in drafts if d.region != "vietnam"]

    if not vietnam or not other:
        return drafts[:limit]

    vn_budget = max(40, int(limit * 0.40))
    other_budget = limit - vn_budget
    if len(vietnam) < vn_budget:
        other_budget = limit - len(vietnam)
        vn_budget = len(vietnam)
    if len(other) < other_budget:
        vn_budget = limit - len(other)
        other_budget = len(other)

    # Prefer newest within each bucket when published_at is available
    def _sort_key(d: ArticleDraft) -> tuple:
        pub = d.published_at.timestamp() if d.published_at else 0.0
        return (-pub, d.title)

    vietnam_sorted = sorted(vietnam, key=_sort_key)
    other_sorted = sorted(other, key=_sort_key)
    return vietnam_sorted[:vn_budget] + other_sorted[:other_budget]


def run_ingest_pipeline(
    session: Session,
    *,
    region: str | None = None,
    fetch_bodies: bool = False,
    max_body_fetch: int = 15,
    classify_after: bool = True,
) -> IngestResult:
    """
    Full ingest pipeline (sync, Streamlit-friendly).

  region: None = all feeds, or 'vietnam' | 'global' | 'crypto'
    fetch_bodies: attempt full text for top N new articles (RSS snippet used on paywall).
    """
    cfg = load_config()
    run = start_pipeline_run(session)
    session.commit()

    feeds = feeds_by_region(region) if region else all_feeds()
    errors: list[str] = []

    try:
        feed_results = fetch_all_feeds_sync(feeds)
        raw_drafts, norm_errors = _normalize_all(feed_results)
        errors.extend(norm_errors)

        unique, deduped_count = deduplicate_drafts(raw_drafts)
        unique = _cap_drafts_fairly(unique, cfg.pipeline.max_articles_per_run)

        new_count = 0
        body_fetched = 0
        for draft in unique:
            if fetch_bodies and body_fetched < max_body_fetch and draft.body_fetch_status == "pending":
                body, status = fetch_article_body(draft.url)
                body_fetched += 1
                if body:
                    draft.body_text = body
                draft.body_fetch_status = status
                if status == "paywalled":
                    draft.raw_metadata["paywall"] = True

            _, is_new = upsert_article_draft(session, draft)
            if is_new:
                new_count += 1

        classified = 0
        pruned = 0
        if classify_after and unique:
            analyze = run_analyze_pipeline(
                session,
                limit=max(300, len(unique) + 50),
                only_unclassified=False,
                hours_back=168,
            )
            classified = analyze.articles_updated
            errors.extend(analyze.errors)

        from intel_terminal.pipeline.archive import prune_archive_articles

        prune = prune_archive_articles(session)
        pruned = prune.deleted

        finish_pipeline_run(
            session,
            run,
            status="ok",
            fetched=len(raw_drafts),
            new_count=new_count,
            deduped=deduped_count,
            errors=errors,
        )
        session.commit()
        return IngestResult(
            run_id=run.id,
            status="ok",
            articles_fetched=len(raw_drafts),
            articles_new=new_count,
            articles_deduped=deduped_count,
            articles_classified=classified,
            articles_pruned=pruned,
            errors=errors,
        )
    except Exception as exc:
        logger.exception("Ingest pipeline failed")
        errors.append(str(exc))
        finish_pipeline_run(session, run, status="error", fetched=0, new_count=0, deduped=0, errors=errors)
        session.commit()
        return IngestResult(
            run_id=run.id,
            status="error",
            articles_fetched=0,
            articles_new=0,
            articles_deduped=0,
            errors=errors,
        )


def latest_articles(session: Session, *, limit: int = 50, region: str | None = None) -> list:
    from sqlalchemy import desc, func, select

    from intel_terminal.db.models import Article

    q = select(Article).order_by(
        desc(func.coalesce(Article.published_at, Article.fetched_at)),
        desc(Article.fetched_at),
    )
    if region:
        q = q.where(Article.region == region)
    return list(session.execute(q.limit(limit)).scalars().all())


def last_pipeline_run(session: Session):
    from sqlalchemy import desc, select

    from intel_terminal.db.models import PipelineRun

    return session.execute(select(PipelineRun).order_by(desc(PipelineRun.id)).limit(1)).scalar_one_or_none()

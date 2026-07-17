"""CRUD helpers for intel articles."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from intel_terminal.db.models import Article, ArticleSummary, DailyNewspaper, PipelineRun
from intel_terminal.pipeline.dedup import headline_cluster_id
from intel_terminal.pipeline.normalize import ArticleDraft, drafts_to_metadata_json, to_naive_utc


def get_article_by_url_hash(session: Session, url_hash: str) -> Article | None:
    return session.execute(select(Article).where(Article.url_hash == url_hash)).scalar_one_or_none()


def upsert_article_draft(session: Session, draft: ArticleDraft) -> tuple[Article, bool]:
    """Insert or update mention count. Returns (article, is_new)."""
    row = get_article_by_url_hash(session, draft.url_hash)
    mention = int(draft.raw_metadata.get("mention_count", 1))
    cluster = draft.raw_metadata.get("dedup_cluster_id") or headline_cluster_id(draft.title)
    meta_json = drafts_to_metadata_json(draft)

    draft.raw_metadata.setdefault("source_quality", draft.source_quality)

    if row is None:
        row = Article(
            url_hash=draft.url_hash,
            url=draft.url,
            canonical_url=draft.canonical_url,
            title=draft.title,
            source=draft.source,
            published_at=to_naive_utc(draft.published_at) if draft.published_at else None,
            fetched_at=datetime.now(timezone.utc).replace(tzinfo=None),
            body_text=draft.body_text,
            body_fetch_status=draft.body_fetch_status,
            category="Uncategorized",
            relevance_score=0.0,
            region=draft.region if draft.region != "crypto" else "global",
            language=draft.language,
            is_paywalled=draft.body_fetch_status == "paywalled",
            dedup_cluster_id=cluster,
            mention_count=mention,
            raw_metadata_json=meta_json,
        )
        session.add(row)
        return row, True

    row.mention_count = max(row.mention_count, mention)
    row.fetched_at = datetime.now(timezone.utc).replace(tzinfo=None)
    pub = to_naive_utc(draft.published_at) if draft.published_at else None
    if pub and (row.published_at is None or pub > row.published_at):
        row.published_at = pub
    if draft.title and draft.title != row.title:
        row.title = draft.title[:500]
    if draft.body_text and (not row.body_text or len(draft.body_text) > len(row.body_text or "")):
        row.body_text = draft.body_text
        row.body_fetch_status = draft.body_fetch_status
    row.dedup_cluster_id = cluster
    return row, False


def start_pipeline_run(session: Session) -> PipelineRun:
    run = PipelineRun(status="running", started_at=datetime.utcnow())
    session.add(run)
    session.flush()
    return run


def finish_pipeline_run(
    session: Session,
    run: PipelineRun,
    *,
    status: str,
    fetched: int,
    new_count: int,
    deduped: int,
    errors: list[str],
) -> None:
    import json

    run.finished_at = datetime.utcnow()
    run.status = status
    run.articles_fetched = fetched
    run.articles_new = new_count
    run.articles_deduped = deduped
    run.errors_json = json.dumps(errors[:50], ensure_ascii=False) if errors else None


def get_fresh_summary(
    session: Session,
    article_id: int,
    agent_type: str,
    model: str,
    *,
    hours: int = 48,
) -> ArticleSummary | None:
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    return session.execute(
        select(ArticleSummary)
        .where(
            ArticleSummary.article_id == article_id,
            ArticleSummary.agent_type == agent_type,
            ArticleSummary.model == model,
            ArticleSummary.created_at >= cutoff,
        )
        .order_by(desc(ArticleSummary.created_at))
        .limit(1)
    ).scalar_one_or_none()


def save_article_summary(
    session: Session,
    *,
    article_id: int,
    agent_type: str,
    provider: str,
    model: str,
    summary_json: str,
    token_count: int | None = None,
) -> ArticleSummary:
    existing = session.execute(
        select(ArticleSummary).where(
            ArticleSummary.article_id == article_id,
            ArticleSummary.agent_type == agent_type,
            ArticleSummary.model == model,
        )
    ).scalar_one_or_none()

    if existing:
        existing.summary_json = summary_json
        existing.provider = provider
        existing.token_count = token_count
        existing.created_at = datetime.utcnow()
        return existing

    row = ArticleSummary(
        article_id=article_id,
        agent_type=agent_type,
        provider=provider,
        model=model,
        summary_json=summary_json,
        token_count=token_count,
        created_at=datetime.utcnow(),
    )
    session.add(row)
    return row


def get_newspaper_for_date(session: Session, report_date: date) -> DailyNewspaper | None:
    return session.execute(
        select(DailyNewspaper).where(DailyNewspaper.report_date == report_date)
    ).scalar_one_or_none()


def save_daily_newspaper(
    session: Session,
    *,
    report_date: date,
    market_regime: str,
    content_json: str,
    provider: str,
    model: str,
    replace: bool = False,
) -> DailyNewspaper:
    row = get_newspaper_for_date(session, report_date)
    if row and not replace:
        return row
    if row and replace:
        row.market_regime = market_regime
        row.content_json = content_json
        row.provider = provider
        row.model = model
        row.created_at = datetime.utcnow()
        return row

    row = DailyNewspaper(
        report_date=report_date,
        market_regime=market_regime,
        content_json=content_json,
        provider=provider,
        model=model,
        created_at=datetime.utcnow(),
    )
    session.add(row)
    return row

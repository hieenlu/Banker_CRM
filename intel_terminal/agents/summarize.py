"""Per-article agent summaries with DB cache."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from intel_terminal.agents.base import AgentOutput, parse_agent_response
from intel_terminal.agents.prompts import AGENT_SYSTEM_PROMPTS, USER_PROMPT_TEMPLATE, pick_agent_for_article
from intel_terminal.config import load_config
from intel_terminal.db.models import Article
from intel_terminal.db.repository import get_fresh_summary, save_article_summary
from intel_terminal.llm.base import BaseLLMProvider
from intel_terminal.llm.factory import get_llm_provider
from intel_terminal.pipeline.analyze import top_articles

logger = logging.getLogger(__name__)


@dataclass
class SummaryRunResult:
    articles_considered: int
    summaries_created: int
    cache_hits: int
    skipped_no_llm: int
    errors: list[str] = field(default_factory=list)


def _article_snippet(article: Article, max_chars: int) -> str:
    body = (article.body_text or "").strip()
    if not body:
        return "(no body — headline only)"
    return body[:max_chars]


def summarize_article(
    session: Session,
    article: Article,
    *,
    agent_type: str | None = None,
    llm: BaseLLMProvider | None = None,
    force: bool = False,
) -> AgentOutput | None:
    """Return cached or freshly generated summary for one article."""
    cfg = load_config()
    provider = llm or get_llm_provider(cfg)
    if not provider.is_configured():
        return None

    agent = agent_type or pick_agent_for_article(
        article.category,
        article.region,
        vietnam_macro_score=article.vietnam_macro_score,
        vietnam_banking_score=article.vietnam_banking_score,
        vietnam_wealth_score=article.vietnam_wealth_score,
    )
    system = AGENT_SYSTEM_PROMPTS.get(agent, AGENT_SYSTEM_PROMPTS["macro"])

    if not force:
        cached = get_fresh_summary(
            session,
            article.id,
            agent,
            provider.model,
            hours=cfg.pipeline.reuse_summary_hours,
        )
        if cached:
            return AgentOutput.from_json(cached.summary_json, agent_type=agent, article_id=article.id)

    user = USER_PROMPT_TEMPLATE.format(
        title=article.title,
        source=article.source,
        category=article.category,
        snippet=_article_snippet(article, cfg.pipeline.summary_max_body_chars),
    )
    resp = provider.complete(system, user)
    output = parse_agent_response(resp.text, agent_type=agent, article_id=article.id)
    tokens = (resp.input_tokens or 0) + (resp.output_tokens or 0)
    save_article_summary(
        session,
        article_id=article.id,
        agent_type=agent,
        provider=resp.provider,
        model=resp.model,
        summary_json=output.to_json(),
        token_count=tokens or None,
    )
    return output


def run_summary_pipeline(
    session: Session,
    *,
    limit: int | None = None,
    llm: BaseLLMProvider | None = None,
    force: bool = False,
) -> SummaryRunResult:
    """Summarize top-ranked articles (budget-capped per run)."""
    cfg = load_config()
    cap = limit if limit is not None else cfg.pipeline.max_summaries_per_run
    provider = llm or get_llm_provider(cfg)

    if not provider.is_configured():
        return SummaryRunResult(
            articles_considered=0,
            summaries_created=0,
            cache_hits=0,
            skipped_no_llm=cap,
            errors=["LLM API key not configured"],
        )

    articles = top_articles(session, limit=cap)
    created = 0
    cache_hits = 0
    errors: list[str] = []

    for article in articles:
        agent = pick_agent_for_article(
            article.category,
            article.region,
            vietnam_macro_score=article.vietnam_macro_score,
            vietnam_banking_score=article.vietnam_banking_score,
            vietnam_wealth_score=article.vietnam_wealth_score,
        )
        try:
            if not force:
                cached = get_fresh_summary(
                    session,
                    article.id,
                    agent,
                    provider.model,
                    hours=cfg.pipeline.reuse_summary_hours,
                )
                if cached:
                    cache_hits += 1
                    continue

            out = summarize_article(session, article, agent_type=agent, llm=provider, force=True)
            if out:
                created += 1
        except Exception as exc:
            errors.append(f"article {article.id}: {exc}")
            logger.warning("Summary failed for %s", article.id, exc_info=True)

    session.flush()
    return SummaryRunResult(
        articles_considered=len(articles),
        summaries_created=created,
        cache_hits=cache_hits,
        skipped_no_llm=0,
        errors=errors,
    )

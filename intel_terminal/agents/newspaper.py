"""Daily newspaper generator — one LLM call or rule-based fallback."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from intel_terminal.agents.base import extract_json_object
from intel_terminal.agents.prompts import NEWSPAPER_SYSTEM_PROMPT, NEWSPAPER_USER_TEMPLATE
from intel_terminal.config import load_config
from intel_terminal.constants import MARKET_REGIMES, NEWSPAPER_SECTIONS
from intel_terminal.db.models import Article, ArticleSummary, DailyNewspaper
from intel_terminal.db.repository import get_newspaper_for_date, save_daily_newspaper
from intel_terminal.llm.base import BaseLLMProvider
from intel_terminal.llm.factory import get_llm_provider
from intel_terminal.pipeline.analyze import top_articles

logger = logging.getLogger(__name__)


@dataclass
class NewspaperResult:
    report_date: date
    market_regime: str
    content: dict
    from_cache: bool
    provider: str
    model: str
    errors: list[str] = field(default_factory=list)


def _infer_regime(articles: list[Article]) -> str:
    blob = " ".join(a.title.lower() for a in articles[:20])
    risk_off = sum(1 for w in ("selloff", "fall", "drop", "recession", "war", "crisis") if w in blob)
    risk_on = sum(1 for w in ("rally", "surge", "record high", "beat", "growth") if w in blob)
    if risk_off > risk_on + 1:
        return "Risk-Off"
    if risk_on > risk_off + 1:
        return "Risk-On"
    return "Neutral"


def _story_line(article: Article, summary_note: str | None) -> str:
    note = f" | {summary_note}" if summary_note else ""
    return f"- {article.title[:100]} | {article.category} | {article.source}{note}"


def _load_summary_note(session: Session, article: Article) -> str | None:
    row = (
        session.execute(
            select(ArticleSummary)
            .where(ArticleSummary.article_id == article.id)
            .order_by(ArticleSummary.created_at.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )
    if not row:
        return None
    try:
        data = json.loads(row.summary_json)
        return str(data.get("summary", ""))[:120] or None
    except Exception:
        return None


def _fallback_newspaper(report_date: date, articles: list[Article]) -> dict:
    """No-LLM template when API key missing or call fails."""
    regime = _infer_regime(articles)
    by_cat: dict[str, list[Article]] = {}
    for a in articles:
        by_cat.setdefault(a.category, []).append(a)

    def _overview(cat: str, default: str = "No major headlines in this bucket today.") -> str:
        items = by_cat.get(cat, [])
        if not items:
            return default
        return " ".join(f"{x.title} ({x.source})." for x in items[:3])

    top = [
        {"title": a.title, "source": a.source, "why_it_matters": f"Relevance {a.relevance_score:.2f}"}
        for a in articles[:5]
    ]
    insights = [f"Watch {a.category}: {a.title[:80]}" for a in articles[:4]]
    talking = [f"Discuss {a.title[:70]} — source {a.source}" for a in articles[:4]]

    content: dict = {
        "executive_summary": (
            f"Automated briefing for {report_date.isoformat()} from {len(articles)} ranked stories. "
            f"Market tone appears {regime}. (LLM synthesis unavailable — headline digest.)"
        ),
        "market_regime": regime,
        "top_stories": top,
        "macro_overview": _overview("Global Macro", _overview("Central Banks")),
        "equity_overview": _overview("Equities"),
        "crypto_overview": _overview("Crypto", "N/A"),
        "china_overview": _overview("China", "N/A"),
        "vietnam_overview": _overview("Vietnam", "See global feed for Vietnam-region sources."),
        "actionable_insights": insights,
        "client_talking_points": talking,
        "generated_at": datetime.utcnow().isoformat(),
        "article_count": len(articles),
        "mode": "fallback",
    }
    for key in NEWSPAPER_SECTIONS:
        content.setdefault(key, "" if key not in content else content[key])
    return content


def generate_daily_newspaper(
    session: Session,
    *,
    report_date: date | None = None,
    llm: BaseLLMProvider | None = None,
    force: bool = False,
) -> NewspaperResult:
    """Build or return cached daily newspaper for report_date (default: today UTC)."""
    cfg = load_config()
    report_date = report_date or datetime.utcnow().date()

    if not force:
        existing = get_newspaper_for_date(session, report_date)
        if existing:
            try:
                content = json.loads(existing.content_json)
            except Exception:
                content = {}
            return NewspaperResult(
                report_date=report_date,
                market_regime=existing.market_regime,
                content=content,
                from_cache=True,
                provider=existing.provider,
                model=existing.model,
            )

    story_count = cfg.pipeline.newspaper_top_story_count
    articles = top_articles(session, limit=story_count)
    provider = llm or get_llm_provider(cfg)

    if not provider.is_configured():
        content = _fallback_newspaper(report_date, articles)
        row = save_daily_newspaper(
            session,
            report_date=report_date,
            market_regime=content.get("market_regime", "Neutral"),
            content_json=json.dumps(content, ensure_ascii=False),
            provider="fallback",
            model="rule-based",
            replace=force,
        )
        session.flush()
        return NewspaperResult(
            report_date=report_date,
            market_regime=row.market_regime,
            content=content,
            from_cache=False,
            provider="fallback",
            model="rule-based",
            errors=["LLM API key not configured — used headline digest"],
        )

    lines = []
    for a in articles:
        note = _load_summary_note(session, a)
        lines.append(_story_line(a, note))
    user = NEWSPAPER_USER_TEMPLATE.format(
        report_date=report_date.isoformat(),
        story_lines="\n".join(lines) or "(no stories)",
    )

    errors: list[str] = []
    try:
        resp = provider.complete(NEWSPAPER_SYSTEM_PROMPT, user)
        content = extract_json_object(resp.text)
        regime = str(content.get("market_regime", "Neutral"))
        if regime not in MARKET_REGIMES:
            regime = _infer_regime(articles)
        content["generated_at"] = datetime.utcnow().isoformat()
        content["article_count"] = len(articles)
        content["mode"] = "llm"
        for key in NEWSPAPER_SECTIONS:
            content.setdefault(key, "")

        row = save_daily_newspaper(
            session,
            report_date=report_date,
            market_regime=regime,
            content_json=json.dumps(content, ensure_ascii=False),
            provider=resp.provider,
            model=resp.model,
            replace=force,
        )
        session.flush()
        return NewspaperResult(
            report_date=report_date,
            market_regime=row.market_regime,
            content=content,
            from_cache=False,
            provider=resp.provider,
            model=resp.model,
            errors=errors,
        )
    except Exception as exc:
        logger.exception("Newspaper LLM failed")
        errors.append(str(exc))
        content = _fallback_newspaper(report_date, articles)
        row = save_daily_newspaper(
            session,
            report_date=report_date,
            market_regime=content.get("market_regime", "Neutral"),
            content_json=json.dumps(content, ensure_ascii=False),
            provider="fallback",
            model="rule-based",
            replace=force,
        )
        session.flush()
        return NewspaperResult(
            report_date=report_date,
            market_regime=row.market_regime,
            content=content,
            from_cache=False,
            provider="fallback",
            model="rule-based",
            errors=errors,
        )

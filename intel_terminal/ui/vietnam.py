"""Vietnam panel helpers — finance, economy, real estate only."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timedelta

import streamlit as st
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session

from intel_terminal.db.models import Article
from intel_terminal.db.repository import get_newspaper_for_date
from intel_terminal.pipeline.vietnam import vietnam_sector_tags
from intel_terminal.ui.components import render_article_list
from intel_terminal.ui.techcombank import render_techcombank_section


def vietnam_sector_label(article: Article) -> str | None:
    tags = vietnam_sector_tags(
        article.title,
        article.body_text,
        source=article.source or "",
        macro=article.vietnam_macro_score or 0.0,
        banking=article.vietnam_banking_score or 0.0,
        wealth=article.vietnam_wealth_score or 0.0,
    )
    return " · ".join(tags) if tags else None


def is_vietnam_sector_article(article: Article) -> bool:
    return vietnam_sector_label(article) is not None


def _article_sort_ts(article: Article) -> datetime:
    return article.published_at or article.fetched_at or datetime.min


def vietnam_sector_articles(
    session: Session,
    *,
    limit: int = 15,
    sector: str | None = None,
    max_age_days: int = 7,
) -> list[Article]:
    """
    Vietnam finance / economy / real-estate headlines, newest first.

    Prefers stories from the last `max_age_days` so the column stays current.
    """
    cutoff = datetime.utcnow() - timedelta(days=max_age_days)
    recent_q = (
        select(Article)
        .where(
            Article.region == "vietnam",
            or_(Article.published_at >= cutoff, Article.fetched_at >= cutoff),
        )
        .order_by(
            desc(Article.published_at.isnot(None)),  # dated rows before null published
            desc(func.coalesce(Article.published_at, Article.fetched_at)),
            desc(Article.fetched_at),
        )
        .limit(max(250, limit * 15))
    )
    rows = list(session.execute(recent_q).scalars().all())

    if len(rows) < limit:
        extra = list(
            session.execute(
                select(Article)
                .where(Article.region == "vietnam")
                .order_by(
                    desc(Article.published_at.isnot(None)),
                    desc(func.coalesce(Article.published_at, Article.fetched_at)),
                    desc(Article.fetched_at),
                )
                .limit(max(250, limit * 15))
            )
            .scalars()
            .all()
        )
        seen = {a.id for a in rows}
        rows.extend(a for a in extra if a.id not in seen)

    out: list[Article] = []
    for a in rows:
        label = vietnam_sector_label(a)
        if not label:
            continue
        if sector and sector.lower() not in label.lower():
            continue
        out.append(a)
        if len(out) >= limit:
            break

    if not out and not sector:
        out = sorted(rows, key=_article_sort_ts, reverse=True)[:limit]
    return out


def render_vietnam_dashboard_column(
    session: Session,
    *,
    mobile_ui: bool,
    techcom_reports_fn: Callable[[int], list[dict[str, str]]],
) -> None:
    st.markdown("##### Vietnam")
    st.caption("Finance · Economy · Real estate · last 7 days")

    sector = st.radio(
        "Sector",
        ["All", "Finance", "Economy", "Real estate"],
        horizontal=True,
        label_visibility="collapsed",
        key="intel_vn_sector_filter",
    )
    filter_sector = None if sector == "All" else sector
    headlines = vietnam_sector_articles(
        session,
        limit=10 if mobile_ui else 12,
        sector=filter_sector,
        max_age_days=7,
    )
    if not headlines:
        st.warning("No Vietnam headlines yet. Click **Refresh News** to pull local feeds.")
    else:
        newest = _article_sort_ts(headlines[0])
        st.caption(f"Newest: {newest.strftime('%Y-%m-%d %H:%M')} UTC")
        render_article_list(headlines, badge_fn=vietnam_sector_label)

    with st.expander("Techcombank monthly outlook", expanded=False):
        render_techcombank_section(techcom_reports_fn, limit=5, expanded=True, inline=True)

    paper = get_newspaper_for_date(session, datetime.utcnow().date())
    if paper:
        try:
            content = json.loads(paper.content_json)
            vn_brief = str(content.get("vietnam_overview", "") or "").strip()
            if vn_brief and vn_brief.upper() != "N/A":
                st.markdown("###### VN briefing")
                st.markdown(
                    f'<div class="intel-card intel-card-tight"><p>{vn_brief}</p></div>',
                    unsafe_allow_html=True,
                )
        except Exception:
            pass

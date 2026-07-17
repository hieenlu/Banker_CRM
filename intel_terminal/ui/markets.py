"""Markets column — US / Korea / Taiwan · equities, economy, finance, AI, crypto, semis."""

from __future__ import annotations

from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session

from intel_terminal.db.models import Article
from intel_terminal.pipeline.global_focus import (
    global_markets_badge,
    is_global_markets_focus,
)
from intel_terminal.ui.components import render_article_list
import streamlit as st


def markets_focus_label(article: Article) -> str | None:
    return global_markets_badge(
        article.title,
        article.body_text,
        source=article.source or "",
        category=article.category or "",
    )


def markets_focus_articles(
    session: Session,
    *,
    limit: int = 12,
    topic: str | None = None,
) -> list[Article]:
    """Global (non-Vietnam) headlines filtered to Markets focus themes."""
    from intel_terminal.pipeline.global_focus import global_geo_tags, global_topic_tags

    rows = list(
        session.execute(
            select(Article)
            .where(or_(Article.region == "global", Article.region == "crypto"))
            .order_by(
                desc(func.coalesce(Article.published_at, Article.fetched_at)),
                desc(Article.fetched_at),
            )
            .limit(max(250, limit * 15))
        )
        .scalars()
        .all()
    )

    out: list[Article] = []
    for a in rows:
        if not is_global_markets_focus(
            a.title,
            a.body_text,
            source=a.source or "",
            category=a.category or "",
            region=a.region or "global",
        ):
            continue
        if topic:
            topics = global_topic_tags(
                a.title, a.body_text, source=a.source or "", category=a.category or ""
            )
            geos = global_geo_tags(a.title, a.body_text, source=a.source or "")
            if topic not in topics and topic not in geos:
                continue
        out.append(a)
        if len(out) >= limit:
            break
    return out


def render_markets_dashboard_column(session: Session, *, mobile_ui: bool = False) -> None:
    st.markdown("##### Markets")
    st.caption("US · Korea · Taiwan · Equities · Economy · Finance · AI · Crypto · Semis")

    topic = st.radio(
        "Focus",
        ["All", "US", "Korea", "Taiwan", "Equities", "Economy", "Finance", "AI", "Crypto", "Semiconductor"],
        horizontal=True,
        label_visibility="collapsed",
        key="intel_markets_focus_filter",
    )
    filter_topic = None if topic == "All" else topic
    headlines = markets_focus_articles(
        session,
        limit=10 if mobile_ui else 12,
        topic=filter_topic,
    )
    if not headlines:
        st.warning("No matching Markets headlines — click **Refresh News**.")
    else:
        render_article_list(headlines, badge_fn=markets_focus_label)

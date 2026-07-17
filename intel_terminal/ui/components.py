"""Reusable Streamlit helpers for intel terminal."""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from typing import Any, Callable

import streamlit as st

from intel_terminal.db.models import Article, ArticleSummary


def _esc(text: str) -> str:
    return html.escape(text or "")


def fmt_dt(dt: datetime | None) -> str:
    if not dt:
        return "—"
    return dt.strftime("%Y-%m-%d %H:%M")


def fmt_dt_short(dt: datetime | None) -> str:
    if not dt:
        return ""
    return dt.strftime("%b %d · %H:%M")


def fmt_relative_time(dt: datetime | None) -> str:
    """Compact relative timestamp for news feeds."""
    if not dt:
        return "Recently"
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    value = dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt
    seconds = max(0, int((now - value).total_seconds()))
    if seconds < 60:
        return "Just now"
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        return f"{seconds // 3600}h"
    if seconds < 604800:
        return f"{seconds // 86400}d"
    return value.strftime("%b %d")


def regime_class(regime: str) -> str:
    r = (regime or "").lower().replace(" ", "-")
    if "risk-on" in r:
        return "intel-regime-risk-on"
    if "risk-off" in r:
        return "intel-regime-risk-off"
    return "intel-regime-neutral"


def render_article_table(articles: list[Article], *, show_scores: bool = True) -> None:
    if not articles:
        st.caption("No articles to display.")
        return

    rows: list[str] = []
    for a in articles:
        title = _esc(a.title[:140])
        link = _esc(a.url)
        src = _esc(a.source)
        cat = _esc(a.category)
        rel = f"{a.relevance_score:.2f}"
        pub = fmt_dt(a.published_at or a.fetched_at)
        score_cols = ""
        if show_scores:
            score_cols = (
                f'<td class="intel-score">{rel}</td>'
                f"<td>{a.vietnam_macro_score:.2f}</td>"
                f"<td>{a.vietnam_banking_score:.2f}</td>"
            )
        rows.append(
            f"<tr>"
            f'<td><a href="{link}" target="_blank">{title}</a></td>'
            f"<td>{src}</td><td>{cat}</td>{score_cols}<td>{pub}</td>"
            f"</tr>"
        )

    head_scores = ""
    if show_scores:
        head_scores = "<th>Rel</th><th>VN Macro</th><th>VN Bank</th>"
    table = f"""
<table class="intel-table">
  <thead><tr>
    <th>Headline</th><th>Source</th><th>Category</th>{head_scores}<th>Published</th>
  </tr></thead>
  <tbody>{"".join(rows)}</tbody>
</table>
"""
    st.markdown(table, unsafe_allow_html=True)


def render_article_list(
    articles: list[Article],
    *,
    badge_fn: Callable[[Article], str | None] | None = None,
    max_title: int = 110,
    meta_on_right: bool = False,
) -> None:
    """Clean headline list — source, time, optional badge. No score grid."""
    if not articles:
        st.caption("No articles to display.")
        return

    items: list[str] = []
    for a in articles:
        title = _esc((a.title or "")[:max_title])
        link = _esc(a.url)
        src = _esc(a.source or "")
        when = _esc(fmt_dt_short(a.published_at or a.fetched_at))
        badge = ""
        if badge_fn:
            raw = badge_fn(a)
            if raw:
                badge = f'<span class="intel-badge">{_esc(raw)}</span>'
        items.append(
            f'<div class="intel-item">'
            f'<a class="intel-item-title" href="{link}" target="_blank" rel="noopener">{title}</a>'
            f'<div class="intel-item-meta">{badge}'
            f'<span class="intel-item-src">{src}</span>'
            f'<span class="intel-item-time">{when}</span></div></div>'
        )
    feed_class = "intel-feed intel-feed-side-meta" if meta_on_right else "intel-feed"
    st.markdown(
        f'<div class="{feed_class}">{"".join(items)}</div>',
        unsafe_allow_html=True,
    )


def render_latest_feed(articles: list[Article]) -> None:
    """Dense, date-grouped index suitable for scanning large news lists."""
    if not articles:
        st.caption("No articles to display.")
        return

    items: list[str] = []
    current_day = ""
    for article in articles:
        title = _esc((article.title or "")[:180])
        link = _esc(article.url)
        source = _esc(article.source or "News")
        category = _esc(
            article.category
            if article.category and article.category != "Uncategorized"
            else "Markets"
        )
        region = "Vietnam" if article.region == "vietnam" else "Global"
        article_dt = article.published_at or article.fetched_at
        when = _esc(fmt_relative_time(article_dt))
        clock = _esc(article_dt.strftime("%H:%M") if article_dt else "")
        day = article_dt.strftime("%Y-%m-%d") if article_dt else "Undated"
        if day != current_day:
            current_day = day
            day_label = (
                article_dt.strftime("%A, %B %d") if article_dt else "Undated"
            )
            items.append(
                f'<div class="news-index-date"><span>{_esc(day_label)}</span></div>'
            )
        items.append(
            f'<a class="news-index-row" href="{link}" target="_blank" rel="noopener">'
            '<span class="news-index-main">'
            f'<strong>{title}</strong>'
            f'<small>{source} · {category} · {region} · {when}</small>'
            "</span>"
            f'<span class="news-index-source">{source}</span>'
            f'<span class="news-index-topic">{category}</span>'
            f'<span class="news-index-time"><b>{clock}</b><small>{when}</small></span>'
            '<span class="news-index-arrow">↗</span>'
            "</a>"
        )

    st.markdown(
        '<div class="news-index">'
        '<div class="news-index-head">'
        "<span>Headline</span><span>Source</span><span>Topic</span><span>Time</span><span></span>"
        "</div>"
        f'{"".join(items)}</div>',
        unsafe_allow_html=True,
    )


def render_summary_cards(summaries: list[tuple[Article, ArticleSummary]], *, limit: int = 8) -> None:
    if not summaries:
        st.caption("No AI summaries yet.")
        return

    for article, summary in summaries[:limit]:
        try:
            data: dict[str, Any] = json.loads(summary.summary_json)
        except Exception:
            data = {"summary": summary.summary_json}

        headline = _esc(str(data.get("headline") or article.title))
        body = _esc(str(data.get("summary") or ""))
        sentiment = _esc(str(data.get("sentiment") or "neutral"))
        agent = _esc(summary.agent_type.replace("_", " "))

        st.markdown(
            f"""<div class="intel-card intel-card-tight">
  <h4>{headline}</h4>
  <div class="intel-muted">{agent} · {sentiment}</div>
  <p>{body}</p>
</div>""",
            unsafe_allow_html=True,
        )


def render_newspaper_sections(content: dict[str, Any], regime: str, *, compact: bool = False) -> None:
    rc = regime_class(regime)
    st.markdown(
        f'<div class="intel-card intel-card-tight"><h4>Market regime</h4>'
        f'<span class="{rc}"><strong>{_esc(regime)}</strong></span></div>',
        unsafe_allow_html=True,
    )

    exec_sum = _esc(str(content.get("executive_summary", "")))
    if exec_sum:
        st.markdown(
            f'<div class="intel-card intel-card-tight"><h4>Executive summary</h4><p>{exec_sum}</p></div>',
            unsafe_allow_html=True,
        )

    sections = [
        ("Macro", "macro_overview"),
        ("Equities", "equity_overview"),
        ("Crypto", "crypto_overview"),
        ("China", "china_overview"),
        ("Vietnam", "vietnam_overview"),
    ]
    if compact:
        for label, key in sections:
            text = str(content.get(key, "") or "").strip()
            if not text or text.upper() == "N/A":
                continue
            st.markdown(
                f'<div class="intel-card intel-card-tight"><h4>{label}</h4><p>{_esc(text)}</p></div>',
                unsafe_allow_html=True,
            )
    else:
        cols = st.columns(2)
        for i, (label, key) in enumerate(sections):
            text = str(content.get(key, "") or "").strip()
            if not text or text.upper() == "N/A":
                continue
            with cols[i % len(cols)]:
                st.markdown(
                    f'<div class="intel-card"><h4>{label}</h4><p>{_esc(text)}</p></div>',
                    unsafe_allow_html=True,
                )

    insights = content.get("actionable_insights") or []
    talking = content.get("client_talking_points") or []
    if insights and not compact:
        st.markdown("#### Actionable insights")
        for item in insights[:6]:
            st.markdown(f"- {item}")
    if talking and not compact:
        st.markdown("#### Client talking points")
        for item in talking[:6]:
            st.markdown(f"- {item}")

    top = content.get("top_stories") or []
    if top and not compact:
        with st.expander("Top stories detail", expanded=False):
            for story in top[:5]:
                if isinstance(story, dict):
                    st.markdown(f"**{story.get('title', '')}** — {story.get('why_it_matters', '')}")

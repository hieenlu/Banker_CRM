"""Dashboard column — X posts from Kobeissi Letter and Citrini."""

from __future__ import annotations

import html
from typing import Any

import streamlit as st
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import NewsCache
from scraper import (
    X_PROFILES_DEFAULT,
    get_cached_news,
    scrape_x_analyst_feeds,
    upsert_cached_news,
)
from utils import keywords_hash


X_FEEDS_CACHE_KEY = "__x_analyst_feeds__:KobeissiLetter,citrini"
X_PROFILE_META: dict[str, dict[str, str]] = {
    "KobeissiLetter": {
        "label": "Kobeissi Letter",
        "url": "https://x.com/KobeissiLetter?lang=en",
    },
    "citrini": {
        "label": "Citrini",
        "url": "https://x.com/citrini?lang=en",
    },
}


def _esc(text: str) -> str:
    return html.escape(text or "")


def _item_handle(item: dict[str, Any]) -> str:
    handle = str(item.get("handle") or "").strip().lstrip("@")
    if handle:
        return handle
    source = str(item.get("source") or "")
    if source.startswith("X @"):
        return source[3:].strip()
    return ""


def _filter_posts(posts: list[dict[str, Any]], focus: str) -> list[dict[str, Any]]:
    if focus == "All":
        return posts
    return [p for p in posts if _item_handle(p).lower() == focus.lower()]


def _render_post_list(posts: list[dict[str, Any]]) -> None:
    if not posts:
        st.caption("No posts to display.")
        return

    items: list[str] = []
    for post in posts:
        title = _esc(str(post.get("headline") or "")[:160])
        link = _esc(str(post.get("link") or ""))
        handle = _item_handle(post)
        meta = X_PROFILE_META.get(handle, {})
        badge = _esc(meta.get("label") or f"@{handle}" or "X")
        when = _esc(str(post.get("date") or "")[:16].replace("T", " "))
        src = _esc(f"@{handle}" if handle else str(post.get("source") or "X"))
        items.append(
            f'<div class="intel-item">'
            f'<a class="intel-item-title" href="{link}" target="_blank" rel="noopener">{title}</a>'
            f'<div class="intel-item-meta">'
            f'<span class="intel-badge">{badge}</span>'
            f'<span class="intel-item-src">{src}</span>'
            f'<span class="intel-item-time">{when}</span></div></div>'
        )
    st.markdown(
        f'<div class="intel-feed">{"".join(items)}</div>',
        unsafe_allow_html=True,
    )


def _refresh_x_feeds(session: Session, *, limit_per_profile: int = 12) -> tuple[int, str | None]:
    try:
        results = scrape_x_analyst_feeds(
            list(X_PROFILES_DEFAULT),
            limit_per_profile=limit_per_profile,
        )
    except Exception as exc:
        return 0, str(exc)

    upsert_cached_news(session, X_FEEDS_CACHE_KEY, results)
    session.commit()
    return len(results), None


def render_x_feeds_dashboard_column(session: Session, *, mobile_ui: bool = False) -> None:
    st.markdown("##### X · Analysts")
    st.caption(
        "[@KobeissiLetter](https://x.com/KobeissiLetter?lang=en) · "
        "[@citrini](https://x.com/citrini?lang=en)"
    )

    focus = st.radio(
        "Account",
        ["All", "KobeissiLetter", "citrini"],
        format_func=lambda x: {
            "All": "All",
            "KobeissiLetter": "Kobeissi",
            "citrini": "Citrini",
        }.get(x, x),
        horizontal=True,
        label_visibility="collapsed",
        key="intel_x_feeds_focus",
    )

    cached = get_cached_news(session, X_FEEDS_CACHE_KEY)
    k_hash = keywords_hash(X_FEEDS_CACHE_KEY)
    row = session.execute(select(NewsCache).where(NewsCache.keywords_hash == k_hash)).scalar_one_or_none()

    btn_col, info_col = st.columns([1, 2])
    with btn_col:
        if st.button("Refresh X", key="intel_x_feeds_refresh", width="stretch"):
            with st.spinner("Fetching X posts…"):
                count, err = _refresh_x_feeds(
                    session,
                    limit_per_profile=10 if mobile_ui else 12,
                )
            if err:
                st.error(f"Could not fetch X feeds: {err}")
            else:
                st.success(f"Loaded {count} posts")
                st.rerun()
    with info_col:
        if row:
            st.caption(f"Updated {row.fetched_at.strftime('%Y-%m-%d %H:%M')} UTC")
        else:
            st.caption("No cache yet — refresh to pull posts.")

    posts = _filter_posts(cached, focus)
    limit = 10 if mobile_ui else 14
    if not posts:
        if cached:
            st.warning("No posts for this account filter.")
        else:
            st.warning("No X posts yet — click **Refresh X**.")
    else:
        _render_post_list(posts[:limit])

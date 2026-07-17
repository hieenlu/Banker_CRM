"""Classic keyword-based news (Google / Yahoo / X) — preserved from pre-intel Market News."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st
from sqlalchemy import select

from models import NewsCache
from scraper import get_cached_news, scrape_news, upsert_cached_news
from utils import keywords_hash


def render_legacy_keyword_news(session) -> None:
    st.markdown("### Classic keyword news")
    st.caption("Google News, Yahoo Finance, and X profile RSS — separate from the RSS intelligence pipeline.")

    default_kw = st.text_input("Keywords (comma separated)", value="crypto, economics, inflation", key="legacy_news_kw")
    per_keyword = st.number_input(
        "Results per keyword per feed",
        min_value=1,
        max_value=20,
        value=5,
        step=1,
        key="legacy_news_per_kw",
    )

    kw_text = default_kw
    cached = get_cached_news(session, kw_text)
    st.caption(f"Cached items: {len(cached)}")

    keywords_list = [k.strip() for k in kw_text.split(",") if k.strip()]
    if not keywords_list:
        st.warning("Enter at least one keyword.")
        return

    if not cached:
        st.info("No cached results yet. Use **Refresh (scrape live)** below.")

    k_hash = keywords_hash(kw_text)
    row = session.execute(select(NewsCache).where(NewsCache.keywords_hash == k_hash)).scalar_one_or_none()

    if cached:
        rows: list[dict[str, Any]] = []
        for item in cached:
            rows.append(
                {
                    "headline": str(item.get("headline", "") or ""),
                    "date": str(item.get("date", "") or ""),
                    "link": str(item.get("link", "") or ""),
                    "source": str(item.get("source", "") or ""),
                }
            )
        sorted_rows = sorted(rows, key=lambda r: r.get("date", ""), reverse=True)
        table_rows = []
        for r in sorted_rows[:80]:
            headline = r["headline"].replace("<", "&lt;").replace(">", "&gt;")
            link = r["link"]
            table_rows.append(
                {
                    "Headline": f'<a href="{link}" target="_blank">{headline}</a>' if link else headline,
                    "Source": r["source"] or "—",
                    "Date": r["date"] or "—",
                }
            )
        if table_rows:
            df = pd.DataFrame(table_rows)
            st.markdown(df.to_html(escape=False, index=False), unsafe_allow_html=True)

    if st.button("Refresh (scrape live)", key="legacy_refresh_news_btn"):
        with st.spinner("Scraping news..."):
            results = scrape_news(keywords_list, per_keyword_per_source=int(per_keyword))
            batch_ts = datetime.utcnow().isoformat(timespec="seconds")
            merged_by_link: dict[str, dict[str, Any]] = {}
            for item in cached:
                link = str(item.get("link", "") or "").strip()
                if link:
                    merged_by_link[link] = dict(item)
            for item in results:
                link = str(item.get("link", "") or "").strip()
                if not link:
                    continue
                it = dict(item)
                it["_batch_ts"] = batch_ts
                merged_by_link[link] = it
            merged_results = list(merged_by_link.values())
            upsert_cached_news(session, kw_text, merged_results)
            session.commit()
        st.success(f"Scraped {len(results)} items. Total cached: {len(merged_results)}.")
        st.rerun()

    if row:
        st.caption(f"Last fetched: {row.fetched_at.strftime('%Y-%m-%d %H:%M:%S')} UTC")

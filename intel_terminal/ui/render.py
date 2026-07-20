"""Main Streamlit renderer for the Financial Intelligence Terminal."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime

import streamlit as st
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session

from intel_terminal.agents import generate_daily_newspaper, run_intel_agents
from intel_terminal.config import load_config
from intel_terminal.constants import ARTICLE_CATEGORIES
from intel_terminal.db.models import Article, ArticleSummary
from intel_terminal.db.repository import get_newspaper_for_date
from intel_terminal.llm.factory import llm_runtime_status
from intel_terminal.pipeline.analyze import run_analyze_pipeline, top_articles
from intel_terminal.pipeline.ingest import last_pipeline_run, run_ingest_pipeline
from intel_terminal.settings_store import api_key_configured, load_intel_settings, merge_intel_settings
from intel_terminal.ui.components import (
    fmt_dt,
    render_article_list,
    render_newspaper_sections,
    render_summary_cards,
)
from intel_terminal.ui.legacy_news import render_legacy_keyword_news
from intel_terminal.ui.markets import render_markets_dashboard_column
from intel_terminal.ui.styles import intel_terminal_css
from intel_terminal.ui.vietnam import render_vietnam_dashboard_column
from intel_terminal.ui.x_feeds import render_x_feeds_dashboard_column


INTEL_PAGES: tuple[str, ...] = ("Dashboard", "Latest News", "Briefing & AI", "Archive")


def _refresh_news(session: Session, *, region: str | None = None) -> None:
    with st.spinner("Fetching latest headlines…"):
        result = run_ingest_pipeline(
            session,
            region=region,
            fetch_bodies=False,
            classify_after=True,
        )
        session.commit()
    if result.articles_fetched == 0:
        from intel_terminal.sources.http_fetch import probe_feed_fetch, ssl_diagnostics

        diag = ssl_diagnostics()
        probe = probe_feed_fetch()
        st.error("Refresh returned 0 articles — feeds could not be downloaded.")
        st.markdown(
            f"**Python:** `{diag['python']}`  \n"
            f"**truststore:** {diag['truststore']} · **certifi:** "
            f"{'yes' if diag.get('certifi') else 'missing'}"
        )
        if not probe["ok"]:
            st.warning(
                f"Connectivity test failed: {probe.get('error') or 'unknown'}. "
                "Try: `pip install truststore certifi` then restart Streamlit."
            )
        if result.errors:
            with st.expander("Feed errors", expanded=True):
                for err in result.errors[:20]:
                    st.markdown(f"- {err}")
        return
    msg = (
        f"Refreshed — {result.articles_fetched} fetched, "
        f"{result.articles_new} new, {result.articles_deduped} duplicates skipped"
    )
    if result.articles_pruned:
        msg += f", {result.articles_pruned} old archived stories removed"
    st.success(msg)
    if result.errors:
        with st.expander("Feed warnings", expanded=False):
            for err in result.errors[:12]:
                st.caption(err)
    st.rerun()


def _render_news_toolbar(session: Session) -> None:
    last_run = last_pipeline_run(session)
    btn_col, info_col = st.columns([1, 4])
    with btn_col:
        if st.button("Refresh News", type="primary", key="intel_refresh_news_toolbar"):
            _refresh_news(session)
    with info_col:
        if last_run:
            ts = fmt_dt(last_run.finished_at or last_run.started_at)
            st.caption(
                f"Last refresh: **{ts}** UTC · "
                f"fetched {last_run.articles_fetched}, new {last_run.articles_new}"
            )
        else:
            st.caption("No refresh yet — click **Refresh News**.")


def _render_nav() -> str:
    if "intel_page" not in st.session_state or st.session_state["intel_page"] not in INTEL_PAGES:
        st.session_state["intel_page"] = "Dashboard"
    st.radio(
        "Section",
        INTEL_PAGES,
        horizontal=True,
        label_visibility="collapsed",
        key="intel_page",
    )
    return str(st.session_state["intel_page"])


def _article_stats(session: Session) -> dict[str, int]:
    total = session.execute(select(func.count()).select_from(Article)).scalar_one()
    vietnam = session.execute(
        select(func.count()).select_from(Article).where(Article.region == "vietnam")
    ).scalar_one()
    return {"total": int(total or 0), "vietnam": int(vietnam or 0)}


def _page_briefing_ai(session: Session) -> None:
    """Dedicated tab for daily briefing generation and AI article summaries."""
    st.markdown("#### Briefing & AI")
    st.caption("Daily market briefing and cached AI article summaries")
    st.markdown('<hr class="intel-metrics-rule" />', unsafe_allow_html=True)

    paper = get_newspaper_for_date(session, datetime.utcnow().date())
    col_a, col_b = st.columns([2, 1])
    with col_a:
        if st.button("Generate briefing", key="intel_briefing_gen_paper"):
            with st.spinner("Generating…"):
                result = generate_daily_newspaper(session, force=False)
                session.commit()
            if result.errors:
                st.warning("; ".join(result.errors[:2]))
            else:
                st.success(f"{result.market_regime}")
                st.rerun()
    with col_b:
        if st.button("Run AI", key="intel_briefing_run_agents"):
            cfg = load_config()
            ready, msg = llm_runtime_status(cfg)
            if not ready:
                st.error(msg)
            else:
                with st.spinner("Running agents…"):
                    r = run_intel_agents(session, force=False)
                    session.commit()
                st.success(f"{r.summary.summaries_created} summaries")
                st.rerun()

    if paper:
        try:
            content = json.loads(paper.content_json)
        except Exception:
            content = {}
        st.caption(f"{paper.market_regime} · {fmt_dt(paper.created_at)}")
        render_newspaper_sections(content, paper.market_regime, compact=False)
    else:
        st.caption("No daily briefing yet — generate one above.")

    st.markdown("##### AI summaries")
    rows = session.execute(
        select(Article, ArticleSummary)
        .join(ArticleSummary, ArticleSummary.article_id == Article.id)
        .order_by(desc(ArticleSummary.created_at))
        .limit(12)
    ).all()
    render_summary_cards([(a, s) for a, s in rows], limit=10)

    q = st.text_input("Search", placeholder="Search headlines…", key="intel_briefing_search")
    if q and len(q.strip()) >= 2:
        term = f"%{q.strip()}%"
        hits = list(
            session.execute(
                select(Article)
                .where(or_(Article.title.ilike(term), Article.body_text.ilike(term)))
                .order_by(desc(func.coalesce(Article.published_at, Article.fetched_at)))
                .limit(12)
            )
            .scalars()
            .all()
        )
        render_article_list(hits)


def _page_dashboard(
    session: Session,
    mobile_ui: bool,
    techcom_reports_fn: Callable[[int], list[dict[str, str]]],
) -> None:
    stats = _article_stats(session)
    last_run = last_pipeline_run(session)
    paper = get_newspaper_for_date(session, datetime.utcnow().date())

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Articles", stats["total"])
    m2.metric("Vietnam", stats["vietnam"])
    m3.metric("Ingest", last_run.status if last_run else "—")
    m4.metric("Regime", paper.market_regime if paper else "—")
    st.markdown('<hr class="intel-metrics-rule" />', unsafe_allow_html=True)

    if mobile_ui:
        render_markets_dashboard_column(session, mobile_ui=True)
        st.markdown('<hr class="intel-section-rule" />', unsafe_allow_html=True)
        render_vietnam_dashboard_column(
            session, mobile_ui=True, techcom_reports_fn=techcom_reports_fn
        )
        st.markdown('<hr class="intel-section-rule" />', unsafe_allow_html=True)
        render_x_feeds_dashboard_column(session, mobile_ui=True)
    else:
        left, mid, right = st.columns([1.15, 1.05, 1.0], gap="large")
        with left:
            st.markdown('<span class="intel-col-marker"></span>', unsafe_allow_html=True)
            render_markets_dashboard_column(session, mobile_ui=False)
        with mid:
            st.markdown('<span class="intel-col-marker"></span>', unsafe_allow_html=True)
            render_vietnam_dashboard_column(
                session, mobile_ui=False, techcom_reports_fn=techcom_reports_fn
            )
        with right:
            st.markdown('<span class="intel-col-marker"></span>', unsafe_allow_html=True)
            render_x_feeds_dashboard_column(session, mobile_ui=False)

    st.markdown('<hr class="intel-section-rule" />', unsafe_allow_html=True)
    with st.expander("Settings & tools", expanded=False):
        _page_settings(session)


def _paginate_articles(
    articles: list[Article],
    *,
    state_key: str,
    fingerprint: str,
    page_size: int = 25,
) -> tuple[list[Article], int, int]:
    """Stable pagination that resets when filters change."""
    fingerprint_key = f"{state_key}_fingerprint"
    if st.session_state.get(fingerprint_key) != fingerprint:
        st.session_state[fingerprint_key] = fingerprint
        st.session_state[state_key] = 0
    page_count = max(1, (len(articles) + page_size - 1) // page_size)
    page = min(max(int(st.session_state.get(state_key, 0)), 0), page_count - 1)
    st.session_state[state_key] = page
    start = page * page_size
    return articles[start : start + page_size], page, page_count


def _render_pager(*, state_key: str, page: int, page_count: int, total: int) -> None:
    left, center, right = st.columns([1, 2, 1])
    with left:
        if st.button(
            "← Previous",
            key=f"{state_key}_prev",
            disabled=page <= 0,
            width="stretch",
        ):
            st.session_state[state_key] = page - 1
            st.rerun()
    with center:
        st.markdown(
            f'<div class="news-pager-label">Page {page + 1} of {page_count} · {total} stories</div>',
            unsafe_allow_html=True,
        )
    with right:
        if st.button(
            "Next →",
            key=f"{state_key}_next",
            disabled=page >= page_count - 1,
            width="stretch",
        ):
            st.session_state[state_key] = page + 1
            st.rerun()


def _article_topic_badge(article: Article) -> str | None:
    if article.category and article.category != "Uncategorized":
        return article.category
    return "Vietnam" if article.region == "vietnam" else "Markets"


def _render_unified_news_list(
    articles: list[Article],
    *,
    selected_region: str,
    empty_message: str,
) -> None:
    """Render one chronological column in the Dashboard's list language."""
    if not articles:
        st.caption(empty_message)
        return

    label = {
        "All": "All regions",
        "global": "Global",
        "vietnam": "Vietnam",
    }.get(selected_region, selected_region)
    st.markdown(f"##### {label} · newest first")
    render_article_list(
        articles,
        badge_fn=_article_topic_badge,
        max_title=150,
        meta_on_right=True,
    )


def _page_latest(session: Session, mobile_ui: bool) -> None:
    del mobile_ui  # The feed CSS is responsive.
    st.markdown("#### Latest News")
    st.caption("Current market intelligence · newest first · last 14 days")
    st.markdown('<hr class="intel-metrics-rule" />', unsafe_allow_html=True)

    st.markdown("##### Filters")
    region = st.radio(
        "Region",
        ["All", "global", "vietnam"],
        format_func=lambda x: {"All": "All regions", "global": "Global", "vietnam": "Vietnam"}[x],
        horizontal=True,
        key="intel_latest_region",
    )
    category = st.radio(
        "Topic",
        ["All", *ARTICLE_CATEGORIES],
        format_func=lambda x: "All topics" if x == "All" else x,
        horizontal=True,
        key="intel_latest_cat",
    )
    query = st.text_input(
        "Search",
        placeholder="Search headlines",
        key="intel_latest_search",
    )

    articles = top_articles(
        session,
        limit=500,
        region=None if region == "All" else region,
        category=None if category == "All" else category,
        min_relevance=0.0,
        max_age_hours=336,
        sort="latest",
    )
    if query.strip():
        needle = query.strip().casefold()
        articles = [
            article
            for article in articles
            if needle in f"{article.title} {article.body_text or ''} {article.source}".casefold()
        ]

    if not articles:
        st.markdown(
            """
<div class="latest-empty">
  <div class="latest-empty-icon">⌁</div>
  <strong>No stories found</strong>
  <span>Try a broader filter or refresh the feeds.</span>
</div>
""",
            unsafe_allow_html=True,
        )
        return

    page_articles, page, page_count = _paginate_articles(
        articles,
        state_key="intel_latest_page",
        fingerprint=f"{region}|{category}|{query.strip().casefold()}",
        page_size=30,
    )
    newest = articles[0].published_at or articles[0].fetched_at
    newest_label = fmt_dt(newest)
    m1, m2, m3 = st.columns(3)
    m1.metric("Matching stories", len(articles))
    m2.metric("Page", f"{page + 1} / {page_count}")
    m3.metric("Newest", newest_label.split(" ")[0])
    st.markdown('<hr class="intel-section-rule" />', unsafe_allow_html=True)

    _render_unified_news_list(
        page_articles,
        selected_region=region,
        empty_message="No stories match these filters.",
    )
    st.markdown('<hr class="intel-section-rule" />', unsafe_allow_html=True)
    _render_pager(
        state_key="intel_latest_page",
        page=page,
        page_count=page_count,
        total=len(articles),
    )


def _page_archive(session: Session) -> None:
    from intel_terminal.pipeline.archive import (
        ARCHIVE_FRESH_DAYS,
        ARCHIVE_KEEP_LIMIT,
        count_archive_articles,
        delete_all_archive_articles,
        delete_article_by_id,
        list_archive_articles,
        prune_archive_articles,
    )

    st.markdown("#### Archive")
    st.caption("Older stories retained for reference · newest 50 only")
    st.markdown('<hr class="intel-metrics-rule" />', unsafe_allow_html=True)

    # Enforce cap when opening the tab (covers DB that grew before the rule existed)
    auto = prune_archive_articles(session)
    if auto.deleted:
        session.commit()
        st.caption(f"Auto-pruned {auto.deleted} stories past the {ARCHIVE_KEEP_LIMIT} archive cap.")

    archive_count = count_archive_articles(session)
    m1, m2, m3 = st.columns(3)
    m1.metric("Archived", archive_count)
    m2.metric("Retention cap", ARCHIVE_KEEP_LIMIT)
    m3.metric("Moves here after", f"{ARCHIVE_FRESH_DAYS} days")

    st.markdown('<hr class="intel-section-rule" />', unsafe_allow_html=True)
    st.markdown("##### Filters")
    region = st.radio(
        "Region",
        ["All", "global", "vietnam"],
        format_func=lambda x: {"All": "All regions", "global": "Global", "vietnam": "Vietnam"}[x],
        horizontal=True,
        key="intel_archive_region",
    )

    articles = list_archive_articles(
        session,
        limit=ARCHIVE_KEEP_LIMIT,
        region=None if region == "All" else region,
    )
    if not articles:
        st.markdown(
            """
<div class="latest-empty">
  <div class="latest-empty-icon">⌁</div>
  <strong>Archive is empty</strong>
  <span>Older stories will appear here after they leave the 14-day fresh window.</span>
</div>
""",
            unsafe_allow_html=True,
        )
        return

    page_articles, page, page_count = _paginate_articles(
        articles,
        state_key="intel_archive_page",
        fingerprint=region,
        page_size=25,
    )
    st.markdown(
        f'<div class="latest-feed-summary"><span>{len(articles)} archived</span>'
        f"<span>Cap {ARCHIVE_KEEP_LIMIT} · older than {ARCHIVE_FRESH_DAYS} days</span></div>",
        unsafe_allow_html=True,
    )
    _render_unified_news_list(
        page_articles,
        selected_region=region,
        empty_message="No archived stories for this region.",
    )
    st.markdown('<hr class="intel-section-rule" />', unsafe_allow_html=True)
    _render_pager(
        state_key="intel_archive_page",
        page=page,
        page_count=page_count,
        total=len(articles),
    )

    with st.expander("Archive management", expanded=False):
        a1, a2 = st.columns(2)
        with a1:
            if st.button(
                "Prune to 50",
                key="intel_archive_prune",
                help="Keep newest 50 old stories; delete the rest",
                width="stretch",
            ):
                result = prune_archive_articles(session)
                session.commit()
                st.success(f"Removed {result.deleted}. Archive now has {result.archive_remaining}.")
                st.rerun()
        with a2:
            if st.button(
                "Delete all archive",
                key="intel_archive_wipe",
                type="secondary",
                width="stretch",
            ):
                n = delete_all_archive_articles(session)
                session.commit()
                st.success(f"Deleted {n} archived stories.")
                st.rerun()

        options = {
            f"#{a.id} · {(a.published_at or a.fetched_at)} · {a.title[:70]}": a.id for a in articles
        }
        pick = st.selectbox("Story", list(options.keys()), key="intel_archive_delete_pick")
        if st.button("Delete selected", key="intel_archive_delete_one"):
            if delete_article_by_id(session, options[pick]):
                session.commit()
                st.success("Deleted.")
                st.rerun()
            else:
                st.warning("Story not found.")


def _page_settings(session: Session) -> None:
    cfg = load_config()
    force_regen = st.checkbox(
        "Force regen (ignore 48h summary cache)",
        value=False,
        key="intel_force_regen_agents",
    )
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Refresh RSS feeds", key="intel_run_ingest"):
            with st.spinner("Ingesting feeds…"):
                r = run_ingest_pipeline(session, fetch_bodies=False, classify_after=True)
                session.commit()
            st.success(f"Fetched {r.articles_fetched}, new {r.articles_new}")
            st.rerun()
    with c2:
        if st.button("Re-classify & rank", key="intel_run_analyze"):
            with st.spinner("Analyzing…"):
                r = run_analyze_pipeline(session, only_unclassified=False, hours_back=168)
                session.commit()
            st.success(f"Updated {r.articles_updated} articles")
            st.rerun()
    with c3:
        if st.button("Run AI agents", key="intel_run_agents"):
            ready, status_msg = llm_runtime_status(cfg)
            if not ready:
                st.error(status_msg)
            else:
                with st.spinner("Summaries + newspaper…"):
                    try:
                        r = run_intel_agents(session, force=force_regen)
                        session.commit()
                    except Exception as exc:
                        st.error(f"Agent run failed: {exc}")
                        st.stop()
                all_errors = list(r.summary.errors) + list(r.errors)
                if r.newspaper:
                    all_errors.extend(r.newspaper.errors)
                if all_errors:
                    st.error("Agent run finished with errors:")
                    for err in all_errors[:8]:
                        st.markdown(f"- {err}")
                elif r.summary.summaries_created == 0 and r.summary.cache_hits == 0:
                    st.warning("No summaries created. Refresh feeds or enable Force regen.")
                else:
                    st.success(
                        f"Summaries: {r.summary.summaries_created} new, "
                        f"{r.summary.cache_hits} cached"
                    )
                st.rerun()

    st.markdown("###### LLM")
    disk_settings = load_intel_settings()
    ready, status_msg = llm_runtime_status(cfg)
    if ready:
        st.success(status_msg)
    else:
        st.warning(status_msg)

    with st.form("intel_llm_settings_form", clear_on_submit=False):
        provider = st.selectbox(
            "LLM provider",
            ["openai", "claude", "gemini"],
            index=["openai", "claude", "gemini"].index(cfg.llm.provider)
            if cfg.llm.provider in {"openai", "claude", "gemini"}
            else 0,
            key="intel_llm_provider_select",
        )
        openai_key = st.text_input(
            "OpenAI API key",
            type="password",
            placeholder="sk-…" if api_key_configured(disk_settings, "openai") else "Paste OpenAI key",
            key="intel_openai_api_key_input",
        )
        anthropic_key = st.text_input(
            "Anthropic API key",
            type="password",
            placeholder="sk-ant-…" if api_key_configured(disk_settings, "claude") else "Paste Anthropic key",
            key="intel_anthropic_api_key_input",
        )
        google_key = st.text_input(
            "Google / Gemini API key",
            type="password",
            placeholder="AIza…" if api_key_configured(disk_settings, "gemini") else "Paste Google key",
            key="intel_google_api_key_input",
        )
        if st.form_submit_button("Save LLM settings"):
            updates: dict[str, str] = {"llm_provider": provider}
            if openai_key.strip():
                updates["openai_api_key"] = openai_key.strip()
            if anthropic_key.strip():
                updates["anthropic_api_key"] = anthropic_key.strip()
            if google_key.strip():
                updates["google_api_key"] = google_key.strip()
            merge_intel_settings(updates)
            load_config.cache_clear()
            st.success("Saved to intel_settings.json")
            st.rerun()

    with st.expander("Network diagnostics", expanded=False):
        from intel_terminal.sources.http_fetch import probe_feed_fetch, ssl_diagnostics

        if st.button("Test feed download", key="intel_probe_feeds"):
            st.json(probe_feed_fetch())
        else:
            st.json(ssl_diagnostics())

    with st.expander("Classic keyword news", expanded=False):
        render_legacy_keyword_news(session)


def render_intel_terminal(
    session: Session,
    *,
    mobile_ui: bool = False,
    techcom_reports_fn: Callable[[int], list[dict[str, str]]],
) -> None:
    """Entry point for app.py Market News tab."""
    st.markdown(intel_terminal_css(), unsafe_allow_html=True)
    st.markdown('<div class="intel-wrap intel-terminal">', unsafe_allow_html=True)
    st.subheader("AI Financial Intelligence Terminal")
    st.caption("US/KR/TW markets · Vietnam · X analysts · briefings")

    current = _render_nav()
    _render_news_toolbar(session)

    if current == "Dashboard":
        _page_dashboard(session, mobile_ui, techcom_reports_fn)
    elif current == "Latest News":
        _page_latest(session, mobile_ui)
    elif current == "Briefing & AI":
        _page_briefing_ai(session)
    else:
        _page_archive(session)

    st.markdown("</div>", unsafe_allow_html=True)

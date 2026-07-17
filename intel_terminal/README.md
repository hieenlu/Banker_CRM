# AI Financial Intelligence Terminal

Bloomberg-style personal research terminal integrated with Banker CRM.

## Module 5 (this release): Streamlit UI

Multi-page **Market News** tab in `app.py`:

| Page | Content |
|------|---------|
| Dashboard | metrics, Fear & Greed, top stories, category breakdown |
| Vietnam | Techcombank outlook, VN headlines, macro/banking/wealth themes, VN AI summaries |
| Latest News | filterable ranked article table |
| AI Summaries | cached agent cards |
| Daily Newspaper | briefing + Techcombank monthly PDFs |
| Search | title/body search |
| Settings | ingest / analyze / agents buttons + classic keyword news |

```python
from intel_terminal.ui import render_intel_terminal
render_intel_terminal(session, mobile_ui=False, techcom_reports_fn=cached_techcom_reports)
```

## Module 4: AI agents + daily newspaper

- **8 agents:** macro, equity, crypto, wealth, vietnam_macro/banking/real_estate/equity
- **Summaries:** one agent per article, cached in `intel_article_summaries` (48h default)
- **Daily newspaper:** single LLM call → `intel_daily_newspapers` JSON (fallback digest without API key)
- **Budget:** max 12 summaries/run, 600-char snippets, reuse cache, ~1 newspaper call/day

```python
from intel_terminal.agents import run_intel_agents

with get_session(db_url) as session:
    result = run_intel_agents(session)  # summarize + newspaper
    print(result.summary, result.newspaper.market_regime)
```

## Module 3: Classify + rank + Vietnam layer

- **Classify:** keyword rules → `ARTICLE_CATEGORIES` (no LLM tokens)
- **Rank:** `relevance_score` from recency, source quality, mentions, category confidence
- **Vietnam:** `vietnam_macro_score`, `vietnam_banking_score`, `vietnam_wealth_score`
- **API:** `run_analyze_pipeline()`, `top_articles(vietnam_focus=True)`

Ingest runs classify/rank automatically when `classify_after=True` (default).

## Module 2: RSS ingest + normalize + dedup

- **Feeds:** Yahoo, CNBC, MarketWatch, Investing.com, Reuters, CoinDesk, CoinTelegraph
- **Vietnam:** VnExpress, VietnamNet, Tuoi Tre, Vietnam News, CafeF/Vietstock via Google News
- **Pipeline:** async RSS fetch → normalize → URL + headline dedup → `intel_articles`
- **Paywall policy:** RSS snippet first; optional body fetch detects paywalls — **no bypass**

**Preserved:** Techcombank monthly reports on Daily Newspaper page; classic Google/Yahoo/X news under Settings.

## Folder structure

```
intel_terminal/
  config.py           # env configuration
  constants.py        # categories, agents, newspaper sections
  db/
    models.py         # Article, Summary, Newspaper, PipelineRun
    session.py        # table init
  llm/
    base.py           # BaseLLMProvider
    openai_provider.py
    claude_provider.py
    gemini_provider.py
    factory.py
  sources/
    feeds.py          # feed registry
    rss_fetcher.py    # async RSS fetch
  pipeline/
    normalize.py      # ArticleDraft + URL normalize
    dedup.py          # URL + headline similarity
    body_fetcher.py   # optional full text (paywall detect)
    ingest.py         # run_ingest_pipeline()
    classify.py       # keyword category rules
    rank.py           # relevance_score
    vietnam.py        # Vietnam macro/banking/wealth scores
    analyze.py        # run_analyze_pipeline(), top_articles()
  agents/
    prompts.py        # agent system prompts + routing
    summarize.py      # run_summary_pipeline()
    newspaper.py      # generate_daily_newspaper()
    runner.py         # run_intel_agents()
  ui/
    render.py         # render_intel_terminal()
    components.py     # tables, summary cards
    techcombank.py    # monthly PDF links
    legacy_news.py    # classic keyword scrape UI
```

## Database schema

| Table | Purpose |
|-------|---------|
| `intel_articles` | Normalized headlines + body, category, relevance, Vietnam scores |
| `intel_article_summaries` | Cached LLM output per article + agent type |
| `intel_article_bookmarks` | User bookmarks |
| `intel_daily_newspapers` | One JSON report per calendar day |
| `intel_pipeline_runs` | Ingest/analyze audit log |

Tables are created automatically on app startup (`database.init_db`).

## Setup

```bash
cp .env.example .env
# Edit API keys — only the provider you use is required.

pip install -r requirements.txt
```

## LLM provider switch

```bash
export INTEL_LLM_PROVIDER=openai   # or claude | gemini
export OPENAI_API_KEY=sk-...
```

Budget tip: default models are **gpt-4o-mini**, **claude-3-5-haiku**, **gemini-2.0-flash**.

## Run ingest + analyze

```python
from database import init_db, get_session
from intel_terminal.pipeline import run_ingest_pipeline, run_analyze_pipeline, top_articles

db_url = "sqlite:///banker_crm.sqlite3"
init_db(db_url)

with get_session(db_url) as session:
    result = run_ingest_pipeline(session, region=None, fetch_bodies=False)
    print(result)

    # Re-analyze existing articles only
    analyze = run_analyze_pipeline(session, only_unclassified=True)
    top = top_articles(session, limit=10, vietnam_focus=True)
    for a in top:
        print(a.relevance_score, a.category, a.title[:60])
```

`region` can be `vietnam`, `global`, or `crypto`. Set `fetch_bodies=True` to attempt full text for up to 15 new articles (falls back to RSS on paywall).

## Verify installation

```bash
python -m pytest tests/test_intel_*.py tests/test_llm_factory.py -q
```

## Docker (optional)

```bash
docker build -f Dockerfile.intel -t banker-crm-intel .
docker run -p 8501:8501 --env-file .env banker-crm-intel
```

## Roadmap

| Module | Scope |
|--------|--------|
| **1** ✓ | Foundation |
| **2** ✓ | RSS sources + fetch/normalize + dedup |
| **3** ✓ | Classify, rank, Vietnam layer |
| **4** ✓ | AI agents + daily newspaper |
| **5** ✓ | Streamlit multi-page UI + Techcombank (this doc) |

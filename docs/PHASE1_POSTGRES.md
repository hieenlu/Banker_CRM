# Phase 1 — Postgres migration

## Goal
Move live CRM + intel data from local `banker_crm.sqlite3` to hosted **Postgres**
(Neon or Supabase), without changing app behavior yet.

## What this branch adds
- Postgres-aware `make_engine()` / `normalize_db_url()` in `database.py`
- Schema bootstrap: `python -m scripts.create_postgres_schema`
- Data copy: `python -m scripts.migrate_sqlite_to_postgres`
- `psycopg` (v3) driver in `requirements.txt`
- `CRM_DB_URL` documented in `.env.example`

## Tables migrated
**CRM:** `clients`, `investments`, `incomes`, `reminders`, `news_cache`  
**Intel:** `intel_articles`, `intel_article_summaries`, `intel_article_bookmarks`,
`intel_daily_newspapers`, `intel_pipeline_runs`

## Setup (Neon or Supabase)

### 1. Create a Postgres database
- **Neon:** https://neon.tech → New project → copy connection string  
- **Supabase:** Project Settings → Database → URI  

Example:
```bash
export CRM_DB_URL='postgresql://USER:PASSWORD@HOST/DB?sslmode=require'
```

### 2. Install driver
```bash
pip install 'psycopg[binary]>=3.1'
# or
pip install -r requirements.txt
```

### 3. Create empty schema
```bash
cd /path/to/banker_crm
python -m scripts.create_postgres_schema --db-url "$CRM_DB_URL"
```

### 4. Migrate data from SQLite
```bash
python -m scripts.migrate_sqlite_to_postgres \
  --source "sqlite:///$(pwd)/banker_crm.sqlite3" \
  --target "$CRM_DB_URL"
```

Re-run safely after wiping target tables:
```bash
python -m scripts.migrate_sqlite_to_postgres \
  --source "sqlite:///$(pwd)/banker_crm.sqlite3" \
  --target "$CRM_DB_URL" \
  --truncate-target
```

### 5. Verify
```bash
python -m scripts.migrate_sqlite_to_postgres \
  --source "sqlite:///$(pwd)/banker_crm.sqlite3" \
  --target "$CRM_DB_URL" \
  --verify-only
```

### 6. Point the app at Postgres
```bash
export CRM_DB_URL='postgresql://USER:PASSWORD@HOST/DB?sslmode=require'
streamlit run app.py
```

`app.py` already reads `CRM_DB_URL`. Leave unset to keep using local SQLite.

## Exit criteria (Phase 1 done)
- [ ] Postgres provisioned
- [ ] Schema created
- [ ] Row counts match SQLite (`--verify-only` all OK)
- [ ] Streamlit runs against `CRM_DB_URL` for a smoke check
- [ ] Local SQLite kept as cold backup (do not delete yet)

## Next (Phase 2)
FastAPI CRUD over the same Postgres models.

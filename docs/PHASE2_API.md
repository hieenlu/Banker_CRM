# Phase 2 — FastAPI layer

## Goal
Serve CRM + intel news over HTTP so Streamlit is optional. Same Postgres/SQLite
models and `CRM_DB_URL` as Phase 1.

## Run locally
```bash
pip install -r requirements.txt
export CRM_DB_URL="sqlite:///$(pwd)/banker_crm.sqlite3"   # or Neon/Supabase URL
export CRM_API_USER=banker
export CRM_API_PASSWORD='choose-a-strong-password'
export CRM_JWT_SECRET='long-random-secret'

uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

Open docs: http://127.0.0.1:8000/docs

## Auth (single-tenant MVP)
- `POST /auth/login` JSON `{ "username", "password" }` → JWT
- `POST /auth/token` OAuth2 form (Swagger Authorize)
- `GET /auth/me` Bearer token

Credentials come from env (`CRM_API_USER` / `CRM_API_PASSWORD`). Multi-user
accounts and Apple Sign In are deferred to a later phase.

## Endpoints
| Area | Routes |
|------|--------|
| Health | `GET /health` |
| Auth | `POST /auth/login`, `GET /auth/me` |
| Clients | `GET/POST /clients`, `GET/PATCH/DELETE /clients/{id}` |
| Investments | `GET/POST /investments`, `GET/PATCH/DELETE /investments/{id}` |
| Incomes | `GET/POST /incomes`, `GET/PATCH/DELETE /incomes/{id}` |
| Reminders | `GET/POST /reminders`, `GET/PATCH/DELETE /reminders/{id}` |
| News | `GET /news/articles`, `GET /news/articles/{id}` |
| Bookmarks | `GET/POST /news/bookmarks`, `DELETE /news/bookmarks/{article_id}` |
| Newspaper | `GET /newspaper/today`, `GET /newspaper`, `GET /newspaper/{date}` |

List endpoints return `{ items, page, page_size, total, pages }`.

## Workers
Intel ingest/analyze/agents already write through SQLAlchemy using `CRM_DB_URL`
(Streamlit path). No separate DB wiring is required for Phase 2 — point the
worker at the same URL:

```bash
export CRM_DB_URL='postgresql://…'
# existing Streamlit or a future cron entry that calls run_ingest_pipeline()
```

## Exit criteria
- [x] FastAPI app boots against SQLite/Postgres via `CRM_DB_URL`
- [x] Auth login + `/me`
- [x] Clients / investments / incomes / reminders CRUD
- [x] News list + article detail + bookmarks
- [x] Daily newspaper endpoints
- [x] Health + pagination
- [ ] Smoke against hosted Postgres (Neon/Supabase)
- [ ] Optional: Streamlit calls API instead of ORM (Phase 4 prep)

## Next (Phase 3)
Implemented as a stacked change. See `docs/PHASE3_FILES.md` for R2/S3 client
attachments, Techcombank PDF mirroring, and export ZIPs.

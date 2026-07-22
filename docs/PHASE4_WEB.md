# Phase 4 — Web app (Next.js)

## Goal
Ship a usable **web CRM + market news** desk that talks to the Phase 2 FastAPI
(and Phase 3 file routes). Desktop and iPad Safari are first-class.

This replaces day-to-day Streamlit usage for browsing; Streamlit can remain as
an admin/ingest console until Phase 5 packaging.

## Stack
- Next.js App Router (`web/`)
- JWT auth against `POST /auth/login` (token in `localStorage`)
- Calls `NEXT_PUBLIC_API_URL` (default `http://127.0.0.1:8000`)

## Run locally

### 1. API (Phases 2–3)
```bash
pip install -r requirements.txt
export CRM_DB_URL="sqlite:///$(pwd)/banker_crm.sqlite3"
export CRM_API_USER=banker
export CRM_API_PASSWORD='changeme'
export CRM_JWT_SECRET='dev-secret'
export CRM_STORAGE_BACKEND=local
export CRM_LOCAL_STORAGE_PATH="$(pwd)/data/files"
export CRM_API_CORS_ORIGINS='http://localhost:3000,http://127.0.0.1:3000'

uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Web UI
```bash
cd web
cp .env.example .env.local   # optional
npm install
npm run dev
```

Open http://127.0.0.1:3000 — sign in with `CRM_API_USER` / `CRM_API_PASSWORD`.

## Screens
| Route | Purpose |
|---|---|
| `/login` | Username / password → JWT |
| `/clients` | Search + create clients |
| `/clients/[id]` | Profile, cashflow, holdings, reminders, **attachments** |
| `/portfolio` | Cross-client holdings |
| `/reminders` | Follow-ups |
| `/news` | Dashboard (top / Vietnam / regime) |
| `/news/latest` | 14-day feed with filters |
| `/news/briefing` | Daily newspaper + Techcombank PDF sync/download |
| `/news/archive` | Older-than-14-day stories |

## iPad Safari notes
- `viewport-fit=cover` + safe-area padding
- Collapsible sidebar / sticky top bar under 960px
- 44px minimum tap targets
- Horizontal tables scroll instead of crushing columns

## Exit criteria
- [x] Login against Phase 2 auth
- [x] Clients list / detail
- [x] Portfolio + reminders views
- [x] Market News: Dashboard / Latest / Briefing / Archive
- [x] Client attachment upload / download / delete + ZIP export
- [x] Techcombank report list + sync trigger
- [x] Responsive layout for desktop and tablet widths
- [ ] Live smoke against hosted API + R2/S3 (ops)

## Deploy on Google Cloud (iPad from anywhere)
See `docs/DEPLOY_GCP.md` and `./scripts/deploy_cloudrun.sh`.

## Next (Phase 5)
Background jobs for RSS / rank / AI / prune without opening the UI.

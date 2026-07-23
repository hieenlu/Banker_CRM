# Banker Personal CRM (Local)

Lightweight personal CRM for a financial banker:
- Clients + investments with live pricing (vnstock for VN symbols, yfinance fallback)
- Reminders (birthdays, investment maturities, manual reminders)
- News scraper (Google News RSS + Yahoo Finance)
- Telegram notifications (optional)
- **Phase 2:** FastAPI over the same DB (`docs/PHASE2_API.md`)
- **Phase 3:** Cloudflare R2 / AWS S3 file storage (`docs/PHASE3_FILES.md`)
- **Phase 4:** Next.js web desk (`docs/PHASE4_WEB.md`)

## Setup

From this folder:
```bash
pip install -r requirements.txt
```

## Run (Streamlit)

```bash
streamlit run app.py
```

## Run (API — Phase 2)

```bash
export CRM_API_USER=banker
export CRM_API_PASSWORD='changeme'
export CRM_JWT_SECRET='dev-secret'
uvicorn api.main:app --reload --port 8000
```

Docs: http://127.0.0.1:8000/docs  
Point `CRM_DB_URL` at Neon/Supabase Postgres (Phase 1) or leave unset for local SQLite.


## Run (Web — Phase 4)

```bash
# terminal 1 — API
export CRM_API_USER=banker CRM_API_PASSWORD='changeme' CRM_JWT_SECRET='dev-secret'
export CRM_STORAGE_BACKEND=local CRM_LOCAL_STORAGE_PATH="$(pwd)/data/files"
uvicorn api.main:app --reload --port 8000

# terminal 2 — web
cd web && npm install && npm run dev
```

Open http://127.0.0.1:3000 — see `docs/PHASE4_WEB.md`.

## Deploy (Google Cloud Run — iPad)

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
export CRM_API_PASSWORD='strong-password'
export CRM_DB_URL='postgresql://…'   # recommended
./scripts/deploy_cloudrun.sh
```

Open the printed `https://banker-crm-web-….run.app` URL in iPad Safari.  
Full guide: `docs/DEPLOY_GCP.md`.

## Telegram configuration (required to send notifications)

Set environment variables:

```bash
export TELEGRAM_BOT_TOKEN="your_bot_token"
export TELEGRAM_CHAT_ID="your_chat_id"
```

You can also set them before launching Streamlit, e.g.:
```bash
TELEGRAM_BOT_TOKEN="..." TELEGRAM_CHAT_ID="..." streamlit run app.py
```

## Notes

- Default DB is local SQLite; set `CRM_DB_URL` for hosted Postgres (see `docs/PHASE1_POSTGRES.md`).
- Live price and news scraping require network access.

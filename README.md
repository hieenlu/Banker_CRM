# Banker Personal CRM (Local)

Lightweight personal CRM for a financial banker:
- Clients + investments with live pricing (vnstock for VN symbols, yfinance fallback)
- Reminders (birthdays, investment maturities, manual reminders)
- News scraper (Google News RSS + Yahoo Finance)
- Telegram notifications (optional)
- **Phase 2:** FastAPI over the same DB (`docs/PHASE2_API.md`)
- **Phase 3:** Cloudflare R2 / AWS S3 file storage (`docs/PHASE3_FILES.md`)

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

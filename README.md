# Banker Personal CRM (Local)

Lightweight personal CRM for a financial banker:
- Clients + investments with live pricing (vnstock for VN symbols, yfinance fallback)
- Reminders (birthdays, investment maturities, manual reminders)
- News scraper (Google News RSS + Yahoo Finance)
- Telegram notifications (optional)

## Setup

From this folder:
```bash
pip install -r requirements.txt
```

## Run

```bash
streamlit run app.py
```

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

- Everything runs locally (SQLite DB created automatically on first run).
- Live price and news scraping require network access.
# Banker_CRM

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from typing import Any
import calendar
import re

import pandas as pd
import streamlit as st
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from database import default_db_path, get_session, init_db, load_app_settings, save_usd_vnd_rate
from models import Client, Income, Investment, NewsCache, Reminder
from scraper import (
    fetch_fear_greed_index,
    get_cached_news,
    scrape_news,
    scrape_techcombank_monthly_reports,
    upsert_cached_news,
)
from telegram_bot import TelegramConfig, load_telegram_config_from_env, send_telegram_message
from fetch_prices import fetch_latest_prices
from client_import import build_import_template_bytes, import_clients_workbook
from utils import (
    client_portfolio_table,
    format_display_money,
    iso_date_or_empty,
    keywords_hash,
    next_birthday_date,
    portfolio_totals,
)


st.set_page_config(page_title="Banker Personal CRM", layout="wide")


def get_db_url() -> str:
    return os.environ.get("CRM_DB_URL", f"sqlite:///{default_db_path()}")


DB_URL = get_db_url()
init_db(DB_URL)
ASSET_TYPES = ["VN_Stock", "US_Stock", "Commodity", "Real Estate", "Bond", "Debt", "Term Deposit", "CD", "Crypto", "Cash"]
CURRENCIES = ["USD", "VND"]
TERM_TENOR_OPTIONS = [f"{i} month" if i == 1 else f"{i} months" for i in range(1, 13)]


def _normalize_asset_type_name(t: str | None) -> str:
    """Map legacy DB label to current ASSET_TYPES name."""
    s = (t or "").strip()
    if s.lower() == "certificate of deposit":
        return "CD"
    if s.lower() == "stock":
        return "VN_Stock"
    if s.lower() == "real estate":
        return "Real Estate"
    if s.lower() == "debt":
        return "Debt"
    return s


def _is_cd_kind(kind: str) -> bool:
    k = (kind or "").lower().strip()
    return k in {"cd", "certificate of deposit"}


def _default_currency_for_asset(asset_type: str | None) -> str:
    k = (asset_type or "").strip().lower()
    return "USD" if k in {"us_stock", "crypto"} else "VND"


def _add_months(d: date, months: int) -> date:
    year = d.year + (d.month - 1 + months) // 12
    month = (d.month - 1 + months) % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


@st.cache_data(ttl=60 * 60)
def cached_latest_prices(
    tickers: tuple[str, ...],
    vn_stock_tickers: tuple[str, ...],
    us_stock_tickers: tuple[str, ...],
    commodity_tickers: tuple[str, ...],
    crypto_tickers: tuple[str, ...],
    refresh_token: int,
) -> dict[str, float | None]:
    # refresh_token is included to let the user force a re-fetch.
    return fetch_latest_prices(
        tickers,
        vn_stock_tickers=vn_stock_tickers,
        us_stock_tickers=us_stock_tickers,
        commodity_tickers=commodity_tickers,
        crypto_tickers=crypto_tickers,
    )


@st.cache_data(ttl=12 * 60 * 60)
def cached_techcom_reports(limit: int = 8) -> list[dict[str, str]]:
    return scrape_techcombank_monthly_reports(limit=limit)


def _safe_str(x: Any) -> str:
    return "" if x is None else str(x)


def _render_clients_table(clients: list[Client]) -> None:
    rows = [
        {
            "ID": c.id,
            "Name": c.name,
            "Birthday": iso_date_or_empty(c.birthday),
            "Phone": _safe_str(c.phone_number),
            "Email": _safe_str(c.email),
        }
        for c in clients
    ]
    if not rows:
        st.dataframe(
            pd.DataFrame(columns=["ID", "Name", "Birthday", "Phone", "Email"]),
            width="stretch",
            hide_index=True,
        )
        return
    st.dataframe(pd.DataFrame(rows).sort_values("Name"), width="stretch", hide_index=True)


def _calc_tickers_for_pricing(
    investments: list[Investment],
) -> tuple[list[str], list[str], list[str], list[str], list[str]]:
    tickers: set[str] = set()
    vn_stock_tickers: set[str] = set()
    us_stock_tickers: set[str] = set()
    commodity_tickers: set[str] = set()
    crypto_tickers: set[str] = set()
    for inv in investments:
        asset_type = (inv.asset_type or "").strip().lower()
        if asset_type in {"stock", "vn_stock", "us_stock", "commodity", "bond", "crypto"}:
            t = (inv.ticker_identifier or "").strip()
            if t:
                tickers.add(t)
                if asset_type in {"stock", "vn_stock"}:
                    vn_stock_tickers.add(t)
                elif asset_type == "us_stock":
                    us_stock_tickers.add(t)
                elif asset_type == "commodity":
                    commodity_tickers.add(t)
                elif asset_type == "crypto":
                    crypto_tickers.add(t)
    return (
        sorted(tickers),
        sorted(vn_stock_tickers),
        sorted(us_stock_tickers),
        sorted(commodity_tickers),
        sorted(crypto_tickers),
    )


def _send_due_telegram_notifications(session) -> dict[str, Any]:
    # Prefer values entered in Settings (session_state), fallback to env vars.
    token = (st.session_state.get("telegram_bot_token") or "").strip()
    chat_id = (st.session_state.get("telegram_chat_id") or "").strip()
    cfg = TelegramConfig(token=token, chat_id=chat_id) if token and chat_id else load_telegram_config_from_env()
    if cfg is None:
        return {
            "sent": 0,
            "error": "Telegram is not configured. Set it in Settings or via TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID.",
        }

    today = date.today()
    sent_events: list[str] = []
    rows_to_mark_sent: list[Reminder] = []

    # Manual due (user-controlled)
    manual_due = session.execute(
        select(Reminder).where(
            Reminder.reminder_type == "manual",
            Reminder.reminder_date == today,
            Reminder.sent_at.is_(None),
        )
    ).scalars().all()

    for r in manual_due:
        msg = f"Manual reminder: {r.title}"
        if r.client_id:
            client = session.get(Client, r.client_id)
            if client:
                msg += f" (Client: {client.name})"
        sent_events.append(msg)
        rows_to_mark_sent.append(r)

    # Automatic due: birthdays (yearless), home insurance expiries, and maturities (date-specific)
    clients = session.execute(select(Client)).scalars().all()
    birthday_due = []
    home_insurance_due = []
    for c in clients:
        if not c.birthday:
            pass
        else:
            next_bday = next_birthday_date(c.birthday, today)
            reminder_date = next_bday - timedelta(days=1)
            if reminder_date == today:
                birthday_due.append(c)
        expiry_date = getattr(c, "home_insurance_expiry_date", None)
        if expiry_date and (expiry_date - timedelta(days=1) == today):
            home_insurance_due.append(c)

    investments = session.execute(select(Investment).options(selectinload(Investment.client))).scalars().all()
    maturity_due = []
    for inv in investments:
        if inv.maturity_date and inv.maturity_date - timedelta(days=1) == today:
            maturity_due.append(inv)

    # Insert/mark birthday due reminders (avoid duplicates)
    for c in birthday_due:
        existing = session.execute(
            select(Reminder).where(
                Reminder.reminder_type == "birthday",
                Reminder.client_id == c.id,
                Reminder.investment_id.is_(None),
                Reminder.reminder_date == today,
            )
        ).scalars().all()
        if existing and any(r.sent_at is not None for r in existing):
            continue
        # Find the first row (create if missing) and send.
        row = existing[0] if existing else Reminder(
            title=f"Birthday reminder: {c.name}",
            client_id=c.id,
            investment_id=None,
            reminder_date=today,
            reminder_type="birthday",
            notes=None,
        )
        if not existing:
            session.add(row)
        sent_events.append(f"Birthday: {c.name}")
        rows_to_mark_sent.append(row)

    # Insert/mark maturity due reminders (avoid duplicates)
    for inv in maturity_due:
        existing = session.execute(
            select(Reminder).where(
                Reminder.reminder_type == "maturity",
                Reminder.investment_id == inv.id,
                Reminder.client_id == inv.client_id,
                Reminder.reminder_date == today,
            )
        ).scalars().all()
        if existing and any(r.sent_at is not None for r in existing):
            continue
        row = existing[0] if existing else Reminder(
            title=f"Maturity reminder: {inv.client.name}",
            client_id=inv.client_id,
            investment_id=inv.id,
            reminder_date=today,
            reminder_type="maturity",
            notes=None,
        )
        if not existing:
            session.add(row)
        sent_events.append(f"Maturity: {inv.client.name} ({iso_date_or_empty(inv.maturity_date)})")
        rows_to_mark_sent.append(row)

    # Insert/mark home insurance due reminders (avoid duplicates)
    for c in home_insurance_due:
        existing = session.execute(
            select(Reminder).where(
                Reminder.reminder_type == "home_insurance",
                Reminder.client_id == c.id,
                Reminder.investment_id.is_(None),
                Reminder.reminder_date == today,
            )
        ).scalars().all()
        if existing and any(r.sent_at is not None for r in existing):
            continue
        row = existing[0] if existing else Reminder(
            title=f"Home insurance expiry reminder: {c.name}",
            client_id=c.id,
            investment_id=None,
            reminder_date=today,
            reminder_type="home_insurance",
            notes=None,
        )
        if not existing:
            session.add(row)
        amount_cov = getattr(c, "home_insurance_amount_covered", None)
        premium = getattr(c, "home_insurance_insured_premium", None)
        exp_txt = iso_date_or_empty(getattr(c, "home_insurance_expiry_date", None))
        cov_txt = f"{float(amount_cov):,.0f}" if amount_cov is not None else "N/A"
        prem_txt = f"{float(premium):,.0f}" if premium is not None else "N/A"
        sent_events.append(
            f"Home Insurance: {c.name} (Expiry {exp_txt}, Covered {cov_txt}, Premium {prem_txt})"
        )
        rows_to_mark_sent.append(row)

    if not sent_events:
        return {"sent": 0, "error": None, "details": "No pending reminders due today."}

    text = "Banker CRM reminder(s) due today:\n\n" + "\n".join([f"- {e}" for e in sent_events])
    try:
        send_telegram_message(cfg, text=text)
    except Exception as exc:
        session.rollback()
        return {"sent": 0, "error": f"Failed to send Telegram notifications: {exc}"}

    sent_at_ts = datetime.utcnow()
    for row in rows_to_mark_sent:
        row.sent_at = sent_at_ts
    session.commit()
    return {"sent": len(sent_events), "error": None}


def main() -> None:
    st.title("Banker Personal CRM")
    st.markdown(
        """
<style>
button[kind="primary"] {
    background-color: #d62828 !important;
    border-color: #d62828 !important;
    color: #ffffff !important;
}
</style>
""",
        unsafe_allow_html=True,
    )

    if "price_refresh_token" not in st.session_state:
        st.session_state.price_refresh_token = 0
    if "telegram_bot_token" not in st.session_state:
        st.session_state.telegram_bot_token = ""
    if "telegram_chat_id" not in st.session_state:
        st.session_state.telegram_chat_id = ""
    if "client_edit_id" not in st.session_state:
        st.session_state.client_edit_id = None
    if "client_delete_confirm_id" not in st.session_state:
        st.session_state.client_delete_confirm_id = None
    if "show_add_client" not in st.session_state:
        st.session_state.show_add_client = False
    if "pending_delete_investment_id" not in st.session_state:
        st.session_state.pending_delete_investment_id = None
    if "pending_done_investment_id" not in st.session_state:
        st.session_state.pending_done_investment_id = None
    if "pending_done_client_id" not in st.session_state:
        st.session_state.pending_done_client_id = None
    if "done_checkbox_reset_key" not in st.session_state:
        st.session_state.done_checkbox_reset_key = None
    # FX: crm_settings.json is the source of truth whenever it contains a rate (reload every run so
    # portfolio always matches saved Settings; session-only init would stay stuck on 25500 after first load).
    _fx_disk = load_app_settings()
    if "usd_vnd_rate" in _fx_disk:
        st.session_state.usd_vnd_rate = float(_fx_disk["usd_vnd_rate"])
    elif "usd_vnd_rate" not in st.session_state:
        st.session_state.usd_vnd_rate = 25500.0
    if "portfolio_display_currency" not in st.session_state:
        st.session_state.portfolio_display_currency = "USD"

    st.sidebar.header("Navigation")
    tab = st.sidebar.radio("Go to", ["Clients", "Reminders", "Market News", "Settings"], index=0)

    # When navigating to Settings, sync the FX editor from the saved rate (fixes tab-switch reset).
    _prev_tab = st.session_state.get("_last_main_tab")
    if _prev_tab != tab and tab == "Settings":
        _disk = load_app_settings()
        if "usd_vnd_rate" in _disk:
            st.session_state.usd_vnd_rate = float(_disk["usd_vnd_rate"])
        st.session_state.settings_fx_rate_input = float(st.session_state.usd_vnd_rate)
    st.session_state._last_main_tab = tab
    if "settings_fx_rate_input" not in st.session_state:
        st.session_state.settings_fx_rate_input = float(st.session_state.usd_vnd_rate)

    st.sidebar.divider()
    st.sidebar.subheader("Price refresh")
    if st.sidebar.button("Refresh latest prices"):
        cached_latest_prices.clear()
        st.session_state.price_refresh_token += 1
        st.sidebar.success("Latest prices refreshed.")

    if tab == "Clients":
        clients_expander_limit = 50  # around 50 clients expected
        with get_session(DB_URL) as session:
            clients = session.execute(select(Client).order_by(Client.name)).scalars().all()
            investments = session.execute(select(Investment).options(selectinload(Investment.client))).scalars().all()
            incomes = session.execute(select(Income)).scalars().all()

            tickers, vn_stock_tickers, us_stock_tickers, commodity_tickers, crypto_tickers = _calc_tickers_for_pricing(investments)
            price_map = cached_latest_prices(
                tuple(tickers),
                tuple(vn_stock_tickers),
                tuple(us_stock_tickers),
                tuple(commodity_tickers),
                tuple(crypto_tickers),
                st.session_state.price_refresh_token,
            )

            header_left, header_right = st.columns([5, 2])
            with header_left:
                st.subheader("Client Actions")
            with header_right:
                if st.button("+", key="toggle_add_client", help="Add a new client"):
                    st.session_state.show_add_client = True

            _render_clients_table(clients)
            st.caption(f"Loaded {len(clients)} clients, {len(investments)} investments. Live pricing for {len(tickers)} tickers.")

            with st.expander("Import clients from Excel", expanded=False):
                st.markdown(
                    "Download the template, fill in **Clients** (required) and optionally **Investments**, "
                    "**Incomes**, and **Obligations** (Home Insurance + Other Obligations). "
                    "Use the same `client_key` on every row for one person."
                )
                st.download_button(
                    label="Download import template (.xlsx)",
                    data=build_import_template_bytes(),
                    file_name="client_import_template.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="download_client_import_template",
                )
                skip_dup_names = st.checkbox(
                    "Skip clients whose name already exists",
                    value=True,
                    key="import_skip_existing_names",
                )
                upload = st.file_uploader(
                    "Upload filled workbook",
                    type=["xlsx"],
                    key="client_import_upload",
                )
                if upload is not None and st.button("Run import", key="client_import_run"):
                    import_result = import_clients_workbook(
                        upload.getvalue(),
                        session,
                        skip_existing_names=skip_dup_names,
                    )
                    if import_result.clients_created or import_result.obligations_created:
                        st.success(
                            f"Created {import_result.clients_created} client(s), "
                            f"{import_result.investments_created} investment(s), "
                            f"{import_result.incomes_created} income/cashflow row(s), "
                            f"{import_result.obligations_created} obligation(s) "
                            f"({import_result.home_insurance_set} home insurance)."
                        )
                    if import_result.clients_skipped:
                        st.info(f"Skipped {import_result.clients_skipped} existing client name(s).")
                    for w in import_result.warnings:
                        st.warning(w)
                    for err in import_result.errors:
                        st.error(err)
                    if (
                        import_result.clients_created
                        and not import_result.errors
                    ):
                        st.rerun()

            # Add client
            if st.session_state.show_add_client:
                add_header_left, add_header_right = st.columns([6, 1])
                with add_header_left:
                    st.markdown("#### Add client")
                with add_header_right:
                    if st.button("×", key="close_add_client", help="Close add client"):
                        st.session_state.show_add_client = False
                        st.rerun()

                name = st.text_input("Name", max_chars=200, key="add_client_name")
                use_bday = st.checkbox("Has birthday?", value=True, key="add_client_use_bday")
                birthday = st.date_input("Birthday", value=date(1990, 1, 1), disabled=not use_bday, key="add_client_bday")
                address = st.text_area("Address", key="add_client_address")
                phone = st.text_input("Phone number", key="add_client_phone")
                email = st.text_input("Email", key="add_client_email")
                notes = st.text_area("Notes", key="add_client_notes")

                st.markdown("#### Initial investments (optional)")
                add_holdings = st.checkbox("Add investment holdings now", value=False, key="add_client_add_holdings")
                init_asset_type = "VN_Stock"
                init_currency = _default_currency_for_asset(init_asset_type)
                init_ticker_identifier = ""
                init_quantity = 0.0
                init_purchase_price = 0.0
                init_purchase_date = None
                init_tenor = None
                init_expected_coupon = None
                init_received_coupon = None
                init_unit = None
                init_ytm = None
                init_current_price = None
                init_maturity_date = None
                init_principal_payment = None
                init_notes = ""
                if add_holdings:
                    init_asset_type = st.selectbox("Asset Type", ASSET_TYPES, index=0, key="init_asset_type")
                    init_asset_kind = init_asset_type.lower()
                    is_cd = _is_cd_kind(init_asset_kind)
                    is_td = init_asset_kind == "term deposit"
                    is_bond = init_asset_kind == "bond"
                    is_stock = init_asset_kind in {"stock", "vn_stock", "us_stock", "commodity"}
                    is_real_estate = init_asset_kind == "real estate"
                    is_debt = init_asset_kind == "debt"
                    is_cash = init_asset_kind == "cash"
                    init_currency = _default_currency_for_asset(init_asset_type)
                    st.caption(f"Currency: {init_currency} (auto by asset type)")
                    init_ticker_name = None
                    if is_cd:
                        init_quantity = 1.0
                        init_ticker_identifier = ""
                        init_principal = st.number_input("Principal", min_value=0.0, value=0.0, step=1000.0, key="init_cd_principal")
                        init_purchase_price = 0.0
                        init_purchase_date = st.date_input("Purchase Date", value=date.today(), key="init_cd_pdate")
                        init_tenor = None
                        init_expected_coupon = None
                        init_maturity_date = None
                        init_interest_rate = None
                    elif is_td:
                        init_quantity = 1.0
                        init_ticker_identifier = ""
                        init_principal = st.number_input("Principal", min_value=0.0, value=0.0, step=1000.0, key="init_td_principal")
                        init_purchase_price = 0.0
                        init_purchase_date = st.date_input("Buy Date", value=date.today(), key="init_td_buy_date")
                        init_tenor = st.selectbox("Tenor", TERM_TENOR_OPTIONS, index=0, key="init_td_tenor")
                        init_interest_rate = st.number_input(
                            "Interest Rate (%)", min_value=0.0, max_value=100.0, value=0.0, step=0.1, key="init_td_ir"
                        )
                        tenor_months = int(init_tenor.split()[0])
                        init_maturity_date = _add_months(init_purchase_date, tenor_months)
                        st.caption(f"Maturity Date (auto): {init_maturity_date.isoformat()}")
                        td_days = max((init_maturity_date - init_purchase_date).days, 0)
                        init_interest_out = float(init_principal) * (float(init_interest_rate) / 100.0) / 365.0 * float(td_days)
                        st.caption(f"Interest (auto): {init_currency} {init_interest_out:,.0f}")
                        init_expected_coupon = None
                    elif is_bond:
                        init_quantity = 1.0
                        init_ticker_identifier = ""
                        init_ticker_name = st.text_input("Ticker", key="init_bond_ticker_name")
                        init_unit = st.number_input("Unit", min_value=0.0, value=0.0, step=1.0, key="init_bond_unit")
                        init_purchase_date = st.date_input("Purchase Date", value=date.today(), key="init_bond_pdate")
                        init_principal = st.number_input("Principal", min_value=0.0, value=0.0, step=1000.0, key="init_bond_principal")
                        init_purchase_price = (float(init_principal) / float(init_unit)) if float(init_unit) > 0 else 0.0
                        st.caption(f"Buy Price (auto) = {init_purchase_price:,.2f}")
                        init_ytm = st.number_input(
                            "YTM (%)", min_value=0.0, max_value=100.0, value=0.0, step=0.1, key="init_bond_ytm"
                        )
                        init_current_price = st.number_input(
                            "Current Price", min_value=0.0, value=0.0, step=0.01, key="init_bond_current_price"
                        )
                        init_expected_coupon = st.number_input(
                            "Expected Coupon (Amount)", min_value=0.0, value=0.0, step=0.01, key="init_bond_coupon"
                        )
                        init_received_coupon = st.number_input(
                            "Received Coupon (Amount)", min_value=0.0, value=0.0, step=0.01, key="init_bond_received_coupon"
                        )
                        init_maturity_date = st.date_input("Maturity Date", value=date.today(), key="init_bond_maturity")
                        init_tenor = None
                        init_interest_rate = None
                    elif is_cash:
                        init_quantity = 1.0
                        init_ticker_identifier = ""
                        init_principal = st.number_input("Amount", min_value=0.0, value=0.0, step=1000.0, key="init_cash_amt")
                        init_purchase_price = 0.0
                        init_purchase_date = None
                        init_tenor = None
                        init_expected_coupon = None
                        init_maturity_date = None
                        init_interest_rate = None
                    elif is_real_estate:
                        init_quantity = 1.0
                        init_ticker_identifier = st.text_input("Property / Identifier", key="init_re_name")
                        init_principal = st.number_input("Principal", min_value=0.0, value=0.0, step=1000.0, key="init_re_principal")
                        init_purchase_price = st.number_input(
                            "Investment Value", min_value=0.0, value=0.0, step=1000.0, key="init_re_investment_value"
                        )
                        init_current_price = st.number_input(
                            "Current Value", min_value=0.0, value=0.0, step=1000.0, key="init_re_current_value"
                        )
                        init_expected_coupon = None
                        init_maturity_date = None
                        init_interest_rate = None
                    elif is_debt:
                        init_quantity = 1.0
                        init_ticker_identifier = st.text_input("Debt / Identifier", key="init_debt_name")
                        init_principal = st.number_input(
                            "Outstanding Balance", min_value=0.0, value=0.0, step=1000.0, key="init_debt_balance"
                        )
                        init_interest_rate = st.number_input(
                            "Interest Rate (%)", min_value=0.0, max_value=100.0, value=0.0, step=0.1, key="init_debt_ir"
                        )
                        init_principal_payment = st.number_input(
                            "Principal Payment",
                            min_value=0.0,
                            value=0.0,
                            step=1000.0,
                            key="init_debt_principal_payment",
                        )
                        init_est_interest_payment = float(init_principal) * (float(init_interest_rate) / 100.0) / 12.0
                        init_total_monthly_payment = float(init_principal_payment) + float(init_est_interest_payment)
                        d_calc_c1, d_calc_c2 = st.columns(2)
                        with d_calc_c1:
                            st.caption(f"Est Interest Payment (auto): {init_currency} {init_est_interest_payment:,.0f}")
                        with d_calc_c2:
                            st.caption(f"Total Monthly Payment (auto): {init_currency} {init_total_monthly_payment:,.0f}")
                        init_purchase_price = 0.0
                        init_current_price = None
                        init_expected_coupon = None
                        init_maturity_date = None
                    else:
                        init_ticker_name = None
                        init_principal = None
                        init_ticker_identifier = st.text_input("Ticker / Identifier", key="init_ticker")
                        init_quantity = st.number_input(
                            "Unit" if is_stock else "Quantity",
                            min_value=0.0,
                            value=0.0,
                            step=1.0,
                            key="init_qty",
                        )
                        init_purchase_price = st.number_input(
                            "Purchase Price (per unit)", min_value=0.0, value=0.0, step=0.01, key="init_pp"
                        )
                        init_purchase_date = None
                        init_tenor = None
                        init_expected_coupon = None
                        init_maturity_date = None
                        init_interest_rate = None
                        init_principal_payment = None
                    init_notes = "" if is_td else st.text_area("Notes", key="init_notes")

                if st.button("Add client", key="add_client_submit"):
                    if not name.strip():
                        st.error("Name is required.")
                    else:
                        c = Client(
                            name=name.strip(),
                            birthday=birthday if use_bday else None,
                            address=address.strip() or None,
                            phone_number=phone.strip() or None,
                            email=email.strip() or None,
                            notes=notes.strip() or None,
                        )
                        session.add(c)
                        session.flush()

                        if add_holdings:
                            asset_kind = init_asset_type.lower()
                            is_bond = asset_kind == "bond"
                            is_stock = asset_kind in {"stock", "vn_stock", "us_stock", "commodity"}
                            is_real_estate = asset_kind == "real estate"
                            if init_currency not in CURRENCIES:
                                init_currency = "USD"
                            inv = Investment(
                                client_id=c.id,
                                asset_type=init_asset_type,
                                currency=init_currency,
                                ticker_name=init_ticker_name.strip() if isinstance(init_ticker_name, str) and init_ticker_name.strip() else None,
                                ticker_identifier=init_ticker_identifier.strip() or None,
                                quantity=float(init_quantity),
                                unit=(
                                    float(init_unit)
                                    if is_bond and init_unit is not None
                                    else float(init_quantity)
                                    if is_stock
                                    else None
                                ),
                                principal=float(init_principal) if init_principal is not None else None,
                                purchase_price=float(init_purchase_price),
                                purchase_date=init_purchase_date,
                                tenor=(init_tenor.strip() or None) if isinstance(init_tenor, str) else None,
                                interest_rate=float(init_interest_rate) if init_interest_rate is not None else None,
                                principal_payment=float(init_principal_payment) if is_debt and init_principal_payment is not None else None,
                                ytm=float(init_ytm) if is_bond and init_ytm is not None else None,
                                current_price=float(init_current_price)
                                if (is_bond or is_real_estate) and init_current_price is not None
                                else None,
                                expected_coupon=float(init_expected_coupon) if is_bond and init_expected_coupon is not None else None,
                                received_coupon=float(init_received_coupon) if is_bond and init_received_coupon is not None else None,
                                maturity_date=init_maturity_date,
                                notes=init_notes.strip() or None,
                            )
                            session.add(inv)
                            st.success("Client added with 1 investment.")
                        else:
                            st.success("Client added.")

                        session.commit()
                        st.session_state.show_add_client = False
                        st.rerun()

            st.subheader("Client Details (expandable)")
            if not clients:
                st.info("No clients yet.")
                return

            for idx, c in enumerate(clients[:clients_expander_limit]):
                invs_all = [inv for inv in investments if inv.client_id == c.id]
                active_invs = [inv for inv in invs_all if not bool(getattr(inv, "is_done", False))]
                past_invs = [inv for inv in invs_all if bool(getattr(inv, "is_done", False))]
                exp_key = f"client_exp_{c.id}"
                with st.expander(f"{c.name} {f'(Birthday: {iso_date_or_empty(c.birthday)})' if c.birthday else ''}", expanded=False, key=exp_key):
                    action_col_left, action_col_edit, action_col_delete = st.columns([5, 2, 2])
                    with action_col_left:
                        st.caption("Client actions")
                    with action_col_edit:
                        if st.button("Edit this client", key=f"edit_client_btn_{c.id}"):
                            st.session_state.client_edit_id = c.id
                            st.session_state.client_delete_confirm_id = None
                    with action_col_delete:
                        if st.button("Delete this client", key=f"delete_client_btn_{c.id}", type="primary"):
                            st.session_state.client_delete_confirm_id = c.id
                            st.session_state.client_edit_id = None

                    if st.session_state.client_edit_id == c.id:
                        with st.form(f"edit_client_inline_form_{c.id}", clear_on_submit=False):
                            name = st.text_input("Name", value=c.name, key=f"edit_client_name_{c.id}")
                            use_bday = st.checkbox("Has birthday?", value=c.birthday is not None, key=f"edit_client_use_bday_{c.id}")
                            birthday_default = c.birthday or date(1990, 1, 1)
                            birthday = st.date_input(
                                "Birthday",
                                value=birthday_default,
                                disabled=not use_bday,
                                key=f"edit_client_birthday_{c.id}",
                            )
                            address = st.text_area("Address", value=c.address or "", key=f"edit_client_address_{c.id}")
                            phone = st.text_input("Phone number", value=c.phone_number or "", key=f"edit_client_phone_{c.id}")
                            email = st.text_input("Email", value=c.email or "", key=f"edit_client_email_{c.id}")
                            notes = st.text_area("Notes", value=c.notes or "", key=f"edit_client_notes_{c.id}")
                            submitted = st.form_submit_button("Save client", key=f"edit_client_submit_{c.id}")
                            if submitted:
                                clean_name = name.strip()
                                if not clean_name:
                                    st.error("Name is required.")
                                else:
                                    client_to_edit = session.get(Client, c.id)
                                    if client_to_edit:
                                        client_to_edit.name = clean_name
                                        client_to_edit.birthday = birthday if use_bday else None
                                        client_to_edit.address = address.strip() or None
                                        client_to_edit.phone_number = phone.strip() or None
                                        client_to_edit.email = email.strip() or None
                                        client_to_edit.notes = notes.strip() or None
                                        session.commit()
                                        st.success("Client updated.")
                                        st.session_state.client_edit_id = None
                                        st.session_state.client_delete_confirm_id = None
                                        st.rerun()

                    if st.session_state.client_delete_confirm_id == c.id:
                        st.warning("This will delete the client and all associated investments.")
                        confirm_col, cancel_col = st.columns([1, 1])
                        with confirm_col:
                            if st.button("Confirm delete", key=f"confirm_delete_client_{c.id}"):
                                client_to_delete = session.get(Client, c.id)
                                if client_to_delete:
                                    session.delete(client_to_delete)
                                    session.commit()
                                    st.success("Client deleted.")
                                st.session_state.client_delete_confirm_id = None
                                st.session_state.client_edit_id = None
                                st.rerun()
                        with cancel_col:
                            if st.button("Cancel", key=f"cancel_delete_client_{c.id}"):
                                st.session_state.client_delete_confirm_id = None
                                st.rerun()

                    disp_ccy = "VND"
                    fx_rate = float(st.session_state.usd_vnd_rate)
                    df, inv_order = client_portfolio_table(
                        c,
                        active_invs,
                        price_map,
                        usd_vnd_rate=fx_rate,
                        display_currency=disp_ccy,
                    )
                    totals = portfolio_totals(df)

                    st.caption(f"Display: **VND** · Settings FX: 1 USD = {fx_rate:,.0f} VND")
                    debt_total = 0.0
                    equity_principal_total = 0.0
                    for _, row in df.iterrows():
                        asset_l = str(row.get("Asset Type", "") or "").strip().lower()
                        principal_disp = float(row.get("Principal Display", row.get("Principal", 0)) or 0)
                        if asset_l == "debt":
                            debt_total += principal_disp
                        else:
                            equity_principal_total += principal_disp

                    # Total Principal = principals in Equities only.
                    total_principal_display = float(equity_principal_total or 0.0)
                    total_current_value_display = float(totals.get("current_value", 0.0) or 0.0)
                    custom_pnl_display = total_current_value_display - debt_total - total_principal_display
                    custom_pnl_pct = (custom_pnl_display / total_principal_display * 100.0) if total_principal_display > 0 else None

                    ratio_text = "N/A" if debt_total <= 0 else f"{(total_current_value_display / debt_total):.2f}x"
                    # Two-row performance summary for quick comparison with/without real estate.
                    principal_all = 0.0
                    current_all = 0.0
                    debt_all = 0.0
                    principal_ex_re = 0.0
                    current_ex_re = 0.0
                    debt_ex_re = 0.0
                    for _, row in df.iterrows():
                        asset_l = str(row.get("Asset Type", "") or "").strip().lower()
                        p_disp = float(row.get("Principal Display", row.get("Principal", 0)) or 0)
                        c_val = float(row.get("Current Value Display", row.get("Current Value", 0)) or 0)
                        if asset_l == "debt":
                            debt_all += p_disp
                        else:
                            # "Including Real Estate" should include equity assets + real estate, excluding debt rows.
                            principal_all += p_disp
                            current_all += c_val
                        # Excluding-RE row should represent Equities group only (exclude debt + real estate).
                        if asset_l not in {"real estate", "debt"}:
                            principal_ex_re += p_disp
                            current_ex_re += c_val

                    pnl_ex_re = current_ex_re - debt_ex_re - principal_ex_re
                    pnl_all = current_all - debt_all - principal_all
                    pct_ex_re = (pnl_ex_re / principal_ex_re * 100.0) if principal_ex_re > 0 else None
                    pct_all = (pnl_all / principal_all * 100.0) if principal_all > 0 else None
                    # Realized P&L = sum of past-investment realized P&L in selected display currency
                    # + done non-concurrent income amounts (one-off income = pure realized gain).
                    realized_past_sum = 0.0
                    if past_invs:
                        df_past_summary, _ = client_portfolio_table(
                            c,
                            past_invs,
                            price_map,
                            usd_vnd_rate=fx_rate,
                            display_currency=disp_ccy,
                        )
                        if not df_past_summary.empty:
                            principal_disp_s = pd.to_numeric(df_past_summary.get("Principal Display"), errors="coerce").fillna(0.0)
                            closing_value_s = pd.to_numeric(
                                df_past_summary.get("Current Value Display", df_past_summary.get("Current Value")),
                                errors="coerce",
                            ).fillna(0.0)
                            realized_past_sum = float((closing_value_s - principal_disp_s).sum())
                    realized_past_sum += sum(
                        float(inc.amount or 0.0)
                        for inc in incomes
                        if inc.client_id == c.id
                        and bool(getattr(inc, "is_done", False))
                        and not bool(getattr(inc, "concurrent", False))
                    )
                    st.markdown(
                        """
<style>
.snapshot-wrap { margin: 0.2rem 0 0.8rem 0; }
.snapshot-section {
  border: 1px solid #dbeafe;
  border-left: 4px solid #2563eb;
  border-radius: 10px;
  padding: 10px 12px;
  margin-bottom: 8px;
  background: linear-gradient(180deg, #f8fbff 0%, #f1f7ff 100%);
}
.snapshot-section:nth-child(2) {
  border-color: #d1fae5;
  border-left-color: #059669;
  background: linear-gradient(180deg, #f7fffb 0%, #f0fff8 100%);
}
.snapshot-section:nth-child(3) {
  border-color: #fecdd3;
  border-left-color: #dc2626;
  background: linear-gradient(180deg, #fff5f5 0%, #fff1f1 100%);
}
.snapshot-title {
  font-size: 0.80rem;
  font-weight: 700;
  color: #1e3a8a;
  text-transform: uppercase;
  letter-spacing: 0.02em;
  margin-bottom: 8px;
}
.snapshot-section:nth-child(2) .snapshot-title { color: #065f46; }
.snapshot-section:nth-child(3) .snapshot-title { color: #991b1b; }
.snapshot-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}
.snapshot-grid-6 {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 8px;
}
.snapshot-card {
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  padding: 8px 9px;
  background: #ffffff;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}
.snapshot-label {
  font-size: 0.69rem;
  color: #475569;
  margin-bottom: 4px;
}
.snapshot-value {
  font-size: 0.86rem;
  font-weight: 700;
  color: #0f172a;
  line-height: 1.2;
  white-space: nowrap;
  overflow-x: auto;
}
@media (prefers-color-scheme: dark) {
  .snapshot-section {
    border-color: #334155;
    border-left-color: #3b82f6;
    background: linear-gradient(180deg, #0b1220 0%, #101827 100%);
  }
  .snapshot-section:nth-child(2) {
    border-color: #334155;
    border-left-color: #10b981;
    background: linear-gradient(180deg, #0b1a17 0%, #0f221d 100%);
  }
  .snapshot-section:nth-child(3) {
    border-color: #334155;
    border-left-color: #ef4444;
    background: linear-gradient(180deg, #1a0b0b 0%, #221010 100%);
  }
  .snapshot-title { color: #bfdbfe; }
  .snapshot-section:nth-child(2) .snapshot-title { color: #a7f3d0; }
  .snapshot-section:nth-child(3) .snapshot-title { color: #fca5a5; }
  .snapshot-card {
    border-color: #334155;
    background: #0f172a;
    box-shadow: none;
  }
  .snapshot-label { color: #94a3b8; }
  .snapshot-value { color: #e2e8f0; }
}
</style>
""",
                        unsafe_allow_html=True,
                    )
                    ex_pct_txt = f" ({pct_ex_re:.2f}%)" if pct_ex_re is not None else ""
                    inc_pct_txt = f" ({pct_all:.2f}%)" if pct_all is not None else ""
                    inc_ratio = "N/A" if debt_all <= 0 else f"{(current_all / debt_all):.2f}x"
                    ex_cards = [
                        ("Total Principal", format_display_money(principal_ex_re, disp_ccy, decimals=0)),
                        ("Current Value", format_display_money(current_ex_re, disp_ccy, decimals=0)),
                        ("Unrealized P&L", f"{format_display_money(pnl_ex_re, disp_ccy, decimals=0)}{ex_pct_txt}"),
                        ("Realized P&L", format_display_money(realized_past_sum, disp_ccy, decimals=0)),
                    ]
                    inc_cards = [
                        ("Total Principal", format_display_money(principal_all, disp_ccy, decimals=0)),
                        ("Current Value", format_display_money(current_all, disp_ccy, decimals=0)),
                        ("Total Debts Value", format_display_money(debt_all, disp_ccy, decimals=0)),
                        ("Unrealized P&L", f"{format_display_money(pnl_all, disp_ccy, decimals=0)}{inc_pct_txt}"),
                        ("Total Equity / Total Debt", inc_ratio),
                    ]
                    ex_cards_html = "".join(
                        f"<div class='snapshot-card'><div class='snapshot-label'>{k}</div><div class='snapshot-value'>{v}</div></div>"
                        for k, v in ex_cards
                    )
                    inc_cards_html = "".join(
                        f"<div class='snapshot-card'><div class='snapshot-label'>{k}</div><div class='snapshot-value'>{v}</div></div>"
                        for k, v in inc_cards
                    )
                    # --- Cashflow section ---
                    _other_obligation_type = "Other Obligations"
                    monthly_income_total = sum(
                        float(inc.amount or 0.0)
                        for inc in incomes
                        if inc.client_id == c.id
                        and getattr(inc, "concurrent", False)
                        and not bool(getattr(inc, "is_done", False))
                        and (inc.income_type or "") != _other_obligation_type
                    )
                    monthly_obligations_total = 0.0
                    for _, row in df.iterrows():
                        tmp_val = row.get("Total Monthly Payment", "")
                        if tmp_val != "" and tmp_val is not None:
                            try:
                                monthly_obligations_total += float(tmp_val)
                            except (TypeError, ValueError):
                                pass
                    monthly_obligations_total += sum(
                        float(inc.amount or 0.0)
                        for inc in incomes
                        if inc.client_id == c.id
                        and getattr(inc, "concurrent", False)
                        and not bool(getattr(inc, "is_done", False))
                        and (inc.income_type or "") == _other_obligation_type
                    )
                    cashflow_ratio = (
                        f"{(monthly_income_total / monthly_obligations_total):.2f}x"
                        if monthly_obligations_total > 0
                        else "N/A"
                    )
                    net_cashflow = monthly_income_total - monthly_obligations_total
                    cf_cards = [
                        ("Monthly Incomes", format_display_money(monthly_income_total, disp_ccy, decimals=0)),
                        ("Monthly Obligations", format_display_money(monthly_obligations_total, disp_ccy, decimals=0)),
                        ("Net Cashflow", format_display_money(net_cashflow, disp_ccy, decimals=0)),
                        ("Income / Obligations Ratio", cashflow_ratio),
                    ]
                    cf_cards_html = "".join(
                        f"<div class='snapshot-card'><div class='snapshot-label'>{k}</div><div class='snapshot-value'>{v}</div></div>"
                        for k, v in cf_cards
                    )
                    st.markdown(
                        f"""
<div class="snapshot-wrap">
  <div class="snapshot-section">
    <div class="snapshot-title">Excluding Real Estate</div>
    <div class="snapshot-grid">
      {ex_cards_html}
    </div>
  </div>
  <div class="snapshot-section">
    <div class="snapshot-title">Including Real Estate</div>
    <div class="snapshot-grid-6">
      {inc_cards_html}
    </div>
  </div>
  <div class="snapshot-section">
    <div class="snapshot-title">Cashflow</div>
    <div class="snapshot-grid">
      {cf_cards_html}
    </div>
  </div>
</div>
""",
                        unsafe_allow_html=True,
                    )

                    if df.empty:
                        st.info("No active investments for this client.")
                    else:
                        st.caption("Active investments grouped into Equities and Debts. Click a group to see details.")
                        reset_done_key = st.session_state.get("done_checkbox_reset_key")
                        if reset_done_key:
                            if reset_done_key in st.session_state:
                                del st.session_state[reset_done_key]
                            st.session_state.done_checkbox_reset_key = None
                        rest_cols = [
                            col
                            for col in df.columns
                            if col
                            not in {
                                "Asset Type",
                                "Principal Display",
                                "Current Value Display",
                                "Unrealized P&L Display",
                            }
                        ]

                        def _active_group_label(asset_name: str) -> str:
                            a = (asset_name or "").strip().lower()
                            return "Debts" if a == "debt" else "Equities"

                        def _active_subgroup_label(asset_name: str) -> str:
                            a = (asset_name or "").strip().lower()
                            if a == "stock":
                                return "VN_Stock"
                            if _is_cd_kind(a) or a == "cash":
                                return "Cash and CDs"
                            if a == "debt":
                                return "Debt"
                            return asset_name

                        def _past_group_label(asset_name: str) -> str:
                            a = (asset_name or "").strip().lower()
                            if _is_cd_kind(a) or a == "cash":
                                return "Cash and CDs"
                            return asset_name

                        subgroup_order_rank = {
                            "Cash and CDs": 1,
                            "Term Deposit": 2,
                            "Bond": 3,
                            "VN_Stock": 4,
                            "US_Stock": 5,
                            "Crypto": 6,
                            "Real Estate": 7,
                        }

                        def _subgroup_sort_key(name: str) -> tuple[int, str]:
                            return (subgroup_order_rank.get(str(name), 999), str(name))

                        def _visible_cols_for_group(group_label: str) -> list[str]:
                            if group_label == "Debt":
                                return [
                                    "Outstanding Balance",
                                    "Interest Rate %",
                                    "Principal Payment",
                                    "Est Interest Payment",
                                    "Total Monthly Payment",
                                    "Notes",
                                ]
                            if group_label == "Cash and CDs":
                                return ["Principal"]
                            if group_label in {"VN_Stock", "US_Stock", "Commodity", "Crypto"}:
                                cols = [
                                    c
                                    for c in rest_cols
                                    if c
                                    in {
                                        "Ticker",
                                        "Unit",
                                        "Buy Price",
                                        "Current Price",
                                        "Principal",
                                        "Current Value",
                                        "Unrealized P&L",
                                        "P&L %",
                                        "Notes",
                                    }
                                ]
                                if "Notes" in cols:
                                    cols = [c for c in cols if c != "Notes"] + ["Notes"]
                                return cols
                            if group_label == "Bond":
                                return [
                                    c
                                    for c in rest_cols
                                    if c
                                    in {
                                        "Ticker",
                                        "Unit",
                                        "Principal",
                                        "Expected Coupon (Amount)",
                                        "Received Coupon (Amount)",
                                        "YTM %",
                                        "Maturity Date",
                                        "Unrealized P&L",
                                    }
                                ]
                            if group_label == "Term Deposit":
                                return [
                                    c
                                    for c in rest_cols
                                    if c
                                    in {
                                        "Principal",
                                        "Buy Date",
                                        "Tenor",
                                        "Interest Rate %",
                                        "Maturity Date",
                                        "Interest",
                                    }
                                ]
                            if group_label == "Real Estate":
                                return ["Principal", "Investment Value", "Current Value", "Unrealized P&L", "P&L %", "Notes"]
                            # Equities default bucket.
                            cols = [
                                c
                                for c in rest_cols
                                if c
                                in {
                                    "Principal",
                                    "Investment Value",
                                    "Current Price",
                                    "Current Value",
                                    "Unrealized P&L",
                                    "P&L %",
                                    "Unit",
                                    "Notes",
                                }
                            ]
                            if "Notes" in cols:
                                cols = [c for c in cols if c != "Notes"] + ["Notes"]
                            return cols

                        def _fmt_cell(col_name: str, value: Any) -> str:
                            if value is None or value == "" or (isinstance(value, float) and pd.isna(value)):
                                return "—"
                            if col_name == "P&L %":
                                return f"{float(value):.2f}%"
                            if col_name in {
                                "Principal",
                                "Outstanding Balance",
                                "Investment Value",
                                "Current Value",
                                "P&L",
                                "Unrealized P&L",
                                "Principal Payment",
                                "Est Interest Payment",
                                "Total Monthly Payment",
                            }:
                                return f"{int(round(float(value))):,}"
                            if col_name == "Interest":
                                return f"{int(round(float(value))):,}"
                            if col_name == "Expected Coupon (Amount)":
                                return f"{int(round(float(value))):,}"
                            if col_name == "Buy Price":
                                return f"{float(value):,.2f}"
                            if col_name == "Current Price":
                                return f"{float(value):,.2f}"
                            if col_name == "Quantity":
                                q = float(value)
                                return f"{int(q):,}" if q.is_integer() else f"{q:,.2f}"
                            return str(value)

                        grouped_active: dict[str, dict[str, list[tuple[Investment, Any]]]] = {}
                        for i, inv in enumerate(inv_order):
                            row = df.iloc[i]
                            top_group = _active_group_label(str(row["Asset Type"]))
                            sub_group = _active_subgroup_label(str(row["Asset Type"]))
                            grouped_active.setdefault(top_group, {}).setdefault(sub_group, []).append((inv, row))
                        total_active_principal = sum(
                            float(row.get("Principal Display", row.get("Principal", 0)) or 0)
                            for subgroup_map in grouped_active.values()
                            for _, row in sum(subgroup_map.values(), [])
                        )

                        for group_name, subgroup_map in grouped_active.items():
                            entries = sum(subgroup_map.values(), [])
                            group_principal = sum(
                                float(e[1].get("Principal Display", e[1].get("Principal", 0)) or 0) for e in entries
                            )
                            if group_name == "Equities":
                                # Exclude Real Estate from Equities unrealized P&L header.
                                group_pnl = sum(
                                    float(
                                        e[1].get(
                                            "Unrealized P&L Display",
                                            e[1].get("Unrealized P&L", 0),
                                        )
                                        or 0
                                    )
                                    for e in entries
                                    if str(e[1].get("Asset Type", "") or "").strip().lower() != "real estate"
                                )
                                group_header = (
                                    f"{group_name} ({len(entries)}) · Principal {disp_ccy} {group_principal:,.0f} · "
                                    f"Unrealized P&L {disp_ccy} {group_pnl:,.0f}"
                                )
                            else:
                                group_pnl = 0.0
                                group_header = (
                                    f"{group_name} ({len(entries)}) · Outstanding Balance {disp_ccy} {group_principal:,.0f}"
                                )
                            with st.expander(
                                group_header,
                                expanded=False,
                            ):
                                subgroup_items = (
                                    [("Debt", entries)]
                                    if group_name == "Debts"
                                    else sorted(list(subgroup_map.items()), key=lambda x: _subgroup_sort_key(x[0]))
                                )
                                for subgroup_name, subgroup_entries in subgroup_items:
                                    sub_principal = sum(
                                        float(e[1].get("Principal Display", e[1].get("Principal", 0)) or 0) for e in subgroup_entries
                                    )
                                    visible_cols = _visible_cols_for_group(subgroup_name)
                                    if group_name == "Debts":
                                        st.caption(f"Outstanding Balance {disp_ccy} {sub_principal:,.0f}")
                                        table_container = st.container()
                                    else:
                                        sub_alloc = (
                                            (sub_principal / equity_principal_total * 100.0)
                                            if equity_principal_total > 0
                                            else 0.0
                                        )
                                        sub_pnl = sum(
                                            float(e[1].get("Unrealized P&L", 0) or 0) for e in subgroup_entries
                                        )
                                        sub_title = (
                                            f"{subgroup_name} ({len(subgroup_entries)}) · Principal {disp_ccy} {sub_principal:,.0f} · "
                                            f"Allocation {sub_alloc:.1f}%"
                                        )
                                        if str(subgroup_name).strip().lower() not in {"real estate", "cash and cds"}:
                                            sub_ccy = _default_currency_for_asset(str(subgroup_name))
                                            sub_title += f" · Unrealized P&L {sub_ccy} {sub_pnl:,.0f}"
                                        table_container = st.expander(
                                            sub_title,
                                            expanded=False,
                                        )
                                    with table_container:
                                        header = st.columns([1.8, 0.45] + [1.35] * len(visible_cols) + [0.7, 0.45])
                                        header[0].markdown("**Asset Type**")
                                        header[1].markdown("** **")
                                        for hi, name in enumerate(visible_cols):
                                            header[hi + 2].markdown(f"**{name}**")
                                        header[-2].markdown("**Done**")
                                        header[-1].markdown("** **")
                                        for inv, row in subgroup_entries:
                                            row_cols = st.columns([1.8, 0.45] + [1.35] * len(visible_cols) + [0.7, 0.45])
                                            row_cols[0].markdown(
                                                f'<span title="Asset type">{row["Asset Type"]}</span>',
                                                unsafe_allow_html=True,
                                            )
                                            if row_cols[1].button(
                                                "✏",
                                                key=f"portfolio_edit_{c.id}_{inv.id}",
                                                help="Edit this investment",
                                            ):
                                                # Clear any stale widget state for this investment edit panel,
                                                # so fields always reload from latest DB values.
                                                suffix = f"_{c.id}_{inv.id}"
                                                for k in list(st.session_state.keys()):
                                                    if k.startswith("edit_") and k.endswith(suffix):
                                                        del st.session_state[k]
                                                st.session_state[f"edit_inv_target_{c.id}"] = inv.id
                                                st.session_state[f"edit_inv_picker_{c.id}"] = inv.id
                                                st.rerun()
                                            for j, name in enumerate(visible_cols):
                                                value_for_cell = row[name]
                                                if (
                                                    name == "Principal"
                                                    and str(row.get("Asset Type", "") or "").strip().lower() == "real estate"
                                                    and "Principal Display" in row
                                                ):
                                                    value_for_cell = row.get("Principal Display", row[name])
                                                cell_text = _fmt_cell(name, value_for_cell)
                                                row_cols[j + 2].write(cell_text)
                                            done_key = f"done_inv_{c.id}_{inv.id}"
                                            done_checked = row_cols[-2].checkbox(
                                                "Done",
                                                value=bool(getattr(inv, "is_done", False)),
                                                key=done_key,
                                                label_visibility="collapsed",
                                            )
                                            if done_checked != bool(getattr(inv, "is_done", False)):
                                                if done_checked:
                                                    # Open close-price prompt once; avoid rerun loops on subsequent rerenders.
                                                    if not (
                                                        st.session_state.pending_done_investment_id == inv.id
                                                        and st.session_state.pending_done_client_id == c.id
                                                    ):
                                                        st.session_state.pending_done_investment_id = inv.id
                                                        st.session_state.pending_done_client_id = c.id
                                                        st.rerun()
                                                else:
                                                    inv_to_update = session.get(Investment, inv.id)
                                                    if inv_to_update:
                                                        inv_to_update.is_done = False
                                                        session.commit()
                                                        st.rerun()
                                            if row_cols[-1].button("✖", key=f"row_del_inv_{c.id}_{inv.id}", type="primary"):
                                                st.session_state.pending_delete_investment_id = inv.id
                                                st.rerun()
                        if "Debts" not in grouped_active:
                            st.caption("No debt.")

                    if (
                        st.session_state.pending_done_investment_id is not None
                        and st.session_state.pending_done_client_id == c.id
                    ):
                        done_id = int(st.session_state.pending_done_investment_id)
                        pending_done_inv = session.get(Investment, done_id)
                        if pending_done_inv and pending_done_inv.client_id == c.id:
                            st.warning("Set closing price before moving investment to past?")
                            default_close = float(getattr(pending_done_inv, "current_price", 0.0) or 0.0)
                            close_price = st.number_input(
                                "Closing Price",
                                min_value=0.0,
                                value=default_close,
                                step=0.01,
                                key=f"done_close_price_{c.id}_{done_id}",
                            )
                            done_col1, done_col2 = st.columns([1, 1])
                            with done_col1:
                                if st.button("Confirm done", key=f"confirm_done_{c.id}_{done_id}", type="primary"):
                                    inv_to_update = session.get(Investment, done_id)
                                    if inv_to_update:
                                        inv_to_update.current_price = float(close_price)
                                        inv_to_update.is_done = True
                                        session.commit()
                                    st.session_state.pending_done_investment_id = None
                                    st.session_state.pending_done_client_id = None
                                    st.success("Investment marked as done.")
                                    st.rerun()
                            with done_col2:
                                if st.button("Cancel", key=f"cancel_done_{c.id}_{done_id}"):
                                    # Reset checkbox state on next run before widget is instantiated.
                                    st.session_state.done_checkbox_reset_key = f"done_inv_{c.id}_{done_id}"
                                    st.session_state.pending_done_investment_id = None
                                    st.session_state.pending_done_client_id = None
                                    st.rerun()
                        else:
                            st.session_state.pending_done_investment_id = None
                            st.session_state.pending_done_client_id = None

                    if st.session_state.pending_delete_investment_id is not None:
                        pending_id = int(st.session_state.pending_delete_investment_id)
                        pending_inv = session.get(Investment, pending_id)
                        if pending_inv and pending_inv.client_id == c.id:
                            st.warning("Confirm delete investment?")
                            del_col1, del_col2 = st.columns([1, 1])
                            with del_col1:
                                if st.button("Confirm delete", key=f"confirm_row_delete_{c.id}_{pending_id}", type="primary"):
                                    session.delete(pending_inv)
                                    session.commit()
                                    st.session_state.pending_delete_investment_id = None
                                    st.success("Investment deleted.")
                                    st.rerun()
                            with del_col2:
                                if st.button("Cancel", key=f"cancel_row_delete_{c.id}_{pending_id}"):
                                    st.session_state.pending_delete_investment_id = None
                                    st.rerun()
                        else:
                            st.session_state.pending_delete_investment_id = None

                    st.markdown("#### Misc")
                    with st.expander("Obligations", expanded=False):
                            obligation_edit_key = f"edit_obligation_{c.id}"
                            obligation_type_key = f"obligation_type_{c.id}"
                            has_home_insurance_saved = getattr(c, "home_insurance_expiry_date", None) is not None
                            if obligation_edit_key not in st.session_state:
                                st.session_state[obligation_edit_key] = False
                            if obligation_type_key not in st.session_state:
                                st.session_state[obligation_type_key] = "Home Insurance" if has_home_insurance_saved else "None"
                            elif st.session_state.get(obligation_type_key) not in {"None", "Home Insurance"}:
                                st.session_state[obligation_type_key] = "Home Insurance" if has_home_insurance_saved else "None"

                            if has_home_insurance_saved and not st.session_state[obligation_edit_key]:
                                st.markdown("**Obligation Type:** Home Insurance")
                                ob_c1, ob_c2, ob_c3, ob_c4 = st.columns([2, 2, 2, 2])
                                with ob_c1:
                                    st.caption("Amount Covered")
                                    st.write(f"{float(getattr(c, 'home_insurance_amount_covered', 0.0) or 0.0):,.0f}")
                                with ob_c2:
                                    st.caption("Expiry Date")
                                    st.write(iso_date_or_empty(getattr(c, "home_insurance_expiry_date", None)))
                                with ob_c3:
                                    st.caption("Insured Premium")
                                    st.write(f"{float(getattr(c, 'home_insurance_insured_premium', 0.0) or 0.0):,.0f}")
                                with ob_c4:
                                    st.caption("Actions")
                                    if st.button("✏ Edit obligation", key=f"edit_obligation_btn_{c.id}"):
                                        st.session_state[obligation_edit_key] = True
                                        st.session_state[obligation_type_key] = "Home Insurance" if has_home_insurance_saved else "None"
                                        st.rerun()
                            elif has_home_insurance_saved and st.session_state[obligation_edit_key]:
                                with st.form(f"obligations_form_{c.id}", clear_on_submit=False):
                                    obligation_type = st.selectbox(
                                        "Obligation Type",
                                        ["None", "Home Insurance"],
                                        key=obligation_type_key,
                                    )
                                    amount_covered = 0.0
                                    expiry_date = date.today()
                                    insured_premium = 0.0
                                    if obligation_type == "Home Insurance":
                                        default_expiry = getattr(c, "home_insurance_expiry_date", None) or date.today()
                                        amount_covered_default = float(getattr(c, "home_insurance_amount_covered", None) or 0.0)
                                        insured_premium_default = float(getattr(c, "home_insurance_insured_premium", None) or 0.0)
                                        hi_col1, hi_col2, hi_col3 = st.columns(3)
                                        with hi_col1:
                                            amount_covered = st.number_input(
                                                "Amount Covered",
                                                min_value=0.0,
                                                value=amount_covered_default,
                                                step=1000.0,
                                                key=f"home_insurance_amount_covered_{c.id}",
                                            )
                                        with hi_col2:
                                            expiry_date = st.date_input(
                                                "Expiry Date",
                                                value=default_expiry,
                                                key=f"home_insurance_expiry_date_{c.id}",
                                            )
                                        with hi_col3:
                                            insured_premium = st.number_input(
                                                "Insured Premium",
                                                min_value=0.0,
                                                value=insured_premium_default,
                                                step=100.0,
                                                key=f"home_insurance_insured_premium_{c.id}",
                                            )
                                    save_col, cancel_col = st.columns([1, 1])
                                    with save_col:
                                        submitted_obligations = st.form_submit_button("Save obligations")
                                    with cancel_col:
                                        cancel_obligations = st.form_submit_button("Cancel")
                                    if cancel_obligations:
                                        st.session_state[obligation_edit_key] = False
                                        st.rerun()
                                    if submitted_obligations:
                                        client_to_update = session.get(Client, c.id)
                                        if client_to_update:
                                            if obligation_type == "Home Insurance":
                                                client_to_update.home_insurance_amount_covered = float(amount_covered)
                                                client_to_update.home_insurance_expiry_date = expiry_date
                                                client_to_update.home_insurance_insured_premium = float(insured_premium)
                                                st.success("Home insurance obligations updated.")
                                            else:
                                                client_to_update.home_insurance_amount_covered = None
                                                client_to_update.home_insurance_expiry_date = None
                                                client_to_update.home_insurance_insured_premium = None
                                                st.success("Obligations cleared.")
                                            session.commit()
                                        st.session_state[obligation_edit_key] = False
                                        st.rerun()
                            else:
                                st.caption("No obligations yet.")

                    with st.expander("Cashflow", expanded=False):
                        income_edit_key = f"edit_income_target_{c.id}"
                        client_incomes = [
                            inc for inc in incomes
                            if inc.client_id == c.id and not bool(getattr(inc, "is_done", False))
                        ]
                        actual_incomes = [inc for inc in client_incomes if (getattr(inc, "income_mode", "Actual") or "Actual") == "Actual"]
                        forecast_incomes = [inc for inc in client_incomes if (getattr(inc, "income_mode", "Actual") or "Actual") == "Forecast"]
                        if actual_incomes:
                            st.markdown("**Incomes**")
                            head_c1, head_c2, head_c3, head_c4, head_c5, head_c6, head_c7 = st.columns([1.4, 1.4, 1.0, 2.6, 0.6, 0.6, 0.6])
                            head_c1.markdown("**Type**")
                            head_c2.markdown("**Amount**")
                            head_c3.markdown("**Concurrent**")
                            head_c4.markdown("**Note**")
                            for inc in actual_incomes:
                                row_c1, row_c2, row_c3, row_c4, row_c5, row_c6, row_c7 = st.columns([1.4, 1.4, 1.0, 2.6, 0.6, 0.6, 0.6])
                                row_c1.write(inc.income_type)
                                row_c2.write(f"{float(inc.amount or 0.0):,.0f}")
                                row_c3.write("Yes" if inc.concurrent else "No")
                                row_c4.write(inc.note or "—")
                                if row_c5.button("✏", key=f"edit_income_{c.id}_{inc.id}", help="Edit"):
                                    st.session_state[income_edit_key] = inc.id
                                    st.rerun()
                                if row_c6.button("✔", key=f"done_income_{c.id}_{inc.id}", help="Done"):
                                    inc_obj = session.get(Income, inc.id)
                                    if inc_obj:
                                        inc_obj.is_done = True
                                        session.commit()
                                    st.rerun()
                                if row_c7.button("✖", key=f"del_income_{c.id}_{inc.id}", type="primary"):
                                    inc_obj = session.get(Income, inc.id)
                                    if inc_obj:
                                        session.delete(inc_obj)
                                        session.commit()
                                        if st.session_state.get(income_edit_key) == inc.id:
                                            st.session_state[income_edit_key] = None
                                        st.rerun()
                        else:
                            st.caption("No incomes yet.")

                        if forecast_incomes:
                            st.markdown("**Forecast Incomes**")
                            f_head_c1, f_head_c2, f_head_c3, f_head_c4, f_head_c5, f_head_c6, f_head_c7 = st.columns([1.4, 1.4, 1.0, 2.6, 0.6, 0.6, 0.6])
                            f_head_c1.markdown("**Type**")
                            f_head_c2.markdown("**Amount**")
                            f_head_c3.markdown("**Concurrent**")
                            f_head_c4.markdown("**Note**")
                            for inc in forecast_incomes:
                                row_c1, row_c2, row_c3, row_c4, row_c5, row_c6, row_c7 = st.columns([1.4, 1.4, 1.0, 2.6, 0.6, 0.6, 0.6])
                                row_c1.write(inc.income_type)
                                row_c2.write(f"{float(inc.amount or 0.0):,.0f}")
                                row_c3.write("Yes" if inc.concurrent else "No")
                                row_c4.write(inc.note or "—")
                                if row_c5.button("✏", key=f"edit_income_{c.id}_{inc.id}", help="Edit"):
                                    st.session_state[income_edit_key] = inc.id
                                    st.rerun()
                                if row_c6.button("✔", key=f"done_income_{c.id}_{inc.id}", help="Done"):
                                    inc_obj = session.get(Income, inc.id)
                                    if inc_obj:
                                        inc_obj.is_done = True
                                        session.commit()
                                    st.rerun()
                                if row_c7.button("✖", key=f"del_income_{c.id}_{inc.id}", type="primary"):
                                    inc_obj = session.get(Income, inc.id)
                                    if inc_obj:
                                        session.delete(inc_obj)
                                        session.commit()
                                        if st.session_state.get(income_edit_key) == inc.id:
                                            st.session_state[income_edit_key] = None
                                        st.rerun()
                        else:
                            st.caption("No forecast incomes yet.")

                        selected_income_id = st.session_state.get(income_edit_key)
                        if selected_income_id is not None:
                            selected_income = session.get(Income, int(selected_income_id))
                            if selected_income and selected_income.client_id == c.id:
                                with st.form(f"edit_income_form_{c.id}_{selected_income.id}", clear_on_submit=False):
                                    st.markdown("**Edit income**")
                                    _income_type_options = ["Salary", "Dividends", "Other Incomes", "Other Obligations"]
                                    _edit_type_val = selected_income.income_type
                                    if _edit_type_val == "Others":
                                        _edit_type_val = "Other Incomes"
                                    edit_type = st.selectbox(
                                        "Income Type",
                                        _income_type_options,
                                        index=_income_type_options.index(_edit_type_val)
                                        if _edit_type_val in _income_type_options
                                        else 0,
                                        key=f"edit_income_type_{c.id}_{selected_income.id}",
                                    )
                                    edit_mode = st.selectbox(
                                        "Mode",
                                        ["Actual", "Forecast"],
                                        index=0
                                        if (getattr(selected_income, "income_mode", "Actual") or "Actual") == "Actual"
                                        else 1,
                                        key=f"edit_income_mode_{c.id}_{selected_income.id}",
                                    )
                                    ec1, ec2 = st.columns([2, 1])
                                    with ec1:
                                        edit_amount = st.number_input(
                                            "Amount",
                                            min_value=0.0,
                                            value=float(selected_income.amount or 0.0),
                                            step=1000.0,
                                            key=f"edit_income_amount_{c.id}_{selected_income.id}",
                                        )
                                    with ec2:
                                        edit_concurrent = st.checkbox(
                                            "Concurrent",
                                            value=bool(selected_income.concurrent),
                                            key=f"edit_income_concurrent_{c.id}_{selected_income.id}",
                                        )
                                    edit_note = st.text_input(
                                        "Note",
                                        value=selected_income.note or "",
                                        key=f"edit_income_note_{c.id}_{selected_income.id}",
                                    )
                                    sv_col, cx_col = st.columns([1, 1])
                                    with sv_col:
                                        save_income = st.form_submit_button("Save income")
                                    with cx_col:
                                        cancel_income = st.form_submit_button("Cancel")
                                    if cancel_income:
                                        st.session_state[income_edit_key] = None
                                        st.rerun()
                                    if save_income:
                                        selected_income.income_type = edit_type
                                        selected_income.income_mode = edit_mode
                                        selected_income.amount = float(edit_amount)
                                        selected_income.concurrent = bool(edit_concurrent)
                                        selected_income.note = edit_note.strip() or None
                                        session.commit()
                                        st.session_state[income_edit_key] = None
                                        st.success("Income updated.")
                                        st.rerun()
                            else:
                                st.session_state[income_edit_key] = None


                    st.markdown("#### Past Investments/Past Activities")
                    past_done_incomes = [
                        inc for inc in incomes
                        if inc.client_id == c.id and bool(getattr(inc, "is_done", False))
                    ]
                    if not past_invs and not past_done_incomes:
                        st.caption("No past investments or activities.")
                    else:
                        if past_invs:
                            df_past, past_order = client_portfolio_table(
                                c,
                                past_invs,
                                price_map,
                                usd_vnd_rate=fx_rate,
                                display_currency=disp_ccy,
                            )
                            closing_value = pd.to_numeric(
                                df_past.get("Current Value Display", df_past.get("Current Value")),
                                errors="coerce",
                            ).fillna(0.0)
                            principal_disp_s = pd.to_numeric(df_past.get("Principal Display"), errors="coerce").fillna(0.0)
                            realized_pnl = closing_value - principal_disp_s
                            realized_pct = realized_pnl.divide(principal_disp_s.where(principal_disp_s != 0), fill_value=0.0) * 100.0
                            df_past["Unrealized P&L"] = realized_pnl.round(0)
                            df_past["P&L %"] = realized_pct
                            past_cols = [
                                col
                                for col in df_past.columns
                                if col
                                not in {
                                    "Asset Type",
                                    "Principal Display",
                                    "Current Value Display",
                                    "Unrealized P&L Display",
                                }
                            ]
                            grouped_past: dict[str, list[tuple[Investment, Any]]] = {}
                            for i, inv in enumerate(past_order):
                                row = df_past.iloc[i]
                                grouped_past.setdefault(_past_group_label(str(row["Asset Type"])), []).append((inv, row))

                            for group_name, entries in sorted(grouped_past.items(), key=lambda x: _subgroup_sort_key(x[0])):
                                visible_past_cols = [c for c in _visible_cols_for_group(group_name) if c in past_cols]
                                with st.expander(f"{group_name} ({len(entries)})", expanded=False):
                                    past_header = st.columns([2.1] + [1.1] * len(visible_past_cols) + [1.0])
                                    past_header[0].markdown("**Asset Type**")
                                    for hi, name in enumerate(visible_past_cols):
                                        display_name = (
                                            "Closing Price"
                                            if name == "Current Price"
                                            else "Closing Value"
                                            if name == "Current Value"
                                            else "Realized P&L"
                                            if name == "Unrealized P&L"
                                            else name
                                        )
                                        past_header[hi + 1].markdown(f"**{display_name}**")
                                    past_header[-1].markdown("**Rollback**")
                                    for inv, row in entries:
                                        row_cols = st.columns([2.1] + [1.1] * len(visible_past_cols) + [1.0])
                                        row_cols[0].write(row["Asset Type"])
                                        for j, name in enumerate(visible_past_cols):
                                            row_cols[j + 1].write(_fmt_cell(name, row[name]))
                                        if row_cols[-1].button("↩ Active", key=f"rollback_inv_{c.id}_{inv.id}"):
                                            inv_to_restore = session.get(Investment, inv.id)
                                            if inv_to_restore:
                                                inv_to_restore.is_done = False
                                                session.commit()
                                                st.success("Investment moved back to active.")
                                            st.rerun()

                        if past_done_incomes:
                            with st.expander(f"Past Activities ({len(past_done_incomes)})", expanded=False):
                                pa_head = st.columns([1.4, 1.4, 1.0, 1.0, 2.4, 1.0])
                                pa_head[0].markdown("**Type**")
                                pa_head[1].markdown("**Amount**")
                                pa_head[2].markdown("**Concurrent**")
                                pa_head[3].markdown("**Mode**")
                                pa_head[4].markdown("**Note**")
                                pa_head[5].markdown("**Rollback**")
                                for inc in past_done_incomes:
                                    rc = st.columns([1.4, 1.4, 1.0, 1.0, 2.4, 1.0])
                                    rc[0].write(inc.income_type)
                                    rc[1].write(f"{float(inc.amount or 0.0):,.0f}")
                                    rc[2].write("Yes" if inc.concurrent else "No")
                                    rc[3].write(getattr(inc, "income_mode", "Actual") or "Actual")
                                    rc[4].write(inc.note or "—")
                                    if rc[5].button("↩ Active", key=f"rollback_income_{c.id}_{inc.id}"):
                                        inc_obj = session.get(Income, inc.id)
                                        if inc_obj:
                                            inc_obj.is_done = False
                                            session.commit()
                                            st.success("Activity moved back to active.")
                                        st.rerun()
                    selected_edit_id = st.session_state.get(f"edit_inv_target_{c.id}")
                    if selected_edit_id is not None:
                        inv_options = sorted(invs_all, key=lambda x: x.id)
                        if inv_options:
                            st.markdown("#### Edit investment")
                            picker_key = f"edit_inv_picker_{c.id}"
                            if st.session_state.get(picker_key) != selected_edit_id:
                                st.session_state[picker_key] = selected_edit_id
                            inv_id = st.selectbox(
                                "Select investment",
                                [inv.id for inv in inv_options],
                                format_func=lambda i: f"{session.get(Investment, i).asset_type} {session.get(Investment, i).ticker_identifier or ''} (Qty {session.get(Investment, i).quantity})",
                                key=picker_key,
                            )
                            st.session_state[f"edit_inv_target_{c.id}"] = inv_id
                            inv = session.get(Investment, inv_id)
                            with st.form(f"edit_inv_form_{c.id}_{inv_id}", clear_on_submit=False):
                                norm_type = _normalize_asset_type_name(inv.asset_type)
                                asset_type = st.selectbox(
                                    "Asset Type",
                                    ASSET_TYPES,
                                    index=ASSET_TYPES.index(norm_type) if norm_type in ASSET_TYPES else 0,
                                    key=f"edit_asset_type_{c.id}_{inv_id}",
                                )
                                asset_kind = asset_type.lower()
                                is_cd = _is_cd_kind(asset_kind)
                                is_td = asset_kind == "term deposit"
                                is_bond = asset_kind == "bond"
                                is_stock = asset_kind in {"stock", "vn_stock", "us_stock", "commodity"}
                                is_real_estate = asset_kind == "real estate"
                                is_debt = asset_kind == "debt"
                                is_cash = asset_kind == "cash"
                                currency = _default_currency_for_asset(asset_type)
                                st.caption(f"Currency: {currency} (auto by asset type)")
                                ticker_identifier = inv.ticker_identifier or ""
                                ticker_name = inv.ticker_name or ""
                                quantity = float(inv.quantity)
                                principal = float(inv.principal) if inv.principal is not None else None
                                purchase_price = float(inv.purchase_price)
                                purchase_date = None
                                tenor = None
                                interest_rate = None
                                expected_coupon = None
                                received_coupon = None
                                unit = None
                                ytm = None
                                current_price = None
                                maturity_date = None
                                principal_payment = None
                                if is_cd:
                                    principal = st.number_input(
                                        "Principal", min_value=0.0, value=float(inv.principal or 0.0), step=1000.0, key=f"edit_cd_principal_{c.id}_{inv_id}"
                                    )
                                    purchase_date = st.date_input(
                                        "Purchase Date", value=inv.purchase_date or date.today(), key=f"edit_cd_pdate_{c.id}_{inv_id}"
                                    )
                                    quantity = 1.0
                                    ticker_identifier = ""
                                    purchase_price = 0.0
                                elif is_td:
                                    principal = st.number_input(
                                        "Principal", min_value=0.0, value=float(inv.principal or 0.0), step=1000.0, key=f"edit_td_principal_{c.id}_{inv_id}"
                                    )
                                    purchase_date = st.date_input(
                                        "Buy Date", value=inv.purchase_date or date.today(), key=f"edit_td_pdate_{c.id}_{inv_id}"
                                    )
                                    tenor_default = inv.tenor if inv.tenor in TERM_TENOR_OPTIONS else TERM_TENOR_OPTIONS[0]
                                    tenor = st.selectbox("Tenor", TERM_TENOR_OPTIONS, index=TERM_TENOR_OPTIONS.index(tenor_default), key=f"edit_td_tenor_{c.id}_{inv_id}")
                                    interest_rate = st.number_input(
                                        "Interest Rate (%)",
                                        min_value=0.0,
                                        max_value=100.0,
                                        value=float(inv.interest_rate or 0.0),
                                        step=0.1,
                                        key=f"edit_td_ir_{c.id}_{inv_id}",
                                    )
                                    maturity_date = _add_months(purchase_date, int(tenor.split()[0]))
                                    st.caption(f"Maturity Date (auto): {maturity_date.isoformat()}")
                                    td_days = max((maturity_date - purchase_date).days, 0)
                                    td_interest = float(principal) * (float(interest_rate) / 100.0) / 365.0 * float(td_days)
                                    st.caption(f"Interest (auto): {currency} {td_interest:,.0f}")
                                    quantity = 1.0
                                    ticker_identifier = ""
                                    purchase_price = 0.0
                                elif is_bond:
                                    ticker_name = st.text_input(
                                        "Ticker",
                                        value=inv.ticker_name or "",
                                        key=f"edit_bond_ticker_name_{c.id}_{inv_id}",
                                    )
                                    unit = st.number_input(
                                        "Unit", min_value=0.0, value=float(inv.unit or 0.0), step=1.0, key=f"edit_bond_unit_{c.id}_{inv_id}"
                                    )
                                    purchase_date = st.date_input(
                                        "Purchase Date", value=inv.purchase_date or date.today(), key=f"edit_bond_pdate_{c.id}_{inv_id}"
                                    )
                                    principal = st.number_input(
                                        "Principal",
                                        min_value=0.0,
                                        value=float(inv.principal or 0.0),
                                        step=1000.0,
                                        key=f"edit_bond_principal_{c.id}_{inv_id}",
                                    )
                                    purchase_price = (float(principal) / float(unit)) if float(unit) > 0 else 0.0
                                    st.caption(f"Buy Price (auto) = {purchase_price:,.2f}")
                                    ytm = st.number_input(
                                        "YTM (%)",
                                        min_value=0.0,
                                        max_value=100.0,
                                        value=float(inv.ytm or 0.0),
                                        step=0.1,
                                        key=f"edit_bond_ytm_{c.id}_{inv_id}",
                                    )
                                    current_price = st.number_input(
                                        "Current Price",
                                        min_value=0.0,
                                        value=float(inv.current_price or 0.0),
                                        step=0.01,
                                        key=f"edit_bond_current_price_{c.id}_{inv_id}",
                                    )
                                    expected_coupon = st.number_input(
                                        "Expected Coupon (Amount)",
                                        min_value=0.0,
                                        value=float(inv.expected_coupon or 0.0),
                                        step=0.01,
                                        key=f"edit_coupon_{c.id}_{inv_id}",
                                    )
                                    expected_cashflow_to_maturity = float(expected_coupon) + (100_000_000.0 * float(unit or 0.0))
                                    st.caption(
                                        f"Expected Cashflow to maturity (auto) = {expected_cashflow_to_maturity:,.2f}"
                                    )
                                    received_coupon = st.number_input(
                                        "Received Coupon (Amount)",
                                        min_value=0.0,
                                        value=float(inv.received_coupon or 0.0),
                                        step=0.01,
                                        key=f"edit_received_coupon_{c.id}_{inv_id}",
                                    )
                                    maturity_date = st.date_input("Maturity Date", value=inv.maturity_date or date.today(), key=f"edit_mat_{c.id}_{inv_id}")
                                    quantity = 1.0
                                    ticker_identifier = ""
                                elif is_cash:
                                    principal = st.number_input(
                                        "Amount",
                                        min_value=0.0,
                                        value=float(inv.principal or 0.0),
                                        step=1000.0,
                                        key=f"edit_cash_amt_{c.id}_{inv_id}",
                                    )
                                    quantity = 1.0
                                    ticker_identifier = ""
                                    purchase_price = 0.0
                                    purchase_date = None
                                elif is_real_estate:
                                    ticker_name = ""
                                    ticker_identifier = st.text_input(
                                        "Property / Identifier", value=inv.ticker_identifier or "", key=f"edit_re_name_{c.id}_{inv_id}"
                                    )
                                    principal = st.number_input(
                                        "Principal",
                                        min_value=0.0,
                                        value=float(inv.principal or 0.0),
                                        step=1000.0,
                                        key=f"edit_re_principal_{c.id}_{inv_id}",
                                    )
                                    purchase_price = st.number_input(
                                        "Investment Value",
                                        min_value=0.0,
                                        value=float(inv.purchase_price or 0.0),
                                        step=1000.0,
                                        key=f"edit_re_iv_{c.id}_{inv_id}",
                                    )
                                    current_price = st.number_input(
                                        "Current Value",
                                        min_value=0.0,
                                        value=float(inv.current_price or 0.0),
                                        step=1000.0,
                                        key=f"edit_re_cv_{c.id}_{inv_id}",
                                    )
                                    quantity = 1.0
                                    unit = 1.0
                                    purchase_date = None
                                elif is_debt:
                                    ticker_name = ""
                                    ticker_identifier = st.text_input(
                                        "Debt / Identifier", value=inv.ticker_identifier or "", key=f"edit_debt_name_{c.id}_{inv_id}"
                                    )
                                    principal = st.number_input(
                                        "Outstanding Balance",
                                        min_value=0.0,
                                        value=float(inv.principal or 0.0),
                                        step=1000.0,
                                        key=f"edit_debt_balance_{c.id}_{inv_id}",
                                    )
                                    interest_rate = st.number_input(
                                        "Interest Rate (%)",
                                        min_value=0.0,
                                        max_value=100.0,
                                        value=float(inv.interest_rate or 0.0),
                                        step=0.1,
                                        key=f"edit_debt_ir_{c.id}_{inv_id}",
                                    )
                                    principal_payment = st.number_input(
                                        "Principal Payment",
                                        min_value=0.0,
                                        value=float(getattr(inv, "principal_payment", 0.0) or 0.0),
                                        step=1000.0,
                                        key=f"edit_debt_principal_payment_{c.id}_{inv_id}",
                                    )
                                    est_interest_payment = float(principal or 0.0) * (float(interest_rate or 0.0) / 100.0) / 12.0
                                    total_monthly_payment = float(principal_payment or 0.0) + float(est_interest_payment)
                                    d_calc_c1, d_calc_c2 = st.columns(2)
                                    with d_calc_c1:
                                        st.caption(f"Est Interest Payment (auto): {currency} {est_interest_payment:,.0f}")
                                    with d_calc_c2:
                                        st.caption(f"Total Monthly Payment (auto): {currency} {total_monthly_payment:,.0f}")
                                    quantity = 1.0
                                    unit = None
                                    purchase_price = 0.0
                                    purchase_date = None
                                else:
                                    ticker_name = ""
                                    ticker_identifier = st.text_input("Ticker / Identifier", value=inv.ticker_identifier or "", key=f"edit_ticker_{c.id}_{inv_id}")
                                    quantity = st.number_input(
                                        "Unit" if is_stock else "Quantity",
                                        min_value=0.0,
                                        value=float(inv.unit if is_stock and inv.unit is not None else inv.quantity),
                                        step=1.0,
                                        key=f"edit_qty_{c.id}_{inv_id}",
                                    )
                                    purchase_price = st.number_input(
                                        "Purchase Price (per unit)",
                                        min_value=0.0,
                                        value=float(inv.purchase_price),
                                        step=0.01,
                                        key=f"edit_pp_{c.id}_{inv_id}",
                                    )
                                notes = "" if (is_bond or is_td) else st.text_area("Notes", value=inv.notes or "", key=f"edit_inv_notes_{c.id}_{inv_id}")
                                save_col, cancel_col = st.columns([1, 1])
                                with save_col:
                                    save_clicked = st.form_submit_button("Save investment")
                                with cancel_col:
                                    cancel_clicked = st.form_submit_button("Cancel edit")
                                if cancel_clicked:
                                    st.session_state[f"edit_inv_target_{c.id}"] = None
                                    st.rerun()
                                if save_clicked:
                                    if float(quantity) < 0 or float(purchase_price) < 0:
                                        st.error("Quantity and purchase price must be non-negative.")
                                    else:
                                        inv.asset_type = asset_type
                                        inv.currency = currency
                                        inv.ticker_name = ticker_name.strip() or None
                                        inv.ticker_identifier = ticker_identifier.strip() or None
                                        inv.quantity = float(quantity)
                                        inv.unit = (
                                            float(unit)
                                            if is_bond
                                            else float(quantity)
                                            if is_stock
                                            else None
                                        )
                                        inv.principal = float(principal) if principal is not None else None
                                        inv.purchase_price = float(purchase_price)
                                        inv.purchase_date = purchase_date
                                        inv.tenor = tenor
                                        inv.interest_rate = float(interest_rate) if interest_rate is not None else None
                                        inv.principal_payment = (
                                            float(principal_payment) if is_debt and principal_payment is not None else None
                                        )
                                        inv.ytm = float(ytm) if is_bond else None
                                        inv.current_price = (
                                            float(current_price)
                                            if (is_bond or is_real_estate) and current_price is not None
                                            else None
                                        )
                                        inv.expected_coupon = float(expected_coupon) if is_bond and expected_coupon is not None else None
                                        inv.received_coupon = float(received_coupon) if is_bond and received_coupon is not None else None
                                        inv.maturity_date = maturity_date
                                        inv.notes = notes.strip() or None
                                        session.commit()
                                        st.success("Investment updated.")
                                        st.session_state[f"edit_inv_target_{c.id}"] = None
                                        st.rerun()

                    # Add investment
                    add_inv_open_key = f"add_inv_open_{c.id}"
                    add_inv_asset_preset_key = f"add_inv_asset_type_{c.id}"
                    asset_type_key = f"asset_type_{c.id}"
                    cashflow_types = ["Salary", "Dividends", "Other Incomes", "Other Obligations"]
                    obligation_types = ["Home Insurance"]
                    add_options = ASSET_TYPES + cashflow_types + obligation_types
                    preset_asset = st.session_state.pop(add_inv_asset_preset_key, None)
                    if preset_asset in add_options:
                        st.session_state[asset_type_key] = preset_asset
                    with st.expander("Add Investment/Debts/Cashflow", expanded=bool(st.session_state.get(add_inv_open_key, False))):
                        asset_type = st.selectbox("Asset Type", add_options, key=asset_type_key)
                        asset_kind = asset_type.lower()
                        is_cd = _is_cd_kind(asset_kind)
                        is_td = asset_kind == "term deposit"
                        is_bond = asset_kind == "bond"
                        is_stock = asset_kind in {"stock", "vn_stock", "us_stock", "commodity"}
                        is_real_estate = asset_kind == "real estate"
                        is_debt = asset_kind == "debt"
                        is_cash = asset_kind == "cash"
                        is_income = asset_type in cashflow_types
                        is_obligation = asset_type in obligation_types
                        currency = _default_currency_for_asset(asset_type)
                        if not is_income and not is_obligation:
                            st.caption(f"Currency: {currency} (auto by asset type)")
                        ticker_name = None
                        ticker_identifier = ""
                        quantity = 1.0
                        principal = None
                        purchase_price = 0.0
                        purchase_date = None
                        tenor = None
                        interest_rate = None
                        expected_coupon = None
                        received_coupon = None
                        unit = None
                        ytm = None
                        current_price = None
                        maturity_date = None
                        principal_payment = None
                        income_amount = 0.0
                        income_concurrent = False
                        income_note = ""
                        obligation_amount_covered = 0.0
                        obligation_expiry_date = date.today()
                        obligation_insured_premium = 0.0
                        if is_cd:
                            principal = st.number_input("Principal", min_value=0.0, value=0.0, step=1000.0, key=f"cd_principal_{c.id}")
                            purchase_date = st.date_input("Purchase Date", value=date.today(), key=f"cd_pdate_{c.id}")
                        elif is_td:
                            principal = st.number_input("Principal", min_value=0.0, value=0.0, step=1000.0, key=f"td_principal_{c.id}")
                            purchase_date = st.date_input("Buy Date", value=date.today(), key=f"td_pdate_{c.id}")
                            tenor = st.selectbox("Tenor", TERM_TENOR_OPTIONS, index=0, key=f"td_tenor_{c.id}")
                            interest_rate = st.number_input(
                                "Interest Rate (%)", min_value=0.0, max_value=100.0, value=0.0, step=0.1, key=f"td_ir_{c.id}"
                            )
                            tenor_months = int(tenor.split()[0])
                            maturity_date = _add_months(purchase_date, tenor_months)
                            st.caption(f"Maturity Date (auto): {maturity_date.isoformat()}")
                            td_days = max((maturity_date - purchase_date).days, 0)
                            td_interest = float(principal) * (float(interest_rate) / 100.0) / 365.0 * float(td_days)
                            st.caption(f"Interest (auto): {currency} {td_interest:,.0f}")
                        elif is_bond:
                            ticker_name = st.text_input("Ticker", key=f"bond_ticker_name_{c.id}")
                            unit = st.number_input("Unit", min_value=0.0, value=0.0, step=1.0, key=f"bond_unit_{c.id}")
                            purchase_date = st.date_input("Purchase Date", value=date.today(), key=f"pdate_{c.id}")
                            principal = st.number_input("Principal", min_value=0.0, value=0.0, step=1000.0, key=f"bond_principal_{c.id}")
                            purchase_price = (float(principal) / float(unit)) if float(unit) > 0 else 0.0
                            st.caption(f"Buy Price (auto) = {purchase_price:,.2f}")
                            ytm = st.number_input(
                                "YTM (%)",
                                min_value=0.0,
                                max_value=100.0,
                                value=0.0,
                                step=0.1,
                                key=f"bond_ytm_{c.id}",
                            )
                            current_price = st.number_input(
                                "Current Price",
                                min_value=0.0,
                                value=0.0,
                                step=0.01,
                                key=f"bond_current_price_{c.id}",
                            )
                            expected_coupon = st.number_input(
                                "Expected Coupon (Amount)",
                                min_value=0.0,
                                value=0.0,
                                step=0.01,
                                key=f"coupon_{c.id}",
                            )
                            received_coupon = st.number_input(
                                "Received Coupon (Amount)",
                                min_value=0.0,
                                value=0.0,
                                step=0.01,
                                key=f"received_coupon_{c.id}",
                            )
                            maturity_date = st.date_input("Maturity Date", value=date.today(), key=f"maturity_{c.id}")
                        elif is_cash:
                            principal = st.number_input("Amount", min_value=0.0, value=0.0, step=1000.0, key=f"cash_amt_{c.id}")
                        elif is_real_estate:
                            ticker_identifier = st.text_input("Property / Identifier", key=f"re_name_{c.id}")
                            principal = st.number_input("Principal", min_value=0.0, value=0.0, step=1000.0, key=f"re_principal_{c.id}")
                            purchase_price = st.number_input(
                                "Investment Value", min_value=0.0, value=0.0, step=1000.0, key=f"re_iv_{c.id}"
                            )
                            current_price = st.number_input(
                                "Current Value", min_value=0.0, value=0.0, step=1000.0, key=f"re_cv_{c.id}"
                            )
                            quantity = 1.0
                            unit = 1.0
                        elif is_debt:
                            ticker_identifier = st.text_input("Debt / Identifier", key=f"debt_name_{c.id}")
                            principal = st.number_input(
                                "Outstanding Balance", min_value=0.0, value=0.0, step=1000.0, key=f"debt_balance_{c.id}"
                            )
                            interest_rate = st.number_input(
                                "Interest Rate (%)", min_value=0.0, max_value=100.0, value=0.0, step=0.1, key=f"debt_ir_{c.id}"
                            )
                            principal_payment = st.number_input(
                                "Principal Payment",
                                min_value=0.0,
                                value=0.0,
                                step=1000.0,
                                key=f"debt_principal_payment_{c.id}",
                            )
                            est_interest_payment = float(principal) * (float(interest_rate) / 100.0) / 12.0
                            total_monthly_payment = float(principal_payment) + float(est_interest_payment)
                            d_calc_c1, d_calc_c2 = st.columns(2)
                            with d_calc_c1:
                                st.caption(f"Est Interest Payment (auto): {currency} {est_interest_payment:,.0f}")
                            with d_calc_c2:
                                st.caption(f"Total Monthly Payment (auto): {currency} {total_monthly_payment:,.0f}")
                            quantity = 1.0
                            purchase_price = 0.0
                        elif is_income:
                            income_mode = st.selectbox(
                                "Mode",
                                ["Actual", "Forecast"],
                                key=f"cashflow_mode_{c.id}",
                            )
                            income_amount = st.number_input(
                                "Amount",
                                min_value=0.0,
                                value=0.0,
                                step=1000.0,
                                key=f"cashflow_amount_{c.id}",
                            )
                            income_concurrent = st.checkbox(
                                "Concurrent",
                                value=False,
                                key=f"cashflow_concurrent_{c.id}",
                            )
                            income_note = st.text_input("Note", value="", key=f"cashflow_note_{c.id}")
                        elif is_obligation:
                            o1, o2, o3 = st.columns(3)
                            with o1:
                                obligation_amount_covered = st.number_input(
                                    "Amount Covered",
                                    min_value=0.0,
                                    value=0.0,
                                    step=1000.0,
                                    key=f"obligation_amount_covered_{c.id}",
                                )
                            with o2:
                                obligation_expiry_date = st.date_input(
                                    "Expiry Date",
                                    value=date.today(),
                                    key=f"obligation_expiry_date_{c.id}",
                                )
                            with o3:
                                obligation_insured_premium = st.number_input(
                                    "Insured Premium",
                                    min_value=0.0,
                                    value=0.0,
                                    step=100.0,
                                    key=f"obligation_insured_premium_{c.id}",
                                )
                        else:
                            ticker_name = None
                            ticker_identifier = st.text_input("Ticker / Identifier", key=f"ticker_{c.id}")
                            quantity = st.number_input(
                                "Unit" if is_stock else "Quantity",
                                min_value=0.0,
                                value=0.0,
                                step=1.0,
                                key=f"qty_{c.id}",
                            )
                            purchase_price = st.number_input(
                                "Purchase Price (per unit)",
                                min_value=0.0,
                                value=0.0,
                                step=0.01,
                                key=f"pp_{c.id}",
                            )
                        notes = "" if (is_bond or is_td or is_income or is_obligation) else st.text_area("Notes", key=f"inv_notes_{c.id}")

                        if st.button("Add", key=f"add_inv_btn_{c.id}"):
                            if is_income:
                                new_income = Income(
                                    client_id=c.id,
                                    income_type=asset_type,
                                    income_mode=income_mode,
                                    amount=float(income_amount),
                                    concurrent=bool(income_concurrent),
                                    note=income_note.strip() or None,
                                )
                                session.add(new_income)
                                session.commit()
                                st.session_state[add_inv_open_key] = False
                                st.success("Cashflow added.")
                                st.rerun()
                            if is_obligation:
                                client_to_update = session.get(Client, c.id)
                                if client_to_update:
                                    client_to_update.home_insurance_amount_covered = float(obligation_amount_covered)
                                    client_to_update.home_insurance_expiry_date = obligation_expiry_date
                                    client_to_update.home_insurance_insured_premium = float(obligation_insured_premium)
                                    session.commit()
                                st.session_state[add_inv_open_key] = False
                                st.success("Obligation added.")
                                st.rerun()
                            inv = Investment(
                                client_id=c.id,
                                asset_type=asset_type,
                                currency=currency,
                                ticker_name=ticker_name.strip() if isinstance(ticker_name, str) and ticker_name.strip() else None,
                                ticker_identifier=ticker_identifier.strip() or None,
                                quantity=float(quantity),
                                unit=(
                                    float(unit)
                                    if is_bond and unit is not None
                                    else float(quantity)
                                    if is_stock
                                    else None
                                ),
                                principal=float(principal) if principal is not None else None,
                                purchase_price=float(purchase_price),
                                purchase_date=purchase_date,
                                tenor=tenor,
                                interest_rate=float(interest_rate) if interest_rate is not None else None,
                                principal_payment=float(principal_payment) if is_debt and principal_payment is not None else None,
                                ytm=float(ytm) if is_bond and ytm is not None else None,
                                current_price=float(current_price)
                                if (is_bond or is_real_estate) and current_price is not None
                                else None,
                                expected_coupon=float(expected_coupon) if is_bond and expected_coupon is not None else None,
                                received_coupon=float(received_coupon) if is_bond and received_coupon is not None else None,
                                maturity_date=maturity_date,
                                notes=notes.strip() or None,
                            )
                            session.add(inv)
                            session.commit()
                            st.session_state[add_inv_open_key] = False
                            st.success("Investment added.")
                            st.rerun()

    elif tab == "Reminders":
        st.subheader("Reminder Center")
        today = date.today()
        year_end = date(today.year, 12, 31)

        st.markdown(
            """
<style>
.rem-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 8px;
  margin: 4px 0 10px 0;
}
.rem-card {
  border: 1px solid rgba(128,128,128,0.25);
  border-radius: 10px;
  padding: 8px 10px;
  background: rgba(148,163,184,0.08);
}
.rem-card-title {
  font-size: 0.72rem;
  opacity: 0.8;
  margin-bottom: 2px;
}
.rem-card-value {
  font-size: 1.05rem;
  font-weight: 700;
}
</style>
""",
            unsafe_allow_html=True,
        )

        with get_session(DB_URL) as session:
            clients = session.execute(select(Client)).scalars().all()
            investments = session.execute(select(Investment).options(selectinload(Investment.client))).scalars().all()
            auto_existing_rows = session.execute(
                select(Reminder).where(
                    Reminder.reminder_type.in_(["birthday", "maturity", "home_insurance"]),
                    Reminder.reminder_date <= year_end,
                )
            ).scalars().all()
            auto_existing_map: dict[tuple[str, int | None, int | None, date], Reminder] = {}
            for rr in auto_existing_rows:
                k = (rr.reminder_type, rr.client_id, rr.investment_id, rr.reminder_date)
                auto_existing_map[k] = rr

            def _status_bucket(due_date: date, sent_at: datetime | None) -> str:
                if sent_at is not None:
                    return "Completed"
                if due_date < today:
                    return "Overdue"
                if due_date == today:
                    return "On Due Date"
                if due_date.year == today.year and due_date.month == today.month:
                    return "In This Month"
                return "In This Year"

            reminder_rows: list[dict[str, Any]] = []

            # Obligations (computed)
            for c in clients:
                expiry_date = getattr(c, "home_insurance_expiry_date", None)
                if not expiry_date:
                    continue
                due_date = expiry_date - timedelta(days=1)
                if due_date > year_end:
                    continue
                existing_row = auto_existing_map.get(("home_insurance", c.id, None, due_date))
                sent_flag = existing_row.sent_at is not None if existing_row else False
                reminder_rows.append(
                    {
                        "Group": _status_bucket(due_date, existing_row.sent_at if existing_row else None),
                        "Type": "Obligation",
                        "Topic": "Home Insurance",
                        "Client": c.name,
                        "Due Date": due_date.isoformat(),
                        "Event Date": expiry_date.isoformat(),
                        "Title": "Home insurance expiry reminder",
                        "Amount Covered": f"{float(getattr(c, 'home_insurance_amount_covered', 0.0) or 0.0):,.0f}",
                        "Insured Premium": f"{float(getattr(c, 'home_insurance_insured_premium', 0.0) or 0.0):,.0f}",
                        "Notes": "",
                        "Sent": "Yes" if sent_flag else "No",
                        "Reminder ID": existing_row.id if existing_row else None,
                        "Reminder Type": "home_insurance",
                        "Client ID": c.id,
                        "Investment ID": None,
                    }
                )

            # Birthdays (computed)
            for c in clients:
                if not c.birthday:
                    continue
                bday_next = next_birthday_date(c.birthday, today)
                due_date = bday_next - timedelta(days=1)
                if due_date > year_end:
                    continue
                existing_row = auto_existing_map.get(("birthday", c.id, None, due_date))
                sent_flag = existing_row.sent_at is not None if existing_row else False
                reminder_rows.append(
                    {
                        "Group": _status_bucket(due_date, existing_row.sent_at if existing_row else None),
                        "Type": "Birthday",
                        "Topic": "Birthday",
                        "Client": c.name,
                        "Due Date": due_date.isoformat(),
                        "Event Date": bday_next.isoformat(),
                        "Title": f"Birthday reminder: {c.name}",
                        "Amount Covered": "",
                        "Insured Premium": "",
                        "Notes": "",
                        "Sent": "Yes" if sent_flag else "No",
                        "Reminder ID": existing_row.id if existing_row else None,
                        "Reminder Type": "birthday",
                        "Client ID": c.id,
                        "Investment ID": None,
                    }
                )

            # Maturities (computed)
            for inv in investments:
                if not inv.maturity_date:
                    continue
                due_date = inv.maturity_date - timedelta(days=1)
                if due_date > year_end:
                    continue
                existing_row = auto_existing_map.get(("maturity", inv.client_id, inv.id, due_date))
                sent_flag = existing_row.sent_at is not None if existing_row else False
                reminder_rows.append(
                    {
                        "Group": _status_bucket(due_date, existing_row.sent_at if existing_row else None),
                        "Type": "Maturity",
                        "Topic": (inv.asset_type or "").strip() or "Investment",
                        "Client": inv.client.name,
                        "Due Date": due_date.isoformat(),
                        "Event Date": inv.maturity_date.isoformat(),
                        "Title": f"Maturity reminder: {inv.client.name}",
                        "Amount Covered": "",
                        "Insured Premium": "",
                        "Notes": "",
                        "Sent": "Yes" if sent_flag else "No",
                        "Reminder ID": existing_row.id if existing_row else None,
                        "Reminder Type": "maturity",
                        "Client ID": inv.client_id,
                        "Investment ID": inv.id,
                    }
                )

            # Manual reminders (persisted)
            manual_rows = session.execute(
                select(Reminder).where(
                    Reminder.reminder_type == "manual",
                    Reminder.reminder_date <= year_end,
                )
                .order_by(Reminder.reminder_date.asc(), Reminder.created_at.asc())
            ).scalars().all()
            for r in manual_rows:
                reminder_rows.append(
                    {
                        "Group": _status_bucket(r.reminder_date, r.sent_at),
                        "Type": "Manual",
                        "Topic": "Manual",
                        "Title": r.title,
                        "Client": session.get(Client, r.client_id).name if r.client_id else "",
                        "Due Date": r.reminder_date.isoformat(),
                        "Event Date": "",
                        "Amount Covered": "",
                        "Insured Premium": "",
                        "Notes": r.notes or "",
                        "Sent": "Yes" if r.sent_at else "No",
                        "Reminder ID": r.id,
                        "Reminder Type": "manual",
                        "Client ID": r.client_id,
                        "Investment ID": r.investment_id,
                    }
                )

            groups = ["On Due Date", "In This Month", "In This Year", "Overdue", "Completed"]
            counts = {g: len([r for r in reminder_rows if r["Group"] == g]) for g in groups}
            counts_html = "".join(
                f"<div class='rem-card'><div class='rem-card-title'>{g}</div><div class='rem-card-value'>{counts[g]}</div></div>"
                for g in groups
            )
            st.markdown(f"<div class='rem-grid'>{counts_html}</div>", unsafe_allow_html=True)

            display_cols = [
                "Done",
                "Type",
                "Topic",
                "Title",
                "Client",
                "Due Date",
                "Event Date",
                "Amount Covered",
                "Insured Premium",
                "Notes",
            ]
            for g in groups:
                g_rows = [r for r in reminder_rows if r["Group"] == g]
                with st.expander(f"{g} ({len(g_rows)})", expanded=(g == "On Due Date")):
                    if not g_rows:
                        st.caption("No reminders.")
                    else:
                        table_rows: list[dict[str, Any]] = []
                        for r in g_rows:
                            table_rows.append(
                                {
                                    "Done": str(r.get("Sent", "No")) == "Yes",
                                    "Type": r.get("Type", ""),
                                    "Topic": r.get("Topic", ""),
                                    "Title": r.get("Title", ""),
                                    "Client": r.get("Client", ""),
                                    "Due Date": r.get("Due Date", ""),
                                    "Event Date": r.get("Event Date", ""),
                                    "Amount Covered": r.get("Amount Covered", ""),
                                    "Insured Premium": r.get("Insured Premium", ""),
                                    "Notes": r.get("Notes", ""),
                                }
                            )
                        df_g = pd.DataFrame(table_rows)[display_cols]
                        edited_df = st.data_editor(
                            df_g,
                            key=f"rem_table_{g}",
                            hide_index=True,
                            width="stretch",
                            disabled=[c for c in display_cols if c != "Done"],
                            column_config={"Done": st.column_config.CheckboxColumn("Done")},
                        )
                        changed = False
                        for i, r in enumerate(g_rows):
                            before_done = str(r.get("Sent", "No")) == "Yes"
                            after_done = bool(edited_df.iloc[i]["Done"])
                            if before_done == after_done:
                                continue
                            rid = r.get("Reminder ID")
                            row_obj = session.get(Reminder, int(rid)) if rid else None
                            if row_obj is None:
                                row_obj = Reminder(
                                    title=str(r.get("Title", "") or ""),
                                    client_id=r.get("Client ID"),
                                    investment_id=r.get("Investment ID"),
                                    reminder_date=date.fromisoformat(str(r.get("Due Date"))),
                                    reminder_type=str(r.get("Reminder Type", "manual")),
                                    notes=(str(r.get("Notes", "") or "").strip() or None),
                                )
                                session.add(row_obj)
                            row_obj.sent_at = datetime.utcnow() if after_done else None
                            changed = True
                        if changed:
                            session.commit()
                            st.rerun()

            st.subheader("Send Telegram Notifications (due today)")
            st.caption("Notifications are sent only when a pending reminder is due today (Streamlit action).")
            st.caption("Configure Telegram in the Settings tab.")

            if st.button("Send due notifications now"):
                result = _send_due_telegram_notifications(session)
                if result.get("error"):
                    st.error(result["error"])
                else:
                    st.success(f"Sent {result.get('sent', 0)} notification(s).")

            st.divider()
            st.subheader("Add / Edit / Delete Manual Reminders")

            manual_list = session.execute(
                select(Reminder)
                .where(Reminder.reminder_type == "manual")
                .order_by(Reminder.reminder_date.desc(), Reminder.created_at.desc())
            ).scalars().all()
            manual_ids = [r.id for r in manual_list]

            with st.expander("Add manual reminder", expanded=False):
                with st.form("add_manual_reminder_form", clear_on_submit=True):
                    title = st.text_input("Title", max_chars=250)
                    client_id = st.selectbox(
                        "Client (optional)",
                        options=[None] + [c.id for c in clients],
                        format_func=lambda i: "None" if i is None else session.get(Client, i).name,
                    )
                    reminder_date = st.date_input("Reminder Date", value=today)
                    notes = st.text_area("Notes")
                    submitted = st.form_submit_button("Add reminder")
                    if submitted:
                        if not title.strip():
                            st.error("Title is required.")
                        else:
                            r = Reminder(
                                title=title.strip(),
                                client_id=client_id,
                                investment_id=None,
                                reminder_date=reminder_date,
                                reminder_type="manual",
                                notes=notes.strip() or None,
                            )
                            session.add(r)
                            session.commit()
                            st.success("Manual reminder added.")
                            st.rerun()

            with st.expander("Edit manual reminder", expanded=False):
                if not manual_ids:
                    st.info("No manual reminders to edit.")
                else:
                    rid = st.selectbox("Select reminder", manual_ids, format_func=lambda i: session.get(Reminder, i).title)
                    r = session.get(Reminder, rid)
                    with st.form("edit_manual_reminder_form", clear_on_submit=False):
                        title = st.text_input("Title", value=r.title)
                        client_options = [None] + [c.id for c in clients]
                        client_index = 0 if r.client_id is None else client_options.index(r.client_id)
                        client_id = st.selectbox(
                            "Client (optional)",
                            options=client_options,
                            index=client_index,
                            format_func=lambda i: "None" if i is None else session.get(Client, i).name,
                        )
                        reminder_date = st.date_input("Reminder Date", value=r.reminder_date)
                        notes = st.text_area("Notes", value=r.notes or "")
                        submitted = st.form_submit_button("Save changes")
                        if submitted:
                            clean_title = title.strip()
                            if not clean_title:
                                st.error("Title is required.")
                            else:
                                r.title = clean_title
                                r.client_id = client_id
                                r.reminder_date = reminder_date
                                r.notes = notes.strip() or None
                                session.commit()
                                st.success("Manual reminder updated.")
                                st.rerun()

            with st.expander("Delete manual reminder", expanded=False):
                if not manual_ids:
                    st.info("No manual reminders to delete.")
                else:
                    rid = st.selectbox("Select reminder to delete", manual_ids, format_func=lambda i: session.get(Reminder, i).title)
                    if st.button("Delete selected manual reminder"):
                        r = session.get(Reminder, rid)
                        if r:
                            session.delete(r)
                            session.commit()
                            st.success("Manual reminder deleted.")
                            st.rerun()

    elif tab == "Market News":
        st.subheader("Market News")
        default_kw = st.sidebar.text_input("Keywords (comma separated)", value="crypto, economics, inflation")
        per_keyword = st.sidebar.number_input("Results per keyword per feed", min_value=1, max_value=20, value=5, step=1)

        with get_session(DB_URL) as session:
            kw_text = default_kw
            k_hash = keywords_hash(kw_text)
            cached = get_cached_news(session, kw_text)
            st.caption(f"Cached items for these keywords: {len(cached)}")

            keywords_list = [k.strip() for k in kw_text.split(",") if k.strip()]
            if not keywords_list:
                st.warning("Enter at least one keyword.")
                return

            # If there's nothing cached, the user needs to refresh.
            if not cached:
                st.info("No cached results yet. Use the refresh button at the bottom of this page.")

            # Show last fetched timestamp (rendered at the bottom under refresh).
            row = session.execute(select(NewsCache).where(NewsCache.keywords_hash == k_hash)).scalar_one_or_none()

            if cached:
                rows: list[dict[str, Any]] = []
                tag_stopwords = {
                    "the",
                    "and",
                    "for",
                    "with",
                    "from",
                    "this",
                    "that",
                    "are",
                    "was",
                    "were",
                    "will",
                    "its",
                    "now",
                    "since",
                }

                def _core_x_tags(text: str) -> list[str]:
                    s = (text or "").lower()
                    tags: list[str] = []

                    def add(tag: str) -> None:
                        if tag not in tags:
                            tags.append(tag)

                    if any(k in s for k in ["inflation", "cpi", "ppi", "pce", "price pressure", "deflation"]):
                        add("inflation")
                    if any(k in s for k in ["economy", "economic", "gdp", "recession", "pmi", "jobs", "employment", "growth"]):
                        add("economics")
                    if any(k in s for k in ["fed", "fomc", "rate cut", "rate hike", "interest rate", "hawkish", "dovish"]):
                        add("monetary-policy")
                    if any(k in s for k in ["yield", "treasury", "bond", "credit spread"]):
                        add("fixed-income")
                    if any(k in s for k in ["s&p", "sp500", "nasdaq", "dow", "equity", "stock", "shares"]):
                        add("equities")
                    if any(k in s for k in ["oil", "crude", "gold", "xau", "silver", "commodity", "natural gas"]):
                        add("commodities")
                    if any(k in s for k in ["bitcoin", "btc", "ethereum", "eth", "crypto", "altcoin"]):
                        add("crypto")
                    if any(k in s for k in ["dollar", "usd", "eur", "jpy", "fx", "forex", "currency"]):
                        add("fx")
                    if any(k in s for k in ["bank", "liquidity", "deposit", "credit", "default"]):
                        add("banking")
                    if any(k in s for k in ["earnings", "eps", "guidance", "revenue", "profit"]):
                        add("earnings")
                    if any(k in s for k in ["war", "sanction", "tariff", "geopolitical", "middle east", "china", "russia"]):
                        add("geopolitics")
                    return tags or ["markets"]

                for item in cached:
                    headline = str(item.get("headline", "") or "")
                    link = str(item.get("link", "") or "")
                    date_s = str(item.get("date", "") or "")
                    source_s = str(item.get("source", "") or "")
                    raw_tags = item.get("tags", [])
                    if isinstance(raw_tags, list):
                        tags = [str(t).strip().lower() for t in raw_tags if str(t).strip()]
                    else:
                        tags = []
                    # Remove historical source-derived tags from older cached data.
                    source_like = {"google-news", "yahoo-finance", "x", "kobeissiletter", "citrini"}
                    tags = [t for t in tags if t not in source_like]
                    if source_s.strip().lower().startswith("x @"):
                        # Enforce core topic tags for X instead of literal headline token tags.
                        tags = _core_x_tags(headline)
                    if not tags and headline:
                        toks = re.findall(r"[a-z0-9]{3,}", headline.lower())
                        tags = []
                        seen_tags: set[str] = set()
                        for tok in toks:
                            if tok in tag_stopwords or tok in seen_tags:
                                continue
                            seen_tags.add(tok)
                            tags.append(tok)
                            if len(tags) >= 4:
                                break
                    rows.append(
                        {
                            "headline": headline,
                            "date": date_s,
                            "link": link,
                            "tags": sorted(set(tags)),
                            "_batch_ts": str(item.get("_batch_ts", "") or ""),
                            "source": source_s,
                        }
                    )

                all_tags = sorted({t for r in rows for t in r["tags"]})
                selected_tags = st.multiselect(
                    "Filter by tags",
                    options=all_tags,
                    default=[],
                    help="Show only items containing all selected tags.",
                )

                filtered_rows = rows
                if selected_tags:
                    sel = set(selected_tags)
                    filtered_rows = [r for r in rows if sel.issubset(set(r["tags"]))]

                def _sort_key(r: dict[str, Any]) -> str:
                    return str(r.get("date", "") or "")

                sorted_rows = sorted(filtered_rows, key=_sort_key, reverse=True)
                x_rows_all = [
                    r
                    for r in sorted_rows
                    if str(r.get("source", "")).strip().lower().startswith("x @")
                ]
                traditional_rows_all = [r for r in sorted_rows if r not in x_rows_all]

                with st.expander("Sentiment Analysis", expanded=False):
                    if not sorted_rows:
                        st.caption("No headlines available for sentiment analysis.")
                    else:
                        positive_terms = {
                            "gain",
                            "gains",
                            "rally",
                            "surge",
                            "beat",
                            "beats",
                            "bull",
                            "bullish",
                            "growth",
                            "recover",
                            "recovery",
                            "up",
                            "rise",
                            "rises",
                            "strong",
                            "optimism",
                            "record",
                        }
                        negative_terms = {
                            "drop",
                            "drops",
                            "fall",
                            "falls",
                            "selloff",
                            "bear",
                            "bearish",
                            "miss",
                            "misses",
                            "recession",
                            "risk",
                            "risks",
                            "crash",
                            "decline",
                            "declines",
                            "weak",
                            "fear",
                            "inflation",
                        }

                        def _headline_sentiment_score(text: str) -> int:
                            tokens = re.findall(r"[a-z0-9]+", (text or "").lower())
                            pos = sum(1 for t in tokens if t in positive_terms)
                            neg = sum(1 for t in tokens if t in negative_terms)
                            return pos - neg

                        row_scores: list[int] = []
                        source_stats: dict[str, dict[str, int]] = {}
                        tag_scores: dict[str, int] = {}
                        for r in sorted_rows:
                            score = _headline_sentiment_score(str(r.get("headline", "") or ""))
                            row_scores.append(score)
                            source_name = str(r.get("source", "") or "Unknown")
                            if source_name not in source_stats:
                                source_stats[source_name] = {"count": 0, "sum": 0}
                            source_stats[source_name]["count"] += 1
                            source_stats[source_name]["sum"] += score
                            for tag in r.get("tags", []):
                                t = str(tag).strip().lower()
                                if not t:
                                    continue
                                tag_scores[t] = tag_scores.get(t, 0) + score

                        total_items = len(row_scores)
                        avg_score = (sum(row_scores) / total_items) if total_items else 0.0
                        if avg_score > 0.1:
                            sentiment_label = "Bullish"
                        elif avg_score < -0.1:
                            sentiment_label = "Bearish"
                        else:
                            sentiment_label = "Neutral"

                        bull_ratio = (sum(1 for s in row_scores if s > 0) / total_items * 100.0) if total_items else 0.0
                        bear_ratio = (sum(1 for s in row_scores if s < 0) / total_items * 100.0) if total_items else 0.0

                        m1, m2, m3, m4 = st.columns(4)
                        m1.metric("Overall", sentiment_label)
                        m2.metric("Avg Score", f"{avg_score:+.2f}")
                        m3.metric("Bullish Headlines", f"{bull_ratio:.0f}%")
                        m4.metric("Bearish Headlines", f"{bear_ratio:.0f}%")

                        src_rows: list[dict[str, Any]] = []
                        for src, stt in source_stats.items():
                            count = stt["count"]
                            avg = (stt["sum"] / count) if count else 0.0
                            src_rows.append({"Source": src, "Headlines": count, "Avg Score": round(avg, 2)})
                        src_rows = sorted(src_rows, key=lambda x: (x["Avg Score"], x["Headlines"]), reverse=True)
                        if src_rows:
                            st.caption("By source")
                            st.dataframe(pd.DataFrame(src_rows), width="stretch", hide_index=True)

                        if tag_scores:
                            top_pos = sorted(tag_scores.items(), key=lambda x: x[1], reverse=True)[:5]
                            top_neg = sorted(tag_scores.items(), key=lambda x: x[1])[:5]
                            cpos, cneg = st.columns(2)
                            with cpos:
                                st.caption("Top positive tags")
                                st.write(", ".join(f"{k} ({v:+d})" for k, v in top_pos) if top_pos else "—")
                            with cneg:
                                st.caption("Top negative tags")
                                st.write(", ".join(f"{k} ({v:+d})" for k, v in top_neg) if top_neg else "—")

                # Global clear-archive by Date field:
                # keep rows from the latest date (and undated rows), remove older dated rows.
                valid_dates_all = [str(r.get("date", "") or "") for r in rows if str(r.get("date", "") or "")]
                latest_date_all = max(valid_dates_all) if valid_dates_all else ""
                if st.button("Clear Archive", key="clear_news_archive_btn"):
                    if not latest_date_all:
                        st.warning("No dated headlines found. Archive was not changed.")
                    else:
                        kept = [
                            item
                            for item in cached
                            if (str(item.get("date", "") or "") == latest_date_all)
                            or (not str(item.get("date", "") or ""))
                        ]
                        upsert_cached_news(session, kw_text, kept)
                        session.commit()
                        st.success(f"Archive cleared. Kept {len(kept)} latest headline(s).")
                        st.rerun()

                with st.expander("Vietnam Market Outlook (Techcombank Monthly)", expanded=False):
                    st.caption("[Techcombank periodic research page](https://techcombank.com/thong-tin/nghien-cuu/bao-cao-dinh-ky)")
                    tc_reports = cached_techcom_reports(limit=8)
                    if tc_reports:
                        tc_rows_html = []
                        for r in tc_reports:
                            period = str(r.get("period", "") or "")
                            url = str(r.get("url", "") or "")
                            safe_period = period.replace("<", "&lt;").replace(">", "&gt;")
                            safe_url = url.replace('"', "&quot;")
                            tc_rows_html.append(
                                f"<tr><td>{safe_period}</td>"
                                f"<td><a href=\"{safe_url}\" target=\"_blank\">Monthly Report {safe_period}</a></td></tr>"
                            )
                        st.markdown(
                            """
<table style="width:100%; border-collapse: collapse;">
  <thead>
    <tr>
      <th style="text-align:left; padding:6px 8px;">Period</th>
      <th style="text-align:left; padding:6px 8px;">Report</th>
    </tr>
  </thead>
  <tbody>
"""
                            + "".join(tc_rows_html)
                            + """
  </tbody>
</table>
""",
                            unsafe_allow_html=True,
                        )
                    else:
                        st.info("No Techcombank monthly reports detected yet.")

                def _render_news_group(title: str, rows_group: list[dict[str, Any]], empty_text: str) -> None:
                    # Archive split by Date field: older dates go to archive.
                    valid_dates = [str(r.get("date", "") or "") for r in rows_group if str(r.get("date", "") or "")]
                    latest_date = max(valid_dates) if valid_dates else ""
                    if latest_date:
                        latest_rows = [r for r in rows_group if str(r.get("date", "") or "") == latest_date]
                        # Undated rows are treated as latest to avoid accidental archival of incomplete feeds.
                        latest_rows.extend([r for r in rows_group if not str(r.get("date", "") or "")])
                        # de-dup while preserving order
                        seen_links: set[str] = set()
                        dedup_latest: list[dict[str, Any]] = []
                        for r in latest_rows:
                            lk = str(r.get("link", "") or "")
                            if lk and lk in seen_links:
                                continue
                            if lk:
                                seen_links.add(lk)
                            dedup_latest.append(r)
                        latest_rows = dedup_latest
                        archive_rows = [
                            r for r in rows_group if str(r.get("date", "") or "") and str(r.get("date", "") or "") < latest_date
                        ]
                    else:
                        latest_rows = rows_group[:80]
                        archive_rows = rows_group[80:]
                    st.markdown(f"### {title}")
                    if not latest_rows:
                        st.caption(empty_text)
                    else:
                        latest_table_rows = []
                        for r in latest_rows:
                            tag_text = ", ".join(r["tags"]) if r["tags"] else "none"
                            headline = str(r["headline"] or "").replace("<", "&lt;").replace(">", "&gt;")
                            link = str(r["link"] or "")
                            latest_table_rows.append(
                                {
                                    "Headline": f'<a href="{link}" target="_blank">{headline}</a>' if link else headline,
                                    "Tags": tag_text,
                                    "Date": r["date"] or "—",
                                }
                            )
                        latest_df = pd.DataFrame(latest_table_rows, columns=["Headline", "Tags", "Date"])
                        st.markdown(latest_df.to_html(escape=False, index=False), unsafe_allow_html=True)

                    with st.expander(f"{title} Archive ({len(archive_rows)})", expanded=False):
                        if not archive_rows:
                            st.caption("No archived headlines.")
                        else:
                            archive_table_rows = []
                            for r in archive_rows[:400]:
                                tag_text = ", ".join(r["tags"]) if r["tags"] else "none"
                                headline = str(r["headline"] or "").replace("<", "&lt;").replace(">", "&gt;")
                                link = str(r["link"] or "")
                                archive_table_rows.append(
                                    {
                                        "Headline": f'<a href="{link}" target="_blank">{headline}</a>' if link else headline,
                                        "Tags": tag_text,
                                        "Date": r["date"] or "—",
                                    }
                                )
                            archive_df = pd.DataFrame(archive_table_rows, columns=["Headline", "Tags", "Date"])
                            st.markdown(archive_df.to_html(escape=False, index=False), unsafe_allow_html=True)

                with st.expander(f"Traditional Sources ({len(traditional_rows_all)})", expanded=False):
                    _render_news_group(
                        "Traditional Sources",
                        traditional_rows_all,
                        "No traditional-source headlines for selected tags.",
                    )

                with st.expander(f"X ({len(x_rows_all)})", expanded=False):
                    st.caption("X Profiles: [@KobeissiLetter](https://x.com/KobeissiLetter) · [@citrini](https://x.com/citrini)")
                    _render_news_group(
                        "X",
                        x_rows_all,
                        "No X headlines for selected tags. Try Refresh (scrape live).",
                    )

            st.markdown("---")
            fg = fetch_fear_greed_index()
            fg_val_raw = fg.get("value")
            fg_label = str(fg.get("classification") or "N/A")
            fg_prev_raw = fg.get("last_week_value")
            lw_label = fg.get("last_week_classification") or "N/A"
            fg_now: int | None = None
            fg_prev: int | None = None
            try:
                if fg_val_raw is not None:
                    fg_now = int(float(str(fg_val_raw)))
            except Exception:
                fg_now = None
            try:
                if fg_prev_raw is not None:
                    fg_prev = int(float(str(fg_prev_raw)))
            except Exception:
                fg_prev = None

            delta_num: int | None = None
            if fg_now is not None and fg_prev is not None:
                try:
                    delta_num = fg_now - fg_prev
                except Exception:
                    delta_num = None
            delta_txt = f"{delta_num:+d}" if delta_num is not None else "N/A"

            # Compact card-style UI for readability on both light/dark themes.
            def _fg_theme(v: int | None) -> tuple[str, str]:
                if v is None:
                    return ("N/A", "#64748b")
                if v < 25:
                    return ("Extreme Fear", "#ef4444")
                if v < 45:
                    return ("Fear", "#f97316")
                if v < 55:
                    return ("Neutral", "#f59e0b")
                if v < 75:
                    return ("Greed", "#22c55e")
                return ("Extreme Greed", "#16a34a")

            inferred_label, band_color = _fg_theme(fg_now)
            display_label = fg_label if fg_label and fg_label != "N/A" else inferred_label
            delta_color = "#22c55e" if (delta_num is not None and delta_num > 0) else "#ef4444" if (delta_num is not None and delta_num < 0) else "#94a3b8"
            gauge_pct = max(0, min(100, fg_now if fg_now is not None else 0))
            src = str(fg.get("source", "N/A")).replace("<", "&lt;").replace(">", "&gt;")
            fg_url = str(fg.get("url", "https://www.binance.com/en/square/fear-and-greed-index")).replace('"', "&quot;")

            st.markdown(
                f"""
<style>
.fg-card {{
  border: 1px solid rgba(128,128,128,0.25);
  border-radius: 10px;
  padding: 10px 12px;
  margin: 4px 0 8px 0;
}}
.fg-row {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}}
.fg-stats {{
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
  margin-top: 6px;
  font-size: 0.92rem;
}}
.fg-chip {{
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid rgba(128,128,128,0.35);
}}
.fg-gauge {{
  width: 100%;
  height: 6px;
  background: rgba(128,128,128,0.2);
  border-radius: 999px;
  overflow: hidden;
  margin-top: 8px;
}}
.fg-fill {{
  height: 6px;
  width: {gauge_pct}%;
  background: {band_color};
}}
</style>
<div class="fg-card">
  <div class="fg-row">
    <div><strong>Bitcoin Fear &amp; Greed</strong></div>
    <div style="font-size:0.82rem; opacity:0.8;">Source: {src} · <a href="{fg_url}" target="_blank">Binance Fear &amp; Greed page</a></div>
  </div>
  <div class="fg-stats">
    <span><strong>Now:</strong> {fg_now if fg_now is not None else "N/A"}</span>
    <span><strong>Class:</strong> <span class="fg-chip">{display_label}</span></span>
    <span><strong>Last week:</strong> {fg_prev if fg_prev is not None else "N/A"} ({lw_label})</span>
    <span><strong>Delta:</strong> <span style="color:{delta_color};">{delta_txt}</span></span>
  </div>
  <div class="fg-gauge"><div class="fg-fill"></div></div>
</div>
""",
                unsafe_allow_html=True,
            )

            if st.button("Refresh (scrape live)", key="refresh_news_btn"):
                with st.spinner("Scraping news..."):
                    results = scrape_news(keywords_list, per_keyword_per_source=int(per_keyword))
                    batch_ts = datetime.utcnow().isoformat(timespec="seconds")
                    tagged_results: list[dict[str, Any]] = []
                    for item in results:
                        it = dict(item)
                        it["_batch_ts"] = batch_ts
                        tagged_results.append(it)

                    # Merge with existing cache so older headlines move to archive.
                    merged_by_link: dict[str, dict[str, Any]] = {}
                    for item in cached:
                        link = str(item.get("link", "") or "").strip()
                        if not link:
                            continue
                        merged_by_link[link] = dict(item)
                    for item in tagged_results:
                        link = str(item.get("link", "") or "").strip()
                        if not link:
                            continue
                        # New scrape overrides previous copy of same link.
                        merged_by_link[link] = dict(item)

                    merged_results = list(merged_by_link.values())
                    upsert_cached_news(session, kw_text, merged_results)
                    session.commit()
                st.success(f"Scraped {len(results)} items. Total cached: {len(merged_results)}.")
                st.rerun()
            if row:
                st.caption(f"Last fetched: {row.fetched_at.strftime('%Y-%m-%d %H:%M:%S')} UTC")

    elif tab == "Settings":
        st.subheader("Settings")

        st.markdown("### FX")
        st.caption("Saved rates persist in `crm_settings.json` next to the app. The portfolio uses this rate for USD/VND conversion.")
        st.number_input(
            "Current USD/VND exchange rate (VND per 1 USD)",
            min_value=1000.0,
            max_value=100000.0,
            step=10.0,
            key="settings_fx_rate_input",
            help="Used for portfolio USD/VND display and VND conversion of USD-priced instruments.",
        )
        if st.button("Save exchange rate", key="save_fx_rate_btn"):
            rate_saved = float(st.session_state.settings_fx_rate_input)
            st.session_state.usd_vnd_rate = rate_saved
            save_usd_vnd_rate(rate_saved)
            st.success(f"Saved: 1 USD = {rate_saved:,.0f} VND")

        st.markdown("### Telegram")
        st.write("You can configure Telegram here (stored in this browser session), or via environment variables.")

        with st.form("telegram_settings_form", clear_on_submit=False):
            st.text_input("TELEGRAM_BOT_TOKEN", key="telegram_bot_token", type="password")
            st.text_input("TELEGRAM_CHAT_ID", key="telegram_chat_id")
            save = st.form_submit_button("Save")
            if save:
                st.success("Saved Telegram settings for this session.")

        st.markdown("#### Environment variables (alternative)")
        st.code("export TELEGRAM_BOT_TOKEN='your_bot_token'", language="bash")
        st.code("export TELEGRAM_CHAT_ID='your_chat_id'", language="bash")

        env_cfg = load_telegram_config_from_env()
        session_cfg = None
        token = (st.session_state.get('telegram_bot_token') or '').strip()
        chat_id = (st.session_state.get('telegram_chat_id') or '').strip()
        if token and chat_id:
            session_cfg = TelegramConfig(token=token, chat_id=chat_id)

        st.markdown("#### Status")
        if session_cfg:
            st.success("Telegram configured from Settings (session).")
        elif env_cfg:
            st.success("Telegram configured from environment variables.")
        else:
            st.warning("Telegram not configured yet.")


if __name__ == "__main__":
    main()


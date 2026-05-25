from __future__ import annotations

import hashlib
import calendar
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Iterable

import pandas as pd

try:
    import yfinance as yf
except Exception:  # pragma: no cover
    yf = None


def _finite_float(value: object, default: float = 0.0) -> float:
    """Coerce to float; replace NaN/inf with default so int(round(...)) never raises."""
    try:
        v = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    if math.isnan(v) or math.isinf(v):
        return default
    return v


def format_currency(value: float | int | None, currency: str = "USD") -> str:
    if value is None:
        return "-"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    # Simple local formatting; avoids locale dependencies.
    return f"{currency} {v:,.2f}"


def convert_for_display(amount: float, from_ccy: str, to_ccy: str, usd_vnd_rate: float) -> float:
    """Convert a monetary amount between USD and VND using Settings rate (VND per 1 USD)."""
    f = (from_ccy or "USD").upper().strip()
    t = (to_ccy or "USD").upper().strip()
    if f == t:
        return float(amount)
    rate = float(usd_vnd_rate or 25500.0)
    if f == "USD" and t == "VND":
        return float(amount) * rate
    if f == "VND" and t == "USD":
        return float(amount) / rate if rate else 0.0
    return float(amount)


def format_display_money(value: float | int | None, currency: str, *, decimals: int = 0) -> str:
    if value is None:
        return "-"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    if decimals <= 0:
        return f"{currency} {v:,.0f}"
    return f"{currency} {v:,.{decimals}f}"


def parse_float(value: str | float | int | None, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    try:
        s = str(value).strip()
        if not s:
            return default
        return float(s)
    except ValueError:
        return default


def keywords_hash(keywords: str) -> str:
    # Normalize whitespace so "a,  b" and "a,b" hit the same cache.
    normalized = ",".join([k.strip().lower() for k in keywords.split(",") if k.strip()])
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def next_birthday_date(birthday: date, today: date) -> date:
    """
    Convert a person's birthday (with year) into the next occurrence relative to `today`.
    For Feb 29 birthdays in non-leap years, use Feb 28.
    """
    def _birthday_for_year(year: int) -> date:
        if birthday.month == 2 and birthday.day == 29 and not calendar.isleap(year):
            return date(year, 2, 28)
        return date(year, birthday.month, birthday.day)

    year = today.year
    candidate = _birthday_for_year(year)
    if candidate < today:
        candidate = _birthday_for_year(year + 1)
    return candidate


@dataclass(frozen=True)
class BirthdayReminder:
    client_name: str
    reminder_date: date
    birthday_date: date


def upcoming_birthday_reminders(
    clients: Iterable, today: date, days_ahead: int = 14
) -> list[BirthdayReminder]:
    results: list[BirthdayReminder] = []
    end = today + timedelta(days=days_ahead)
    for c in clients:
        if not c.birthday:
            continue
        bday_next = next_birthday_date(c.birthday, today)
        reminder_date = bday_next - timedelta(days=1)
        if today <= reminder_date <= end:
            results.append(BirthdayReminder(c.name, reminder_date=reminder_date, birthday_date=bday_next))
    results.sort(key=lambda x: x.reminder_date)
    return results


@dataclass(frozen=True)
class MaturityReminder:
    client_name: str
    investment_id: int
    reminder_date: date
    maturity_date: date


def upcoming_maturity_reminders(
    investments: Iterable, today: date, days_ahead: int = 14
) -> list[MaturityReminder]:
    results: list[MaturityReminder] = []
    end = today + timedelta(days=days_ahead)
    for inv in investments:
        if not inv.maturity_date:
            continue
        reminder_date = inv.maturity_date - timedelta(days=1)
        if today <= reminder_date <= end:
            results.append(
                MaturityReminder(
                    client_name=inv.client.name,
                    investment_id=inv.id,
                    reminder_date=reminder_date,
                    maturity_date=inv.maturity_date,
                )
            )
    results.sort(key=lambda x: x.reminder_date)
    return results


@dataclass(frozen=True)
class HomeInsuranceReminder:
    client_name: str
    reminder_date: date
    expiry_date: date
    amount_covered: float | None
    insured_premium: float | None


def upcoming_home_insurance_reminders(
    clients: Iterable, today: date, days_ahead: int = 14
) -> list[HomeInsuranceReminder]:
    results: list[HomeInsuranceReminder] = []
    end = today + timedelta(days=days_ahead)
    for c in clients:
        expiry_date = getattr(c, "home_insurance_expiry_date", None)
        if not expiry_date:
            continue
        reminder_date = expiry_date - timedelta(days=1)
        if today <= reminder_date <= end:
            amount_covered = getattr(c, "home_insurance_amount_covered", None)
            insured_premium = getattr(c, "home_insurance_insured_premium", None)
            results.append(
                HomeInsuranceReminder(
                    client_name=c.name,
                    reminder_date=reminder_date,
                    expiry_date=expiry_date,
                    amount_covered=float(amount_covered) if amount_covered is not None else None,
                    insured_premium=float(insured_premium) if insured_premium is not None else None,
                )
            )
    results.sort(key=lambda x: x.reminder_date)
    return results


def investment_cost(investment) -> float:
    asset_type = (investment.asset_type or "").lower().strip()
    principal = getattr(investment, "principal", None)
    if asset_type == "real estate":
        # Real estate should contribute only Principal to Total Principal.
        return float(principal) if principal is not None else 0.0
    if asset_type in {"cd", "certificate of deposit", "term deposit", "bond", "cash", "real estate", "debt"} and principal is not None:
        return float(principal)
    if asset_type in {"stock", "vn_stock"}:
        # VN stock local convention: lot-size multiplier.
        return float(investment.quantity) * float(investment.purchase_price) * 1000.0
    # quantity * purchase_price (quantity may be 0.0 for user errors; treat it as such).
    return float(investment.quantity) * float(investment.purchase_price)


def investment_value_and_pnl(investment, latest_price: float | None, usd_vnd_rate: float = 25500.0) -> dict[str, float | None]:
    cost = investment_cost(investment)

    asset_type = (investment.asset_type or "").lower().strip()
    unit = float(getattr(investment, "unit", None) or getattr(investment, "quantity", 0.0) or 0.0)
    current_price = getattr(investment, "current_price", None)
    # Only compute live value for things we can reasonably price from yfinance.
    # For deposits we fall back to "current value == principal".
    if asset_type == "bond":
        expected_coupon = float(getattr(investment, "expected_coupon", 0.0) or 0.0)
        bond_units = float(getattr(investment, "unit", None) or getattr(investment, "quantity", None) or 1.0)
        expected_cashflow_to_maturity = expected_coupon + (100_000_000.0 * bond_units)
        # Requested formula: Unrealized P&L = Expected Cashflow to maturity - Principal.
        pnl = expected_cashflow_to_maturity - cost
        # Keep current value consistent with the above P&L math for summary totals.
        current_value = expected_cashflow_to_maturity
        pnl_pct = None
        return {"cost": cost, "current_value": current_value, "pnl": pnl, "pnl_pct": pnl_pct}
    elif asset_type == "real estate":
        investment_value = float(getattr(investment, "purchase_price", 0.0) or 0.0)
        current_value = float(current_price) if current_price is not None else investment_value
        # Equity for real estate.
        pnl = current_value - investment_value
        pnl_pct = (pnl / cost * 100.0) if cost not in (0.0, 0) else None
        return {"cost": cost, "current_value": current_value, "pnl": pnl, "pnl_pct": pnl_pct}
    elif asset_type == "debt":
        current_value = cost
        pnl = 0.0
        pnl_pct = None
        return {"cost": cost, "current_value": current_value, "pnl": pnl, "pnl_pct": pnl_pct}
    elif asset_type == "term deposit":
        buy_date_td = getattr(investment, "purchase_date", None)
        maturity_date_td = getattr(investment, "maturity_date", None)
        rate_td = float(getattr(investment, "interest_rate", 0.0) or 0.0)
        day_count_td = (
            max((maturity_date_td - buy_date_td).days, 0)
            if (buy_date_td is not None and maturity_date_td is not None)
            else 0
        )
        accrued_interest = float(cost) * (rate_td / 100.0) / 365.0 * float(day_count_td)
        current_value = float(cost) + accrued_interest
        pnl = accrued_interest
        pnl_pct = (pnl / cost * 100.0) if cost not in (0.0, 0) else None
        return {"cost": cost, "current_value": current_value, "pnl": pnl, "pnl_pct": pnl_pct}
    elif asset_type in {"stock", "vn_stock", "us_stock", "commodity", "crypto"}:
        effective_price = latest_price if latest_price is not None else current_price
        if effective_price is not None and unit > 0:
            lot_multiplier = 1000.0 if asset_type in {"stock", "vn_stock"} else 1.0
            current_value = float(unit) * float(effective_price) * lot_multiplier
        else:
            current_value = cost
    else:
        current_value = cost

    pnl = current_value - cost
    pnl_pct = (pnl / cost * 100.0) if cost not in (0.0, 0) else None
    return {"cost": cost, "current_value": current_value, "pnl": pnl, "pnl_pct": pnl_pct}


def client_portfolio_table(
    client,
    investments: list,
    price_map: dict[str, float | None],
    usd_vnd_rate: float = 25500.0,
    display_currency: str = "USD",
) -> tuple[pd.DataFrame, list]:
    """
    Build portfolio rows in display_currency (USD or VND). Principal column = cost basis (merged with former Cost), integers.
    Returns (dataframe, investments in same row order as dataframe).
    """
    disp = (display_currency or "USD").upper().strip()
    sorted_invs = sorted(
        investments,
        key=lambda inv: (inv.asset_type or "", inv.maturity_date.isoformat() if inv.maturity_date else ""),
    )
    rows: list[dict] = []
    today = date.today()
    for inv in sorted_invs:
        ticker = (inv.ticker_identifier or "").strip()
        latest = price_map.get(ticker) if ticker else None
        metrics = investment_value_and_pnl(inv, latest_price=latest, usd_vnd_rate=usd_vnd_rate)
        asset_type_l = (inv.asset_type or "").strip().lower()
        # By business rule: US_Stock/Crypto are USD, all other asset types are VND.
        inv_ccy = "USD" if asset_type_l in {"us_stock", "crypto"} else "VND"
        cost = _finite_float(metrics.get("cost"), 0.0)
        cur_v = _finite_float(metrics.get("current_value"), 0.0)
        pnl = _finite_float(metrics.get("pnl"), 0.0)
        cost_d = _finite_float(convert_for_display(cost, inv_ccy, disp, usd_vnd_rate), 0.0)
        cur_d = _finite_float(convert_for_display(cur_v, inv_ccy, disp, usd_vnd_rate), 0.0)
        pnl_d = _finite_float(convert_for_display(pnl, inv_ccy, disp, usd_vnd_rate), 0.0)
        tenor_display = inv.tenor or ""
        if asset_type_l == "bond" and inv.maturity_date:
            months = (inv.maturity_date.year - today.year) * 12 + (inv.maturity_date.month - today.month)
            if inv.maturity_date.day < today.day:
                months -= 1
            tenor_display = f"{max(months, 0)} months"
        term_interest = ""
        if asset_type_l == "term deposit":
            try:
                principal_td = float(inv.principal or 0.0)
                rate_td = float(inv.interest_rate or 0.0)
                buy_date_td = inv.purchase_date
                maturity_date_td = inv.maturity_date
                day_count_td = (
                    max((maturity_date_td - buy_date_td).days, 0)
                    if (buy_date_td is not None and maturity_date_td is not None)
                    else 0
                )
                term_interest = principal_td * (rate_td / 100.0) / 365.0 * float(day_count_td)
            except Exception:
                term_interest = ""
        rows.append(
            {
                "Asset Type": inv.asset_type,
                "Currency": inv_ccy,
                "Ticker": (inv.ticker_name or "") if (inv.asset_type or "").strip().lower() == "bond" else (inv.ticker_identifier or ""),
                "Unit": (
                    float(inv.unit)
                    if getattr(inv, "unit", None) is not None
                    else float(inv.quantity)
                    if (inv.asset_type or "").strip().lower() in {"stock", "vn_stock", "us_stock", "commodity", "crypto"}
                    else ""
                ),
                # Keep principal in the investment's native currency for row display.
                "Principal": int(round(cost)),
                # Hidden helper used by totals/allocation in selected display currency.
                "Principal Display": int(round(cost_d)),
                # Debt view should always reflect selected display currency.
                "Outstanding Balance": int(round(convert_for_display(cost, inv_ccy, disp, usd_vnd_rate)))
                if asset_type_l == "debt"
                else "",
                "Principal Payment": (
                    int(
                        round(
                            convert_for_display(
                                float(getattr(inv, "principal_payment", 0.0) or 0.0),
                                inv_ccy,
                                disp,
                                usd_vnd_rate,
                            )
                        )
                    )
                    if asset_type_l == "debt"
                    else ""
                ),
                "Est Interest Payment": (
                    int(
                        round(
                            convert_for_display(
                                float(cost) * (float(getattr(inv, "interest_rate", 0.0) or 0.0) / 100.0) / 12.0,
                                inv_ccy,
                                disp,
                                usd_vnd_rate,
                            )
                        )
                    )
                    if asset_type_l == "debt"
                    else ""
                ),
                "Total Monthly Payment": (
                    int(
                        round(
                            convert_for_display(
                                float(getattr(inv, "principal_payment", 0.0) or 0.0)
                                + (float(cost) * (float(getattr(inv, "interest_rate", 0.0) or 0.0) / 100.0) / 12.0),
                                inv_ccy,
                                disp,
                                usd_vnd_rate,
                            )
                        )
                    )
                    if asset_type_l == "debt"
                    else ""
                ),
                "Buy Price": float(inv.purchase_price),
                "Investment Value": int(round(convert_for_display(float(inv.purchase_price or 0.0), inv_ccy, disp, usd_vnd_rate)))
                if asset_type_l == "real estate"
                else "",
                "Buy Date": inv.purchase_date.isoformat() if inv.purchase_date else "",
                "Purchase Date": inv.purchase_date.isoformat() if inv.purchase_date else "",
                "Tenor": tenor_display,
                "Interest Rate %": float(inv.interest_rate) if getattr(inv, "interest_rate", None) is not None else "",
                "Interest": (
                    int(round(convert_for_display(float(term_interest), inv_ccy, disp, usd_vnd_rate)))
                    if term_interest != ""
                    else ""
                ),
                "YTM %": float(inv.ytm) if getattr(inv, "ytm", None) is not None else "",
                "Current Price": (
                    float(latest)
                    if (
                        asset_type_l in {"stock", "vn_stock", "us_stock", "commodity", "crypto"}
                        and latest is not None
                        and not bool(getattr(inv, "is_done", False))
                    )
                    else float(inv.current_price)
                    if getattr(inv, "current_price", None) is not None
                    else ""
                ),
                "Expected Coupon (Amount)": float(inv.expected_coupon) if getattr(inv, "expected_coupon", None) is not None else "",
                "Received Coupon (Amount)": float(inv.received_coupon) if getattr(inv, "received_coupon", None) is not None else "",
                "Maturity Date": inv.maturity_date.isoformat() if inv.maturity_date else "",
                "Notes": inv.notes or "",
                # Row display uses native/default currency by asset type.
                "Current Value": int(round(cur_v)),
                "Unrealized P&L": int(round(pnl)),
                # Hidden helpers for portfolio totals in selected display currency.
                "Current Value Display": int(round(cur_d)),
                "Unrealized P&L Display": int(round(pnl_d)),
                "P&L %": metrics["pnl_pct"],
            }
        )
    df = pd.DataFrame(rows)
    return df, sorted_invs


def portfolio_totals(df: pd.DataFrame) -> dict[str, float | None]:
    if df.empty:
        return {"current_value": 0.0, "cost": 0.0, "principal": 0.0, "pnl": 0.0, "pnl_pct": None}
    principal_col = (
        "Principal Display"
        if "Principal Display" in df.columns
        else "Principal"
        if "Principal" in df.columns
        else "Cost"
    )
    principal = float(df[principal_col].sum()) if principal_col in df.columns else 0.0
    current_value = float(df["Current Value"].sum()) if "Current Value" in df.columns else 0.0
    pnl = (
        float(df["Unrealized P&L"].sum())
        if "Unrealized P&L" in df.columns
        else float(df["P&L"].sum())
        if "P&L" in df.columns
        else (current_value - principal)
    )
    pnl_pct = (pnl / principal * 100.0) if principal not in (0.0, 0) else None
    return {"current_value": current_value, "cost": principal, "principal": principal, "pnl": pnl, "pnl_pct": pnl_pct}


def iso_date_or_empty(d: date | None) -> str:
    return d.isoformat() if d else ""


def fetch_latest_prices_yfinance(tickers: Iterable[str]) -> dict[str, float | None]:
    """
    Best-effort latest price fetch using yfinance.
    Returns a map {ticker: last_price_or_none}.
    """
    if yf is None:
        return {t: None for t in tickers}

    out: dict[str, float | None] = {}
    uniq = []
    seen: set[str] = set()
    for t in tickers:
        tt = str(t).strip()
        if not tt or tt in seen:
            continue
        seen.add(tt)
        uniq.append(tt)

    for t in uniq:
        try:
            ticker_obj = yf.Ticker(t)
            # fast_info is convenient but sometimes missing; fallback to history.
            last_price = None
            try:
                last_price = ticker_obj.fast_info.get("last_price")  # type: ignore[union-attr]
            except Exception:
                last_price = None

            if last_price is None:
                hist = ticker_obj.history(period="5d", interval="1d")
                if not hist.empty:
                    # "Close" is last trading day close; this is typically adequate.
                    last_price = float(hist["Close"].iloc[-1])

            out[t] = float(last_price) if last_price is not None else None
        except Exception:
            out[t] = None
    return out


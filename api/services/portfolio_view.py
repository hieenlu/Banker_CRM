"""Portfolio valuation helpers for the API (reuse Streamlit formulas)."""

from __future__ import annotations

from typing import Any

from models import Investment
from utils import client_portfolio_table, portfolio_totals


SUBGROUP_ORDER = [
    "Cash and CDs",
    "Term Deposit",
    "Bond",
    "VN_Stock",
    "US_Stock",
    "Crypto",
    "Commodity",
    "Real Estate",
    "Debt",
]

EQUITY_COLS = [
    "Ticker",
    "Unit",
    "Buy Price",
    "Current Price",
    "Principal",
    "Current Value",
    "Unrealized P&L",
    "P&L %",
    "Notes",
]
BOND_COLS = [
    "Ticker",
    "Unit",
    "Principal",
    "Expected Coupon (Amount)",
    "Received Coupon (Amount)",
    "YTM %",
    "Maturity Date",
    "Unrealized P&L",
]
TERM_DEPOSIT_COLS = [
    "Principal",
    "Buy Date",
    "Tenor",
    "Interest Rate %",
    "Maturity Date",
    "Interest",
]
DEBT_COLS = [
    "Outstanding Balance",
    "Interest Rate %",
    "Principal Payment",
    "Est Interest Payment",
    "Total Monthly Payment",
    "Notes",
]
CASH_COLS = ["Principal"]
REAL_ESTATE_COLS = [
    "Principal",
    "Investment Value",
    "Current Value",
    "Unrealized P&L",
    "P&L %",
    "Notes",
]


def columns_for_subgroup(group: str) -> list[str]:
    if group == "Debt":
        return list(DEBT_COLS)
    if group == "Cash and CDs":
        return list(CASH_COLS)
    if group in {"VN_Stock", "US_Stock", "Commodity", "Crypto"}:
        return list(EQUITY_COLS)
    if group == "Bond":
        return list(BOND_COLS)
    if group == "Term Deposit":
        return list(TERM_DEPOSIT_COLS)
    if group == "Real Estate":
        return list(REAL_ESTATE_COLS)
    return ["Principal", "Current Value", "Unrealized P&L", "P&L %", "Notes"]


def top_group_for(asset_type: str) -> str:
    a = (asset_type or "").strip().lower()
    return "Debts" if a == "debt" else "Equities"


def subgroup_for(asset_type: str) -> str:
    a = (asset_type or "").strip().lower()
    if a == "stock":
        return "VN_Stock"
    if a in {"cd", "certificate of deposit"} or a == "cash":
        return "Cash and CDs"
    if a == "debt":
        return "Debt"
    # Preserve canonical Streamlit labels.
    mapping = {
        "vn_stock": "VN_Stock",
        "us_stock": "US_Stock",
        "term deposit": "Term Deposit",
        "real estate": "Real Estate",
        "bond": "Bond",
        "crypto": "Crypto",
        "commodity": "Commodity",
    }
    return mapping.get(a, asset_type or "Other")


def native_currency(asset_type: str) -> str:
    a = (asset_type or "").strip().lower()
    return "USD" if a in {"us_stock", "crypto"} else "VND"


def price_map_from_investments(investments: list[Investment]) -> dict[str, float | None]:
    """Use stored current_price as latest when live fetch was not requested."""
    out: dict[str, float | None] = {}
    for inv in investments:
        t = (inv.ticker_identifier or "").strip()
        if not t:
            continue
        if getattr(inv, "current_price", None) is not None:
            out[t] = float(inv.current_price)
    return out


def build_portfolio_view(
    investments: list[Investment],
    *,
    price_map: dict[str, float | None],
    usd_vnd_rate: float,
    display_currency: str = "VND",
    client_names: dict[int, str] | None = None,
) -> dict[str, Any]:
    df, inv_order = client_portfolio_table(
        client=None,
        investments=investments,
        price_map=price_map,
        usd_vnd_rate=usd_vnd_rate,
        display_currency=display_currency,
    )
    totals = portfolio_totals(df)

    groups: dict[str, dict[str, list[dict[str, Any]]]] = {}
    if not df.empty:
        for i, inv in enumerate(inv_order):
            row = df.iloc[i]
            asset = str(row.get("Asset Type") or inv.asset_type or "")
            top = top_group_for(asset)
            sub = subgroup_for(asset)
            payload = {col: _jsonable(row.get(col)) for col in df.columns}
            payload["id"] = inv.id
            payload["client_id"] = inv.client_id
            payload["is_done"] = bool(inv.is_done)
            payload["asset_type"] = inv.asset_type
            payload["native_currency"] = native_currency(inv.asset_type or "")
            if client_names is not None:
                payload["client_name"] = client_names.get(inv.client_id, f"#{inv.client_id}")
            groups.setdefault(top, {}).setdefault(sub, []).append(payload)

    ordered_sections: list[dict[str, Any]] = []
    for top in ("Equities", "Debts"):
        if top not in groups:
            continue
        subs = groups[top]
        ranked = sorted(
            subs.keys(),
            key=lambda name: (
                SUBGROUP_ORDER.index(name) if name in SUBGROUP_ORDER else 999,
                name,
            ),
        )
        sections = []
        for sub in ranked:
            rows = subs[sub]
            # Subgroup PnL in native currency (match Streamlit header).
            pnl_sum = sum(float(r.get("Unrealized P&L") or 0) for r in rows)
            sections.append(
                {
                    "name": sub,
                    "columns": columns_for_subgroup(sub),
                    "rows": rows,
                    "unrealized_pnl": pnl_sum,
                    "native_currency": native_currency(sub if sub != "Cash and CDs" else "cash"),
                }
            )
        ordered_sections.append({"name": top, "subgroups": sections})

    return {
        "display_currency": display_currency.upper(),
        "usd_vnd_rate": usd_vnd_rate,
        "totals": {
            "principal": float(totals.get("principal") or 0),
            "current_value": float(totals.get("current_value") or 0),
            "pnl": float(totals.get("pnl") or 0),
            "pnl_pct": totals.get("pnl_pct"),
        },
        "groups": ordered_sections,
    }


def _jsonable(value: Any) -> Any:
    if value is None:
        return None
    try:
        import math

        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return None
    except Exception:
        pass
    if value == "":
        return None
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return value

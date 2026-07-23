"""Live price refresh for investments."""

from __future__ import annotations

from models import Investment


def calc_tickers_for_pricing(
    investments: list[Investment],
) -> tuple[list[str], list[str], list[str], list[str], list[str]]:
    tickers: set[str] = set()
    vn_stock_tickers: set[str] = set()
    us_stock_tickers: set[str] = set()
    commodity_tickers: set[str] = set()
    crypto_tickers: set[str] = set()
    for inv in investments:
        asset_type = (inv.asset_type or "").strip().lower()
        # Bonds keep face/current values in CRM — do not send tickers to live quote APIs.
        if asset_type in {"stock", "vn_stock", "us_stock", "commodity", "crypto"}:
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


def refresh_investment_prices(investments: list[Investment]) -> dict:
    """Fetch live prices and persist onto investment.current_price for priced assets."""
    from fetch_prices import fetch_latest_prices

    tickers, vn, us, commodity, crypto = calc_tickers_for_pricing(investments)
    if not tickers:
        return {
            "requested": 0,
            "resolved": 0,
            "updated": 0,
            "prices": {},
            "missing": [],
        }

    price_map = fetch_latest_prices(
        tickers,
        vn_stock_tickers=vn,
        us_stock_tickers=us,
        commodity_tickers=commodity,
        crypto_tickers=crypto,
    )

    updated = 0
    for inv in investments:
        asset_type = (inv.asset_type or "").strip().lower()
        if asset_type not in {"stock", "vn_stock", "us_stock", "commodity", "crypto"}:
            continue
        if inv.is_done:
            continue
        t = (inv.ticker_identifier or "").strip()
        if not t:
            continue
        px = price_map.get(t)
        if px is None:
            continue
        inv.current_price = float(px)
        updated += 1

    missing = [t for t, px in price_map.items() if px is None]
    resolved = sum(1 for px in price_map.values() if px is not None)
    return {
        "requested": len(tickers),
        "resolved": resolved,
        "updated": updated,
        "prices": {k: v for k, v in price_map.items() if v is not None},
        "missing": missing,
    }

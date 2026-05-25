from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable

import pandas as pd
import requests
import re

from utils import fetch_latest_prices_yfinance

try:
    from vnstock import Vnstock  # type: ignore
except Exception:  # pragma: no cover
    Vnstock = None  # type: ignore


def _extract_last_price_from_df(df: pd.DataFrame | None) -> float | None:
    if df is None or df.empty:
        return None
    for col in ("close", "Close", "price", "match_price", "lastPrice", "last_price"):
        if col in df.columns:
            v = df[col].iloc[-1]
            if pd.notna(v):
                return float(v)
    try:
        row = df.iloc[-1]
        nums = pd.to_numeric(row, errors="coerce").dropna()
        if not nums.empty:
            return float(nums.iloc[-1])
    except Exception:
        return None
    return None


def _fetch_one_vnstock_price(ticker: str) -> float | None:
    if Vnstock is None:
        return None
    symbol = ticker.strip().upper().replace(" ", "")
    if not symbol:
        return None
    symbol_candidates = [symbol]
    # Support identifiers like FPT.VN / FPT.HM by extracting base symbol for vnstock.
    if "." in symbol:
        base = symbol.split(".", 1)[0].strip()
        if base and base not in symbol_candidates:
            symbol_candidates.append(base)
    end = date.today()
    start = end - timedelta(days=10)
    for sym in symbol_candidates:
        for source in ("VCI", "TCBS", "KBS"):
            try:
                stock = Vnstock().stock(symbol=sym, source=source)
                df = stock.quote.history(start=start.isoformat(), end=end.isoformat())
                px = _extract_last_price_from_df(df)
                if px is not None:
                    return px
            except Exception:
                continue
    return None


def _fetch_vn_prices_yahoo_with_alias(tickers: Iterable[str]) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for t in tickers:
        tt = str(t).strip()
        if not tt:
            continue
        cands = [tt]
        up = tt.upper().replace(" ", "")
        if "." not in up and up.isalpha():
            cands.extend([f"{up}.VN", f"{up}.HN", f"{up}.HM"])
        px = None
        for c in cands:
            px = fetch_latest_prices_yfinance([c]).get(c)
            if px is not None:
                break
        out[tt] = px
    return out


def _normalize_crypto_symbol(symbol: str) -> str:
    s = (symbol or "").strip().upper()
    if not s:
        return s
    if "-" in s:
        base, quote = s.split("-", 1)
        if base and quote:
            return f"{base}{quote}"
    if "/" in s:
        base, quote = s.split("/", 1)
        if base and quote:
            return f"{base}{quote}"
    return s


def _base_crypto_symbol(symbol: str) -> str:
    s = _normalize_crypto_symbol(symbol)
    for q in ("USDT", "USD"):
        if s.endswith(q) and len(s) > len(q):
            return s[: -len(q)]
    return s


def _fetch_crypto_prices_coingecko(symbols: Iterable[str]) -> dict[str, float | None]:
    raw_syms = [str(s).strip() for s in symbols if str(s).strip()]
    if not raw_syms:
        return {}
    out: dict[str, float | None] = {s: None for s in raw_syms}
    try:
        lst = requests.get(
            "https://api.coingecko.com/api/v3/coins/list",
            params={"include_platform": "false"},
            timeout=15,
        )
        lst.raise_for_status()
        coins = lst.json() or []
    except Exception:
        return out

    symbol_to_ids: dict[str, list[str]] = {}
    for c in coins:
        sym = str(c.get("symbol", "")).strip().lower()
        cid = str(c.get("id", "")).strip()
        if not sym or not cid:
            continue
        symbol_to_ids.setdefault(sym, []).append(cid)

    canonical_ids = {
        "btc": "bitcoin",
        "eth": "ethereum",
        "bnb": "binancecoin",
        "sol": "solana",
        "xrp": "ripple",
        "ada": "cardano",
        "doge": "dogecoin",
        "trx": "tron",
        "dot": "polkadot",
        "matic": "matic-network",
        "avax": "avalanche-2",
        "link": "chainlink",
    }

    symbol_to_id: dict[str, str] = {}
    for s in raw_syms:
        base = _base_crypto_symbol(s).lower()
        canon = canonical_ids.get(base)
        if canon:
            symbol_to_id[s] = canon
            continue
        ids = symbol_to_ids.get(base, [])
        if not ids:
            continue
        preferred = [f"{base}", f"{base}-token", f"wrapped-{base}"]
        chosen = next((x for x in preferred if x in ids), ids[0])
        symbol_to_id[s] = chosen

    if not symbol_to_id:
        return out

    ids_csv = ",".join(sorted(set(symbol_to_id.values())))
    try:
        pr = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": ids_csv, "vs_currencies": "usd"},
            timeout=15,
        )
        pr.raise_for_status()
        data = pr.json() or {}
    except Exception:
        return out

    for sym, cid in symbol_to_id.items():
        val = (data.get(cid) or {}).get("usd")
        out[sym] = float(val) if val is not None else None
    return out


def _fetch_gold_price_apmex() -> float | None:
    """
    Fetch spot gold price from APMEX gold-price page.
    Returns USD price per ounce when available.
    """
    try:
        resp = requests.get("https://www.apmex.com/gold-price", timeout=20)
        resp.raise_for_status()
        html = resp.text
    except Exception:
        return None

    # Try JSON-LD/embedded numeric fields first.
    patterns = [
        r'"goldPrice"\s*:\s*"?([0-9][0-9,]*\.?[0-9]*)"?',
        r'"price"\s*:\s*"?([0-9][0-9,]*\.?[0-9]*)"?',
        r'Gold Price[^0-9$]{0,40}\$([0-9][0-9,]*\.?[0-9]*)',
        r'\$([0-9][0-9,]*\.[0-9]{2})',
    ]
    for pat in patterns:
        m = re.search(pat, html, flags=re.IGNORECASE)
        if m:
            try:
                return float(m.group(1).replace(",", ""))
            except Exception:
                continue
    return None


def _fetch_hyperliquid_prices_us(tickers: Iterable[str]) -> dict[str, float | None]:
    """
    Fetch US stock prices from Hyperliquid public API.
    Reference: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api
    Endpoint used: POST /info with {"type":"allMids"}.
    """
    out: dict[str, float | None] = {}
    wanted = [str(t).strip().upper() for t in tickers if str(t).strip()]
    if not wanted:
        return out

    # Map app tickers to Hyperliquid instrument keys when they differ.
    hl_alias = {
        "SAMSUNG": "SMSN",
        "SKHYNIX": "SKHX",
        "HYUNDAI": "HYUNDAI",
    }

    try:
        resp = requests.post(
            "https://api.hyperliquid.xyz/info",
            json={"type": "allMids"},
            timeout=20,
        )
        resp.raise_for_status()
        mids = resp.json() or {}
    except Exception:
        mids = {}

    normalized_mids: dict[str, float] = {}
    if isinstance(mids, dict):
        for k, v in mids.items():
            kk = str(k).strip().upper()
            try:
                normalized_mids[kk] = float(v)
            except Exception:
                continue

    for t in tickers:
        tt = str(t).strip()
        if not tt:
            continue
        raw_key = tt.upper()
        mapped = hl_alias.get(raw_key, raw_key)
        # Try direct key, then xyz: prefixed pair used in Hyperliquid routing.
        out[tt] = normalized_mids.get(mapped)
        if out[tt] is None:
            out[tt] = normalized_mids.get(f"XYZ:{mapped}")
    return out


def _fetch_us_prices_yahoo_with_alias(tickers: Iterable[str]) -> dict[str, float | None]:
    """
    Yahoo fallback with ticker aliases for non-US listing underlyings.
    """
    out: dict[str, float | None] = {}
    alias = {
        "SAMSUNG": "005930.KS",
        "SKHYNIX": "000660.KS",
        "HYUNDAI": "005380.KS",
        "SP500": "^GSPC",
    }
    # Yahoo FX pair for KRW conversion into USD-equivalent prices.
    usdk_rw_pair = "USDKRW=X"
    usdkrw = fetch_latest_prices_yfinance([usdk_rw_pair]).get(usdk_rw_pair)
    usdkrw_rate = float(usdkrw) if usdkrw not in (None, 0, 0.0) else None
    for t in tickers:
        tt = str(t).strip()
        if not tt:
            continue
        mapped = alias.get(tt.upper(), tt)
        px = fetch_latest_prices_yfinance([mapped]).get(mapped)
        if px is not None and mapped.endswith(".KS") and usdkrw_rate:
            # Convert KRW-listed underlying to USD to match Hyperliquid convention.
            out[tt] = float(px) / float(usdkrw_rate)
        else:
            out[tt] = px
    return out


def fetch_latest_prices(
    tickers: Iterable[str],
    *,
    vn_stock_tickers: Iterable[str] | None = None,
    us_stock_tickers: Iterable[str] | None = None,
    commodity_tickers: Iterable[str] | None = None,
    crypto_tickers: Iterable[str] | None = None,
) -> dict[str, float | None]:
    uniq: list[str] = []
    seen: set[str] = set()
    for t in tickers:
        tt = (str(t) if t is not None else "").strip()
        if not tt or tt in seen:
            continue
        seen.add(tt)
        uniq.append(tt)

    out: dict[str, float | None] = {t: None for t in uniq}
    vn_set = {str(t).strip() for t in (vn_stock_tickers or []) if str(t).strip()}
    us_set = {str(t).strip() for t in (us_stock_tickers or []) if str(t).strip()}
    commodity_set = {str(t).strip() for t in (commodity_tickers or []) if str(t).strip()}
    crypto_set = {str(t).strip() for t in (crypto_tickers or []) if str(t).strip()}

    failed: list[str] = []
    non_routed: list[str] = []

    crypto_candidates = [t for t in uniq if t in crypto_set]
    crypto_prices = _fetch_crypto_prices_coingecko(crypto_candidates) if crypto_candidates else {}

    us_candidates = [t for t in uniq if t in us_set]
    us_prices = _fetch_hyperliquid_prices_us(us_candidates) if us_candidates else {}
    us_missing = [t for t in us_candidates if us_prices.get(t) is None]
    if us_missing:
        us_yf = _fetch_us_prices_yahoo_with_alias(us_missing)
        for t, v in us_yf.items():
            us_prices[t] = v
    commodity_candidates = [t for t in uniq if t in commodity_set]
    commodity_prices = fetch_latest_prices_yfinance(commodity_candidates) if commodity_candidates else {}
    gold_tickers = {
        t for t in commodity_candidates if t.strip().upper() in {"GOLD", "XAU"}
    }
    if gold_tickers:
        gold_price = _fetch_gold_price_apmex()
        if gold_price is None:
            # Robust fallback symbols on Yahoo Finance for spot/futures gold.
            yf_gold = fetch_latest_prices_yfinance(["GC=F", "XAUUSD=X"])
            gold_price = yf_gold.get("XAUUSD=X")
            if gold_price is None:
                gold_price = yf_gold.get("GC=F")
        if gold_price is not None:
            for t in gold_tickers:
                commodity_prices[t] = gold_price

    for t in uniq:
        if t in crypto_set:
            px = crypto_prices.get(t)
            if px is None:
                failed.append(t)
            else:
                out[t] = px
        elif t in vn_set:
            px = _fetch_one_vnstock_price(t)
            if px is None:
                failed.append(t)
            else:
                out[t] = px
        elif t in us_set:
            px = us_prices.get(t)
            if px is None:
                failed.append(t)
            else:
                out[t] = px
        elif t in commodity_set:
            px = commodity_prices.get(t)
            if px is None:
                failed.append(t)
            else:
                out[t] = px
        else:
            non_routed.append(t)

    yfinance_needed = non_routed + failed
    if yfinance_needed:
        yf_map = fetch_latest_prices_yfinance(yfinance_needed)
        for t, v in yf_map.items():
            out[t] = v
        vn_missing = [t for t in failed if t in vn_set and out.get(t) is None]
        if vn_missing:
            vn_yf = _fetch_vn_prices_yahoo_with_alias(vn_missing)
            for t, v in vn_yf.items():
                if v is not None:
                    out[t] = v
        for t in failed:
            if t in crypto_set and out.get(t) is None:
                base = _base_crypto_symbol(t)
                usd_pair = f"{base}-USD"
                usdt_pair = f"{base}-USDT"
                usd_val = fetch_latest_prices_yfinance([usd_pair]).get(usd_pair)
                if usd_val is not None:
                    out[t] = usd_val
                else:
                    usdt_val = fetch_latest_prices_yfinance([usdt_pair]).get(usdt_pair)
                    if usdt_val is not None:
                        out[t] = usdt_val
    return out


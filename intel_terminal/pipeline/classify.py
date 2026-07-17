"""Rule-based article classification (no LLM — token-free)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from intel_terminal.constants import ARTICLE_CATEGORIES

# (category, weight, keywords) — first match wins ties by score
_CATEGORY_RULES: tuple[tuple[str, float, tuple[str, ...]], ...] = (
    (
        "Vietnam",
        1.15,
        (
            "vietnam",
            "viet nam",
            "hanoi",
            "ho chi minh",
            "saigon",
            "dong",
            "vnd",
            "vn-index",
            "vnindex",
            "hose",
            "hnx",
            "upcom",
            "sbv",
            "techcombank",
            "vietcombank",
            "bidv",
            "cafef",
            "vietstock",
            # Vietnamese finance / macro terms
            "ngân hàng",
            "ngan hang",
            "chứng khoán",
            "chung khoan",
            "cổ phiếu",
            "co phieu",
            "lãi suất",
            "lai suat",
            "bất động sản",
            "bat dong san",
            "kinh tế",
            "kinh te",
            "đầu tư",
            "dau tu",
            "vn-index",
            "vnindex",
            "vn index",
        ),
    ),
    (
        "China",
        1.1,
        (
            "china",
            "chinese",
            "beijing",
            "shanghai",
            "pboc",
            "yuan",
            "renminbi",
            "csi 300",
            "hang seng",
            "evergrande",
            "property sector china",
        ),
    ),
    (
        "Crypto",
        1.1,
        (
            "bitcoin",
            "btc",
            "ethereum",
            "eth",
            "crypto",
            "blockchain",
            "defi",
            "stablecoin",
            "binance",
            "solana",
            "token",
            "web3",
        ),
    ),
    (
        "Central Banks",
        1.05,
        (
            "federal reserve",
            "fed ",
            " fomc",
            "ecb",
            "european central bank",
            "bank of england",
            "boj",
            "bank of japan",
            "rate decision",
            "rate hike",
            "rate cut",
            "monetary policy",
            "powell",
            "lagarde",
        ),
    ),
    (
        "Inflation",
        1.05,
        (
            "inflation",
            "cpi",
            "pce",
            "consumer prices",
            "deflation",
            "stagflation",
            "price pressures",
            "core inflation",
        ),
    ),
    (
        "Fixed Income",
        1.0,
        (
            "bond",
            "treasury",
            "yield",
            "yields",
            "fixed income",
            "credit spread",
            "sovereign",
            "investment grade",
            "high yield",
            "duration",
        ),
    ),
    (
        "Equities",
        1.0,
        (
            "stock",
            "stocks",
            "equity",
            "equities",
            "s&p 500",
            "s&p500",
            "nasdaq",
            "dow jones",
            "earnings",
            "ipo",
            "share price",
            "rally",
            "selloff",
        ),
    ),
    (
        "Commodities",
        1.0,
        (
            "oil",
            "crude",
            "gold",
            "silver",
            "copper",
            "commodity",
            "commodities",
            "natural gas",
            "wheat",
            "opec",
        ),
    ),
    (
        "FX",
        1.0,
        (
            "forex",
            "currency",
            "dollar",
            "usd",
            "euro",
            "eur",
            "yen",
            "jpy",
            "exchange rate",
            "fx ",
        ),
    ),
    (
        "Geopolitics",
        1.0,
        (
            "war",
            "sanctions",
            "geopolit",
            "tariff",
            "trade war",
            "conflict",
            "nato",
            "election",
            "summit",
            "diplomat",
        ),
    ),
    (
        "Global Macro",
        0.95,
        (
            "gdp",
            "recession",
            "growth",
            "unemployment",
            "jobs report",
            "pmi",
            "macro",
            "economy",
            "economic outlook",
            "imf",
            "world bank",
        ),
    ),
)


@dataclass(frozen=True)
class ClassificationResult:
    category: str
    confidence: float  # 0–1
    matched_terms: tuple[str, ...]


def _text_blob(title: str, body: str | None, source: str) -> str:
    parts = [title or "", body or "", source or ""]
    return " ".join(parts).lower()


def _term_hits(blob: str, keywords: tuple[str, ...]) -> list[str]:
    hits: list[str] = []
    for kw in keywords:
        if any(ord(c) > 127 for c in kw):
            if kw in blob:
                hits.append(kw)
            continue
        if " " in kw or len(kw) > 4:
            if kw in blob:
                hits.append(kw)
        elif re.search(rf"\b{re.escape(kw)}\b", blob):
            hits.append(kw)
    return hits


def classify_text(
    title: str,
    body: str | None = None,
    *,
    source: str = "",
    region: str = "global",
) -> ClassificationResult:
    """Assign best category from keyword rules."""
    blob = _text_blob(title, body, source)
    best_cat = "Uncategorized"
    best_score = 0.0
    best_hits: tuple[str, ...] = ()

    for category, weight, keywords in _CATEGORY_RULES:
        if category not in ARTICLE_CATEGORIES:
            continue
        hits = _term_hits(blob, keywords)
        if not hits:
            continue
        raw = min(1.0, len(hits) * 0.22) * weight
        if region == "vietnam" and category == "Vietnam":
            raw = min(1.0, raw + 0.25)
        if raw > best_score:
            best_score = raw
            best_cat = category
            best_hits = tuple(hits[:8])

    if region == "vietnam" and best_cat == "Uncategorized":
        return ClassificationResult(
            category="Vietnam",
            confidence=0.48,
            matched_terms=("feed:vietnam",),
        )

    confidence = min(1.0, best_score) if best_cat != "Uncategorized" else 0.0
    return ClassificationResult(category=best_cat, confidence=confidence, matched_terms=best_hits)

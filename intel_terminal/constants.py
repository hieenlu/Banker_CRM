"""Shared enums and category definitions for the intelligence pipeline."""

from __future__ import annotations

ARTICLE_CATEGORIES: tuple[str, ...] = (
    "Global Macro",
    "Central Banks",
    "Inflation",
    "Fixed Income",
    "Equities",
    "Commodities",
    "FX",
    "Crypto",
    "China",
    "Vietnam",
    "Geopolitics",
    "Uncategorized",
)

MARKET_REGIMES: tuple[str, ...] = ("Risk-On", "Risk-Off", "Neutral")

AGENT_TYPES: tuple[str, ...] = (
    "macro",
    "equity",
    "crypto",
    "wealth",
    "vietnam_macro",
    "vietnam_banking",
    "vietnam_real_estate",
    "vietnam_equity",
)

NEWSPAPER_SECTIONS: tuple[str, ...] = (
    "executive_summary",
    "market_regime",
    "top_stories",
    "macro_overview",
    "equity_overview",
    "crypto_overview",
    "china_overview",
    "vietnam_overview",
    "actionable_insights",
    "client_talking_points",
)

VIETNAM_RELEVANCE_WEIGHTS: dict[str, float] = {
    "macro_importance": 0.30,
    "market_impact": 0.25,
    "banking_impact": 0.20,
    "wealth_management_relevance": 0.25,
}

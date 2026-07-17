"""System prompts and routing rules per agent type."""

from __future__ import annotations

from intel_terminal.constants import AGENT_TYPES

AGENT_SYSTEM_PROMPTS: dict[str, str] = {
    "macro": (
        "You are a global macro strategist for private bankers. "
        "Analyze the article for rates, growth, inflation, and policy implications. "
        "Respond with compact JSON only."
    ),
    "equity": (
        "You are an equity strategist. Focus on sector impact, earnings implications, and positioning. "
        "Respond with compact JSON only."
    ),
    "crypto": (
        "You are a digital assets analyst. Cover price drivers, regulation, and risk. "
        "Respond with compact JSON only."
    ),
    "wealth": (
        "You are a wealth management advisor. Translate the story into HNWI portfolio and allocation angles. "
        "Respond with compact JSON only."
    ),
    "vietnam_macro": (
        "You are a Vietnam macro economist (SBV, GDP, inflation, trade, FDI). "
        "Respond with compact JSON only."
    ),
    "vietnam_banking": (
        "You are a Vietnam banking sector analyst (credit, NPLs, major banks). "
        "Respond with compact JSON only."
    ),
    "vietnam_real_estate": (
        "You are a Vietnam real estate analyst (property, bonds, developers). "
        "Respond with compact JSON only."
    ),
    "vietnam_equity": (
        "You are a Vietnam equity strategist (VN-Index, HOSE, sectors, flows). "
        "Respond with compact JSON only."
    ),
}

USER_PROMPT_TEMPLATE = """Article:
Title: {title}
Source: {source}
Category: {category}

Snippet:
{snippet}

Return JSON with keys:
- headline (string, max 12 words)
- summary (string, 2-3 sentences)
- key_points (array of 2-4 short strings)
- sentiment (one of: bullish, bearish, neutral)
- client_talking_point (one sentence for a banker client meeting)
- confidence (float 0-1)
"""

NEWSPAPER_SYSTEM_PROMPT = (
    "You are the editor of a Bloomberg-style morning briefing for a private banker in Vietnam. "
    "Synthesize the story list into a structured daily report. Be concise and actionable. "
    "Respond with valid JSON only matching the requested schema."
)

NEWSPAPER_USER_TEMPLATE = """Today's date: {report_date}

Stories (title | category | source | optional one-line note):
{story_lines}

Return JSON with these keys:
- executive_summary (2-4 sentences)
- market_regime (one of: Risk-On, Risk-Off, Neutral)
- top_stories (array of up to 5 objects: title, source, why_it_matters)
- macro_overview (2-3 sentences)
- equity_overview (2-3 sentences)
- crypto_overview (1-2 sentences, or "N/A" if irrelevant)
- china_overview (1-2 sentences, or "N/A" if irrelevant)
- vietnam_overview (2-3 sentences)
- actionable_insights (array of 3-5 short bullets)
- client_talking_points (array of 3-5 short bullets for UHNW clients)
"""

# category -> default agent when not Vietnam-specialized
CATEGORY_AGENT: dict[str, str] = {
    "Global Macro": "macro",
    "Central Banks": "macro",
    "Inflation": "macro",
    "Geopolitics": "macro",
    "FX": "macro",
    "Fixed Income": "wealth",
    "Equities": "equity",
    "Commodities": "macro",
    "Crypto": "crypto",
    "China": "macro",
    "Vietnam": "vietnam_macro",
    "Uncategorized": "macro",
}


def pick_agent_for_article(
    category: str,
    region: str,
    *,
    vietnam_macro_score: float = 0.0,
    vietnam_banking_score: float = 0.0,
    vietnam_wealth_score: float = 0.0,
) -> str:
    """Pick a single agent to minimize duplicate LLM calls per article."""
    if region == "vietnam" or category == "Vietnam":
        scores = {
            "vietnam_banking": vietnam_banking_score,
            "vietnam_macro": vietnam_macro_score,
            "vietnam_real_estate": vietnam_wealth_score,
            "vietnam_equity": vietnam_wealth_score * 0.9,
        }
        best = max(scores, key=scores.get)
        if scores[best] >= 0.12:
            return best
        return "vietnam_macro"

    agent = CATEGORY_AGENT.get(category, "macro")
    if agent not in AGENT_TYPES:
        return "macro"
    return agent

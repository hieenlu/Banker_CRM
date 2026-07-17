"""Global Markets focus — US / Korea / Taiwan · equities, economy, finance, AI, crypto, semis."""

from __future__ import annotations

import re

# Geography signals (mainly US, Korea, Taiwan)
_GEO_US = re.compile(
    r"\b("
    r"u\.?s\.?a?|united states|wall street|america|american|"
    r"federal reserve|\bfed\b|powell|treasury|nasdaq|nyse|s&p|dow|"
    r"sec\b|white house|congress|dollar|\busd\b"
    r")\b",
    re.I,
)
_GEO_KR = re.compile(
    r"\b("
    r"korea|korean|seoul|kospi|kosdaq|samsung|sk[\s-]?hynix|"
    r"hyundai|naver|kakao|won\b|bank of korea|\bbok\b"
    r")\b",
    re.I,
)
_GEO_TW = re.compile(
    r"\b("
    r"taiwan|taiwanese|taipei|taiex|tsmc|taiwan semiconductor|"
    r"mediaTek|mediatek|foxconn|twd\b|central bank of the republic of china"
    r")\b",
    re.I,
)

# Topic signals
_TOPIC_EQUITIES = re.compile(
    r"\b("
    r"stock|stocks|equity|equities|shares|earnings|ipo|rally|selloff|"
    r"nasdaq|nyse|s&p|dow|kospi|kosdaq|taiex|index|etf|portfolio"
    r")\b",
    re.I,
)
_TOPIC_ECONOMY = re.compile(
    r"\b("
    r"economy|economic|gdp|cpi|inflation|recession|jobs|payroll|"
    r"unemployment|pmi|growth|trade|tariff|export|import|consumer"
    r")\b",
    re.I,
)
_TOPIC_FINANCE = re.compile(
    r"\b("
    r"finance|financial|bank|banking|credit|loan|bond|yields?|"
    r"interest rate|mortgage|liquidity|treasury|hedge fund"
    r")\b",
    re.I,
)
_TOPIC_AI = re.compile(
    r"\b("
    r"\bai\b|artificial intelligence|machine learning|openai|chatgpt|"
    r"anthropic|gemini|llm|generative ai|deepseek|copilot"
    r")\b",
    re.I,
)
_TOPIC_CRYPTO = re.compile(
    r"\b("
    r"crypto|bitcoin|btc|ethereum|eth|blockchain|stablecoin|defi|"
    r"solana|coinbase|binance|etf bitcoin"
    r")\b",
    re.I,
)
_TOPIC_SEMI = re.compile(
    r"\b("
    r"semiconductor|semiconductors|chip|chips|foundry|wafer|"
    r"nvidia|nvda|tsmc|broadcom|amd|intel|qualcomm|arm\b|"
    r"sk[\s-]?hynix|micron|asml|gpu|hbm|ai chip"
    r")\b",
    re.I,
)

# Company / ticker proxies often tied to AI or semis
_AI_SEMI_COS = re.compile(
    r"\b("
    r"nvidia|tsmc|samsung|sk[\s-]?hynix|broadcom|amd|intel|apple|"
    r"microsoft|meta|google|alphabet|amazon|tesla|openai|softbank|"
    r"super\s*micro|arm holdings|asml|taiwan semiconductor"
    r")\b",
    re.I,
)

_SOURCE_CRYPTO = ("coindesk", "cointelegraph", "crypto")
_SOURCE_US_MARKETS = ("yahoo", "cnbc", "marketwatch", "bloomberg")


def global_geo_tags(title: str, body: str | None = None, *, source: str = "") -> list[str]:
    blob = f"{title} {body or ''} {source}"
    tags: list[str] = []
    if _GEO_US.search(blob):
        tags.append("US")
    if _GEO_KR.search(blob):
        tags.append("Korea")
    if _GEO_TW.search(blob):
        tags.append("Taiwan")
    src = (source or "").lower()
    if not tags and any(s in src for s in _SOURCE_US_MARKETS):
        tags.append("US")
    if not tags and any(s in src for s in _SOURCE_CRYPTO):
        # crypto is global but often US-listed — keep without forcing geography
        pass
    return tags


def global_topic_tags(
    title: str,
    body: str | None = None,
    *,
    source: str = "",
    category: str = "",
) -> list[str]:
    blob = f"{title} {body or ''} {source} {category}"
    tags: list[str] = []
    if _TOPIC_EQUITIES.search(blob) or category == "Equities":
        tags.append("Equities")
    if _TOPIC_ECONOMY.search(blob) or category in {"Global Macro", "Inflation", "Central Banks"}:
        tags.append("Economy")
    if _TOPIC_FINANCE.search(blob) or category in {"Fixed Income", "FX"}:
        tags.append("Finance")
    if _TOPIC_AI.search(blob) or _AI_SEMI_COS.search(blob):
        tags.append("AI")
    if _TOPIC_CRYPTO.search(blob) or category == "Crypto" or any(
        s in (source or "").lower() for s in _SOURCE_CRYPTO
    ):
        tags.append("Crypto")
    if _TOPIC_SEMI.search(blob) or _AI_SEMI_COS.search(blob):
        tags.append("Semiconductor")
    return tags


def is_global_markets_focus(
    title: str,
    body: str | None = None,
    *,
    source: str = "",
    category: str = "",
    region: str = "global",
) -> bool:
    """
    True when story fits Markets column:
    - Not Vietnam
    - Topic in equities / economy / finance / AI / crypto / semiconductor
    - Prefer US / Korea / Taiwan; also allow topic-only AI/crypto/semi/global finance wires
    """
    if region == "vietnam" or category == "Vietnam":
        return False

    topics = global_topic_tags(title, body, source=source, category=category)
    if not topics:
        return False

    geos = global_geo_tags(title, body, source=source)
    if geos:
        return True

    # Topic-only pass for AI / crypto / semis / mega-caps (global tech complex)
    if any(t in topics for t in ("AI", "Crypto", "Semiconductor")):
        return True

    src = (source or "").lower()
    if any(s in src for s in _SOURCE_US_MARKETS + _SOURCE_CRYPTO):
        return True
    return False


def global_markets_badge(
    title: str,
    body: str | None = None,
    *,
    source: str = "",
    category: str = "",
) -> str | None:
    geos = global_geo_tags(title, body, source=source)
    topics = global_topic_tags(title, body, source=source, category=category)
    if not topics and not geos:
        return None
    parts = geos[:2] + topics[:2]
    return " · ".join(parts) if parts else None

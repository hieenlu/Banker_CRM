"""Vietnam relevance scoring — macro, banking, wealth (rule-based)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from intel_terminal.constants import VIETNAM_RELEVANCE_WEIGHTS

_MACRO_TERMS = (
    "gdp",
    "inflation",
    "cpi",
    "sbv",
    "state bank",
    "monetary",
    "fiscal",
    "budget",
    "trade balance",
    "export",
    "import",
    "fdi",
    "dong",
    "vnd",
    "macro",
    "growth target",
    "pmi vietnam",
)

_BANKING_TERMS = (
    "bank",
    "banking",
    "credit growth",
    "npl",
    "non-performing",
    "lending",
    "deposit",
    "interest rate",
    "techcombank",
    "vietcombank",
    "bidv",
    "mbbank",
    "acb",
    "vpbank",
    "hdbank",
    "capital adequacy",
    "car ratio",
)

_WEALTH_TERMS = (
    "wealth",
    "hnwi",
    "ultra-high",
    "private banking",
    "asset management",
    "family office",
    "luxury",
    "real estate",
    "property",
    "housing",
    "apartment",
    "bất động sản",
    "nhà đất",
    "căn hộ",
    "chung cư",
    "bđs",
    "bond issuance",
    "corporate bond",
    "securities",
    "brokerage",
    "portfolio",
    "affluent",
)

# Display / ingest focus: finance, economy, real estate only
_SECTOR_FINANCE = re.compile(
    r"(bank|banking|finance|financial|interest\s*rate|credit|deposit|npl|"
    r"stock|equity|securities|brokerage|bond|ipo|vn-?index|sbv|hocse|"
    r"ngân\s*hàng|lai\s*suất|lãi\s*suất|tín\s*dụng|tin\s*dung|"
    r"chứng\s*khoán|chung\s*khoan|cổ\s*phiếu|co\s*phieu|"
    r"trái\s*phiếu|trai\s*phieu|tài\s*chính|tai\s*chinh|thanh\s*khoản|"
    r"thanh\s*khoan|lợi\s*nhuận|loi\s*nhuan)",
    re.I,
)
_SECTOR_ECONOMY = re.compile(
    r"(economy|economic|gdp|cpi|inflation|export|import|fdi|trade|pmi|"
    r"macro|fiscal|monetary|growth|dong|\bvnd\b|business|"
    r"kinh\s*tế|kinh\s*te|kinh\s*doanh|lạm\s*phát|lam\s*phat|"
    r"xuất\s*khẩu|xuat\s*khau|nhập\s*khẩu|nhap\s*khau|"
    r"tăng\s*trưởng|tang\s*truong|ngân\s*sách|ngan\s*sach|"
    r"tỷ\s*giá|ty\s*gia|thị\s*trường|thi\s*truong)",
    re.I,
)
_SECTOR_REAL_ESTATE = re.compile(
    r"(real\s*estate|property|housing|apartment|condo|"
    r"bất\s*động\s*sản|bat\s*dong\s*san|nhà\s*đất|nha\s*dat|"
    r"căn\s*hộ|can\s*ho|chung\s*cư|chung\s*cu|dự\s*án|du\s*an|"
    r"\bbđs\b|\bbds\b|đất\s*nền|dat\s*nen)",
    re.I,
)

# Known Vietnam finance / economy / RE outlet names → default sector tags
_SOURCE_SECTOR: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("bat dong san", ("Real estate",)),
    ("bất động sản", ("Real estate",)),
    ("real estate", ("Real estate",)),
    ("chung khoan", ("Finance",)),
    ("chứng khoán", ("Finance",)),
    ("tai chinh ngan hang", ("Finance",)),
    ("tài chính ngân hàng", ("Finance",)),
    ("vi mo", ("Economy",)),
    ("vĩ mô", ("Economy",)),
    ("cafef chung khoan", ("Finance",)),
    ("cafef tai chinh", ("Finance",)),
    ("cafef vi mo", ("Economy",)),
    ("cafef bat dong san", ("Real estate",)),
    ("vietstock", ("Finance", "Economy")),
    ("kinh doanh", ("Finance", "Economy")),
    ("kinh te", ("Economy",)),
    ("kinh tế", ("Economy",)),
    ("vnexpress", ("Finance", "Economy")),
    ("vietnamnet", ("Finance", "Economy")),
    ("tuoi tre", ("Finance", "Economy")),
    ("vietnam news", ("Economy",)),
    ("vn finance", ("Finance", "Economy")),
)


def vietnam_sector_tags(
    title: str,
    body: str | None = None,
    *,
    source: str = "",
    macro: float = 0.0,
    banking: float = 0.0,
    wealth: float = 0.0,
) -> list[str]:
    """Tags for Vietnam sector focus: Finance, Economy, Real estate."""
    blob = f"{title} {body or ''} {source}"
    tags: list[str] = []
    src_l = (source or "").lower()

    for needle, defaults in _SOURCE_SECTOR:
        if needle in src_l:
            for t in defaults:
                if t not in tags:
                    tags.append(t)

    if _SECTOR_FINANCE.search(blob) or banking >= 0.12:
        if "Finance" not in tags:
            tags.append("Finance")
    if _SECTOR_ECONOMY.search(blob) or macro >= 0.12:
        if "Economy" not in tags:
            tags.append("Economy")
    if _SECTOR_REAL_ESTATE.search(blob) or wealth >= 0.28:
        if "Real estate" not in tags:
            tags.append("Real estate")

    # Vietnam-region pieces from business feeds still count as Economy if untagged
    if not tags and any(
        x in src_l
        for x in (
            "vnexpress",
            "vietnamnet",
            "tuoi tre",
            "vietnam news",
            "cafef chung",
            "cafef tai",
            "cafef vi",
            "cafef bat",
        )
    ):
        tags.append("Economy")
    return tags


@dataclass(frozen=True)
class VietnamScores:
    macro: float
    banking: float
    wealth: float
    composite: float


def _score_terms(blob: str, terms: tuple[str, ...], *, region_boost: float) -> float:
    hits = 0
    for term in terms:
        if " " in term:
            if term in blob:
                hits += 1
        elif re.search(rf"\b{re.escape(term)}\b", blob):
            hits += 1
    if hits == 0:
        return 0.0
    raw = min(1.0, hits * 0.18) + region_boost
    return min(1.0, raw)


def score_vietnam_relevance(
    title: str,
    body: str | None = None,
    *,
    source: str = "",
    region: str = "global",
    category: str = "",
) -> VietnamScores:
    blob = f"{title} {body or ''} {source} {category}".lower()
    boost = 0.15 if region == "vietnam" else 0.0
    if category == "Vietnam":
        boost += 0.12

    macro = _score_terms(blob, _MACRO_TERMS, region_boost=boost)
    banking = _score_terms(blob, _BANKING_TERMS, region_boost=boost)
    wealth = _score_terms(blob, _WEALTH_TERMS, region_boost=boost)

    w = VIETNAM_RELEVANCE_WEIGHTS
    composite = (
        macro * w["macro_importance"]
        + banking * w["banking_impact"]
        + wealth * w["wealth_management_relevance"]
        + max(macro, banking, wealth) * w["market_impact"]
    ) / (sum(w.values()))
    composite = min(1.0, composite)

    return VietnamScores(macro=macro, banking=banking, wealth=wealth, composite=composite)

"""RSS feed registry — global + Vietnam + optional APIs."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FeedSource:
    key: str
    name: str
    url: str
    region: str  # global | vietnam | crypto
    quality_weight: float = 0.7
    language: str = "en"


# --- Global: US / Korea / Taiwan · equities, economy, finance, AI, crypto, semis ---
GLOBAL_FEEDS: tuple[FeedSource, ...] = (
    FeedSource("yahoo_finance", "Yahoo Finance", "https://finance.yahoo.com/news/rssindex", "global", 0.75),
    FeedSource(
        "cnbc_markets",
        "CNBC Markets",
        "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
        "global",
        0.80,
    ),
    FeedSource(
        "marketwatch",
        "MarketWatch",
        "https://feeds.marketwatch.com/marketwatch/topstories/",
        "global",
        0.72,
    ),
    FeedSource(
        "bloomberg_markets",
        "Bloomberg Markets",
        "https://feeds.bloomberg.com/markets/news.rss",
        "global",
        0.84,
    ),
    FeedSource(
        "google_us_equities",
        "US Equities",
        "https://news.google.com/rss/search?q=(US+OR+%22Wall+Street%22)+(stocks+OR+equities+OR+Nasdaq+OR+%22S%26P%22)"
        "+when:3d&hl=en-US&gl=US&ceid=US:en",
        "global",
        0.78,
    ),
    FeedSource(
        "google_korea_markets",
        "Korea Markets",
        "https://news.google.com/rss/search?q=(Korea+OR+Samsung+OR+%22SK+Hynix%22+OR+Kospi)"
        "+(stock+OR+economy+OR+finance+OR+semiconductor)+when:7d&hl=en-US&gl=US&ceid=US:en",
        "global",
        0.80,
    ),
    FeedSource(
        "google_taiwan_semis",
        "Taiwan & Semis",
        "https://news.google.com/rss/search?q=(Taiwan+OR+TSMC)+(stock+OR+semiconductor+OR+chip+OR+economy)"
        "+when:7d&hl=en-US&gl=US&ceid=US:en",
        "global",
        0.82,
    ),
    FeedSource(
        "google_ai_tech",
        "AI & Tech",
        "https://news.google.com/rss/search?q=(AI+OR+%22artificial+intelligence%22+OR+Nvidia+OR+OpenAI)"
        "+(stock+OR+earnings+OR+chip)+when:3d&hl=en-US&gl=US&ceid=US:en",
        "global",
        0.82,
    ),
)

CRYPTO_FEEDS: tuple[FeedSource, ...] = (
    FeedSource(
        "coindesk",
        "CoinDesk",
        "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "crypto",
        0.78,
    ),
    FeedSource(
        "cointelegraph",
        "CoinTelegraph",
        "https://cointelegraph.com/rss",
        "crypto",
        0.72,
    ),
)

# --- Vietnam: finance / economy / real estate only (URLs verified 2026) ---
VIETNAM_NEWS_FEEDS: tuple[FeedSource, ...] = (
    FeedSource(
        "vnexpress_business",
        "VnExpress Kinh doanh",
        "https://vnexpress.net/rss/kinh-doanh.rss",
        "vietnam",
        0.86,
        "vi",
    ),
    FeedSource(
        "vietnamnet_business",
        "VietnamNet Kinh doanh",
        "https://vietnamnet.vn/rss/kinh-doanh.rss",
        "vietnam",
        0.84,
        "vi",
    ),
    FeedSource(
        "tuoitre_business",
        "Tuoi Tre Kinh doanh",
        "https://tuoitre.vn/rss/kinh-doanh.rss",
        "vietnam",
        0.82,
        "vi",
    ),
    FeedSource(
        "vietnamnews_economy",
        "Vietnam News Economy",
        "https://vietnamnews.vn/rss/economy.rss",
        "vietnam",
        0.80,
        "en",
    ),
    FeedSource(
        "vietnamnet_realestate",
        "VietnamNet Bat dong san",
        "https://vietnamnet.vn/rss/bat-dong-san.rss",
        "vietnam",
        0.78,
        "vi",
    ),
    FeedSource(
        "cafef_stocks",
        "CafeF Chung khoan",
        "https://cafef.vn/thi-truong-chung-khoan.rss",
        "vietnam",
        0.86,
        "vi",
    ),
    FeedSource(
        "cafef_banking",
        "CafeF Tai chinh ngan hang",
        "https://cafef.vn/tai-chinh-ngan-hang.rss",
        "vietnam",
        0.86,
        "vi",
    ),
    FeedSource(
        "cafef_macro",
        "CafeF Vi mo dau tu",
        "https://cafef.vn/vi-mo-dau-tu.rss",
        "vietnam",
        0.84,
        "vi",
    ),
    FeedSource(
        "cafef_realestate",
        "CafeF Bat dong san",
        "https://cafef.vn/bat-dong-san.rss",
        "vietnam",
        0.84,
        "vi",
    ),
    FeedSource(
        "google_vn_finance_economy",
        "VN Finance & Economy",
        "https://news.google.com/rss/search?q="
        "(Vietnam+OR+Vi%E1%BB%87t+Nam)+(finance+OR+banking+OR+economy+OR+GDP+OR+SBV+OR+VN-Index"
        "+OR+ng%C3%A2n+h%C3%A0ng+OR+kinh+t%E1%BA%BF)&hl=vi&gl=VN&ceid=VN:vi",
        "vietnam",
        0.84,
        "vi",
    ),
    FeedSource(
        "google_vn_realestate",
        "VN Real Estate",
        "https://news.google.com/rss/search?q="
        "(Vietnam+OR+Vi%E1%BB%87t+Nam)+(real+estate+OR+property+OR+%22b%E1%BA%A5t+%C4%91%E1%BB%99ng+s%E1%BA%A3n%22"
        "+OR+nh%C3%A0+%C4%91%E1%BA%A5t)&hl=vi&gl=VN&ceid=VN:vi",
        "vietnam",
        0.80,
        "vi",
    ),
)

# Legacy official feeds — disabled (RSS endpoints broken); kept for reference
VIETNAM_OFFICIAL_FEEDS: tuple[FeedSource, ...] = ()


def vietnam_feeds() -> list[FeedSource]:
    return list(VIETNAM_NEWS_FEEDS) + list(VIETNAM_OFFICIAL_FEEDS)


def all_feeds(*, include_official: bool = True) -> list[FeedSource]:
    feeds: list[FeedSource] = list(GLOBAL_FEEDS) + list(CRYPTO_FEEDS) + list(VIETNAM_NEWS_FEEDS)
    if include_official:
        feeds.extend(VIETNAM_OFFICIAL_FEEDS)
    return feeds


def feeds_by_region(region: str | None = None) -> list[FeedSource]:
    if region is None:
        return all_feeds()
    if region == "vietnam":
        return vietnam_feeds()
    if region == "crypto":
        return [f for f in all_feeds() if f.region == "crypto"]
    if region == "global":
        return list(GLOBAL_FEEDS)
    return [f for f in all_feeds() if f.region == region]

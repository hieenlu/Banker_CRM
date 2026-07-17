"""Global markets focus filter tests."""

from __future__ import annotations

from intel_terminal.pipeline.global_focus import (
    global_geo_tags,
    global_markets_badge,
    global_topic_tags,
    is_global_markets_focus,
)
from intel_terminal.sources.feeds import GLOBAL_FEEDS


def test_us_equity_passes():
    title = "Nasdaq jumps as Nvidia leads chip rally"
    assert is_global_markets_focus(title, source="CNBC Markets")
    assert "US" in global_geo_tags(title, source="CNBC Markets") or "Semiconductor" in global_topic_tags(title)
    assert "AI" in global_topic_tags(title) or "Semiconductor" in global_topic_tags(title)


def test_korea_samsung_passes():
    title = "Samsung and SK Hynix lift Kospi on AI chip demand"
    assert is_global_markets_focus(title)
    assert "Korea" in global_geo_tags(title)
    assert "Semiconductor" in global_topic_tags(title)


def test_taiwan_tsmc_passes():
    title = "TSMC raises capex outlook as AI demand surges"
    assert is_global_markets_focus(title)
    assert "Taiwan" in global_geo_tags(title)


def test_crypto_passes():
    title = "Bitcoin holds above $100,000 as ETF inflows accelerate"
    assert is_global_markets_focus(title, source="CoinDesk", category="Crypto")
    assert "Crypto" in global_topic_tags(title, source="CoinDesk", category="Crypto")


def test_vietnam_excluded():
    assert not is_global_markets_focus(
        "VN-Index rises on banking stocks",
        region="vietnam",
        category="Vietnam",
    )


def test_unrelated_lifestyle_excluded():
    assert not is_global_markets_focus("Best travel destinations for summer vacation", source="Lifestyle")


def test_global_feeds_cover_focus_regions():
    keys = {f.key for f in GLOBAL_FEEDS}
    assert "google_korea_markets" in keys
    assert "google_taiwan_semis" in keys
    assert "google_ai_tech" in keys
    assert "bbc_business" not in keys


def test_badge_format():
    badge = global_markets_badge("Fed holds rates as inflation cools", source="Bloomberg Markets")
    assert badge
    assert "US" in badge or "Economy" in badge or "Finance" in badge

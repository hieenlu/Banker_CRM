"""Vietnam feed registry sanity checks."""

from __future__ import annotations

from intel_terminal.pipeline.vietnam import vietnam_sector_tags
from intel_terminal.sources.feeds import VIETNAM_NEWS_FEEDS, feeds_by_region, vietnam_feeds


def test_vietnam_feeds_non_empty():
    feeds = vietnam_feeds()
    assert len(feeds) >= 6
    assert all(f.region == "vietnam" for f in feeds)


def test_feeds_by_region_vietnam_only():
    vn = feeds_by_region("vietnam")
    global_feeds = feeds_by_region("global")
    assert len(vn) == len(VIETNAM_NEWS_FEEDS)
    assert not any(f.key in {g.key for g in global_feeds} for f in vn)


def test_vietnam_feeds_are_sector_focused():
    keys = {f.key for f in VIETNAM_NEWS_FEEDS}
    assert "vietnamnet_realestate" in keys
    assert "google_vn_finance_economy" in keys
    assert "google_vn_realestate" in keys
    assert "cafef_stocks" in keys
    assert "cafef_banking" in keys
    assert "cafef_realestate" in keys
    assert "cafef_home" not in keys
    assert "tuoitre_business" in keys
    assert "tuoitre_economy" not in keys


def test_vietnam_sector_tags_finance_economy_re():
    assert "Finance" in vietnam_sector_tags("Lãi suất ngân hàng hôm nay", banking=0.0)
    assert "Economy" in vietnam_sector_tags("GDP tăng trưởng quý II", macro=0.0)
    assert "Real estate" in vietnam_sector_tags("Giá chung cư Hà Nội tăng", wealth=0.0)
    # Business outlet name implies finance/economy coverage
    tagged = vietnam_sector_tags("Tin mới trong ngày", source="VnExpress Kinh doanh")
    assert "Economy" in tagged or "Finance" in tagged
    assert vietnam_sector_tags("Ca sĩ ra mắt MV mới", source="Entertainment Daily") == []

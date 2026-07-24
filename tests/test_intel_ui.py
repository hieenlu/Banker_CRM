"""UI navigation smoke tests."""

from __future__ import annotations

from intel_terminal.ui.render import INTEL_PAGES
from intel_terminal.ui.x_feeds import X_PROFILE_META, _filter_posts
from scraper import X_FEEDS_CACHE_KEY, X_PROFILES_DEFAULT, _nitter_link_to_x


def test_intel_pages_include_briefing_and_archive():
    assert INTEL_PAGES == ("Dashboard", "Latest News", "Briefing & AI", "Archive")
    assert "Vietnam" not in INTEL_PAGES
    assert "Settings" not in INTEL_PAGES


def test_x_analyst_profiles_default():
    assert X_PROFILES_DEFAULT == ["KobeissiLetter", "citrini"]
    assert set(X_PROFILE_META) == {"KobeissiLetter", "citrini"}
    assert "KobeissiLetter" in X_FEEDS_CACHE_KEY


def test_nitter_link_rewrites_to_x():
    assert (
        _nitter_link_to_x("https://nitter.net/KobeissiLetter/status/1", "KobeissiLetter")
        == "https://x.com/KobeissiLetter/status/1"
    )
    assert (
        _nitter_link_to_x("https://nitter.privacydev.net/citrini/status/9", "citrini")
        == "https://x.com/citrini/status/9"
    )
    assert (
        _nitter_link_to_x("https://rss.xcancel.com/citrini/status/9", "citrini")
        == "https://x.com/citrini/status/9"
    )
    assert _nitter_link_to_x("https://x.com/citrini/status/9", "citrini") == "https://x.com/citrini/status/9"
    assert _nitter_link_to_x("https://rss.xcancel.com/KobeissiLetter/rss", "KobeissiLetter") == (
        "https://x.com/KobeissiLetter"
    )


def test_snowflake_and_jina_cleanup():
    from scraper import (
        _clean_jina_post_body,
        _is_usable_x_headline,
        _parse_jina_profile_markdown,
        _snowflake_to_iso,
        _status_id_from_link,
    )

    sid = _status_id_from_link("https://x.com/KobeissiLetter/status/2079213251372646426")
    assert sid == 2079213251372646426
    assert _snowflake_to_iso(sid).startswith("2026-07-20T")

    cleaned = _clean_jina_post_body(
        'BREAKING: Alphabet, [$GOOGL](https://x.com/search?q=$GOOGL), launches a chip. '
        "Show more   121 0 1 2 1 135 0 1 3 5 1.7K 0 1.7 K [](https://x.com/x)"
    )
    assert "$GOOGL" in cleaned
    assert "Show more" not in cleaned
    assert "1.7K" not in cleaned
    assert cleaned.startswith("BREAKING: Alphabet")

    cleaned_nl = _clean_jina_post_body(
        "ETFs launched   26 0 2 6 18 0 1 8 746 0 7 4 6 "
        "[](https://x.com/citrini/status/1/quotes)"
        "[99K 0 9 9 K](https://x.com/citrini/status/1/quotes)\n* Citrini @citrini"
    )
    assert cleaned_nl == "ETFs launched"
    assert not _is_usable_x_headline("Citrini @citrini", "citrini")
    assert not _is_usable_x_headline("RSS reader not yet whitelisted!", "citrini")

    sample = (
        "[7h](https://x.com/KobeissiLetter/status/2080443353355743663) "
        "BREAKING: Markets rally on soft CPI. 147 315 3.8K "
        "[](https://x.com/KobeissiLetter/status/2080443353355743663/quotes)"
        "[341K](https://x.com/KobeissiLetter/status/2080443353355743663/quotes) "
        "* [The Kobeissi Letter](https://x.com/KobeissiLetter) "
        "[@KobeissiLetter](https://x.com/KobeissiLetter) "
        "[8h](https://x.com/KobeissiLetter/status/2080424539360571422) "
        "BREAKING: Intel beats earnings expectations. "
    )
    parsed = _parse_jina_profile_markdown(sample, "KobeissiLetter", limit=5)
    assert len(parsed) == 2
    assert parsed[0]["link"].endswith("2080443353355743663")
    assert "soft CPI" in parsed[0]["headline"]
    assert "The Kobeissi Letter" not in parsed[0]["headline"]



def test_filter_x_posts_by_handle():
    posts = [
        {"headline": "a", "handle": "KobeissiLetter", "link": "1"},
        {"headline": "b", "source": "X @citrini", "link": "2"},
    ]
    assert len(_filter_posts(posts, "All")) == 2
    assert [p["headline"] for p in _filter_posts(posts, "citrini")] == ["b"]
    assert [p["headline"] for p in _filter_posts(posts, "KobeissiLetter")] == ["a"]

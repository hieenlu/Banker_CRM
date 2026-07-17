"""Module 2: normalize + dedup unit tests."""

from __future__ import annotations

from intel_terminal.pipeline.dedup import deduplicate_drafts, headline_similarity
from datetime import datetime, timezone

from intel_terminal.pipeline.normalize import ArticleDraft, normalize_feed_entry, normalize_url, url_hash
from intel_terminal.sources.feeds import FeedSource


def _draft(title: str, url: str, source: str = "Test") -> ArticleDraft:
    return ArticleDraft(
        url=url,
        url_hash=url_hash(url),
        canonical_url=normalize_url(url),
        title=title,
        source=source,
        published_at=None,
        body_text="snippet",
        body_fetch_status="snippet_only",
        region="global",
        language="en",
        feed_key="test",
        source_quality=0.7,
    )


def test_normalize_url_strips_tracking():
    raw = "https://www.example.com/news/foo?utm_source=twitter&id=1"
    norm = normalize_url(raw)
    assert "utm_source" not in norm
    assert norm.startswith("https://example.com/")


def test_url_hash_stable():
    a = url_hash("https://Example.com/path/")
    b = url_hash("https://example.com/path")
    assert a == b


def test_normalize_feed_entry():
    feed = FeedSource("test", "Test Source", "https://example.com/rss", "global")
    entry = {
        "title": "Fed holds rates steady amid inflation concerns",
        "link": "https://example.com/article-1",
        "summary": "<p>Markets reacted calmly.</p>",
        "published": "Mon, 01 Jun 2026 10:00:00 GMT",
    }
    draft = normalize_feed_entry(entry, feed)
    assert draft is not None
    assert draft.title.startswith("Fed holds")
    assert draft.body_text is not None
    assert "Markets" in draft.body_text
    assert draft.source == "Test Source"
    assert draft.published_at is not None
    assert draft.published_at.tzinfo is None


def test_parse_tuoitre_us_style_datetime():
    from intel_terminal.pipeline.normalize import _parse_datetime

    dt = _parse_datetime("7/17/2026 7:56:00\u202fPM")
    assert dt is not None
    assert dt.year == 2026
    assert dt.month == 7
    assert dt.day == 17


def test_normalize_datetime_is_naive_utc():
    feed = FeedSource("test", "Test", "https://example.com/rss", "global")
    aware = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
    draft = normalize_feed_entry(
        {"title": "Markets open higher on rate outlook", "link": "https://example.com/x", "published": aware},
        feed,
    )
    assert draft is not None
    assert draft.published_at == datetime(2026, 6, 1, 12, 0)
    assert draft.published_at.tzinfo is None


def test_headline_similarity_near_duplicates():
    a = "US stocks rise as Fed signals pause on rate hikes"
    b = "US stocks rise as Federal Reserve signals pause on rates"
    assert headline_similarity(a, b) >= 0.5


def test_deduplicate_by_url_and_headline():
    drafts = [
        _draft("Apple earnings beat estimates", "https://a.com/1"),
        _draft("Apple earnings beat estimates", "https://a.com/1?utm=1"),
        _draft("Apple earnings beat estimates badly", "https://b.com/2"),
    ]
    unique, removed = deduplicate_drafts(drafts, similarity_threshold=0.88)
    assert removed >= 1
    assert len(unique) <= 2

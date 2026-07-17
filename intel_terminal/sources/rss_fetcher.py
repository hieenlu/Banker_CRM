"""RSS fetcher using http_fetch (requests + robust SSL)."""

from __future__ import annotations

import logging
from typing import Any

import feedparser

from intel_terminal.config import load_config
from intel_terminal.sources.feeds import FeedSource, all_feeds
from intel_terminal.sources.http_fetch import fetch_url

logger = logging.getLogger(__name__)


def _parse_feed(data: bytes, feed: FeedSource) -> list[dict[str, Any]]:
    parsed = feedparser.parse(data)
    entries: list[dict[str, Any]] = []
    for entry in parsed.entries[:50]:
        entries.append(
            {
                "title": getattr(entry, "title", ""),
                "link": getattr(entry, "link", "") or getattr(entry, "id", ""),
                "summary": getattr(entry, "summary", ""),
                "description": getattr(entry, "description", ""),
                "published": getattr(entry, "published", None) or getattr(entry, "published_parsed", None),
                "updated": getattr(entry, "updated", None) or getattr(entry, "updated_parsed", None),
                "author": getattr(entry, "author", None),
                "tags": [getattr(t, "term", "") for t in getattr(entry, "tags", [])],
            }
        )
    if parsed.bozo and not entries:
        logger.warning("Feed parse warning for %s: %s", feed.key, parsed.bozo_exception)
    return entries


def fetch_all_feeds_sync(
    feeds: list[FeedSource] | None = None,
) -> list[tuple[FeedSource, list[dict[str, Any]], str | None]]:
    """Blocking RSS fetch (sequential, reliable SSL)."""
    cfg = load_config()
    feed_list = feeds or all_feeds()
    results: list[tuple[FeedSource, list[dict[str, Any]], str | None]] = []

    for feed in feed_list:
        data, err = fetch_url(
            feed.url,
            timeout=cfg.request_timeout_sec,
            user_agent=cfg.user_agent,
        )
        if err or not data:
            results.append((feed, [], err or "empty response"))
            continue
        try:
            entries = _parse_feed(data, feed)
            if not entries:
                results.append((feed, [], "empty feed"))
            else:
                results.append((feed, entries, None))
        except Exception as exc:
            results.append((feed, [], str(exc)))

    return results

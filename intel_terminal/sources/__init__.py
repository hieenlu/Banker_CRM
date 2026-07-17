"""RSS / API news source adapters (Module 2)."""

from intel_terminal.sources.feeds import all_feeds, feeds_by_region
from intel_terminal.sources.rss_fetcher import fetch_all_feeds_sync

__all__ = ["all_feeds", "feeds_by_region", "fetch_all_feeds_sync"]

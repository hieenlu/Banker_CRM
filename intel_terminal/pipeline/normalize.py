"""Normalize raw RSS entries into pipeline article drafts."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlparse

from intel_terminal.sources.feeds import FeedSource


@dataclass
class ArticleDraft:
    url: str
    url_hash: str
    canonical_url: str
    title: str
    source: str
    published_at: datetime | None
    body_text: str | None
    body_fetch_status: str
    region: str
    language: str | None
    feed_key: str
    source_quality: float
    raw_metadata: dict[str, Any] = field(default_factory=dict)


_TRACKING_PARAMS = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "fbclid",
        "gclid",
        "mc_cid",
        "mc_eid",
    }
)


def normalize_url(url: str) -> str:
    """Strip tracking params and normalize host for dedup."""
    u = (url or "").strip()
    if not u:
        return ""
    try:
        from urllib.parse import parse_qsl, urlencode, urlunparse

        parsed = urlparse(u)
        host = (parsed.netloc or "").lower()
        if host.startswith("www."):
            host = host[4:]
        q_pairs = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k.lower() not in _TRACKING_PARAMS]
        query = urlencode(q_pairs)
        path = parsed.path.rstrip("/") or "/"
        return urlunparse((parsed.scheme.lower(), host, path, "", query, ""))
    except Exception:
        return u.lower().rstrip("/")


def url_hash(url: str) -> str:
    norm = normalize_url(url)
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def to_naive_utc(dt: datetime) -> datetime:
    """Store/compare as naive UTC (SQLite DateTime columns are timezone-naive)."""
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _normalize_date_text(text: str) -> str:
    # Tuoi Tre / Windows feeds often use narrow no-break space before AM/PM
    return (
        text.replace("\u202f", " ")
        .replace("\xa0", " ")
        .replace("\u2009", " ")
        .strip()
    )


def _parse_datetime(raw: Any) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        if raw.tzinfo is None:
            return raw
        return raw.astimezone(timezone.utc).replace(tzinfo=None)
    if hasattr(raw, "tm_year"):
        try:
            return datetime(*raw[:6], tzinfo=timezone.utc).replace(tzinfo=None)
        except Exception:
            pass
    text = _normalize_date_text(str(raw))
    if not text:
        return None
    # CafeF etc. emit "+07" — RFC822 parsers want "+0700"
    text = re.sub(r"([+-])(\d{2})$", r"\g<1>\g<2>00", text)

    try:
        dt = parsedate_to_datetime(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    except Exception:
        pass

    for fmt in (
        "%m/%d/%Y %I:%M:%S %p",
        "%m/%d/%Y %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            dt = datetime.strptime(text, fmt)
            if dt.tzinfo is None:
                # Local VN wall times without TZ: treat as ICT (+07)
                if fmt.startswith("%m/%d"):
                    from datetime import timedelta

                    dt = dt.replace(tzinfo=timezone(timedelta(hours=7)))
                else:
                    dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        except Exception:
            continue
    return None


def _clean_text(text: str) -> str:
    s = re.sub(r"<[^>]+>", " ", text or "")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def normalize_feed_entry(entry: dict[str, Any], feed: FeedSource) -> ArticleDraft | None:
    """Map feedparser entry dict to ArticleDraft."""
    link = str(entry.get("link") or entry.get("id") or "").strip()
    title = _clean_text(str(entry.get("title") or ""))
    if not link or not title or len(title) < 8:
        return None

    summary = _clean_text(
        str(
            entry.get("summary")
            or entry.get("description")
            or entry.get("content")
            or ""
        )
    )
    published = _parse_datetime(entry.get("published") or entry.get("updated"))
    canonical = normalize_url(link)

    return ArticleDraft(
        url=link,
        url_hash=url_hash(link),
        canonical_url=canonical,
        title=title[:500],
        source=feed.name,
        published_at=published,
        body_text=summary[:8000] if summary else None,
        body_fetch_status="snippet_only" if summary else "pending",
        region=feed.region if feed.region != "crypto" else "global",
        language=feed.language,
        feed_key=feed.key,
        source_quality=feed.quality_weight,
        raw_metadata={
            "feed_key": feed.key,
            "tags": entry.get("tags") or [],
            "author": entry.get("author"),
        },
    )


def drafts_to_metadata_json(draft: ArticleDraft) -> str:
    return json.dumps(draft.raw_metadata, ensure_ascii=False, default=str)

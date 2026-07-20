from __future__ import annotations

import json
import time
import re
from email.utils import parsedate_to_datetime
from datetime import date, datetime, timezone
from typing import Any
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import NewsCache
from utils import keywords_hash


NEWS_TIMEOUT_SECS = 20
USER_AGENT = "BankerCRM/1.0 (local personal project; contact: none)"
X_PROFILES_DEFAULT = ["KobeissiLetter", "citrini"]
# Public Nitter mirrors — tried in order; first success wins.
NITTER_RSS_HOSTS = (
    "https://nitter.net",
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
    "https://nitter.cz",
)


STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "to",
    "of",
    "for",
    "in",
    "on",
    "at",
    "with",
    "by",
    "from",
    "as",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "will",
    "would",
    "could",
    "should",
    "may",
    "might",
    "this",
    "that",
    "these",
    "those",
    "it",
    "its",
    "into",
    "over",
    "under",
    "after",
    "before",
    "up",
    "down",
    "out",
    "about",
    "market",
    "markets",
    "news",
}


def _core_topic_tags(text: str) -> list[str]:
    s = (text or "").lower()
    tags: list[str] = []

    def add(tag: str) -> None:
        if tag not in tags:
            tags.append(tag)

    if any(k in s for k in ["inflation", "cpi", "ppi", "pce", "price pressure", "deflation"]):
        add("inflation")
    if any(k in s for k in ["economy", "economic", "gdp", "recession", "pmi", "jobs", "employment", "growth"]):
        add("economics")
    if any(k in s for k in ["fed", "fomc", "rate cut", "rate hike", "interest rate", "hawkish", "dovish"]):
        add("monetary-policy")
    if any(k in s for k in ["yield", "treasury", "bond", "credit spread"]):
        add("fixed-income")
    if any(k in s for k in ["s&p", "sp500", "nasdaq", "dow", "equity", "stock", "shares"]):
        add("equities")
    if any(k in s for k in ["oil", "crude", "gold", "xau", "silver", "commodity", "natural gas"]):
        add("commodities")
    if any(k in s for k in ["bitcoin", "btc", "ethereum", "eth", "crypto", "altcoin"]):
        add("crypto")
    if any(k in s for k in ["dollar", "usd", "eur", "jpy", "fx", "forex", "currency"]):
        add("fx")
    if any(k in s for k in ["bank", "liquidity", "deposit", "credit", "default"]):
        add("banking")
    if any(k in s for k in ["earnings", "eps", "guidance", "revenue", "profit"]):
        add("earnings")
    if any(k in s for k in ["war", "sanction", "tariff", "geopolitical", "middle east", "china", "russia"]):
        add("geopolitics")

    return tags or ["markets"]


def _headline_tags(headline: str, max_tags: int = 4) -> list[str]:
    text = (headline or "").lower()
    tokens = re.findall(r"[a-z0-9]{3,}", text)
    tags: list[str] = []
    seen: set[str] = set()
    for t in tokens:
        if t in STOPWORDS:
            continue
        if t in seen:
            continue
        seen.add(t)
        tags.append(t)
        if len(tags) >= max_tags:
            break
    return tags


def _parse_pubdate(raw: str | None) -> str:
    if not raw:
        return ""
    try:
        dt = parsedate_to_datetime(raw)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return raw.strip()


def scrape_google_news_rss(keyword: str, limit: int = 10) -> list[dict[str, Any]]:
    q = quote_plus(keyword.strip())
    url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=NEWS_TIMEOUT_SECS)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.content, "xml")
    items = soup.find_all("item")

    results: list[dict[str, Any]] = []
    for item in items[:limit]:
        title_tag = item.find("title")
        link_tag = item.find("link")
        pub_tag = item.find("pubDate")
        title = title_tag.get_text(strip=True) if title_tag else ""
        link = link_tag.get_text(strip=True) if link_tag else ""
        if link.startswith("https://nitter.net/") or link.startswith("http://nitter.net/"):
            link = link.replace("http://nitter.net/", "https://x.com/").replace("https://nitter.net/", "https://x.com/")
        date_s = _parse_pubdate(pub_tag.get_text(strip=True) if pub_tag else None)
        if title and link:
            results.append(
                {
                    "headline": title,
                    "source": "Google News",
                    "date": date_s,
                    "link": link,
                    "tags": _headline_tags(title),
                }
            )
    return results


def scrape_yahoo_finance_news(keyword: str, limit: int = 10) -> list[dict[str, Any]]:
    q = quote_plus(keyword.strip())
    url = f"https://finance.yahoo.com/news/search/?p={q}"
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=NEWS_TIMEOUT_SECS)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Yahoo markup changes often; use a heuristic: grab anchors to "/news/" and use text as headline.
    candidates = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href.startswith("/news/"):
            continue
        headline = a.get_text(" ", strip=True)
        if not headline or len(headline) < 8:
            continue

        # Attempt to find nearby date info in a <time datetime="..."> element.
        date_s = ""
        time_tag = None
        # Search upward a bit for a time element.
        parent = a
        for _ in range(4):
            if parent is None:
                break
            maybe = parent.find("time")
            if maybe and maybe.get("datetime"):
                time_tag = maybe
                break
            parent = parent.parent if hasattr(parent, "parent") else None
        if time_tag and time_tag.get("datetime"):
            # datetime is typically ISO-8601.
            try:
                date_s = time_tag["datetime"][:10]
            except Exception:
                date_s = ""

        full_link = "https://finance.yahoo.com" + href
        candidates.append(
            {
                "headline": headline,
                "source": "Yahoo Finance",
                "date": date_s,
                "link": full_link,
                "tags": _headline_tags(headline),
            }
        )

    # Deduplicate by link while preserving order.
    seen: set[str] = set()
    results: list[dict[str, Any]] = []
    for c in candidates:
        if c["link"] in seen:
            continue
        seen.add(c["link"])
        results.append(c)
        if len(results) >= limit:
            break
    return results


def _nitter_link_to_x(link: str, handle: str) -> str:
    """Rewrite Nitter post URLs to x.com so readers land on the public profile."""
    raw = (link or "").strip()
    if not raw:
        return f"https://x.com/{handle}"
    lowered = raw.lower()
    for marker in ("https://", "http://"):
        if not lowered.startswith(marker):
            continue
        rest = raw[len(marker) :]
        host, sep, path = rest.partition("/")
        host_l = host.lower()
        if host_l == "nitter.net" or host_l.startswith("nitter."):
            return f"https://x.com/{path}" if sep and path else f"https://x.com/{handle}"
        break
    return raw


def _status_id_from_link(link: str) -> int | None:
    m = re.search(r"/status/(\d+)", link or "")
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def _snowflake_to_iso(status_id: int) -> str:
    """Convert an X snowflake status id to a UTC ISO timestamp."""
    # Twitter epoch: 2010-11-04T01:42:54.657Z
    ms = (status_id >> 22) + 1288834974657
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _looks_like_rss(content: bytes) -> bool:
    head = (content or b"")[:400].lower()
    return b"<rss" in head or b"<feed" in head or b"<item>" in head


def _parse_nitter_rss_items(content: bytes, handle: str, limit: int) -> list[dict[str, Any]]:
    soup = BeautifulSoup(content, "xml")
    items = soup.find_all("item")
    results: list[dict[str, Any]] = []
    for item in items[:limit]:
        title_tag = item.find("title")
        link_tag = item.find("link")
        pub_tag = item.find("pubDate")
        title = title_tag.get_text(strip=True) if title_tag else ""
        link = _nitter_link_to_x(
            link_tag.get_text(strip=True) if link_tag else "",
            handle,
        )
        date_s = _parse_pubdate(pub_tag.get_text(strip=True) if pub_tag else None)
        status_id = _status_id_from_link(link)
        if status_id and (not date_s or date_s == ""):
            date_s = _snowflake_to_iso(status_id)
        if title and link:
            results.append(
                {
                    "headline": title,
                    "source": f"X @{handle}",
                    "date": date_s,
                    "link": link,
                    "handle": handle,
                    "tags": _core_topic_tags(title),
                }
            )
    return results


def _clean_jina_post_body(raw: str) -> str:
    """Normalize Jina markdown tweet text into a plain headline."""
    text = raw or ""
    # Flatten whitespace early so engagement tails are easier to detect.
    text = text.replace("\r", "\n")
    # Drop empty media / action links and view-count pseudo-links.
    text = re.sub(r"\[\]\((https?://[^)]+)\)", " ", text)
    text = re.sub(r"\[[^\]]*\dK?[^\]]*\]\((https?://[^)]+/quotes?)\)", " ", text, flags=re.I)
    # Keep cashtag / mention label text from remaining markdown links.
    text = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"\1", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", text)
    text = re.sub(r"Show more", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text)
    # Drop trailing X engagement counters (likes/reposts/views) and profile echoes.
    text = re.sub(
        r"(?:\s+\d[\d.,]*K?){3,}.*$",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"(?:\s+\*\s+.*)$", "", text)
    return text.strip(" \t\r\n-•")


def _scrape_x_profile_via_jina(handle: str, limit: int = 10) -> list[dict[str, Any]]:
    """Fallback: read the public x.com profile through Jina's reader API."""
    url = f"https://r.jina.ai/https://x.com/{handle}"
    resp = requests.get(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "X-Return-Format": "markdown",
            "Accept": "text/plain",
        },
        timeout=max(NEWS_TIMEOUT_SECS, 30),
    )
    resp.raise_for_status()
    text = resp.text or ""

    marker = re.compile(
        rf"\[([^\]]+)\]\((https://x\.com/{re.escape(handle)}/status/\d+)\)",
        re.IGNORECASE,
    )
    matches = list(marker.finditer(text))
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for idx, match in enumerate(matches):
        link = match.group(2).strip()
        if link in seen:
            continue
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        body = _clean_jina_post_body(text[start:end])
        if not body or len(body) < 12:
            continue
        # Skip empty quote/media-only shells.
        if body.lower() in {"show more", "quote", "quotes"}:
            continue
        seen.add(link)
        status_id = _status_id_from_link(link)
        date_s = _snowflake_to_iso(status_id) if status_id else ""
        results.append(
            {
                "headline": body[:280],
                "source": f"X @{handle}",
                "date": date_s,
                "link": link,
                "handle": handle,
                "tags": _core_topic_tags(body),
            }
        )
        if len(results) >= limit:
            break
    return results


def scrape_x_profile_rss(profile: str, limit: int = 10) -> list[dict[str, Any]]:
    """Fetch recent posts for an X handle (Jina reader, then Nitter RSS mirrors)."""
    handle = (profile or "").strip().lstrip("@")
    if not handle:
        return []

    last_error: Exception | None = None
    try:
        fallback = _scrape_x_profile_via_jina(handle, limit=limit)
        if fallback:
            return fallback
    except Exception as exc:
        last_error = exc

    for host in NITTER_RSS_HOSTS:
        rss_url = f"{host.rstrip('/')}/{handle}/rss"
        try:
            resp = requests.get(
                rss_url,
                headers={"User-Agent": USER_AGENT},
                timeout=min(NEWS_TIMEOUT_SECS, 8),
            )
            resp.raise_for_status()
            if not _looks_like_rss(resp.content):
                last_error = RuntimeError(f"{host} returned non-RSS content")
                continue
            parsed = _parse_nitter_rss_items(resp.content, handle, limit)
            if parsed:
                return parsed
            last_error = RuntimeError(f"{host} RSS had no items")
        except Exception as exc:  # Best-effort across mirrors.
            last_error = exc
            continue

    if last_error is not None:
        raise last_error
    return []


def scrape_x_analyst_feeds(
    profiles: list[str] | None = None,
    *,
    limit_per_profile: int = 12,
) -> list[dict[str, Any]]:
    """Fetch recent posts for the configured X analyst accounts."""
    handles = profiles or list(X_PROFILES_DEFAULT)
    aggregated: list[dict[str, Any]] = []
    errors: list[str] = []
    for handle in handles:
        try:
            aggregated.extend(scrape_x_profile_rss(handle, limit=limit_per_profile))
        except Exception as exc:
            errors.append(f"@{handle.lstrip('@')}: {exc}")
        time.sleep(0.35)

    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for item in aggregated:
        link = str(item.get("link") or "")
        if not link or link in seen:
            continue
        seen.add(link)
        deduped.append(item)

    deduped.sort(key=lambda r: str(r.get("date") or ""), reverse=True)
    if errors and not deduped:
        raise RuntimeError("; ".join(errors[:3]))
    return deduped


def scrape_news(
    keywords: list[str],
    per_keyword_per_source: int = 5,
    x_profiles: list[str] | None = None,
) -> list[dict[str, Any]]:
    aggregated: list[dict[str, Any]] = []
    for kw in keywords:
        if not kw.strip():
            continue
        try:
            aggregated.extend(scrape_google_news_rss(kw, limit=per_keyword_per_source))
        except Exception:
            # Best effort: continue with other sources/keywords.
            pass

        # Respectful pacing to reduce throttling.
        time.sleep(0.5)
        try:
            aggregated.extend(scrape_yahoo_finance_news(kw, limit=per_keyword_per_source))
        except Exception:
            pass
        time.sleep(0.5)

    for handle in (x_profiles or X_PROFILES_DEFAULT):
        try:
            aggregated.extend(scrape_x_profile_rss(handle, limit=per_keyword_per_source))
        except Exception:
            pass
        time.sleep(0.5)

    # Deduplicate by link.
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for item in aggregated:
        link = item.get("link")
        if not link or link in seen:
            continue
        seen.add(link)
        deduped.append(item)
    return deduped


def fetch_fear_greed_index() -> dict[str, Any]:
    """
    Fetch Fear & Greed index for Market News.
    Primary target is Binance Square URL; if blocked by JS/anti-bot,
    fallback to the equivalent public index feed.
    """
    binance_url = "https://www.binance.com/en/square/fear-and-greed-index"
    out = {
        "value": None,
        "classification": "",
        "timestamp": "",
        "last_week_value": None,
        "last_week_classification": "",
        "last_week_timestamp": "",
        "source": "Binance",
        "url": binance_url,
    }

    # Best effort: Binance page may block non-JS clients.
    try:
        resp = requests.get(binance_url, headers={"User-Agent": USER_AGENT}, timeout=NEWS_TIMEOUT_SECS)
        if resp.status_code == 200 and resp.text:
            text = resp.text
            # Try common inline patterns.
            import re

            m_val = re.search(r'"value"\s*:\s*"?(\\d{1,3})"?', text, flags=re.IGNORECASE)
            m_cls = re.search(r'"classification"\s*:\s*"([^"]+)"', text, flags=re.IGNORECASE)
            if m_val:
                out["value"] = int(m_val.group(1))
                if m_cls:
                    out["classification"] = m_cls.group(1)
                out["source"] = "Binance"
                return out
    except Exception:
        pass

    # Fallback: public crypto fear & greed endpoint (same metric family).
    try:
        alt_url = "https://api.alternative.me/fng/?limit=8"
        r = requests.get(alt_url, headers={"User-Agent": USER_AGENT}, timeout=NEWS_TIMEOUT_SECS)
        r.raise_for_status()
        payload = r.json() or {}
        series = payload.get("data") or []
        if series:
            cur = series[0]
            val = cur.get("value")
            cls = cur.get("value_classification") or ""
            ts = cur.get("timestamp") or ""
            out["value"] = int(val) if val is not None else None
            out["classification"] = str(cls)
            out["timestamp"] = str(ts)
        if len(series) >= 8:
            prev = series[7]
            pval = prev.get("value")
            pcls = prev.get("value_classification") or ""
            pts = prev.get("timestamp") or ""
            out["last_week_value"] = int(pval) if pval is not None else None
            out["last_week_classification"] = str(pcls)
            out["last_week_timestamp"] = str(pts)
        out["source"] = "Alternative.me (Binance page fallback)"
        out["url"] = binance_url
    except Exception:
        pass
    return out


def scrape_techcombank_monthly_reports(limit: int = 8) -> list[dict[str, str]]:
    """
    Fetch Techcombank Vietnam monthly outlook report links.
    Strategy:
    1) Parse listing page for monthly-report pdf links
    2) Fallback to generated YYYYMM URL patterns (both uppercase/lowercase styles)
    """
    listing_url = "https://techcombank.com/thong-tin/nghien-cuu/bao-cao-dinh-ky"
    found: dict[str, dict[str, str]] = {}

    # Step 1: Parse listing page for embedded PDF URLs.
    try:
        resp = requests.get(listing_url, headers={"User-Agent": USER_AGENT}, timeout=NEWS_TIMEOUT_SECS)
        if resp.status_code == 200 and resp.text:
            urls = re.findall(
                r"https://techcombank\.com/content/dam/techcombank/public-site/documents/[^\s\"']*monthly-report\.pdf",
                resp.text,
                flags=re.IGNORECASE,
            )
            for u in urls:
                m = re.search(r"(\d{6})", u)
                if not m:
                    continue
                yyyymm = m.group(1)
                period = f"{yyyymm[:4]}-{yyyymm[4:]}"
                found[yyyymm] = {"yyyymm": yyyymm, "period": period, "url": u}
    except Exception:
        pass

    # Step 2: Fallback to generated month patterns for recent months.
    def _month_add(y: int, m: int, delta: int) -> tuple[int, int]:
        idx = (y * 12 + (m - 1)) + delta
        ny = idx // 12
        nm = idx % 12 + 1
        return ny, nm

    today = date.today()
    for back in range(0, max(limit * 2, 6)):
        yy, mm = _month_add(today.year, today.month, -back)
        yyyymm = f"{yy}{mm:02d}"
        if yyyymm in found:
            continue
        candidates = [
            f"https://techcombank.com/content/dam/techcombank/public-site/documents/VN-{yyyymm}-Monthly-Report.pdf",
            f"https://techcombank.com/content/dam/techcombank/public-site/documents/vn-{yyyymm}-monthly-report.pdf",
        ]
        chosen = None
        for u in candidates:
            try:
                h = requests.head(u, headers={"User-Agent": USER_AGENT}, timeout=10, allow_redirects=True)
                if h.status_code == 200:
                    chosen = u
                    break
            except Exception:
                continue
        if chosen:
            period = f"{yyyymm[:4]}-{yyyymm[4:]}"
            found[yyyymm] = {"yyyymm": yyyymm, "period": period, "url": chosen}
        if len(found) >= limit:
            break

    items = sorted(found.values(), key=lambda x: x["yyyymm"], reverse=True)
    return items[:limit]


def get_cached_news(session: Session, keywords: str) -> list[dict[str, Any]]:
    k_hash = keywords_hash(keywords)
    row = session.execute(select(NewsCache).where(NewsCache.keywords_hash == k_hash)).scalar_one_or_none()
    if not row:
        return []
    try:
        return json.loads(row.results_json)
    except Exception:
        return []


def upsert_cached_news(session: Session, keywords: str, results: list[dict[str, Any]]) -> None:
    k_hash = keywords_hash(keywords)
    payload = json.dumps(results, ensure_ascii=False)

    row = session.execute(select(NewsCache).where(NewsCache.keywords_hash == k_hash)).scalar_one_or_none()
    if row:
        row.keywords_text = keywords.strip()
        row.results_json = payload
        row.fetched_at = datetime.utcnow()
    else:
        session.add(
            NewsCache(
                keywords_hash=k_hash,
                keywords_text=keywords.strip(),
                results_json=payload,
            )
        )


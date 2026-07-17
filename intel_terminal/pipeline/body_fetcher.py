"""Optional full-text fetch with paywall detection (no bypass — RSS snippet fallback)."""

from __future__ import annotations

import re
from typing import Any

import requests

from intel_terminal.config import load_config

_PAYWALL_MARKERS = re.compile(
    r"(subscribe to (continue|read)|sign in to read|premium subscribers only|"
    r"register to continue|paywall|members only)",
    re.I,
)


def detect_paywall(html: str) -> bool:
    if not html:
        return False
    if _PAYWALL_MARKERS.search(html[:12000]):
        return True
    return False


def fetch_article_body(url: str, *, timeout: int | None = None) -> tuple[str | None, str]:
    """
    Attempt to fetch article body. Returns (text, status).
    status: full | snippet_only | paywalled | failed
    """
    cfg = load_config()
    timeout = timeout or cfg.request_timeout_sec
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": cfg.user_agent},
            timeout=timeout,
            allow_redirects=True,
        )
        if resp.status_code in {401, 403, 451}:
            return None, "paywalled"
        if resp.status_code >= 400:
            return None, "failed"

        html = resp.text or ""
        if detect_paywall(html):
            return None, "paywalled"

        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "lxml")
            for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                tag.decompose()
            article = soup.find("article")
            root = article if article else soup.find("body")
            if not root:
                return None, "failed"
            text = " ".join(root.get_text(" ", strip=True).split())
            if len(text) < 120:
                return None, "snippet_only"
            return text[:12000], "full"
        except Exception:
            return None, "failed"
    except Exception:
        return None, "failed"

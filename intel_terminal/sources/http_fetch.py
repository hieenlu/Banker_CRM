"""HTTP fetch with macOS-friendly SSL (truststore + certifi fallbacks)."""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

logger = logging.getLogger(__name__)

# Use system + certifi CAs before any HTTPS requests (macOS Python.org installs).
try:
    import certifi

    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
except ImportError:
    certifi = None  # type: ignore[assignment,misc]

try:
    import truststore

    truststore.inject_into_ssl()
    _TRUSTSTORE = True
except ImportError:
    _TRUSTSTORE = False


def ssl_diagnostics() -> dict[str, Any]:
    ca_path = None
    if certifi is not None:
        ca_path = certifi.where()
    return {
        "python": sys.executable,
        "certifi": ca_path,
        "truststore": _TRUSTSTORE,
        "insecure_ssl": os.getenv("INTEL_RSS_INSECURE_SSL", "").lower() in {"1", "true", "yes"},
    }


def fetch_url(
    url: str,
    *,
    timeout: int = 25,
    user_agent: str = "BankerCRM-IntelTerminal/1.0",
) -> tuple[bytes | None, str | None]:
    """GET url; return (content, error). Tries multiple SSL verify strategies."""
    import requests
    from requests.exceptions import SSLError

    headers = {
        "User-Agent": user_agent,
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
    }

    verify_options: list[bool | str] = []
    if certifi is not None:
        verify_options.append(certifi.where())
    verify_options.append(True)
    if os.getenv("INTEL_RSS_INSECURE_SSL", "").strip().lower() in {"1", "true", "yes"}:
        verify_options.append(False)

    last_ssl_err: Exception | None = None
    for verify in verify_options:
        try:
            resp = requests.get(url, headers=headers, timeout=timeout, verify=verify)
            if resp.status_code >= 400:
                return None, f"HTTP {resp.status_code}"
            return resp.content, None
        except SSLError as exc:
            last_ssl_err = exc
            logger.debug("SSL verify=%r failed for %s: %s", verify, url, exc)
            continue
        except Exception as exc:
            return None, str(exc)

    if last_ssl_err:
        return None, f"SSL error: {last_ssl_err}"
    return None, "Request failed"


def probe_feed_fetch(test_url: str = "https://vnexpress.net/rss/kinh-doanh.rss") -> dict[str, Any]:
    """Quick connectivity test for Settings UI."""
    data, err = fetch_url(test_url)
    info = ssl_diagnostics()
    info["test_url"] = test_url
    info["ok"] = data is not None and len(data) > 200
    info["bytes"] = len(data) if data else 0
    info["error"] = err
    return info

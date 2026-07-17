"""HTTP fetch / SSL helper tests."""

from __future__ import annotations

from intel_terminal.sources.http_fetch import fetch_url, probe_feed_fetch, ssl_diagnostics


def test_ssl_diagnostics_has_python():
    d = ssl_diagnostics()
    assert "python" in d
    assert d["python"]


def test_probe_vnexpress_feed():
    p = probe_feed_fetch()
    assert p["ok"] is True
    assert p["bytes"] > 200


def test_fetch_url_returns_bytes():
    data, err = fetch_url("https://vnexpress.net/rss/kinh-doanh.rss", timeout=20)
    assert err is None
    assert data and len(data) > 200

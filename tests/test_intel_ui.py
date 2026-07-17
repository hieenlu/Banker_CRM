"""UI navigation smoke tests."""

from __future__ import annotations

from intel_terminal.ui.render import INTEL_PAGES


def test_intel_pages_include_archive():
    assert INTEL_PAGES == ("Dashboard", "Latest News", "Archive")
    assert "Vietnam" not in INTEL_PAGES
    assert "Settings" not in INTEL_PAGES

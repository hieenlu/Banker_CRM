"""Techcombank monthly reports — preserved Vietnam research section."""

from __future__ import annotations

import html
from collections.abc import Callable

import streamlit as st


def _render_techcombank_table(fetch_reports: Callable[[int], list[dict[str, str]]], limit: int) -> None:
    st.caption(
        "[Techcombank periodic research page](https://techcombank.com/thong-tin/nghien-cuu/bao-cao-dinh-ky)"
    )
    reports = fetch_reports(limit)
    if not reports:
        st.info("No Techcombank monthly reports detected yet.")
        return

    rows: list[str] = []
    for r in reports:
        period = html.escape(str(r.get("period", "") or ""))
        url = html.escape(str(r.get("url", "") or ""), quote=True)
        rows.append(
            f"<tr><td>{period}</td>"
            f'<td><a href="{url}" target="_blank">Monthly Report {period}</a></td></tr>'
        )
    st.markdown(
        """
<table class="intel-table">
  <thead><tr><th>Period</th><th>Report</th></tr></thead>
  <tbody>"""
        + "".join(rows)
        + "</tbody></table>",
        unsafe_allow_html=True,
    )


def render_techcombank_section(
    fetch_reports: Callable[[int], list[dict[str, str]]],
    *,
    limit: int = 8,
    expanded: bool = True,
    inline: bool = False,
) -> None:
    """Render Techcombank monthly PDF links. inline=True skips the expander wrapper."""
    if inline:
        _render_techcombank_table(fetch_reports, limit)
        return

    with st.expander("Vietnam Market Outlook (Techcombank Monthly)", expanded=expanded):
        _render_techcombank_table(fetch_reports, limit)

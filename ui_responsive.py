"""Global responsive CSS for phone-sized viewports (iPhone Pro / Pro Max and similar)."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

import streamlit as st

T = TypeVar("T")


def iter_item_pairs(items: list[T]):
    for i in range(0, len(items), 2):
        yield items[i], items[i + 1] if i + 1 < len(items) else None


def render_two_column_cards(items: list[T], render_item: Callable[[T], None]) -> None:
    """Render list items as bordered cards in a 2-column grid."""
    if not items:
        return
    for left, right in iter_item_pairs(items):
        col_left, col_right = st.columns(2, gap="small")
        with col_left:
            with st.container(border=True):
                render_item(left)
        if right is not None:
            with col_right:
                with st.container(border=True):
                    render_item(right)


def render_mobile_kv_grid(pairs: list[tuple[str, str]]) -> None:
    """Show label/value pairs in two columns (no vertical stack)."""
    for i in range(0, len(pairs), 2):
        c1, c2 = st.columns(2, gap="small")
        for col, idx in ((c1, i), (c2, i + 1)):
            if idx >= len(pairs):
                break
            label, value = pairs[idx]
            with col:
                st.caption(label)
                st.write(value)


def responsive_styles_css() -> str:
    """Return CSS injected once at app startup."""
    return """
<style>
/* --- Base / safe area (notched iPhones) --- */
@supports (padding: max(0px)) {
  .main .block-container {
    padding-left: max(0.75rem, env(safe-area-inset-left));
    padding-right: max(0.75rem, env(safe-area-inset-right));
    padding-bottom: max(1rem, env(safe-area-inset-bottom));
  }
}

/* Layout mode set by ui_device.py viewport sync */
body[data-crm-layout="mobile"] .main .block-container {
  padding-left: 0.65rem;
  padding-right: 0.65rem;
}

/* --- Phones: iPhone Pro (~393px) and Pro Max (~430px); cap at tablet --- */
@media (max-width: 768px) {
  .main .block-container {
    padding-top: 0.85rem;
    padding-left: 0.65rem;
    padding-right: 0.65rem;
    max-width: 100%;
  }

  h1 {
    font-size: 1.35rem !important;
    line-height: 1.25 !important;
  }
  h2, h3 {
    font-size: 1.05rem !important;
  }

  /* Sidebar: larger tap targets */
  section[data-testid="stSidebar"] {
    min-width: min(18rem, 85vw);
  }
  section[data-testid="stSidebar"] label {
    font-size: 0.95rem;
  }
  section[data-testid="stSidebar"] button {
    min-height: 2.75rem;
  }

  /* Primary actions: touch-friendly */
  .main button {
    min-height: 2.6rem;
    padding: 0.35rem 0.65rem;
    font-size: 0.9rem;
  }
  .main button p {
    font-size: 0.9rem;
  }

  /* Streamlit rows: consistent two-column rhythm on phone */
  div[data-testid="stHorizontalBlock"] {
    overflow-x: visible;
    overflow-y: visible;
    flex-wrap: wrap !important;
    gap: 0.4rem;
    margin-bottom: 0.1rem;
  }
  div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
    flex: 1 1 calc(50% - 0.35rem) !important;
    width: calc(50% - 0.35rem) !important;
    min-width: 0 !important;
  }

  /* Dataframes / editors */
  div[data-testid="stDataFrame"],
  div[data-testid="stDataEditor"],
  [data-testid="stTable"] {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    max-width: 100%;
  }

  /* HTML tables (Market News, Techcombank, etc.) */
  .main table {
    display: block;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    max-width: 100%;
    font-size: 0.82rem;
  }
  .main table thead,
  .main table tbody {
    display: table;
    width: max-content;
    min-width: 100%;
  }

  /* Expander headers */
  details summary {
    font-size: 0.92rem;
  }

  /* Metrics row */
  div[data-testid="stMetric"] {
    min-width: 6.5rem;
  }
  div[data-testid="stMetric"] label {
    font-size: 0.75rem;
  }
  div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
    font-size: 1.1rem;
  }

  /* Forms: full-width inputs */
  .main input, .main textarea, .main select {
    font-size: 16px !important; /* avoids iOS zoom-on-focus */
  }

  /* Portfolio snapshot cards */
  .snapshot-grid,
  .snapshot-grid-6 {
    grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
    gap: 6px;
  }
  .snapshot-card {
    padding: 7px 8px;
  }
  .snapshot-label {
    font-size: 0.62rem;
  }
  .snapshot-value {
    font-size: 0.78rem;
    white-space: normal;
    word-break: break-word;
    overflow-x: visible;
  }
  .snapshot-title {
    font-size: 0.72rem;
  }

  /* Fear & Greed card */
  .fg-card {
    padding: 8px 10px;
  }
  .fg-stats {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 6px;
    font-size: 0.82rem;
  }
  .fg-row {
    flex-direction: column;
    align-items: flex-start;
  }

}

body[data-crm-layout="mobile"] div[data-testid="stMetric"] {
  min-width: 0;
}
</style>
"""

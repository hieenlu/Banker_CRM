"""Global responsive CSS for phone-sized viewports (iPhone Pro / Pro Max and similar)."""


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

  /* Streamlit column rows: horizontal swipe (keeps header/row alignment) */
  div[data-testid="stHorizontalBlock"] {
    overflow-x: auto;
    overflow-y: hidden;
    flex-wrap: nowrap !important;
    -webkit-overflow-scrolling: touch;
    gap: 0.45rem;
    padding-bottom: 6px;
    margin-bottom: 0.15rem;
    scrollbar-width: thin;
  }
  div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
    flex: 0 0 auto !important;
    width: auto !important;
    min-width: 4.25rem;
  }
  div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:first-child {
    min-width: 5.5rem;
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
    flex-direction: column;
    align-items: flex-start;
    gap: 6px;
    font-size: 0.86rem;
  }
  .fg-row {
    flex-direction: column;
    align-items: flex-start;
  }

  .crm-mobile-hint {
    display: block;
    font-size: 0.8rem;
    color: #64748b;
    margin: 0 0 0.65rem 0;
    padding: 0.4rem 0.55rem;
    border-radius: 6px;
    background: rgba(100, 116, 139, 0.12);
  }
}

.crm-mobile-hint {
  display: none;
}

/* Narrow phones (Pro non-Max) */
@media (max-width: 400px) {
  .snapshot-grid,
  .snapshot-grid-6 {
    grid-template-columns: 1fr !important;
  }
  div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
    min-width: 3.75rem;
  }
}
</style>
"""

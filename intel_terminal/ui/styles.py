"""Dark terminal styling for Market News UI."""

from __future__ import annotations


def intel_terminal_css() -> str:
    return """
<style>
.intel-wrap {
  --intel-bg: #141414;
  --intel-panel: #1e1e1e;
  --intel-card: #252525;
  --intel-border: #333;
  --intel-text: #f5f5f5;
  --intel-muted: #9ca3af;
  --intel-accent: #d62828;
  --intel-green: #22c55e;
  --intel-amber: #f59e0b;
  font-family: "IBM Plex Sans", "Segoe UI", system-ui, sans-serif;
  color: var(--intel-text);
  margin-bottom: 0.5rem;
}
div[data-testid="stVerticalBlock"]:has(.intel-terminal) div[data-testid="stRadio"] {
  margin: 0.25rem 0 0.75rem;
}
div[data-testid="stVerticalBlock"]:has(.intel-terminal) div[data-testid="stRadio"] > div[role="radiogroup"] {
  display: flex; flex-wrap: wrap; gap: 0.35rem;
  background: transparent; border: none; padding: 0;
}
div[data-testid="stVerticalBlock"]:has(.intel-terminal) div[data-testid="stRadio"] > div[role="radiogroup"] > label {
  background: var(--intel-panel) !important;
  border: 1px solid var(--intel-border) !important;
  border-radius: 999px !important;
  color: var(--intel-muted) !important;
  font-weight: 600 !important;
  font-size: 0.82rem !important;
  padding: 0.35rem 0.85rem !important;
  margin: 0 !important;
}
div[data-testid="stVerticalBlock"]:has(.intel-terminal) div[data-testid="stRadio"] > div[role="radiogroup"] > label > div:first-child {
  display: none !important;
}
div[data-testid="stVerticalBlock"]:has(.intel-terminal) div[data-testid="stRadio"] > div[role="radiogroup"] > label[data-checked="true"],
div[data-testid="stVerticalBlock"]:has(.intel-terminal) div[data-testid="stRadio"] > div[role="radiogroup"] > label:has(input:checked) {
  border-color: var(--intel-accent) !important;
  color: var(--intel-text) !important;
  background: rgba(214, 40, 40, 0.12) !important;
}
.intel-card {
  background: var(--intel-card); border: 1px solid var(--intel-border);
  border-radius: 10px; padding: 0.85rem 1rem; margin-bottom: 0.65rem;
}
.intel-card-tight { padding: 0.65rem 0.8rem; margin-bottom: 0.45rem; }
.intel-card h4 { margin: 0 0 0.35rem; font-size: 0.92rem; }
.intel-muted { color: var(--intel-muted); font-size: 0.78rem; }
.intel-score { font-weight: 700; color: var(--intel-amber); }
.intel-table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
.intel-table th, .intel-table td {
  text-align: left; padding: 0.45rem 0.5rem; border-bottom: 1px solid var(--intel-border);
}
.intel-table th { color: var(--intel-muted); font-weight: 600; font-size: 0.75rem;
  text-transform: uppercase; letter-spacing: 0.03em; }
.intel-table a { color: #93c5fd; text-decoration: none; }
.intel-table a:hover { text-decoration: underline; }
.intel-regime-risk-on { color: var(--intel-green); }
.intel-regime-risk-off { color: var(--intel-accent); }
.intel-regime-neutral { color: var(--intel-amber); }

/* Clean headline feed */
.intel-feed { display: flex; flex-direction: column; gap: 0; }
.intel-item {
  padding: 0.7rem 0;
  border-bottom: 1px solid var(--intel-border);
}
.intel-item:last-child { border-bottom: none; }
.intel-item-title {
  display: block;
  color: #e8eef7 !important;
  text-decoration: none !important;
  font-size: 0.95rem;
  font-weight: 600;
  line-height: 1.35;
  margin-bottom: 0.28rem;
}
.intel-item-title:hover { color: #93c5fd !important; }
.intel-item-meta {
  display: flex; flex-wrap: wrap; align-items: center; gap: 0.4rem 0.65rem;
  color: var(--intel-muted); font-size: 0.75rem;
}
.intel-item-src { font-weight: 500; color: #b0b8c4; }
.intel-item-time { opacity: 0.85; }
.intel-badge {
  display: inline-block;
  font-size: 0.68rem;
  font-weight: 600;
  letter-spacing: 0.02em;
  color: #fca5a5;
  background: rgba(214, 40, 40, 0.14);
  border: 1px solid rgba(214, 40, 40, 0.35);
  border-radius: 4px;
  padding: 0.1rem 0.35rem;
}

/* Latest + Archive only: place metadata to the right of headlines */
.intel-feed-side-meta .intel-item {
  align-items: center;
  display: grid;
  gap: 1rem;
  grid-template-columns: minmax(0, 1fr) auto;
}
.intel-feed-side-meta .intel-item-title {
  margin: 0;
  min-width: 0;
}
.intel-feed-side-meta .intel-item-meta {
  flex-wrap: nowrap;
  justify-content: flex-end;
  white-space: nowrap;
}

/* Dashboard 3-column dividers */
div[data-testid="stHorizontalBlock"]:has(.intel-col-marker) > div[data-testid="stColumn"] {
  border-right: 1px solid #3a3a3a;
  padding-right: 1rem;
  padding-left: 0.75rem;
}
div[data-testid="stHorizontalBlock"]:has(.intel-col-marker) > div[data-testid="stColumn"]:first-child {
  padding-left: 0;
}
div[data-testid="stHorizontalBlock"]:has(.intel-col-marker) > div[data-testid="stColumn"]:last-child {
  border-right: none;
  padding-right: 0;
}
.intel-section-rule {
  border: 0;
  border-top: 1px solid #3a3a3a;
  margin: 0.85rem 0 1rem;
}
.intel-metrics-rule {
  border: 0;
  border-top: 1px solid rgba(255,255,255,0.08);
  margin: 0.35rem 0 1rem;
}

/* Latest News — calm, Meta-inspired newsroom */
.latest-hero {
  max-width: 1100px;
  margin: 0.25rem auto 0.8rem;
  padding: 0.9rem 0 0.8rem;
  border-bottom: 1px solid #30343b;
}
.latest-hero h2 {
  color: #f7f8fa;
  font-size: clamp(1.65rem, 3vw, 2.25rem);
  font-weight: 650;
  letter-spacing: -0.045em;
  line-height: 1;
  margin: 0.45rem 0 0.45rem;
}
.latest-hero p {
  color: #8a919e;
  font-size: 0.96rem;
  margin: 0;
}
.latest-eyebrow {
  align-items: center;
  color: #8ab4f8;
  display: inline-flex;
  font-size: 0.7rem;
  font-weight: 700;
  gap: 0.45rem;
  letter-spacing: 0.12em;
}
.latest-eyebrow i {
  background: #31a24c;
  border-radius: 50%;
  box-shadow: 0 0 0 4px rgba(49, 162, 76, 0.13);
  display: inline-block;
  height: 7px;
  width: 7px;
}
.latest-filter-marker { display: none; }
div[data-testid="stVerticalBlock"]:has(.latest-filter-marker)
  div[data-testid="stHorizontalBlock"] {
  max-width: 1100px;
  margin-left: auto;
  margin-right: auto;
}
div[data-testid="stVerticalBlock"]:has(.latest-filter-marker)
  div[data-baseweb="select"] > div,
div[data-testid="stVerticalBlock"]:has(.latest-filter-marker)
  div[data-testid="stTextInput"] input {
  background: #202328 !important;
  border-color: #353941 !important;
  border-radius: 10px !important;
  min-height: 2.65rem;
}
div[data-testid="stVerticalBlock"]:has(.latest-filter-marker)
  div[data-baseweb="select"] > div:focus-within,
div[data-testid="stVerticalBlock"]:has(.latest-filter-marker)
  div[data-testid="stTextInput"] input:focus {
  border-color: #0866ff !important;
  box-shadow: 0 0 0 1px #0866ff !important;
}
div[data-testid="stVerticalBlock"]:has(.latest-filter-marker)
  label[data-testid="stWidgetLabel"] p {
  color: #8a919e;
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.02em;
}
.latest-feed-summary {
  align-items: center;
  color: #7e8590;
  display: flex;
  font-size: 0.75rem;
  justify-content: space-between;
  margin: 1.15rem auto 0;
  max-width: 1100px;
  padding: 0 0.15rem 0.7rem;
}
.latest-feed {
  background: #1c1f23;
  border: 1px solid #30343b;
  border-radius: 14px;
  box-shadow: 0 12px 35px rgba(0, 0, 0, 0.14);
  margin: 0 auto 1.5rem;
  max-width: 880px;
  overflow: hidden;
}
.latest-story {
  background: #1c1f23;
  border-bottom: 1px solid #30343b;
  padding: 1.15rem 1.25rem 1rem;
  transition: background 140ms ease;
}
.latest-story:last-child { border-bottom: 0; }
.latest-story:hover { background: #20242a; }
.latest-story-source {
  align-items: center;
  display: flex;
  margin-bottom: 0.75rem;
  min-width: 0;
}
.latest-source-avatar {
  align-items: center;
  background: linear-gradient(145deg, #1877f2, #0866ff);
  border-radius: 50%;
  color: white;
  display: inline-flex;
  flex: 0 0 32px;
  font-size: 0.74rem;
  font-weight: 700;
  height: 32px;
  justify-content: center;
  margin-right: 0.65rem;
  width: 32px;
}
.latest-source-copy {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  min-width: 0;
}
.latest-source-name {
  color: #e8eaed;
  font-size: 0.8rem;
  font-weight: 650;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.latest-source-meta {
  color: #747b87;
  font-size: 0.69rem;
  margin-top: 0.05rem;
}
.latest-topic {
  background: rgba(8, 102, 255, 0.11);
  border: 1px solid rgba(8, 102, 255, 0.24);
  border-radius: 999px;
  color: #8ab4f8;
  flex: 0 0 auto;
  font-size: 0.66rem;
  font-weight: 650;
  margin-left: 0.75rem;
  padding: 0.2rem 0.55rem;
}
.latest-story-title {
  color: #f1f3f5 !important;
  display: block;
  font-size: 1.04rem;
  font-weight: 620;
  letter-spacing: -0.012em;
  line-height: 1.38;
  text-decoration: none !important;
}
.latest-story:hover .latest-story-title { color: #a8c7fa !important; }
.latest-story-snippet {
  color: #969da8;
  display: -webkit-box;
  font-size: 0.81rem;
  line-height: 1.45;
  margin: 0.45rem 0 0;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}
.latest-story-open {
  color: #8ab4f8 !important;
  display: inline-block;
  font-size: 0.73rem;
  font-weight: 600;
  margin-top: 0.7rem;
  text-decoration: none !important;
}
.latest-story-open span {
  display: inline-block;
  margin-left: 0.15rem;
  transition: transform 140ms ease;
}
.latest-story-open:hover span { transform: translate(2px, -2px); }
.latest-empty {
  align-items: center;
  border: 1px dashed #3b4048;
  border-radius: 14px;
  color: #a4aab4;
  display: flex;
  flex-direction: column;
  margin: 1.25rem auto;
  max-width: 1100px;
  padding: 3rem 1rem;
  text-align: center;
}
.latest-empty-icon {
  color: #0866ff;
  font-size: 2rem;
  margin-bottom: 0.5rem;
}
.latest-empty span { color: #747b87; font-size: 0.8rem; margin-top: 0.3rem; }

/* Dense news index — built for scanning 25–50 rows */
.news-index {
  border: 1px solid #30343b;
  border-radius: 10px;
  margin: 0 auto 0.8rem;
  max-width: 1100px;
  overflow: hidden;
}
.news-index-head,
.news-index-row {
  display: grid;
  grid-template-columns: minmax(300px, 1fr) 145px 125px 62px 20px;
  gap: 0.75rem;
}
.news-index-head {
  align-items: center;
  background: #202328;
  color: #777f8b;
  font-size: 0.66rem;
  font-weight: 700;
  letter-spacing: 0.07em;
  padding: 0.55rem 0.9rem;
  text-transform: uppercase;
}
.news-index-date {
  background: #181b1f;
  border-bottom: 1px solid #30343b;
  color: #8a919e;
  font-size: 0.68rem;
  font-weight: 650;
  letter-spacing: 0.035em;
  padding: 0.38rem 0.9rem;
  text-transform: uppercase;
}
.news-index-row {
  align-items: center;
  background: #1c1f23;
  border-bottom: 1px solid #2b2f35;
  color: inherit !important;
  min-height: 54px;
  padding: 0.5rem 0.9rem;
  text-decoration: none !important;
  transition: background 100ms ease;
}
.news-index-row:last-child { border-bottom: 0; }
.news-index-row:hover { background: #23272d; }
.news-index-main { min-width: 0; }
.news-index-main strong {
  color: #e9ebee;
  display: block;
  font-size: 0.84rem;
  font-weight: 570;
  line-height: 1.28;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.news-index-main small {
  color: #747b87;
  display: none;
  font-size: 0.68rem;
  margin-top: 0.18rem;
}
.news-index-source {
  color: #aab0ba;
  font-size: 0.73rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.news-index-topic {
  background: rgba(8, 102, 255, 0.09);
  border-radius: 5px;
  color: #8ab4f8;
  font-size: 0.65rem;
  justify-self: start;
  max-width: 115px;
  overflow: hidden;
  padding: 0.2rem 0.42rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.news-index-time {
  color: #9299a4;
  display: flex;
  flex-direction: column;
  font-size: 0.7rem;
  text-align: right;
}
.news-index-time b { font-weight: 560; }
.news-index-time small { color: #656c77; font-size: 0.62rem; }
.news-index-arrow {
  color: #66707d;
  font-size: 0.8rem;
  opacity: 0;
  transition: opacity 100ms ease, transform 100ms ease;
}
.news-index-row:hover .news-index-arrow {
  opacity: 1;
  transform: translate(1px, -1px);
}
.news-pager-label {
  color: #7e8590;
  font-size: 0.74rem;
  padding-top: 0.6rem;
  text-align: center;
}
.archive-retention-note {
  align-items: flex-end;
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-height: 4.2rem;
}
.archive-retention-note strong {
  color: #e8eaed;
  font-size: 0.95rem;
}
.archive-retention-note span {
  color: #767e89;
  font-size: 0.72rem;
}

@media (max-width: 700px) {
  .intel-feed-side-meta .intel-item {
    align-items: start;
    gap: 0.3rem;
    grid-template-columns: minmax(0, 1fr);
  }
  .intel-feed-side-meta .intel-item-meta {
    justify-content: flex-start;
    white-space: normal;
  }
  .latest-hero { padding-top: 1rem; }
  .latest-story { padding: 1rem; }
  .latest-story-title { font-size: 0.98rem; }
  .latest-story-snippet { display: none; }
  .latest-topic { max-width: 34%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .latest-feed-summary { padding-left: 0.2rem; padding-right: 0.2rem; }
  .news-index-head { display: none; }
  .news-index-row {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 18px;
    min-height: 58px;
    padding: 0.62rem 0.75rem;
  }
  .news-index-main strong {
    font-size: 0.8rem;
    white-space: normal;
  }
  .news-index-main small { display: block; }
  .news-index-source,
  .news-index-topic,
  .news-index-time { display: none; }
  .news-index-arrow { opacity: 0.7; }
  .archive-retention-note { align-items: flex-start; min-height: 2rem; }
}
</style>
"""

"""Wealth-style client portfolio overview (donut + asset catalog)."""

from __future__ import annotations

import html
import math
from typing import Any

# Subgroup display metadata: icon, accent color, catalog metric labels
SUBGROUP_META: dict[str, dict[str, str]] = {
    "Cash and CDs": {"icon": "💵", "color": "#ec4899", "m1": "Total value", "m2": "Principal"},
    "Cash": {"icon": "💵", "color": "#ec4899", "m1": "Total value", "m2": "Principal"},
    "Term Deposit": {"icon": "📅", "color": "#f59e0b", "m1": "Principal", "m2": "Interest"},
    "Bond": {"icon": "📊", "color": "#14b8a6", "m1": "Cost", "m2": "Unrealized P&L"},
    "VN_Stock": {"icon": "📈", "color": "#8b5cf6", "m1": "Market value", "m2": "Profit"},
    "US_Stock": {"icon": "📈", "color": "#6366f1", "m1": "Market value", "m2": "Profit"},
    "Commodity": {"icon": "🥇", "color": "#a855f7", "m1": "Market value", "m2": "Profit"},
    "Crypto": {"icon": "₿", "color": "#f97316", "m1": "Market value", "m2": "Profit"},
    "Real Estate": {"icon": "🏠", "color": "#22c55e", "m1": "Investment value", "m2": "Current value"},
    "Debt": {"icon": "🏦", "color": "#ef4444", "m1": "Outstanding", "m2": "Monthly payment"},
    "VN_Stock_legacy": {"icon": "📈", "color": "#8b5cf6", "m1": "Market value", "m2": "Profit"},
}

DEFAULT_META = {"icon": "📁", "color": "#64748b", "m1": "Total", "m2": "P&L"}


def client_dashboard_css() -> str:
    return """
<style>
.crm-dash { --crm-bg: #141414; --crm-panel: #1e1e1e; --crm-card: #252525; --crm-border: #333;
  --crm-text: #f5f5f5; --crm-muted: #9ca3af; --crm-red: #ef4444; --crm-green: #22c55e;
  font-family: system-ui, -apple-system, sans-serif; color: var(--crm-text);
  margin: 0 -0.5rem 1rem 0; }
.crm-dash * { box-sizing: border-box; }
.crm-tabbar { display: flex; flex-wrap: wrap; gap: 0; border-bottom: 1px solid var(--crm-border);
  margin-bottom: 1rem; }
.crm-tabbar button { flex: 1; min-width: 4.5rem; padding: 0.65rem 0.5rem; border: none;
  background: transparent; color: var(--crm-muted); font-size: 0.82rem; font-weight: 600;
  cursor: pointer; border-bottom: 2px solid transparent; }
.crm-tabbar button.crm-tab-active { color: var(--crm-text); border-bottom-color: #d62828; }
/* Overview row: donut/legend (left) + asset catalog (right) — keep horizontal */
div[data-testid="stHorizontalBlock"]:has(.crm-dash) {
  flex-wrap: nowrap !important;
  align-items: flex-start !important;
}
div[data-testid="stHorizontalBlock"]:has(.crm-dash) > div[data-testid="column"]:first-child {
  flex: 0 0 min(300px, 36%) !important;
  width: min(300px, 36%) !important;
  min-width: 260px !important;
  max-width: 360px !important;
}
div[data-testid="stHorizontalBlock"]:has(.crm-dash) > div[data-testid="column"]:last-child {
  flex: 1 1 0 !important;
  width: auto !important;
  min-width: 0 !important;
}
.crm-sidebar { background: var(--crm-panel); border-radius: 12px; padding: 1.25rem 1rem;
  border: 1px solid var(--crm-border); }
.crm-donut-row { display: flex; flex-direction: column; gap: 1rem; align-items: stretch;
  margin-bottom: 0.75rem; }
.crm-donut-panel { width: 100%; max-width: 100%; }
.crm-donut-panel + .crm-donut-panel {
  border-top: 1px solid var(--crm-border); padding-top: 1rem;
}
.crm-donut-caption { font-size: 0.62rem; color: var(--crm-muted); text-transform: uppercase;
  letter-spacing: 0.03em; text-align: center; margin-bottom: 0.4rem; line-height: 1.2; }
.crm-donut-wrap { position: relative; width: 200px; height: 200px; margin: 0 auto 0.65rem; }
.crm-donut-wrap.crm-donut-sm { width: 128px; height: 128px; margin-bottom: 0.45rem; }
.crm-donut-sm .crm-donut-total { font-size: 0.82rem; }
.crm-donut-sm .crm-donut-label { font-size: 0.58rem; }
.crm-donut-sm .crm-donut-pct { font-size: 0.72rem; }
.crm-legend-compact { margin-bottom: 0.35rem !important; font-size: 0.7rem !important; }
.crm-donut-ring {
  width: 100%; height: 100%; border-radius: 50%;
  position: relative;
}
.crm-donut-hole {
  position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
  width: 58%; height: 58%; border-radius: 50%; background: var(--crm-panel);
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  text-align: center; padding: 0.35rem;
}
.crm-donut-label { font-size: 0.65rem; color: var(--crm-muted); text-transform: uppercase;
  letter-spacing: 0.04em; }
.crm-donut-total { font-size: 1.05rem; font-weight: 700; line-height: 1.2; margin-top: 2px; }
.crm-donut-pct { font-size: 0.8rem; font-weight: 600; margin-top: 2px; }
.crm-donut-pct.neg { color: var(--crm-red); }
.crm-donut-pct.pos { color: var(--crm-green); }
.crm-legend { padding: 0; margin: 0 0 1rem 0; font-size: 0.78rem; }
.crm-legend-item { display: flex; align-items: center; gap: 0.45rem; margin-bottom: 0.35rem;
  color: var(--crm-muted); line-height: 1.25; }
.crm-legend .dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.crm-summary-block { margin-top: 0.5rem; padding-top: 0.4rem; border-top: 1px solid var(--crm-border); }
.crm-summary-row { display: flex; justify-content: space-between; align-items: baseline;
  padding: 0.45rem 0; border-bottom: 1px solid var(--crm-border); font-size: 0.82rem; gap: 0.35rem; }
.crm-summary-block .crm-summary-row:last-child { border-bottom: none; }
.crm-summary-row span:first-child { color: var(--crm-muted); flex-shrink: 0; }
.crm-summary-row span:last-child { font-weight: 600; text-align: right; word-break: break-word; }
.crm-catalog-head { display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 0.75rem; flex-wrap: wrap; gap: 0.5rem; }
.crm-catalog-title { font-size: 1rem; font-weight: 700; }
.crm-catalog-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0.75rem; }
@media (max-width: 1100px) { .crm-catalog-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 520px) { .crm-catalog-grid { grid-template-columns: 1fr; } }
.crm-asset-card {
  background: var(--crm-card); border: 1px solid var(--crm-border); border-radius: 10px;
  padding: 0.85rem 0.9rem; min-height: 118px;
}
.crm-asset-card:hover { border-color: #555; }
.crm-asset-head { display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.65rem; }
.crm-asset-icon { font-size: 1.1rem; line-height: 1; }
.crm-asset-name { font-weight: 700; font-size: 0.9rem; flex: 1; }
.crm-asset-prop { font-size: 0.72rem; color: var(--crm-muted); white-space: nowrap; }
.crm-asset-metric { display: flex; justify-content: space-between; font-size: 0.78rem;
  margin-bottom: 0.35rem; gap: 0.5rem; }
.crm-asset-metric span:first-child { color: var(--crm-muted); }
.crm-asset-metric span:last-child { font-weight: 600; text-align: right; }
.crm-val-neg { color: var(--crm-red) !important; }
.crm-val-pos { color: var(--crm-green) !important; }
.crm-kpi-strip { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 0.5rem; margin-bottom: 1rem; }
.crm-kpi { background: var(--crm-card); border: 1px solid var(--crm-border); border-radius: 8px;
  padding: 0.6rem 0.75rem; }
.crm-kpi .lbl { font-size: 0.68rem; color: var(--crm-muted); text-transform: uppercase; }
.crm-kpi .val { font-size: 0.88rem; font-weight: 700; margin-top: 2px; }
.crm-table-divider {
  border-bottom: 1px solid #333;
  margin: 0.15rem 0 0.4rem 0;
  height: 0;
  width: 100%;
}
.crm-table-header-divider {
  border-bottom: 1px solid #444;
  margin: 0 0 0.35rem 0;
  height: 0;
  width: 100%;
}
div[data-testid="stRadio"] > div[role="radiogroup"] {
  background: #1a1a1a; border-radius: 8px 8px 0 0; padding: 0.25rem 0.5rem 0;
  border-bottom: 1px solid #333; gap: 0.25rem;
}
div[data-testid="stRadio"] > div[role="radiogroup"] > label {
  background: transparent !important; color: #9ca3af !important;
  font-weight: 600 !important; font-size: 0.82rem !important;
  border-bottom: 2px solid transparent !important; border-radius: 0 !important;
  padding: 0.55rem 0.85rem !important;
}
div[data-testid="stRadio"] > div[role="radiogroup"] > label[data-checked="true"],
div[data-testid="stRadio"] > div[role="radiogroup"] > label:has(input:checked) {
  color: #f5f5f5 !important; border-bottom-color: #d62828 !important;
}
div[data-testid="stVerticalBlock"]:has(.crm-dash) [data-testid="stVerticalBlockBorderWrapper"] {
  background: #252525; border-color: #333 !important;
}
</style>
"""


def _meta_for_subgroup(name: str) -> dict[str, str]:
    return SUBGROUP_META.get(name, SUBGROUP_META.get(name.replace(" ", "_"), DEFAULT_META))


def _fmt_compact(value: float, currency: str = "VND") -> str:
    v = abs(float(value))
    sign = "-" if value < 0 else ""
    if v >= 1_000_000_000:
        return f"{sign}{currency} {v / 1_000_000_000:.1f}B"
    if v >= 1_000_000:
        return f"{sign}{currency} {v / 1_000_000:.1f}M"
    if v >= 1_000:
        return f"{sign}{currency} {v:,.0f}"
    return f"{sign}{currency} {v:.0f}"


def _fmt_full(value: float, currency: str = "VND") -> str:
    return f"{currency} {float(value):,.0f}"


def build_subgroup_stats(
    grouped: dict[str, dict[str, list[tuple[Any, Any]]]],
    equity_principal_total: float,
    disp_ccy: str,
) -> list[dict[str, Any]]:
    """Flatten Equities + Debts subgroups into catalog card stats."""
    cards: list[dict[str, Any]] = []
    for top_group, subgroup_map in grouped.items():
        items = (
            [("Debt", sum(subgroup_map.values(), []))]
            if top_group == "Debts"
            else sorted(subgroup_map.items(), key=lambda x: (x[0],))
        )
        for subgroup_name, entries in items:
            if not entries:
                continue
            principal = sum(
                float(e[1].get("Principal Display", e[1].get("Principal", 0)) or 0) for e in entries
            )
            current = sum(
                float(e[1].get("Current Value Display", e[1].get("Current Value", 0)) or 0)
                for e in entries
            )
            pnl = sum(
                float(
                    e[1].get("Unrealized P&L Display", e[1].get("Unrealized P&L", 0)) or 0
                )
                for e in entries
            )
            pct = (pnl / principal * 100.0) if principal > 0 else None
            alloc = (
                (principal / equity_principal_total * 100.0)
                if equity_principal_total > 0 and top_group != "Debts"
                else (principal / principal * 100.0 if principal else 0.0)
            )
            if top_group == "Debts":
                alloc_pct = 100.0 * principal / max(principal, 1.0)  # shown as debt share later
                monthly = sum(
                    float(e[1].get("Total Monthly Payment", 0) or 0) for e in entries
                )
                m2_val = monthly
            else:
                alloc_pct = (principal / equity_principal_total * 100.0) if equity_principal_total > 0 else 0.0
                m2_val = pnl

            meta = _meta_for_subgroup(subgroup_name)
            cards.append(
                {
                    "key": subgroup_name,
                    "top_group": top_group,
                    "name": subgroup_name,
                    "icon": meta["icon"],
                    "color": meta["color"],
                    "proportion": alloc_pct,
                    "principal": principal,
                    "current": current,
                    "pnl": pnl,
                    "pnl_pct": pct,
                    "m1_label": meta["m1"],
                    "m2_label": meta["m2"] if top_group != "Debts" else "Monthly payment",
                    "m1_value": current if subgroup_name not in {"Bond"} else principal,
                    "m2_value": m2_val,
                    "count": len(entries),
                    "inv_ids": [inv.id for inv, _ in entries],
                }
            )
    return cards


def _donut_gradient(segments: list[tuple[float, str]]) -> str:
    if not segments:
        return "conic-gradient(#333 0% 100%)"
    total = sum(s[0] for s in segments) or 1.0
    stops: list[str] = []
    acc = 0.0
    for weight, color in segments:
        pct = weight / total * 100.0
        stops.append(f"{color} {acc:.2f}% {acc + pct:.2f}%")
        acc += pct
    return f"conic-gradient({', '.join(stops)})"


def allocation_cards_ex_re_debt(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Subgroup cards for allocation pie (no real estate, no debt)."""
    filtered = [
        c
        for c in cards
        if c.get("top_group") != "Debts"
        and str(c.get("name", "")).strip().lower() != "real estate"
        and str(c.get("key", "")).strip().lower() != "real estate"
    ]
    total = sum(float(c.get("current") or c.get("principal") or 0) for c in filtered)
    if total <= 0:
        return filtered
    out: list[dict[str, Any]] = []
    for c in filtered:
        weight = float(c.get("current") or c.get("principal") or 0)
        out.append({**c, "proportion": weight / total * 100.0})
    return out


def _legend_html(cards: list[dict[str, Any]], *, limit: int = 6) -> str:
    return "".join(
        f'<div class="crm-legend-item">'
        f'<span class="dot" style="background:{html.escape(c["color"])}"></span>'
        f'<span>{html.escape(c["name"])} <strong>{c["proportion"]:.1f}%</strong></span>'
        f"</div>"
        for c in cards[:limit]
    )


def _summary_block_html(rows: list[tuple[str, str]]) -> str:
    if not rows:
        return ""
    items = "".join(
        f'<div class="crm-summary-row"><span>{html.escape(label)}</span><span>{value}</span></div>'
        for label, value in rows
    )
    return f'<div class="crm-summary-block">{items}</div>'


def _donut_panel_html(
    *,
    caption: str,
    donut_style: str,
    center_label: str,
    center_value: str,
    center_sub: str = "",
    center_sub_cls: str = "",
    legend_html: str = "",
    summary_html: str = "",
) -> str:
    sub_html = ""
    if center_sub:
        sub_html = f'<div class="crm-donut-pct {center_sub_cls}">{html.escape(center_sub)}</div>'
    legend_block = ""
    if legend_html:
        legend_block = f'<div class="crm-legend crm-legend-compact">{legend_html}</div>'
    return f"""
    <div class="crm-donut-panel">
      <div class="crm-donut-caption">{html.escape(caption)}</div>
      <div class="crm-donut-wrap crm-donut-sm">
        <div class="crm-donut-ring" style="background: {donut_style};">
          <div class="crm-donut-hole">
            <div class="crm-donut-label">{html.escape(center_label)}</div>
            <div class="crm-donut-total">{html.escape(center_value)}</div>
            {sub_html}
          </div>
        </div>
      </div>
      {legend_block}
      {summary_html}
    </div>"""


def render_sidebar_html(
    *,
    disp_ccy: str,
    total_assets: float,
    debt: float,
    nav: float,
    allocation_total: float,
    allocation_pnl: float,
    allocation_pnl_pct: float | None,
    realized_pnl: float,
    allocation_cards: list[dict[str, Any]],
) -> str:
    """Two donuts: allocation (ex RE & debt) and total assets vs debt."""
    alloc_pct_cls = "pos" if allocation_pnl >= 0 else "neg"
    realized_cls = "pos" if realized_pnl >= 0 else "neg"
    alloc_pct_txt = f"{allocation_pnl_pct:+.1f}%" if allocation_pnl_pct is not None else "—"

    alloc_segments = [
        (float(c.get("current") or c.get("principal") or 0), c["color"])
        for c in allocation_cards
        if float(c.get("current") or c.get("principal") or 0) > 0
    ]
    if not alloc_segments:
        alloc_segments = [(1.0, "#333")]

    exposure_total = float(total_assets) + float(debt)
    if exposure_total > 0:
        asset_share = float(total_assets) / exposure_total * 100.0
        debt_share = float(debt) / exposure_total * 100.0
        exposure_segments = [(float(total_assets), "#22c55e"), (float(debt), "#ef4444")]
    else:
        asset_share = debt_share = 0.0
        exposure_segments = [(1.0, "#333")]

    alloc_panel = _donut_panel_html(
        caption="Excl. RE & debt",
        donut_style=_donut_gradient(alloc_segments),
        center_label="Current value",
        center_value=_fmt_compact(allocation_total, disp_ccy),
        center_sub=alloc_pct_txt,
        center_sub_cls=alloc_pct_cls,
        legend_html=_legend_html(allocation_cards, limit=6),
        summary_html=_summary_block_html(
            [
                ("Current value", html.escape(_fmt_full(allocation_total, disp_ccy))),
                (
                    "Unrealized P&L",
                    f'{html.escape(_fmt_full(allocation_pnl, disp_ccy))} '
                    f'<span class="crm-donut-pct {alloc_pct_cls}">({html.escape(alloc_pct_txt)})</span>',
                ),
                (
                    "Realized P&L",
                    f'<span class="crm-donut-pct {realized_cls}">'
                    f'{html.escape(_fmt_full(realized_pnl, disp_ccy))}</span>',
                ),
            ]
        ),
    )
    exposure_panel = _donut_panel_html(
        caption="Assets vs debt",
        donut_style=_donut_gradient(exposure_segments),
        center_label="Net assets",
        center_value=_fmt_compact(nav, disp_ccy),
        center_sub=f"{asset_share:.0f}% / {debt_share:.0f}%",
        legend_html=(
            f'<div class="crm-legend-item">'
            f'<span class="dot" style="background:#22c55e"></span>'
            f'<span>Total assets <strong>{asset_share:.1f}%</strong></span></div>'
            f'<div class="crm-legend-item">'
            f'<span class="dot" style="background:#ef4444"></span>'
            f'<span>Total debt <strong>{debt_share:.1f}%</strong></span></div>'
        ),
        summary_html=_summary_block_html(
            [
                ("Total assets", html.escape(_fmt_full(total_assets, disp_ccy))),
                ("Debt", html.escape(_fmt_full(debt, disp_ccy))),
                ("Net asset value", html.escape(_fmt_full(nav, disp_ccy))),
            ]
        ),
    )

    return f"""
<div class="crm-dash">
  <div class="crm-sidebar">
    <div class="crm-donut-row">
      {alloc_panel}
      {exposure_panel}
    </div>
  </div>
</div>
"""


def render_overview_html(
    *,
    disp_ccy: str,
    total_assets: float,
    debt: float,
    nav: float,
    pnl_total: float,
    pnl_pct: float | None,
    subgroup_cards: list[dict[str, Any]],
    debt_share_pct: float,
) -> str:
    """Return HTML for full overview panel (donut + catalog)."""
    pct_cls = "pos" if pnl_total >= 0 else "neg"
    pct_txt = f"{pnl_pct:+.1f}%" if pnl_pct is not None else "—"
    center_total = _fmt_compact(total_assets, disp_ccy)

    segments = [(c["principal"] or c["current"], c["color"]) for c in subgroup_cards if (c["principal"] or c["current"]) > 0]
    if not segments:
        segments = [(1.0, "#333")]

    legend_html = _legend_html(subgroup_cards, limit=8)

    cards_html = ""
    for c in subgroup_cards:
        m1 = _fmt_full(float(c["m1_value"]), disp_ccy)
        m2_raw = float(c["m2_value"])
        if c["m2_label"] in {"Profit", "Unrealized P&L"} and c.get("pnl_pct") is not None:
            sign_cls = "crm-val-pos" if m2_raw >= 0 else "crm-val-neg"
            m2 = f'{_fmt_full(m2_raw, disp_ccy)} <span class="{sign_cls}">({c["pnl_pct"]:+.1f}%)</span>'
        else:
            sign_cls = "crm-val-pos" if m2_raw >= 0 else "crm-val-neg" if m2_raw < 0 else ""
            m2 = f'<span class="{sign_cls}">{_fmt_full(m2_raw, disp_ccy)}</span>' if sign_cls else _fmt_full(m2_raw, disp_ccy)

        cards_html += f"""
<div class="crm-asset-card" data-subgroup="{html.escape(c['key'])}">
  <div class="crm-asset-head">
    <span class="crm-asset-icon">{c['icon']}</span>
    <span class="crm-asset-name">{html.escape(c['name'])}</span>
    <span class="crm-asset-prop">Proportion: {c['proportion']:.1f}%</span>
  </div>
  <div class="crm-asset-metric"><span>{html.escape(c['m1_label'])}</span><span>{m1}</span></div>
  <div class="crm-asset-metric"><span>{html.escape(c['m2_label'])}</span><span>{m2}</span></div>
</div>"""

    donut_style = _donut_gradient(segments)

    return f"""
<div class="crm-dash">
<div class="crm-overview">
  <div class="crm-sidebar">
    <div class="crm-donut-wrap">
      <div class="crm-donut-ring" style="background: {donut_style};">
        <div class="crm-donut-hole">
          <div class="crm-donut-label">Total assets</div>
          <div class="crm-donut-total">{html.escape(center_total)}</div>
          <div class="crm-donut-pct {pct_cls}">{html.escape(pct_txt)}</div>
        </div>
      </div>
    </div>
    <div class="crm-legend">{legend_html}</div>
    <div class="crm-summary-row"><span>Total assets</span><span>{_fmt_full(total_assets, disp_ccy)}</span></div>
    <div class="crm-summary-row"><span>Debt</span><span>{_fmt_full(debt, disp_ccy)}</span></div>
    <div class="crm-summary-row"><span>Net asset value</span><span>{_fmt_full(nav, disp_ccy)}</span></div>
  </div>
  <div class="crm-catalog">
    <div class="crm-catalog-head">
      <div style="font-size:0.78rem;color:var(--crm-muted);">{len(subgroup_cards)} categories · Debt {debt_share_pct:.1f}% of exposure</div>
    </div>
    <div class="crm-catalog-grid">{cards_html}</div>
  </div>
</div>
</div>
"""


def pending_client_tab_key(client_id: int) -> str:
    return f"pending_client_tab_{client_id}"


def apply_pending_client_tab(st_module: Any, client_id: int) -> None:
    """Apply a queued tab change before the tab radio widget is created."""
    tab_key = f"client_tab_{client_id}"
    pending_key = pending_client_tab_key(client_id)
    if pending_key in st_module.session_state:
        st_module.session_state[tab_key] = st_module.session_state.pop(pending_key)


def queue_client_tab(st_module: Any, client_id: int, tab: str) -> None:
    """Queue a tab switch for the next run (safe after the radio exists)."""
    st_module.session_state[pending_client_tab_key(client_id)] = tab


def render_table_header_divider(st_module: Any) -> None:
    st_module.markdown('<div class="crm-table-header-divider"></div>', unsafe_allow_html=True)


def render_table_row_divider(st_module: Any) -> None:
    st_module.markdown('<div class="crm-table-divider"></div>', unsafe_allow_html=True)


def render_html_block(st_module: Any, html: str) -> None:
    """Render raw HTML (Streamlit may strip ul/li from st.markdown)."""
    if hasattr(st_module, "html"):
        st_module.html(html, unsafe_allow_javascript=False)
    else:
        st_module.markdown(html, unsafe_allow_html=True)


def render_catalog_streamlit(
    st_module: Any,
    cards: list[dict[str, Any]],
    *,
    client_id: int,
    disp_ccy: str,
    mobile_drill_key: str,
    cols_per_row: int = 3,
) -> None:
    """Streamlit asset cards with View holdings → portfolio drill-down."""
    if not cards:
        st_module.info("No assets in catalog yet.")
        return
    for i in range(0, len(cards), cols_per_row):
        row = cards[i : i + cols_per_row]
        cols = st_module.columns(cols_per_row)
        for col, card in zip(cols, row):
            with col:
                with st_module.container(border=True):
                    st_module.markdown(
                        f"**{card['icon']} {card['name']}** · "
                        f"<span style='color:#9ca3af;font-size:0.8rem'>"
                        f"Proportion: {card['proportion']:.1f}%</span>",
                        unsafe_allow_html=True,
                    )
                    m1 = _fmt_full(float(card["m1_value"]), disp_ccy)
                    m2_raw = float(card["m2_value"])
                    if card["m2_label"] in {"Profit", "Unrealized P&L"} and card.get("pnl_pct") is not None:
                        m2 = f"{_fmt_full(m2_raw, disp_ccy)} ({card['pnl_pct']:+.1f}%)"
                    else:
                        m2 = _fmt_full(m2_raw, disp_ccy)
                    st_module.caption(f"{card['m1_label']}: **{m1}**")
                    st_module.caption(f"{card['m2_label']}: **{m2}**")
                    if st_module.button(
                        "View holdings",
                        key=f"cat_open_{client_id}_{card['key']}",
                        width="stretch",
                    ):
                        st_module.session_state[mobile_drill_key] = {
                            "group": card["top_group"],
                            "subgroup": card["key"],
                            "inv_ids": card["inv_ids"],
                        }
                        queue_client_tab(st_module, client_id, "Portfolio")
                        st_module.rerun()

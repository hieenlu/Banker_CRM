"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { explainError } from "@/components/AuthProvider";
import { PortfolioTables } from "@/components/PortfolioTables";
import {
  ErrorBanner,
  LoadingBlock,
  PageHeader,
  Panel,
} from "@/components/ui";
import { formatMoney, formatPct, pnlClass } from "@/lib/format";
import type { PortfolioView } from "@/lib/types";

export default function PortfolioPage() {
  const [view, setView] = useState<PortfolioView | null>(null);
  const [showDone, setShowDone] = useState(false);
  const [showDetails, setShowDetails] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.portfolioView({
        is_done: showDone ? null : false,
        display_currency: "VND",
      });
      setView(data);
    } catch (err) {
      setError(explainError(err));
    } finally {
      setLoading(false);
    }
  }, [showDone]);

  useEffect(() => {
    void load();
  }, [load]);

  async function onRefreshPrices() {
    setBusy(true);
    setStatus(null);
    setError(null);
    try {
      const result = await api.refreshPrices({
        is_done: showDone ? undefined : false,
      });
      setStatus(
        `Prices: ${result.resolved}/${result.requested} resolved, ${result.updated} positions updated` +
          (result.missing.length
            ? ` · missing: ${result.missing.slice(0, 8).join(", ")}`
            : ""),
      );
      await load();
    } catch (err) {
      setError(explainError(err));
    } finally {
      setBusy(false);
    }
  }

  const totals = view?.totals;

  return (
    <>
      <PageHeader
        title="Portfolio"
        description="Book-wide holdings. Expand a group to inspect positions."
        actions={
          <>
            <button
              type="button"
              className="btn btn-secondary"
              disabled={busy}
              onClick={() => void onRefreshPrices()}
            >
              {busy ? "Refreshing…" : "Refresh prices"}
            </button>
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => setShowDetails((v) => !v)}
            >
              {showDetails ? "Compact columns" : "All columns"}
            </button>
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => setShowDone((v) => !v)}
            >
              {showDone ? "Hide completed" : "Include completed"}
            </button>
          </>
        }
      />

      {status ? <p className="muted">{status}</p> : null}
      <ErrorBanner message={error} />

      {totals ? (
        <div className="metric-grid" style={{ marginBottom: "1rem" }}>
          <div className="metric">
            <div className="metric-label">Principal</div>
            <div className="metric-value">
              {formatMoney(totals.principal, "VND")}
            </div>
          </div>
          <div className="metric">
            <div className="metric-label">Current value</div>
            <div className="metric-value">
              {formatMoney(totals.current_value, "VND")}
            </div>
          </div>
          <div className="metric">
            <div className="metric-label">Unrealized P&L</div>
            <div className={`metric-value ${pnlClass(totals.pnl)}`}>
              {formatMoney(totals.pnl, "VND")}
            </div>
          </div>
          <div className="metric">
            <div className="metric-label">P&L %</div>
            <div className={`metric-value ${pnlClass(totals.pnl)}`}>
              {formatPct(totals.pnl_pct)}
            </div>
          </div>
        </div>
      ) : null}

      {view ? (
        <p className="muted small" style={{ marginBottom: "0.75rem" }}>
          FX: 1 USD = {formatMoney(view.usd_vnd_rate, "VND").replace(" ₫", "")}{" "}
          VND
        </p>
      ) : null}

      {loading ? <LoadingBlock /> : null}
      {!loading && view ? (
        <PortfolioTables
          view={view}
          showClient
          compact={!showDetails}
          collapsedByDefault
        />
      ) : null}
      {!loading && !view?.groups.length ? (
        <Panel>
          <p className="muted">No open investments yet.</p>
        </Panel>
      ) : null}
    </>
  );
}

"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { explainError } from "@/components/AuthProvider";
import {
  EmptyState,
  ErrorBanner,
  LoadingBlock,
  PageHeader,
  Pagination,
  Panel,
} from "@/components/ui";
import { formatDate, formatMoney, formatNumber, marketValue } from "@/lib/format";
import type { Client, Investment } from "@/lib/types";

export default function PortfolioPage() {
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<Investment[]>([]);
  const [clients, setClients] = useState<Record<number, string>>({});
  const [pages, setPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [showDone, setShowDone] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [inv, clientPage] = await Promise.all([
        api.listInvestments({
          page,
          page_size: 50,
          is_done: showDone ? undefined : false,
        }),
        api.listClients({ page_size: 200 }),
      ]);
      setItems(inv.items);
      setPages(inv.pages);
      setTotal(inv.total);
      const map: Record<number, string> = {};
      for (const c of clientPage.items as Client[]) map[c.id] = c.name;
      setClients(map);
    } catch (err) {
      setError(explainError(err));
    } finally {
      setLoading(false);
    }
  }, [page, showDone]);

  useEffect(() => {
    void load();
  }, [load]);

  const summary = useMemo(() => {
    const open = items.filter((i) => !i.is_done);
    const mv = open.reduce((s, i) => s + marketValue(i), 0);
    const byType = open.reduce<Record<string, number>>((acc, i) => {
      acc[i.asset_type] = (acc[i.asset_type] || 0) + marketValue(i);
      return acc;
    }, {});
    return { mv, byType, openCount: open.length };
  }, [items]);

  return (
    <>
      <PageHeader
        title="Portfolio"
        description="Cross-client holdings with estimated market value from current or purchase price."
        actions={
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => {
              setPage(1);
              setShowDone((v) => !v);
            }}
          >
            {showDone ? "Hide completed" : "Include completed"}
          </button>
        }
      />

      <div className="metric-grid" style={{ marginBottom: "1rem" }}>
        <div className="metric">
          <div className="metric-label">Positions on page</div>
          <div className="metric-value">{summary.openCount}</div>
        </div>
        <div className="metric">
          <div className="metric-label">Est. value (page)</div>
          <div className="metric-value">{formatMoney(summary.mv)}</div>
        </div>
        {Object.entries(summary.byType)
          .slice(0, 2)
          .map(([type, value]) => (
            <div className="metric" key={type}>
              <div className="metric-label">{type}</div>
              <div className="metric-value">{formatMoney(value)}</div>
            </div>
          ))}
      </div>

      <ErrorBanner message={error} />
      <Panel>
        {loading ? <LoadingBlock /> : null}
        {!loading && !items.length ? (
          <EmptyState title="No investments" description="Add holdings from Streamlit or the API." />
        ) : null}
        {items.length ? (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Client</th>
                  <th>Asset</th>
                  <th>Qty</th>
                  <th>Price</th>
                  <th>Value</th>
                  <th>Maturity</th>
                </tr>
              </thead>
              <tbody>
                {items.map((inv) => (
                  <tr key={inv.id}>
                    <td>
                      <Link className="linkish" href={`/clients/${inv.client_id}`}>
                        {clients[inv.client_id] || `#${inv.client_id}`}
                      </Link>
                    </td>
                    <td>
                      <strong>{inv.ticker_name || inv.asset_type}</strong>
                      <div className="muted small">
                        {inv.ticker_identifier || inv.asset_type}
                        {inv.is_done ? " · done" : ""}
                      </div>
                    </td>
                    <td>{formatNumber(inv.quantity)}</td>
                    <td>
                      {formatMoney(
                        inv.current_price ?? inv.purchase_price,
                        inv.currency,
                      )}
                    </td>
                    <td>{formatMoney(marketValue(inv), inv.currency)}</td>
                    <td>{formatDate(inv.maturity_date)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
        <Pagination page={page} pages={pages} total={total} onChange={setPage} />
      </Panel>
    </>
  );
}

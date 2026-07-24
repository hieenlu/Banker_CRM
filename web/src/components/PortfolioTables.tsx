"use client";

import Link from "next/link";
import {
  formatDate,
  formatMoney,
  formatNumber,
  formatPct,
  pnlClass,
} from "@/lib/format";
import type { PortfolioView } from "@/lib/types";
import { EmptyState, Panel } from "@/components/ui";

const MONEY_COLS = new Set([
  "Principal",
  "Outstanding Balance",
  "Investment Value",
  "Current Value",
  "Unrealized P&L",
  "Principal Payment",
  "Est Interest Payment",
  "Total Monthly Payment",
  "Interest",
  "Expected Coupon (Amount)",
  "Received Coupon (Amount)",
  "Closing Value",
  "Realized P&L",
]);

const PRICE_COLS = new Set(["Buy Price", "Current Price", "Closing Price"]);
const PCT_COLS = new Set(["P&L %", "Interest Rate %", "YTM %"]);
const DATE_COLS = new Set(["Buy Date", "Purchase Date", "Maturity Date"]);

function pastColumnLabel(col: string, pastMode: boolean): string {
  if (!pastMode) return col;
  if (col === "Current Price") return "Closing Price";
  if (col === "Current Value") return "Closing Value";
  if (col === "Unrealized P&L") return "Realized P&L";
  return col;
}

function cellValue(
  col: string,
  row: Record<string, unknown>,
  displayCurrency: string,
  nativeCurrency: string,
): string {
  const raw = row[col];
  if (raw == null || raw === "") return "—";
  if (PCT_COLS.has(col)) {
    if (col === "P&L %") return formatPct(Number(raw));
    return `${Number(raw).toFixed(2)}%`;
  }
  if (DATE_COLS.has(col)) return formatDate(String(raw));
  if (PRICE_COLS.has(col)) {
    return formatMoney(Number(raw), nativeCurrency);
  }
  if (MONEY_COLS.has(col)) {
    const ccy =
      col === "Outstanding Balance" ||
      col === "Principal Payment" ||
      col === "Est Interest Payment" ||
      col === "Total Monthly Payment"
        ? displayCurrency
        : nativeCurrency;
    return formatMoney(Number(raw), ccy);
  }
  if (col === "Unit") return formatNumber(Number(raw));
  return String(raw);
}

export type PortfolioRowActions = {
  mode?: "readonly" | "active" | "past";
  onEdit?: (investmentId: number) => void;
  onDone?: (investmentId: number, currentPrice: number | null) => void;
  onDelete?: (investmentId: number) => void;
  onRevert?: (investmentId: number) => void;
  busyId?: number | null;
};

export function PortfolioTables({
  view,
  showClient = false,
  actions,
}: {
  view: PortfolioView;
  showClient?: boolean;
  actions?: PortfolioRowActions;
}) {
  const mode = actions?.mode || "readonly";
  const pastMode = mode === "past";
  const showActions = mode === "active" || mode === "past";

  if (!view.groups.length) {
    return (
      <EmptyState
        title="No investments"
        description="Add holdings via Add Investment/Debts/Cashflow on a client, or via the API, then refresh prices."
      />
    );
  }

  return (
    <div className="stack">
      {view.groups.map((group) => (
        <div key={group.name} className="portfolio-group">
          <h2 className="group-title">{group.name}</h2>
          {group.subgroups.map((sub) => {
            const cols = showClient ? ["Client", ...sub.columns] : sub.columns;
            return (
              <Panel
                key={`${group.name}-${sub.name}`}
                title={sub.name}
                actions={
                  <span
                    className={`muted small ${pnlClass(sub.unrealized_pnl)}`}
                  >
                    {pastMode ? "Realized P&L" : "Unrealized P&L"}{" "}
                    {formatMoney(sub.unrealized_pnl, sub.native_currency)}
                  </span>
                }
              >
                <div className="table-wrap">
                  <table className="data">
                    <thead>
                      <tr>
                        {cols.map((c) => (
                          <th key={c}>{pastColumnLabel(c, pastMode)}</th>
                        ))}
                        {showActions ? <th>Actions</th> : null}
                      </tr>
                    </thead>
                    <tbody>
                      {sub.rows.map((row) => {
                        const id = Number(row.id);
                        const native = String(
                          row.native_currency || sub.native_currency || "VND",
                        );
                        const busy = actions?.busyId === id;
                        const currentPrice =
                          row["Current Price"] != null
                            ? Number(row["Current Price"])
                            : row.current_price != null
                              ? Number(row.current_price)
                              : null;
                        return (
                          <tr key={id}>
                            {cols.map((c) => {
                              if (c === "Client") {
                                const cid = Number(row.client_id);
                                const name = String(
                                  row.client_name || `#${cid}`,
                                );
                                return (
                                  <td key={c}>
                                    <Link
                                      className="linkish"
                                      href={`/clients/${cid}`}
                                    >
                                      {name}
                                    </Link>
                                  </td>
                                );
                              }
                              const text = cellValue(
                                c,
                                row,
                                view.display_currency,
                                native,
                              );
                              const cls =
                                c === "Unrealized P&L" || c === "P&L %"
                                  ? pnlClass(
                                      Number(
                                        c === "P&L %"
                                          ? row["P&L %"]
                                          : row["Unrealized P&L"],
                                      ),
                                    )
                                  : "";
                              return (
                                <td key={c} className={cls}>
                                  {text}
                                </td>
                              );
                            })}
                            {showActions ? (
                              <td>
                                <div className="row-actions">
                                  {mode === "active" ? (
                                    <>
                                      <button
                                        type="button"
                                        className="btn btn-ghost"
                                        title="Edit this investment"
                                        disabled={busy}
                                        onClick={() => actions?.onEdit?.(id)}
                                      >
                                        ✏
                                      </button>
                                      <button
                                        type="button"
                                        className="btn btn-secondary"
                                        title="Mark done"
                                        disabled={busy}
                                        onClick={() =>
                                          actions?.onDone?.(id, currentPrice)
                                        }
                                      >
                                        Done
                                      </button>
                                      <button
                                        type="button"
                                        className="btn btn-primary"
                                        title="Delete investment"
                                        disabled={busy}
                                        onClick={() => actions?.onDelete?.(id)}
                                      >
                                        ✖
                                      </button>
                                    </>
                                  ) : (
                                    <button
                                      type="button"
                                      className="btn btn-secondary"
                                      title="Move back to active"
                                      disabled={busy}
                                      onClick={() => actions?.onRevert?.(id)}
                                    >
                                      ↩ Active
                                    </button>
                                  )}
                                </div>
                              </td>
                            ) : null}
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </Panel>
            );
          })}
        </div>
      ))}
    </div>
  );
}

"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  formatDate,
  formatMoney,
  formatNumber,
  formatPct,
  pnlClass,
} from "@/lib/format";
import type { PortfolioView } from "@/lib/types";
import { EmptyState } from "@/components/ui";

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

/** Columns kept in compact mode — identity + money signal. */
const COMPACT_DROP = new Set([
  "Buy Price",
  "Current Price",
  "Closing Price",
  "Unit",
  "Expected Coupon (Amount)",
  "Received Coupon (Amount)",
  "Principal Payment",
  "Est Interest Payment",
  "Interest",
  "YTM %",
]);

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
  compact = true,
  collapsedByDefault = true,
  focusSubgroup = null,
}: {
  view: PortfolioView;
  showClient?: boolean;
  actions?: PortfolioRowActions;
  /** Drop secondary columns for a lighter scan. */
  compact?: boolean;
  /** Start subgroups collapsed (summary row only). */
  collapsedByDefault?: boolean;
  /** When set, only render this subgroup. */
  focusSubgroup?: string | null;
}) {
  const mode = actions?.mode || "readonly";
  const pastMode = mode === "past";
  const showActions = mode === "active" || mode === "past";

  const filteredGroups = useMemo(() => {
    if (!focusSubgroup) return view.groups;
    return view.groups
      .map((g) => ({
        ...g,
        subgroups: g.subgroups.filter((s) => s.name === focusSubgroup),
      }))
      .filter((g) => g.subgroups.length > 0);
  }, [view.groups, focusSubgroup]);

  const subgroupKeys = useMemo(() => {
    const keys: string[] = [];
    for (const g of filteredGroups) {
      for (const s of g.subgroups) keys.push(`${g.name}::${s.name}`);
    }
    return keys;
  }, [filteredGroups]);

  const [openKeys, setOpenKeys] = useState<Set<string>>(() => {
    if (!collapsedByDefault || focusSubgroup) {
      return new Set(subgroupKeys);
    }
    return new Set();
  });

  const keySignature = subgroupKeys.join("|");
  useEffect(() => {
    if (focusSubgroup || !collapsedByDefault) {
      setOpenKeys(new Set(subgroupKeys));
    } else {
      setOpenKeys(new Set());
    }
    // Reset expand state when the visible subgroup set changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [keySignature, focusSubgroup, collapsedByDefault]);

  function toggle(key: string) {
    setOpenKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  if (!filteredGroups.length) {
    return (
      <EmptyState
        title="No investments"
        description="Add a holding from the Holdings tab, then refresh prices if needed."
      />
    );
  }

  return (
    <div className="stack portfolio-stack">
      {filteredGroups.map((group) => (
        <div key={group.name} className="portfolio-group">
          <h2 className="group-title">{group.name}</h2>
          {group.subgroups.map((sub) => {
            const key = `${group.name}::${sub.name}`;
            const open = openKeys.has(key);
            const colsRaw = showClient ? ["Client", ...sub.columns] : sub.columns;
            const cols = compact
              ? colsRaw.filter((c) => !COMPACT_DROP.has(c))
              : colsRaw;
            return (
              <section key={key} className="holdings-block">
                <button
                  type="button"
                  className="holdings-toggle"
                  aria-expanded={open}
                  onClick={() => toggle(key)}
                >
                  <span className="holdings-toggle-main">
                    <span className="holdings-chevron" aria-hidden>
                      {open ? "▾" : "▸"}
                    </span>
                    <span className="holdings-name">{sub.name}</span>
                    <span className="muted small">
                      {sub.rows.length}{" "}
                      {sub.rows.length === 1 ? "position" : "positions"}
                    </span>
                  </span>
                  <span
                    className={`muted small ${pnlClass(sub.unrealized_pnl)}`}
                  >
                    {pastMode ? "Realized" : "P&L"}{" "}
                    {formatMoney(sub.unrealized_pnl, sub.native_currency)}
                  </span>
                </button>

                {open ? (
                  <div className="holdings-body">
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
                              row.native_currency ||
                                sub.native_currency ||
                                "VND",
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
                                            disabled={busy}
                                            onClick={() =>
                                              actions?.onEdit?.(id)
                                            }
                                          >
                                            Edit
                                          </button>
                                          <button
                                            type="button"
                                            className="btn btn-secondary"
                                            disabled={busy}
                                            onClick={() =>
                                              actions?.onDone?.(
                                                id,
                                                currentPrice,
                                              )
                                            }
                                          >
                                            Done
                                          </button>
                                          <button
                                            type="button"
                                            className="btn btn-ghost danger"
                                            disabled={busy}
                                            onClick={() =>
                                              actions?.onDelete?.(id)
                                            }
                                          >
                                            Delete
                                          </button>
                                        </>
                                      ) : (
                                        <button
                                          type="button"
                                          className="btn btn-secondary"
                                          disabled={busy}
                                          onClick={() =>
                                            actions?.onRevert?.(id)
                                          }
                                        >
                                          Restore
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
                  </div>
                ) : null}
              </section>
            );
          })}
        </div>
      ))}
    </div>
  );
}

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
import { formatDate } from "@/lib/format";
import type { Client, Reminder } from "@/lib/types";

type BucketKey =
  | "on_due"
  | "this_month"
  | "this_year"
  | "overdue"
  | "completed";

function ymd(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function bucketFor(r: Reminder, today: Date): BucketKey {
  if (r.sent_at) return "completed";
  const due = new Date(r.reminder_date);
  if (Number.isNaN(due.getTime())) return "this_year";
  const dueDay = ymd(due);
  const todayDay = ymd(today);
  if (dueDay === todayDay) return "on_due";
  if (dueDay < todayDay) return "overdue";
  if (
    due.getFullYear() === today.getFullYear() &&
    due.getMonth() === today.getMonth()
  ) {
    return "this_month";
  }
  if (due.getFullYear() === today.getFullYear()) return "this_year";
  return "this_year";
}

const BUCKETS: Array<{ key: BucketKey; label: string }> = [
  { key: "on_due", label: "On Due Date" },
  { key: "this_month", label: "This Month" },
  { key: "this_year", label: "This Year" },
  { key: "overdue", label: "Overdue" },
  { key: "completed", label: "Completed" },
];

export default function RemindersPage() {
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<Reminder[]>([]);
  const [allItems, setAllItems] = useState<Reminder[]>([]);
  const [clients, setClients] = useState<Record<number, string>>({});
  const [pages, setPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [activeBucket, setActiveBucket] = useState<BucketKey>("on_due");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [rem, allRem, clientPage] = await Promise.all([
        api.listReminders({ page, page_size: 50 }),
        api.listReminders({ page: 1, page_size: 200 }),
        api.listClients({ page_size: 200 }),
      ]);
      setItems(rem.items);
      setAllItems(allRem.items);
      setPages(rem.pages);
      setTotal(rem.total);
      const map: Record<number, string> = {};
      for (const c of clientPage.items as Client[]) map[c.id] = c.name;
      setClients(map);
    } catch (err) {
      setError(explainError(err));
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => {
    void load();
  }, [load]);

  const today = useMemo(() => new Date(), []);
  const counts = useMemo(() => {
    const c: Record<BucketKey, number> = {
      on_due: 0,
      this_month: 0,
      this_year: 0,
      overdue: 0,
      completed: 0,
    };
    for (const r of allItems) c[bucketFor(r, today)] += 1;
    return c;
  }, [allItems, today]);

  const filtered = useMemo(
    () => items.filter((r) => bucketFor(r, today) === activeBucket),
    [items, activeBucket, today],
  );

  return (
    <>
      <PageHeader
        title="Reminder Center"
        description="Birthdays, maturities, and manual follow-ups across your book."
      />
      <ErrorBanner message={error} />

      <div className="kpi-strip">
        {BUCKETS.map((b) => (
          <button
            key={b.key}
            type="button"
            className="kpi-card"
            style={{
              cursor: "pointer",
              textAlign: "left",
              borderColor:
                activeBucket === b.key ? "var(--crm-accent)" : undefined,
              background:
                activeBucket === b.key
                  ? "rgba(214, 40, 40, 0.12)"
                  : undefined,
            }}
            onClick={() => setActiveBucket(b.key)}
          >
            <div className="kpi-label">{b.label}</div>
            <div className="kpi-value">{counts[b.key]}</div>
          </button>
        ))}
      </div>

      <Panel title={BUCKETS.find((b) => b.key === activeBucket)?.label}>
        {loading ? <LoadingBlock /> : null}
        {!loading && !filtered.length ? (
          <EmptyState title="No reminders in this bucket" />
        ) : null}
        {filtered.length ? (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>When</th>
                  <th>Title</th>
                  <th>Client</th>
                  <th>Type</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((r) => (
                  <tr key={r.id}>
                    <td>{formatDate(r.reminder_date)}</td>
                    <td>
                      <strong>{r.title}</strong>
                      {r.notes ? (
                        <div className="muted small">{r.notes}</div>
                      ) : null}
                    </td>
                    <td>
                      {r.client_id ? (
                        <Link
                          className="linkish"
                          href={`/clients/${r.client_id}`}
                        >
                          {clients[r.client_id] || `#${r.client_id}`}
                        </Link>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td>{r.reminder_type}</td>
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

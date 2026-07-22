"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
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

export default function RemindersPage() {
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<Reminder[]>([]);
  const [clients, setClients] = useState<Record<number, string>>({});
  const [pages, setPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [rem, clientPage] = await Promise.all([
        api.listReminders({ page, page_size: 50 }),
        api.listClients({ page_size: 200 }),
      ]);
      setItems(rem.items);
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

  return (
    <>
      <PageHeader
        title="Reminders"
        description="Birthdays, maturities, and manual follow-ups across your book."
      />
      <ErrorBanner message={error} />
      <Panel>
        {loading ? <LoadingBlock /> : null}
        {!loading && !items.length ? (
          <EmptyState title="No reminders" />
        ) : null}
        {items.length ? (
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
                {items.map((r) => (
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
                        <Link className="linkish" href={`/clients/${r.client_id}`}>
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

"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { explainError } from "@/components/AuthProvider";
import { AttachmentPanel } from "@/components/AttachmentPanel";
import {
  EmptyState,
  ErrorBanner,
  LoadingBlock,
  PageHeader,
  Panel,
} from "@/components/ui";
import { formatDate, formatMoney, formatNumber, marketValue } from "@/lib/format";
import type { Client, Income, Investment, Reminder } from "@/lib/types";

export default function ClientDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const clientId = Number(params.id);
  const [client, setClient] = useState<Client | null>(null);
  const [investments, setInvestments] = useState<Investment[]>([]);
  const [incomes, setIncomes] = useState<Income[]>([]);
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<Partial<Client>>({});
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!Number.isFinite(clientId)) return;
    setLoading(true);
    setError(null);
    try {
      const [c, inv, inc, rem] = await Promise.all([
        api.getClient(clientId),
        api.listInvestments({ client_id: clientId, page_size: 100 }),
        api.listIncomes({ client_id: clientId, page_size: 100 }),
        api.listReminders({ client_id: clientId, page_size: 50 }),
      ]);
      setClient(c);
      setForm(c);
      setInvestments(inv.items);
      setIncomes(inc.items);
      setReminders(rem.items);
    } catch (err) {
      setError(explainError(err));
    } finally {
      setLoading(false);
    }
  }, [clientId]);

  useEffect(() => {
    void load();
  }, [load]);

  const totals = useMemo(() => {
    const open = investments.filter((i) => !i.is_done);
    const mv = open.reduce((sum, i) => sum + marketValue(i), 0);
    const cashflow = [
      client?.salary_amount || 0,
      client?.dividends_amount || 0,
      client?.others_income_amount || 0,
      ...incomes.filter((i) => !i.is_done).map((i) => i.amount || 0),
    ].reduce((a, b) => a + b, 0);
    return { mv, openCount: open.length, cashflow };
  }, [investments, incomes, client]);

  async function onSave(e: FormEvent) {
    e.preventDefault();
    if (!client) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await api.updateClient(client.id, {
        name: form.name || client.name,
        birthday: form.birthday || null,
        address: form.address || null,
        phone_number: form.phone_number || null,
        email: form.email || null,
        notes: form.notes || null,
        salary_amount: form.salary_amount ?? null,
        dividends_amount: form.dividends_amount ?? null,
        others_income_amount: form.others_income_amount ?? null,
      });
      setClient(updated);
      setForm(updated);
      setEditing(false);
    } catch (err) {
      setError(explainError(err));
    } finally {
      setBusy(false);
    }
  }

  async function onDelete() {
    if (!client) return;
    if (!window.confirm(`Delete ${client.name}? This cannot be undone.`)) return;
    setBusy(true);
    try {
      await api.deleteClient(client.id);
      router.replace("/clients");
    } catch (err) {
      setError(explainError(err));
      setBusy(false);
    }
  }

  if (loading) return <LoadingBlock label="Loading client…" />;
  if (!client) {
    return (
      <>
        <ErrorBanner message={error || "Client not found"} />
        <Link href="/clients" className="linkish">
          Back to clients
        </Link>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title={client.name}
        description="Profile, holdings, recurring cashflow, reminders, and file attachments."
        actions={
          <>
            <Link href="/clients" className="btn btn-ghost">
              All clients
            </Link>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => setEditing((v) => !v)}
            >
              {editing ? "Cancel edit" : "Edit"}
            </button>
            <button
              type="button"
              className="btn btn-ghost danger"
              disabled={busy}
              onClick={() => void onDelete()}
            >
              Delete
            </button>
          </>
        }
      />

      <ErrorBanner message={error} />

      <div className="metric-grid" style={{ marginBottom: "1rem" }}>
        <div className="metric">
          <div className="metric-label">Open positions</div>
          <div className="metric-value">{totals.openCount}</div>
        </div>
        <div className="metric">
          <div className="metric-label">Est. market value</div>
          <div className="metric-value">{formatMoney(totals.mv)}</div>
        </div>
        <div className="metric">
          <div className="metric-label">Recurring income</div>
          <div className="metric-value">{formatMoney(totals.cashflow)}</div>
        </div>
      </div>

      <Panel title="Profile">
        {editing ? (
          <form className="stack" onSubmit={onSave}>
            <div className="detail-grid">
              {(
                [
                  ["name", "Name"],
                  ["email", "Email"],
                  ["phone_number", "Phone"],
                  ["birthday", "Birthday"],
                  ["address", "Address"],
                ] as const
              ).map(([key, label]) => (
                <label key={key} className="field">
                  <span>{label}</span>
                  <input
                    type={key === "birthday" ? "date" : "text"}
                    value={(form[key] as string) || ""}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, [key]: e.target.value }))
                    }
                  />
                </label>
              ))}
              <label className="field">
                <span>Notes</span>
                <textarea
                  value={form.notes || ""}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, notes: e.target.value }))
                  }
                />
              </label>
            </div>
            <button type="submit" className="btn btn-primary" disabled={busy}>
              {busy ? "Saving…" : "Save profile"}
            </button>
          </form>
        ) : (
          <dl className="detail-grid">
            <div>
              <dt>Email</dt>
              <dd>{client.email || "—"}</dd>
            </div>
            <div>
              <dt>Phone</dt>
              <dd>{client.phone_number || "—"}</dd>
            </div>
            <div>
              <dt>Birthday</dt>
              <dd>{formatDate(client.birthday)}</dd>
            </div>
            <div>
              <dt>Address</dt>
              <dd>{client.address || "—"}</dd>
            </div>
            <div>
              <dt>Notes</dt>
              <dd>{client.notes || "—"}</dd>
            </div>
          </dl>
        )}
      </Panel>

      <Panel title="Cashflow">
        <dl className="detail-grid">
          <div>
            <dt>Salary</dt>
            <dd>{formatMoney(client.salary_amount)}</dd>
          </div>
          <div>
            <dt>Dividends</dt>
            <dd>{formatMoney(client.dividends_amount)}</dd>
          </div>
          <div>
            <dt>Other income</dt>
            <dd>{formatMoney(client.others_income_amount)}</dd>
          </div>
        </dl>
        {incomes.length ? (
          <div className="table-wrap" style={{ marginTop: "1rem" }}>
            <table className="data">
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Mode</th>
                  <th>Amount</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {incomes.map((row) => (
                  <tr key={row.id}>
                    <td>{row.income_type}</td>
                    <td>{row.income_mode}</td>
                    <td>{formatMoney(row.amount)}</td>
                    <td>{row.is_done ? "Done" : "Open"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No income rows" description="Add incomes via API or Streamlit." />
        )}
      </Panel>

      <Panel title="Holdings">
        {investments.length ? (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Asset</th>
                  <th>Qty</th>
                  <th>Price</th>
                  <th>Value</th>
                  <th>Maturity</th>
                </tr>
              </thead>
              <tbody>
                {investments.map((inv) => (
                  <tr key={inv.id}>
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
        ) : (
          <EmptyState title="No investments" />
        )}
      </Panel>

      <Panel title="Reminders">
        {reminders.length ? (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Title</th>
                  <th>Date</th>
                  <th>Type</th>
                </tr>
              </thead>
              <tbody>
                {reminders.map((r) => (
                  <tr key={r.id}>
                    <td>{r.title}</td>
                    <td>{formatDate(r.reminder_date)}</td>
                    <td>{r.reminder_type}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No reminders" />
        )}
      </Panel>

      <Panel title="Attachments">
        <AttachmentPanel clientId={client.id} />
      </Panel>
    </>
  );
}

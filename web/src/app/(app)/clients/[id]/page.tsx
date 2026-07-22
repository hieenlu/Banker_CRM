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
import {
  allocationSlices,
  assetsVsDebt,
  conicGradient,
  groupInvestments,
  subgroupMeta,
} from "@/lib/portfolioMeta";
import type { Client, Income, Investment, Reminder } from "@/lib/types";

const TABS = ["Overview", "Portfolio", "Cashflow", "Past", "More"] as const;
type Tab = (typeof TABS)[number];

export default function ClientDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const clientId = Number(params.id);
  const [tab, setTab] = useState<Tab>("Overview");
  const [client, setClient] = useState<Client | null>(null);
  const [investments, setInvestments] = useState<Investment[]>([]);
  const [incomes, setIncomes] = useState<Income[]>([]);
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<Partial<Client>>({});
  const [busy, setBusy] = useState(false);
  const [drillGroup, setDrillGroup] = useState<string | null>(null);

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

  const groups = useMemo(() => groupInvestments(investments), [investments]);
  const alloc = useMemo(
    () => allocationSlices(groups, { excludeDebtRe: true }),
    [groups],
  );
  const vsDebt = useMemo(() => assetsVsDebt(groups), [groups]);
  const openInv = useMemo(
    () => investments.filter((i) => !i.is_done),
    [investments],
  );
  const pastInv = useMemo(
    () => investments.filter((i) => i.is_done),
    [investments],
  );
  const openInc = useMemo(() => incomes.filter((i) => !i.is_done), [incomes]);
  const pastInc = useMemo(() => incomes.filter((i) => i.is_done), [incomes]);

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
        home_insurance_amount_covered:
          form.home_insurance_amount_covered ?? null,
        home_insurance_expiry_date: form.home_insurance_expiry_date || null,
        home_insurance_insured_premium:
          form.home_insurance_insured_premium ?? null,
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
          ← Back to all clients
        </Link>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title={client.name}
        description={`Birthday: ${formatDate(client.birthday)}`}
        actions={
          <>
            <Link href="/clients" className="btn btn-ghost">
              ← Back to all clients
            </Link>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                setTab("More");
                setEditing(true);
              }}
            >
              Edit this client
            </button>
            <button
              type="button"
              className="btn btn-primary"
              disabled={busy}
              onClick={() => void onDelete()}
            >
              Delete this client
            </button>
          </>
        }
      />

      <ErrorBanner message={error} />

      <div className="crm-tabs" role="tablist">
        {TABS.map((t) => (
          <button
            key={t}
            type="button"
            role="tab"
            aria-selected={tab === t}
            className={`crm-tab ${tab === t ? "active" : ""}`}
            onClick={() => setTab(t)}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "Overview" ? (
        <OverviewTab
          groups={groups}
          alloc={alloc}
          vsDebt={vsDebt}
          drillGroup={drillGroup}
          setDrillGroup={setDrillGroup}
        />
      ) : null}

      {tab === "Portfolio" ? (
        <HoldingsTable
          title="Open positions"
          items={openInv}
          empty="No open investments"
        />
      ) : null}

      {tab === "Cashflow" ? (
        <>
          <div className="metric-grid" style={{ marginBottom: "1rem" }}>
            <div className="metric">
              <div className="metric-label">Salary</div>
              <div className="metric-value">
                {formatMoney(client.salary_amount)}
              </div>
            </div>
            <div className="metric">
              <div className="metric-label">Dividends</div>
              <div className="metric-value">
                {formatMoney(client.dividends_amount)}
              </div>
            </div>
            <div className="metric">
              <div className="metric-label">Other income</div>
              <div className="metric-value">
                {formatMoney(client.others_income_amount)}
              </div>
            </div>
          </div>
          <IncomeTable items={openInc} />
        </>
      ) : null}

      {tab === "Past" ? (
        <>
          <HoldingsTable
            title="Completed investments"
            items={pastInv}
            empty="No completed investments"
          />
          <IncomeTable items={pastInc} title="Completed incomes" />
        </>
      ) : null}

      {tab === "More" ? (
        <>
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
                <div className="toolbar">
                  <button
                    type="submit"
                    className="btn btn-primary"
                    disabled={busy}
                  >
                    {busy ? "Saving…" : "Save profile"}
                  </button>
                  <button
                    type="button"
                    className="btn btn-ghost"
                    onClick={() => {
                      setForm(client);
                      setEditing(false);
                    }}
                  >
                    Cancel
                  </button>
                </div>
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

          <Panel title="Home insurance">
            <dl className="detail-grid">
              <div>
                <dt>Amount covered</dt>
                <dd>{formatMoney(client.home_insurance_amount_covered)}</dd>
              </div>
              <div>
                <dt>Expiry</dt>
                <dd>{formatDate(client.home_insurance_expiry_date)}</dd>
              </div>
              <div>
                <dt>Premium</dt>
                <dd>{formatMoney(client.home_insurance_insured_premium)}</dd>
              </div>
            </dl>
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
      ) : null}
    </>
  );
}

function OverviewTab({
  groups,
  alloc,
  vsDebt,
  drillGroup,
  setDrillGroup,
}: {
  groups: ReturnType<typeof groupInvestments>;
  alloc: ReturnType<typeof allocationSlices>;
  vsDebt: ReturnType<typeof assetsVsDebt>;
  drillGroup: string | null;
  setDrillGroup: (name: string | null) => void;
}) {
  const drill = groups.find((g) => g.name === drillGroup);

  return (
    <div className="overview-layout">
      <aside className="overview-side">
        <div className="donut-panel">
          <div className="donut-caption">Allocation (excl. RE / debt)</div>
          <div
            className="donut-wrap"
            style={{ background: conicGradient(alloc.slices) }}
          >
            <div className="donut-hole">
              <div className="donut-total">{formatMoney(alloc.total)}</div>
              <div className="donut-label">Invested</div>
            </div>
          </div>
          <ul className="legend">
            {alloc.slices.map((s) => (
              <li key={s.name}>
                <span>
                  <span
                    className="legend-swatch"
                    style={{ background: s.color }}
                  />
                  {s.name}
                </span>
                <span>{s.pct.toFixed(0)}%</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="donut-panel">
          <div className="donut-caption">Assets vs debt</div>
          <div
            className="donut-wrap"
            style={{
              width: 128,
              height: 128,
              background: conicGradient(vsDebt.slices),
            }}
          >
            <div className="donut-hole">
              <div className="donut-total" style={{ fontSize: "0.82rem" }}>
                {formatMoney(vsDebt.assets)}
              </div>
              <div className="donut-label">Net assets</div>
            </div>
          </div>
          <ul className="legend">
            {vsDebt.slices.map((s) => (
              <li key={s.name}>
                <span>
                  <span
                    className="legend-swatch"
                    style={{ background: s.color }}
                  />
                  {s.name}
                </span>
                <span>{formatMoney(s.value)}</span>
              </li>
            ))}
          </ul>
        </div>
      </aside>

      <div>
        {drill ? (
          <Panel
            title={`${subgroupMeta(drill.name).icon} ${drill.name}`}
            actions={
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => setDrillGroup(null)}
              >
                Back to catalog
              </button>
            }
          >
            <HoldingsTable items={drill.items} empty="No holdings" />
          </Panel>
        ) : (
          <div className="asset-catalog">
            {groups.length ? (
              groups.map((g) => {
                const meta = subgroupMeta(g.name);
                const pnl = g.value - g.cost;
                const share =
                  alloc.total > 0 &&
                  g.name !== "Debt" &&
                  g.name !== "Real Estate"
                    ? (Math.abs(g.value) / alloc.total) * 100
                    : vsDebt.total > 0
                      ? (Math.abs(g.value) / vsDebt.total) * 100
                      : 0;
                return (
                  <button
                    key={g.name}
                    type="button"
                    className="asset-card"
                    style={{ ["--card-accent" as string]: meta.color, textAlign: "left", cursor: "pointer", width: "100%" }}
                    onClick={() => setDrillGroup(g.name)}
                  >
                    <div className="asset-card-head">
                      <span className="asset-card-name">
                        {meta.icon} {g.name}
                      </span>
                      <span className="asset-card-pct">{share.toFixed(0)}%</span>
                    </div>
                    <div className="asset-card-metrics">
                      <div>
                        <span>{meta.m1}: </span>
                        <strong>{formatMoney(g.value)}</strong>
                      </div>
                      <div>
                        <span>{meta.m2}: </span>
                        <strong
                          className={
                            pnl >= 0 ? "pnl-pos" : "pnl-neg"
                          }
                        >
                          {formatMoney(pnl)}
                        </strong>
                      </div>
                      <div className="muted small">{g.count} positions</div>
                    </div>
                  </button>
                );
              })
            ) : (
              <EmptyState title="No open holdings" />
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function HoldingsTable({
  title,
  items,
  empty,
}: {
  title?: string;
  items: Investment[];
  empty: string;
}) {
  const body = items.length ? (
    <div className="table-wrap">
      <table className="data">
        <thead>
          <tr>
            <th>Asset type</th>
            <th>Name</th>
            <th>Qty</th>
            <th>Price</th>
            <th>Value</th>
            <th>Maturity</th>
          </tr>
        </thead>
        <tbody>
          {items.map((inv) => (
            <tr key={inv.id}>
              <td>{inv.asset_type}</td>
              <td>
                <strong>{inv.ticker_name || inv.ticker_identifier || "—"}</strong>
                <div className="muted small">{inv.ticker_identifier}</div>
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
    <EmptyState title={empty} />
  );

  if (!title) return body;
  return <Panel title={title}>{body}</Panel>;
}

function IncomeTable({
  items,
  title = "Incomes",
}: {
  items: Income[];
  title?: string;
}) {
  return (
    <Panel title={title}>
      {items.length ? (
        <div className="table-wrap">
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
              {items.map((row) => (
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
        <EmptyState title="No income rows" />
      )}
    </Panel>
  );
}

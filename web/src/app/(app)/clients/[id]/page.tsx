"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { explainError } from "@/components/AuthProvider";
import { AddFinancialEntryForm } from "@/components/AddFinancialEntryForm";
import { AttachmentPanel } from "@/components/AttachmentPanel";
import { IncomeEditForm } from "@/components/IncomeEditForm";
import { InvestmentEditForm } from "@/components/InvestmentEditForm";
import { PortfolioTables } from "@/components/PortfolioTables";
import {
  EmptyState,
  ErrorBanner,
  LoadingBlock,
  PageHeader,
  Panel,
} from "@/components/ui";
import { formatDate, formatMoney, formatPct, pnlClass } from "@/lib/format";
import type { AddEntryOption } from "@/lib/investmentMeta";
import {
  allocationSlices,
  assetsVsDebt,
  conicGradient,
  subgroupMeta,
  type GroupTotals,
} from "@/lib/portfolioMeta";
import type {
  Client,
  Income,
  PortfolioSubgroup,
  PortfolioView,
  Reminder,
} from "@/lib/types";

const TABS = ["Overview", "Portfolio", "Cashflow", "Past", "More"] as const;
type Tab = (typeof TABS)[number];

function groupsFromView(view: PortfolioView | null): GroupTotals[] {
  if (!view) return [];
  const out: GroupTotals[] = [];
  for (const g of view.groups) {
    for (const s of g.subgroups) {
      const value = s.rows.reduce(
        (sum, r) =>
          sum +
          Number(r["Current Value Display"] ?? r["Current Value"] ?? 0),
        0,
      );
      const cost = s.rows.reduce(
        (sum, r) =>
          sum + Number(r["Principal Display"] ?? r["Principal"] ?? 0),
        0,
      );
      out.push({
        name: s.name,
        value,
        cost,
        count: s.rows.length,
        items: [],
      });
    }
  }
  return out.sort((a, b) => Math.abs(b.value) - Math.abs(a.value));
}

function findSubgroup(
  view: PortfolioView | null,
  name: string | null,
): PortfolioSubgroup | null {
  if (!view || !name) return null;
  for (const g of view.groups) {
    for (const s of g.subgroups) {
      if (s.name === name) return s;
    }
  }
  return null;
}

export default function ClientDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const clientId = Number(params.id);
  const [tab, setTab] = useState<Tab>("Overview");
  const [client, setClient] = useState<Client | null>(null);
  const [portfolio, setPortfolio] = useState<PortfolioView | null>(null);
  const [pastPortfolio, setPastPortfolio] = useState<PortfolioView | null>(
    null,
  );
  const [incomes, setIncomes] = useState<Income[]>([]);
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [editingInsurance, setEditingInsurance] = useState(false);
  const [form, setForm] = useState<Partial<Client>>({});
  const [insuranceForm, setInsuranceForm] = useState({
    home_insurance_amount_covered: "" as string,
    home_insurance_expiry_date: "" as string,
    home_insurance_insured_premium: "" as string,
  });
  const [hasBirthday, setHasBirthday] = useState(false);
  const [busy, setBusy] = useState(false);
  const [drillGroup, setDrillGroup] = useState<string | null>(null);
  const [editInvId, setEditInvId] = useState<number | null>(null);
  const [pendingDone, setPendingDone] = useState<{
    id: number;
    closingPrice: string;
  } | null>(null);
  const [busyInvId, setBusyInvId] = useState<number | null>(null);
  const [showAddEntry, setShowAddEntry] = useState(false);
  const [addEntryPreset, setAddEntryPreset] = useState<
    AddEntryOption | undefined
  >(undefined);
  const [editIncomeId, setEditIncomeId] = useState<number | null>(null);
  const [busyIncomeId, setBusyIncomeId] = useState<number | null>(null);

  const load = useCallback(async () => {
    if (!Number.isFinite(clientId)) return;
    setLoading(true);
    setError(null);
    try {
      const [c, port, past, inc, rem] = await Promise.all([
        api.getClient(clientId),
        api.portfolioView({
          client_id: clientId,
          is_done: false,
          display_currency: "VND",
        }),
        api.portfolioView({
          client_id: clientId,
          is_done: true,
          display_currency: "VND",
        }),
        api.listIncomes({ client_id: clientId, page_size: 100 }),
        api.listReminders({ client_id: clientId, page_size: 50 }),
      ]);
      setClient(c);
      setForm(c);
      setHasBirthday(Boolean(c.birthday));
      setInsuranceForm({
        home_insurance_amount_covered:
          c.home_insurance_amount_covered != null
            ? String(c.home_insurance_amount_covered)
            : "",
        home_insurance_expiry_date: c.home_insurance_expiry_date || "",
        home_insurance_insured_premium:
          c.home_insurance_insured_premium != null
            ? String(c.home_insurance_insured_premium)
            : "",
      });
      setEditing(false);
      setEditingInsurance(false);
      setPortfolio(port);
      setPastPortfolio(past);
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

  const groups = useMemo(() => groupsFromView(portfolio), [portfolio]);
  const alloc = useMemo(
    () => allocationSlices(groups, { excludeDebtRe: true }),
    [groups],
  );
  const vsDebt = useMemo(() => assetsVsDebt(groups), [groups]);
  const openInc = useMemo(() => incomes.filter((i) => !i.is_done), [incomes]);
  const pastInc = useMemo(() => incomes.filter((i) => i.is_done), [incomes]);
  const actualInc = useMemo(
    () => openInc.filter((i) => (i.income_mode || "Actual") !== "Forecast"),
    [openInc],
  );
  const forecastInc = useMemo(
    () => openInc.filter((i) => (i.income_mode || "Actual") === "Forecast"),
    [openInc],
  );
  const editingIncome = useMemo(
    () => incomes.find((i) => i.id === editIncomeId) || null,
    [incomes, editIncomeId],
  );

  async function onRefreshPrices() {
    setBusy(true);
    setStatus(null);
    setError(null);
    try {
      const result = await api.refreshPrices({
        client_id: clientId,
        is_done: false,
      });
      setStatus(
        `Prices: ${result.resolved}/${result.requested} resolved, ${result.updated} updated` +
          (result.missing?.length
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

  function startEditClient() {
    if (!client) return;
    setForm(client);
    setHasBirthday(Boolean(client.birthday));
    setEditing(true);
    setEditingInsurance(false);
    setTab("More");
    setStatus(null);
    setError(null);
  }

  function revertClientEdit() {
    if (!client) return;
    setForm(client);
    setHasBirthday(Boolean(client.birthday));
    setEditing(false);
    setStatus(null);
    setError(null);
  }

  function startEditInsurance() {
    if (!client) return;
    setInsuranceForm({
      home_insurance_amount_covered:
        client.home_insurance_amount_covered != null
          ? String(client.home_insurance_amount_covered)
          : "",
      home_insurance_expiry_date: client.home_insurance_expiry_date || "",
      home_insurance_insured_premium:
        client.home_insurance_insured_premium != null
          ? String(client.home_insurance_insured_premium)
          : "",
    });
    setEditingInsurance(true);
    setEditing(false);
    setStatus(null);
    setError(null);
  }

  function revertInsuranceEdit() {
    if (!client) return;
    setInsuranceForm({
      home_insurance_amount_covered:
        client.home_insurance_amount_covered != null
          ? String(client.home_insurance_amount_covered)
          : "",
      home_insurance_expiry_date: client.home_insurance_expiry_date || "",
      home_insurance_insured_premium:
        client.home_insurance_insured_premium != null
          ? String(client.home_insurance_insured_premium)
          : "",
    });
    setEditingInsurance(false);
    setStatus(null);
    setError(null);
  }

  async function onSave(e: FormEvent) {
    e.preventDefault();
    if (!client) return;
    const cleanName = (form.name || "").trim();
    if (!cleanName) {
      setError("Name is required.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const updated = await api.updateClient(client.id, {
        name: cleanName,
        birthday: hasBirthday ? form.birthday || null : null,
        address: (form.address || "").trim() || null,
        phone_number: (form.phone_number || "").trim() || null,
        email: (form.email || "").trim() || null,
        notes: (form.notes || "").trim() || null,
      });
      setClient(updated);
      setForm(updated);
      setHasBirthday(Boolean(updated.birthday));
      setEditing(false);
      setStatus("Client updated.");
    } catch (err) {
      setError(explainError(err));
    } finally {
      setBusy(false);
    }
  }

  async function onSaveInsurance(e: FormEvent) {
    e.preventDefault();
    if (!client) return;
    setBusy(true);
    setError(null);
    try {
      const amount = insuranceForm.home_insurance_amount_covered.trim();
      const premium = insuranceForm.home_insurance_insured_premium.trim();
      const expiry = insuranceForm.home_insurance_expiry_date.trim();
      const updated = await api.updateClient(client.id, {
        home_insurance_amount_covered: amount === "" ? null : Number(amount),
        home_insurance_expiry_date: expiry || null,
        home_insurance_insured_premium: premium === "" ? null : Number(premium),
      });
      setClient(updated);
      setForm(updated);
      setInsuranceForm({
        home_insurance_amount_covered:
          updated.home_insurance_amount_covered != null
            ? String(updated.home_insurance_amount_covered)
            : "",
        home_insurance_expiry_date: updated.home_insurance_expiry_date || "",
        home_insurance_insured_premium:
          updated.home_insurance_insured_premium != null
            ? String(updated.home_insurance_insured_premium)
            : "",
      });
      setEditingInsurance(false);
      setStatus("Home insurance updated.");
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

  const handleInvError = useCallback((message: string) => {
    setError(message);
  }, []);

  async function reloadPortfolios() {
    const [port, past] = await Promise.all([
      api.portfolioView({
        client_id: clientId,
        is_done: false,
        display_currency: "VND",
      }),
      api.portfolioView({
        client_id: clientId,
        is_done: true,
        display_currency: "VND",
      }),
    ]);
    setPortfolio(port);
    setPastPortfolio(past);
  }

  async function reloadIncomes() {
    const inc = await api.listIncomes({ client_id: clientId, page_size: 100 });
    setIncomes(inc.items);
  }

  function openAddEntry(preset?: AddEntryOption, nextTab?: Tab) {
    setShowAddEntry(true);
    setAddEntryPreset(preset);
    setEditInvId(null);
    setEditIncomeId(null);
    setPendingDone(null);
    setEditing(false);
    setEditingInsurance(false);
    if (nextTab) setTab(nextTab);
    setError(null);
    setStatus(null);
  }

  function startEditInvestment(id: number) {
    setEditInvId(id);
    setPendingDone(null);
    setShowAddEntry(false);
    setEditIncomeId(null);
    setEditing(false);
    setEditingInsurance(false);
    setTab("Portfolio");
    setError(null);
    setStatus(null);
  }

  function startEditIncome(id: number) {
    setEditIncomeId(id);
    setShowAddEntry(false);
    setEditInvId(null);
    setPendingDone(null);
    setTab("Cashflow");
    setError(null);
    setStatus(null);
  }

  function startDoneInvestment(id: number, currentPrice: number | null) {
    setPendingDone({
      id,
      closingPrice:
        currentPrice != null && Number.isFinite(currentPrice)
          ? String(currentPrice)
          : "0",
    });
    setEditInvId(null);
    setShowAddEntry(false);
    setEditIncomeId(null);
    setError(null);
    setStatus(null);
  }

  async function confirmDoneInvestment() {
    if (!pendingDone) return;
    setBusyInvId(pendingDone.id);
    setError(null);
    try {
      const close = Number(pendingDone.closingPrice);
      await api.updateInvestment(pendingDone.id, {
        is_done: true,
        current_price: Number.isFinite(close) ? close : 0,
      });
      setPendingDone(null);
      setStatus("Investment marked as done.");
      await reloadPortfolios();
      setTab("Past");
    } catch (err) {
      setError(explainError(err));
    } finally {
      setBusyInvId(null);
    }
  }

  async function revertInvestment(id: number) {
    setBusyInvId(id);
    setError(null);
    try {
      await api.updateInvestment(id, { is_done: false });
      setStatus("Investment moved back to active.");
      await reloadPortfolios();
      setTab("Portfolio");
    } catch (err) {
      setError(explainError(err));
    } finally {
      setBusyInvId(null);
    }
  }

  async function deleteInvestment(id: number) {
    if (!window.confirm("Confirm delete investment?")) return;
    setBusyInvId(id);
    setError(null);
    try {
      await api.deleteInvestment(id);
      if (editInvId === id) setEditInvId(null);
      if (pendingDone?.id === id) setPendingDone(null);
      setStatus("Investment deleted.");
      await reloadPortfolios();
    } catch (err) {
      setError(explainError(err));
    } finally {
      setBusyInvId(null);
    }
  }

  async function revertIncome(id: number) {
    setBusyIncomeId(id);
    setError(null);
    try {
      await api.updateIncome(id, { is_done: false });
      await reloadIncomes();
      setStatus("Activity moved back to active.");
      setTab("Cashflow");
    } catch (err) {
      setError(explainError(err));
    } finally {
      setBusyIncomeId(null);
    }
  }

  async function markIncomeDone(id: number) {
    setBusyIncomeId(id);
    setError(null);
    try {
      await api.updateIncome(id, { is_done: true });
      if (editIncomeId === id) setEditIncomeId(null);
      await reloadIncomes();
      setStatus("Cashflow marked as done.");
      setTab("Past");
    } catch (err) {
      setError(explainError(err));
    } finally {
      setBusyIncomeId(null);
    }
  }

  async function deleteIncome(id: number) {
    if (!window.confirm("Confirm delete cashflow entry?")) return;
    setBusyIncomeId(id);
    setError(null);
    try {
      await api.deleteIncome(id);
      if (editIncomeId === id) setEditIncomeId(null);
      await reloadIncomes();
      setStatus("Cashflow deleted.");
    } catch (err) {
      setError(explainError(err));
    } finally {
      setBusyIncomeId(null);
    }
  }

  async function onAddEntrySaved(result: {
    kind: "investment" | "income" | "obligation";
    item: unknown;
  }) {
    setShowAddEntry(false);
    setAddEntryPreset(undefined);
    try {
      if (result.kind === "investment") {
        setStatus("Investment added.");
        await reloadPortfolios();
        setTab("Portfolio");
      } else if (result.kind === "income") {
        setStatus("Cashflow added.");
        await reloadIncomes();
        setTab("Cashflow");
      } else {
        setStatus("Obligation added.");
        const c = result.item as Client;
        setClient(c);
        setForm(c);
        setInsuranceForm({
          home_insurance_amount_covered:
            c.home_insurance_amount_covered != null
              ? String(c.home_insurance_amount_covered)
              : "",
          home_insurance_expiry_date: c.home_insurance_expiry_date || "",
          home_insurance_insured_premium:
            c.home_insurance_insured_premium != null
              ? String(c.home_insurance_insured_premium)
              : "",
        });
        setTab("More");
      }
    } catch (err) {
      setError(explainError(err));
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

  const totals = portfolio?.totals;

  return (
    <>
      <PageHeader
        title={client.name}
        description={`Birthday: ${formatDate(client.birthday)} · Display VND`}
        actions={
          <>
            <Link href="/clients" className="btn btn-ghost">
              ← Back to all clients
            </Link>
            <button
              type="button"
              className="btn btn-secondary"
              disabled={busy}
              onClick={() => void onRefreshPrices()}
            >
              {busy ? "Refreshing…" : "Refresh prices"}
            </button>
          </>
        }
      />

      <div className="toolbar client-actions" style={{ marginBottom: "0.85rem" }}>
        <span className="muted small">Client actions</span>
        <button
          type="button"
          className="btn btn-secondary"
          disabled={busy || editing}
          onClick={startEditClient}
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
      </div>

      {status ? <p className="muted">{status}</p> : null}
      <ErrorBanner message={error} />

      {editing ? (
        <Panel title="Client's information">
          <form className="stack" onSubmit={onSave}>
            <div className="detail-grid">
              <label className="field">
                <span>Name</span>
                <input
                  type="text"
                  required
                  value={form.name || ""}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, name: e.target.value }))
                  }
                />
              </label>
              <label className="field checkbox-field">
                <span>Has birthday?</span>
                <input
                  type="checkbox"
                  checked={hasBirthday}
                  onChange={(e) => setHasBirthday(e.target.checked)}
                />
              </label>
              <label className="field">
                <span>Birthday</span>
                <input
                  type="date"
                  disabled={!hasBirthday}
                  value={form.birthday || ""}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, birthday: e.target.value }))
                  }
                />
              </label>
              <label className="field">
                <span>Address</span>
                <textarea
                  value={form.address || ""}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, address: e.target.value }))
                  }
                />
              </label>
              <label className="field">
                <span>Phone number</span>
                <input
                  type="text"
                  value={form.phone_number || ""}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, phone_number: e.target.value }))
                  }
                />
              </label>
              <label className="field">
                <span>Email</span>
                <input
                  type="email"
                  value={form.email || ""}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, email: e.target.value }))
                  }
                />
              </label>
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
                {busy ? "Saving…" : "Save client"}
              </button>
              <button
                type="button"
                className="btn btn-ghost"
                disabled={busy}
                onClick={revertClientEdit}
              >
                Revert
              </button>
            </div>
          </form>
        </Panel>
      ) : null}

      {totals ? (
        <div className="metric-grid" style={{ marginBottom: "1rem" }}>
          <div className="metric">
            <div className="metric-label">Principal (VND)</div>
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
              {formatMoney(totals.pnl, "VND")}{" "}
              <span className="small">{formatPct(totals.pnl_pct)}</span>
            </div>
          </div>
        </div>
      ) : null}

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
          portfolio={portfolio}
        />
      ) : null}

      {tab === "Portfolio" ? (
        <>
          <div className="toolbar" style={{ marginBottom: "0.85rem" }}>
            <button
              type="button"
              className="btn btn-secondary"
              disabled={busy}
              onClick={() => openAddEntry(undefined, "Portfolio")}
            >
              Add Investment/Debts/Cashflow
            </button>
          </div>

          {showAddEntry ? (
            <AddFinancialEntryForm
              clientId={clientId}
              initialEntryType={addEntryPreset}
              onError={handleInvError}
              onCancel={() => {
                setShowAddEntry(false);
                setAddEntryPreset(undefined);
              }}
              onSaved={(result) => void onAddEntrySaved(result)}
            />
          ) : null}

          {editInvId != null ? (
            <InvestmentEditForm
              investmentId={editInvId}
              onError={handleInvError}
              onCancel={() => {
                setEditInvId(null);
                setStatus(null);
              }}
              onSaved={async () => {
                setEditInvId(null);
                setStatus("Investment updated.");
                try {
                  await reloadPortfolios();
                } catch (err) {
                  setError(explainError(err));
                }
              }}
            />
          ) : null}

          {pendingDone ? (
            <Panel title="Mark investment done">
              <p className="muted">
                Set closing price before moving investment to past?
              </p>
              <form
                className="stack"
                onSubmit={(e) => {
                  e.preventDefault();
                  void confirmDoneInvestment();
                }}
              >
                <label className="field">
                  <span>Closing Price</span>
                  <input
                    type="number"
                    min={0}
                    step={0.01}
                    value={pendingDone.closingPrice}
                    onChange={(e) =>
                      setPendingDone((p) =>
                        p ? { ...p, closingPrice: e.target.value } : p,
                      )
                    }
                  />
                </label>
                <div className="toolbar">
                  <button
                    type="submit"
                    className="btn btn-primary"
                    disabled={busyInvId === pendingDone.id}
                  >
                    Confirm done
                  </button>
                  <button
                    type="button"
                    className="btn btn-ghost"
                    disabled={busyInvId === pendingDone.id}
                    onClick={() => setPendingDone(null)}
                  >
                    Cancel
                  </button>
                </div>
              </form>
            </Panel>
          ) : null}

          {portfolio ? (
            <PortfolioTables
              view={portfolio}
              actions={{
                mode: "active",
                busyId: busyInvId,
                onEdit: startEditInvestment,
                onDone: startDoneInvestment,
                onDelete: (id) => void deleteInvestment(id),
              }}
            />
          ) : (
            <EmptyState title="No open investments" />
          )}
        </>
      ) : null}

      {tab === "Cashflow" ? (
        <>
          <div className="toolbar" style={{ marginBottom: "0.85rem" }}>
            <button
              type="button"
              className="btn btn-secondary"
              disabled={busy}
              onClick={() => openAddEntry("Salary", "Cashflow")}
            >
              Add cashflow
            </button>
          </div>

          {showAddEntry && tab === "Cashflow" ? (
            <AddFinancialEntryForm
              clientId={clientId}
              initialEntryType={addEntryPreset || "Salary"}
              onError={handleInvError}
              onCancel={() => {
                setShowAddEntry(false);
                setAddEntryPreset(undefined);
              }}
              onSaved={(result) => void onAddEntrySaved(result)}
            />
          ) : null}

          {editingIncome ? (
            <IncomeEditForm
              income={editingIncome}
              onError={handleInvError}
              onCancel={() => setEditIncomeId(null)}
              onSaved={async () => {
                setEditIncomeId(null);
                setStatus("Income updated.");
                try {
                  await reloadIncomes();
                } catch (err) {
                  setError(explainError(err));
                }
              }}
            />
          ) : null}

          <div className="metric-grid" style={{ marginBottom: "1rem" }}>
            <div className="metric">
              <div className="metric-label">Salary</div>
              <div className="metric-value">
                {formatMoney(client.salary_amount, "VND")}
              </div>
            </div>
            <div className="metric">
              <div className="metric-label">Dividends</div>
              <div className="metric-value">
                {formatMoney(client.dividends_amount, "VND")}
              </div>
            </div>
            <div className="metric">
              <div className="metric-label">Other income</div>
              <div className="metric-value">
                {formatMoney(client.others_income_amount, "VND")}
              </div>
            </div>
          </div>
          <IncomeTable
            items={actualInc}
            title="Incomes"
            busyId={busyIncomeId}
            onEdit={startEditIncome}
            onDone={(id) => void markIncomeDone(id)}
            onDelete={(id) => void deleteIncome(id)}
          />
          <IncomeTable
            items={forecastInc}
            title="Forecast incomes"
            busyId={busyIncomeId}
            onEdit={startEditIncome}
            onDone={(id) => void markIncomeDone(id)}
            onDelete={(id) => void deleteIncome(id)}
          />
        </>
      ) : null}

      {tab === "Past" ? (
        <>
          {pastPortfolio?.groups.length ? (
            <PortfolioTables
              view={pastPortfolio}
              actions={{
                mode: "past",
                busyId: busyInvId,
                onRevert: (id) => void revertInvestment(id),
              }}
            />
          ) : (
            <EmptyState title="No completed investments" />
          )}
          <IncomeTable
            items={pastInc}
            title="Completed incomes"
            busyId={busyIncomeId}
            onRevert={(id) => void revertIncome(id)}
          />
        </>
      ) : null}

      {tab === "More" ? (
        <>
          <div className="toolbar" style={{ marginBottom: "0.85rem" }}>
            <button
              type="button"
              className="btn btn-secondary"
              disabled={busy}
              onClick={() => openAddEntry(undefined, "More")}
            >
              Add Investment/Debts/Cashflow
            </button>
          </div>

          {showAddEntry ? (
            <AddFinancialEntryForm
              clientId={clientId}
              initialEntryType={addEntryPreset}
              onError={handleInvError}
              onCancel={() => {
                setShowAddEntry(false);
                setAddEntryPreset(undefined);
              }}
              onSaved={(result) => void onAddEntrySaved(result)}
            />
          ) : null}

          <Panel
            title="Client's information"
            actions={
              editing ? null : (
                <button
                  type="button"
                  className="btn btn-secondary"
                  disabled={busy}
                  onClick={startEditClient}
                >
                  Edit
                </button>
              )
            }
          >
            {editing ? (
              <p className="muted small">
                Editing above — use Save client or Revert.
              </p>
            ) : (
              <dl className="detail-grid">
                <div>
                  <dt>Name</dt>
                  <dd>{client.name}</dd>
                </div>
                <div>
                  <dt>Birthday</dt>
                  <dd>{formatDate(client.birthday)}</dd>
                </div>
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

          <Panel
            title="Home insurance"
            actions={
              editingInsurance ? null : (
                <button
                  type="button"
                  className="btn btn-secondary"
                  disabled={busy}
                  onClick={startEditInsurance}
                >
                  Edit
                </button>
              )
            }
          >
            {editingInsurance ? (
              <form className="stack" onSubmit={onSaveInsurance}>
                <div className="detail-grid">
                  <label className="field">
                    <span>Amount covered</span>
                    <input
                      type="number"
                      min={0}
                      step={1000}
                      value={insuranceForm.home_insurance_amount_covered}
                      onChange={(e) =>
                        setInsuranceForm((f) => ({
                          ...f,
                          home_insurance_amount_covered: e.target.value,
                        }))
                      }
                    />
                  </label>
                  <label className="field">
                    <span>Expiry date</span>
                    <input
                      type="date"
                      value={insuranceForm.home_insurance_expiry_date}
                      onChange={(e) =>
                        setInsuranceForm((f) => ({
                          ...f,
                          home_insurance_expiry_date: e.target.value,
                        }))
                      }
                    />
                  </label>
                  <label className="field">
                    <span>Insured premium</span>
                    <input
                      type="number"
                      min={0}
                      step={100}
                      value={insuranceForm.home_insurance_insured_premium}
                      onChange={(e) =>
                        setInsuranceForm((f) => ({
                          ...f,
                          home_insurance_insured_premium: e.target.value,
                        }))
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
                    {busy ? "Saving…" : "Save"}
                  </button>
                  <button
                    type="button"
                    className="btn btn-ghost"
                    disabled={busy}
                    onClick={revertInsuranceEdit}
                  >
                    Revert
                  </button>
                </div>
              </form>
            ) : (
              <dl className="detail-grid">
                <div>
                  <dt>Amount covered</dt>
                  <dd>
                    {formatMoney(client.home_insurance_amount_covered, "VND")}
                  </dd>
                </div>
                <div>
                  <dt>Expiry</dt>
                  <dd>{formatDate(client.home_insurance_expiry_date)}</dd>
                </div>
                <div>
                  <dt>Premium</dt>
                  <dd>
                    {formatMoney(client.home_insurance_insured_premium, "VND")}
                  </dd>
                </div>
              </dl>
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
  portfolio,
}: {
  groups: GroupTotals[];
  alloc: ReturnType<typeof allocationSlices>;
  vsDebt: ReturnType<typeof assetsVsDebt>;
  drillGroup: string | null;
  setDrillGroup: (name: string | null) => void;
  portfolio: PortfolioView | null;
}) {
  const drill = findSubgroup(portfolio, drillGroup);

  return (
    <div className="overview-layout">
      <aside className="overview-side">
        <div className="donut-panel">
          <div
            className="donut"
            style={{ background: conicGradient(alloc.slices) }}
            aria-hidden
          />
          <p className="donut-caption muted small">Allocation (ex debt / RE)</p>
          <ul className="legend">
            {alloc.slices.map((s) => (
              <li key={s.name}>
                <span>
                  <i style={{ background: s.color }} />
                  {s.name}
                </span>
                <span>{formatMoney(s.value, "VND")}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="donut-panel">
          <div
            className="donut"
            style={{ background: conicGradient(vsDebt.slices) }}
            aria-hidden
          />
          <p className="donut-caption muted small">Assets vs debt</p>
          <ul className="legend">
            {vsDebt.slices.map((s) => (
              <li key={s.name}>
                <span>
                  <i style={{ background: s.color }} />
                  {s.name}
                </span>
                <span>{formatMoney(s.value, "VND")}</span>
              </li>
            ))}
          </ul>
        </div>
      </aside>

      <div>
        {drill && portfolio ? (
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
            <PortfolioTables
              view={{
                ...portfolio,
                groups: [
                  {
                    name: "Detail",
                    subgroups: [drill],
                  },
                ],
              }}
            />
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
                    style={{
                      ["--card-accent" as string]: meta.color,
                      textAlign: "left",
                      cursor: "pointer",
                      width: "100%",
                    }}
                    onClick={() => setDrillGroup(g.name)}
                  >
                    <div className="asset-card-head">
                      <span className="asset-card-name">
                        {meta.icon} {g.name}
                      </span>
                      <span className="asset-card-pct">
                        {share.toFixed(0)}%
                      </span>
                    </div>
                    <div className="asset-card-metrics">
                      <div>
                        <span>{meta.m1}: </span>
                        <strong>{formatMoney(g.value, "VND")}</strong>
                      </div>
                      <div>
                        <span>{meta.m2}: </span>
                        <strong className={pnlClass(pnl)}>
                          {formatMoney(pnl, "VND")}
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

function IncomeTable({
  items,
  title = "Incomes",
  busyId = null,
  onEdit,
  onDone,
  onDelete,
  onRevert,
}: {
  items: Income[];
  title?: string;
  busyId?: number | null;
  onEdit?: (id: number) => void;
  onDone?: (id: number) => void;
  onDelete?: (id: number) => void;
  onRevert?: (id: number) => void;
}) {
  const showActiveActions = Boolean(onEdit || onDone || onDelete);
  const showRevert = Boolean(onRevert);

  return (
    <Panel title={title}>
      {items.length ? (
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>Type</th>
                <th>Mode</th>
                <th>Amount (VND)</th>
                <th>Concurrent</th>
                <th>Note</th>
                {showActiveActions || showRevert ? <th>Actions</th> : null}
              </tr>
            </thead>
            <tbody>
              {items.map((row) => {
                const busy = busyId === row.id;
                return (
                  <tr key={row.id}>
                    <td>{row.income_type}</td>
                    <td>{row.income_mode}</td>
                    <td>{formatMoney(row.amount, "VND")}</td>
                    <td>{row.concurrent ? "Yes" : "No"}</td>
                    <td>{row.note || "—"}</td>
                    {showActiveActions ? (
                      <td>
                        <div className="row-actions">
                          {onEdit ? (
                            <button
                              type="button"
                              className="btn btn-ghost"
                              title="Edit cashflow"
                              disabled={busy}
                              onClick={() => onEdit(row.id)}
                            >
                              ✏
                            </button>
                          ) : null}
                          {onDone ? (
                            <button
                              type="button"
                              className="btn btn-secondary"
                              title="Mark done"
                              disabled={busy}
                              onClick={() => onDone(row.id)}
                            >
                              ✔
                            </button>
                          ) : null}
                          {onDelete ? (
                            <button
                              type="button"
                              className="btn btn-primary"
                              title="Delete cashflow"
                              disabled={busy}
                              onClick={() => onDelete(row.id)}
                            >
                              ✖
                            </button>
                          ) : null}
                        </div>
                      </td>
                    ) : null}
                    {showRevert && !showActiveActions ? (
                      <td>
                        <button
                          type="button"
                          className="btn btn-secondary"
                          disabled={busy}
                          onClick={() => onRevert?.(row.id)}
                        >
                          ↩ Active
                        </button>
                      </td>
                    ) : null}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyState title="No incomes" />
      )}
    </Panel>
  );
}

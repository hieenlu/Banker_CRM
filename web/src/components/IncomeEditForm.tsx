"use client";

import { FormEvent, useState } from "react";
import { api } from "@/lib/api";
import { explainError } from "@/components/AuthProvider";
import { Panel } from "@/components/ui";
import type { Income } from "@/lib/types";
import {
  CASHFLOW_TYPES,
  INCOME_MODES,
  normalizeIncomeType,
} from "@/lib/investmentMeta";

export function IncomeEditForm({
  income,
  onSaved,
  onCancel,
  onError,
}: {
  income: Income;
  onSaved: (item: Income) => void;
  onCancel: () => void;
  onError: (message: string) => void;
}) {
  const [incomeType, setIncomeType] = useState(
    normalizeIncomeType(income.income_type),
  );
  const [incomeMode, setIncomeMode] = useState(
    income.income_mode === "Forecast" ? "Forecast" : "Actual",
  );
  const [amount, setAmount] = useState(String(income.amount ?? 0));
  const [concurrent, setConcurrent] = useState(Boolean(income.concurrent));
  const [note, setNote] = useState(income.note || "");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const amt = Number(amount || 0);
    if (amt < 0) {
      onError("Amount must be non-negative.");
      return;
    }
    setBusy(true);
    try {
      const updated = await api.updateIncome(income.id, {
        income_type: incomeType,
        income_mode: incomeMode,
        amount: amt,
        concurrent,
        note: note.trim() || null,
      });
      onSaved(updated);
    } catch (err) {
      onError(explainError(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel title="Edit cashflow">
      <form className="stack" onSubmit={onSubmit}>
        <div className="detail-grid">
          <label className="field">
            <span>Income Type</span>
            <select
              value={incomeType}
              onChange={(e) => setIncomeType(normalizeIncomeType(e.target.value))}
            >
              {CASHFLOW_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Mode</span>
            <select
              value={incomeMode}
              onChange={(e) => setIncomeMode(e.target.value)}
            >
              {INCOME_MODES.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Amount</span>
            <input
              type="number"
              min={0}
              step={1000}
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
            />
          </label>
          <label className="field checkbox-field">
            <span>Concurrent</span>
            <input
              type="checkbox"
              checked={concurrent}
              onChange={(e) => setConcurrent(e.target.checked)}
            />
          </label>
          <label className="field">
            <span>Note</span>
            <input
              type="text"
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
          </label>
        </div>
        <div className="toolbar">
          <button type="submit" className="btn btn-primary" disabled={busy}>
            {busy ? "Saving…" : "Save income"}
          </button>
          <button
            type="button"
            className="btn btn-ghost"
            disabled={busy}
            onClick={onCancel}
          >
            Cancel
          </button>
        </div>
      </form>
    </Panel>
  );
}

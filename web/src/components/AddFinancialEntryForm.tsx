"use client";

import { FormEvent, useState } from "react";
import { api } from "@/lib/api";
import { explainError } from "@/components/AuthProvider";
import { InvestmentFields } from "@/components/InvestmentFields";
import { Panel } from "@/components/ui";
import type { Client, Income, Investment } from "@/lib/types";
import {
  ADD_ENTRY_OPTIONS,
  ASSET_TYPES,
  INCOME_MODES,
  isCashflowType,
  isObligationType,
  type AddEntryOption,
} from "@/lib/investmentMeta";
import {
  buildInvestmentPayload,
  emptyInvestmentForm,
  validateInvestmentForm,
  type InvestmentFormState,
} from "@/lib/investmentForm";

type Result =
  | { kind: "investment"; item: Investment }
  | { kind: "income"; item: Income }
  | { kind: "obligation"; item: Client };

export function AddFinancialEntryForm({
  clientId,
  initialEntryType,
  onSaved,
  onCancel,
  onError,
}: {
  clientId: number;
  initialEntryType?: AddEntryOption;
  onSaved: (result: Result) => void;
  onCancel: () => void;
  onError: (message: string) => void;
}) {
  const [entryType, setEntryType] = useState<string>(
    initialEntryType || ASSET_TYPES[0],
  );
  const [invForm, setInvForm] = useState<InvestmentFormState>(() =>
    emptyInvestmentForm(ASSET_TYPES[0]),
  );
  const [incomeMode, setIncomeMode] = useState<string>(INCOME_MODES[0]);
  const [incomeAmount, setIncomeAmount] = useState("0");
  const [incomeConcurrent, setIncomeConcurrent] = useState(false);
  const [incomeNote, setIncomeNote] = useState("");
  const [obligationAmount, setObligationAmount] = useState("0");
  const [obligationExpiry, setObligationExpiry] = useState(
    () => new Date().toISOString().slice(0, 10),
  );
  const [obligationPremium, setObligationPremium] = useState("0");
  const [busy, setBusy] = useState(false);

  const isIncome = isCashflowType(entryType);
  const isObligation = isObligationType(entryType);

  function onEntryTypeChange(next: string) {
    setEntryType(next);
    if (!isCashflowType(next) && !isObligationType(next)) {
      setInvForm(emptyInvestmentForm(next));
    }
  }

  function setInv<K extends keyof InvestmentFormState>(
    key: K,
    value: InvestmentFormState[K],
  ) {
    setInvForm((f) => ({ ...f, [key]: value }));
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      if (isIncome) {
        const amount = Number(incomeAmount || 0);
        if (amount < 0) {
          onError("Amount must be non-negative.");
          return;
        }
        const item = await api.createIncome({
          client_id: clientId,
          income_type: entryType,
          income_mode: incomeMode,
          amount,
          concurrent: incomeConcurrent,
          note: incomeNote.trim() || null,
        });
        onSaved({ kind: "income", item });
        return;
      }

      if (isObligation) {
        const amount = Number(obligationAmount || 0);
        const premium = Number(obligationPremium || 0);
        if (amount < 0 || premium < 0) {
          onError("Amounts must be non-negative.");
          return;
        }
        const item = await api.updateClient(clientId, {
          home_insurance_amount_covered: amount,
          home_insurance_expiry_date: obligationExpiry || null,
          home_insurance_insured_premium: premium,
        });
        onSaved({ kind: "obligation", item });
        return;
      }

      const form = { ...invForm, asset_type: entryType };
      const validation = validateInvestmentForm(form);
      if (validation) {
        onError(validation);
        return;
      }
      const payload = buildInvestmentPayload(form);
      const item = await api.createInvestment({
        client_id: clientId,
        ...payload,
        is_done: false,
      });
      onSaved({ kind: "investment", item });
    } catch (err) {
      onError(explainError(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel title="Add Investment/Debts/Cashflow">
      <form className="stack" onSubmit={onSubmit}>
        <div className="detail-grid">
          <label className="field">
            <span>Asset Type</span>
            <select
              value={entryType}
              onChange={(e) => onEntryTypeChange(e.target.value)}
            >
              {ADD_ENTRY_OPTIONS.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </label>
        </div>

        {isIncome ? (
          <div className="detail-grid">
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
                value={incomeAmount}
                onChange={(e) => setIncomeAmount(e.target.value)}
              />
            </label>
            <label className="field checkbox-field">
              <span>Concurrent</span>
              <input
                type="checkbox"
                checked={incomeConcurrent}
                onChange={(e) => setIncomeConcurrent(e.target.checked)}
              />
            </label>
            <label className="field">
              <span>Note</span>
              <input
                type="text"
                value={incomeNote}
                onChange={(e) => setIncomeNote(e.target.value)}
              />
            </label>
          </div>
        ) : null}

        {isObligation ? (
          <div className="detail-grid">
            <label className="field">
              <span>Amount Covered</span>
              <input
                type="number"
                min={0}
                step={1000}
                value={obligationAmount}
                onChange={(e) => setObligationAmount(e.target.value)}
              />
            </label>
            <label className="field">
              <span>Expiry Date</span>
              <input
                type="date"
                value={obligationExpiry}
                onChange={(e) => setObligationExpiry(e.target.value)}
              />
            </label>
            <label className="field">
              <span>Insured Premium</span>
              <input
                type="number"
                min={0}
                step={100}
                value={obligationPremium}
                onChange={(e) => setObligationPremium(e.target.value)}
              />
            </label>
          </div>
        ) : null}

        {!isIncome && !isObligation ? (
          <InvestmentFields
            form={{ ...invForm, asset_type: entryType }}
            set={(key, value) => {
              if (key === "asset_type") {
                onEntryTypeChange(String(value));
              } else {
                setInv(key, value);
              }
            }}
            allowAssetTypeChange={false}
          />
        ) : null}

        <div className="toolbar">
          <button type="submit" className="btn btn-primary" disabled={busy}>
            {busy
              ? "Adding…"
              : isIncome
                ? "Add cashflow"
                : isObligation
                  ? "Add obligation"
                  : "Add"}
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

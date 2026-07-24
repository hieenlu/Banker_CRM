"use client";

import { FormEvent, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { explainError } from "@/components/AuthProvider";
import { InvestmentFields } from "@/components/InvestmentFields";
import { Panel } from "@/components/ui";
import type { Investment } from "@/lib/types";
import {
  buildInvestmentPayload,
  formFromInvestment,
  validateInvestmentForm,
  type InvestmentFormState,
} from "@/lib/investmentForm";

export function InvestmentEditForm({
  investmentId,
  onSaved,
  onCancel,
  onError,
}: {
  investmentId: number;
  onSaved: (inv: Investment) => void;
  onCancel: () => void;
  onError: (message: string) => void;
}) {
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState<InvestmentFormState | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    void api
      .getInvestment(investmentId)
      .then((inv) => {
        if (!cancelled) setForm(formFromInvestment(inv));
      })
      .catch((err) => {
        onError(explainError(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [investmentId, onError]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!form) return;
    const validation = validateInvestmentForm(form);
    if (validation) {
      onError(validation);
      return;
    }
    setBusy(true);
    try {
      const updated = await api.updateInvestment(
        investmentId,
        buildInvestmentPayload(form),
      );
      onSaved(updated);
    } catch (err) {
      onError(explainError(err));
    } finally {
      setBusy(false);
    }
  }

  if (loading || !form) {
    return (
      <Panel title="Edit investment">
        <p className="muted">Loading investment…</p>
      </Panel>
    );
  }

  function set<K extends keyof InvestmentFormState>(
    key: K,
    value: InvestmentFormState[K],
  ) {
    setForm((f) => (f ? { ...f, [key]: value } : f));
  }

  return (
    <Panel title="Edit investment">
      <form className="stack" onSubmit={onSubmit}>
        <InvestmentFields form={form} set={set} />
        <div className="toolbar">
          <button type="submit" className="btn btn-primary" disabled={busy}>
            {busy ? "Saving…" : "Save investment"}
          </button>
          <button
            type="button"
            className="btn btn-ghost"
            disabled={busy}
            onClick={onCancel}
          >
            Cancel edit
          </button>
        </div>
      </form>
    </Panel>
  );
}

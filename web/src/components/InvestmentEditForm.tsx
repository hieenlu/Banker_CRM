"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { explainError } from "@/components/AuthProvider";
import { Panel } from "@/components/ui";
import type { Investment } from "@/lib/types";
import {
  ASSET_TYPES,
  TERM_TENOR_OPTIONS,
  addMonths,
  assetKind,
  defaultCurrencyForAsset,
  normalizeAssetType,
} from "@/lib/investmentMeta";

type FormState = {
  asset_type: string;
  ticker_name: string;
  ticker_identifier: string;
  quantity: string;
  unit: string;
  principal: string;
  purchase_price: string;
  purchase_date: string;
  tenor: string;
  interest_rate: string;
  principal_payment: string;
  ytm: string;
  current_price: string;
  expected_coupon: string;
  received_coupon: string;
  maturity_date: string;
  notes: string;
};

function fromInvestment(inv: Investment): FormState {
  const kind = assetKind(normalizeAssetType(inv.asset_type));
  return {
    asset_type: normalizeAssetType(inv.asset_type),
    ticker_name: inv.ticker_name || "",
    ticker_identifier: inv.ticker_identifier || "",
    quantity: String(
      kind.isStock && inv.unit != null ? inv.unit : inv.quantity ?? 0,
    ),
    unit: inv.unit != null ? String(inv.unit) : "",
    principal: inv.principal != null ? String(inv.principal) : "",
    purchase_price: String(inv.purchase_price ?? 0),
    purchase_date: inv.purchase_date || "",
    tenor: inv.tenor || TERM_TENOR_OPTIONS[0],
    interest_rate: inv.interest_rate != null ? String(inv.interest_rate) : "",
    principal_payment:
      inv.principal_payment != null ? String(inv.principal_payment) : "",
    ytm: inv.ytm != null ? String(inv.ytm) : "",
    current_price: inv.current_price != null ? String(inv.current_price) : "",
    expected_coupon:
      inv.expected_coupon != null ? String(inv.expected_coupon) : "",
    received_coupon:
      inv.received_coupon != null ? String(inv.received_coupon) : "",
    maturity_date: inv.maturity_date || "",
    notes: inv.notes || "",
  };
}

function numOrNull(v: string): number | null {
  const t = v.trim();
  if (t === "") return null;
  const n = Number(t);
  return Number.isFinite(n) ? n : null;
}

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
  const [form, setForm] = useState<FormState | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    void api
      .getInvestment(investmentId)
      .then((inv) => {
        if (!cancelled) setForm(fromInvestment(inv));
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

  const kind = useMemo(
    () => (form ? assetKind(form.asset_type) : null),
    [form],
  );
  const currency = form ? defaultCurrencyForAsset(form.asset_type) : "VND";

  const maturityAuto =
    form && kind?.isTd && form.purchase_date && form.tenor
      ? addMonths(form.purchase_date, parseInt(form.tenor, 10) || 1)
      : null;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!form || !kind) return;
    const quantity = Number(form.quantity || 0);
    const purchasePrice = Number(form.purchase_price || 0);
    if (quantity < 0 || purchasePrice < 0) {
      onError("Quantity and purchase price must be non-negative.");
      return;
    }
    setBusy(true);
    try {
      let tickerName = form.ticker_name.trim() || null;
      let tickerId = form.ticker_identifier.trim() || null;
      let qty = quantity;
      let unit: number | null = null;
      let principal = numOrNull(form.principal);
      let purchase_price = purchasePrice;
      let purchase_date = form.purchase_date || null;
      let tenor: string | null = null;
      let interest_rate = numOrNull(form.interest_rate);
      let principal_payment: number | null = null;
      let ytm: number | null = null;
      let current_price: number | null = null;
      let expected_coupon: number | null = null;
      let received_coupon: number | null = null;
      let maturity_date: string | null = null;
      let notes = form.notes.trim() || null;

      if (kind.isCd) {
        qty = 1;
        tickerId = null;
        purchase_price = 0;
        notes = form.notes.trim() || null;
      } else if (kind.isTd) {
        qty = 1;
        tickerId = null;
        purchase_price = 0;
        tenor = form.tenor;
        maturity_date = maturityAuto;
        notes = null;
      } else if (kind.isBond) {
        tickerName = form.ticker_name.trim() || null;
        tickerId = tickerName;
        unit = numOrNull(form.unit) ?? 0;
        qty = unit;
        purchase_price =
          unit && principal != null && unit > 0 ? principal / unit : 0;
        ytm = numOrNull(form.ytm);
        current_price = numOrNull(form.current_price);
        expected_coupon = numOrNull(form.expected_coupon);
        received_coupon = numOrNull(form.received_coupon);
        maturity_date = form.maturity_date || null;
        notes = null;
      } else if (kind.isCash) {
        qty = 1;
        tickerId = null;
        purchase_price = 0;
        principal = numOrNull(form.principal);
      } else if (kind.isRealEstate) {
        tickerId = form.ticker_identifier.trim() || null;
        qty = 1;
        unit = 1;
        purchase_date = null;
        principal = numOrNull(form.principal);
        purchase_price = Number(form.purchase_price || 0);
        current_price = numOrNull(form.current_price);
      } else if (kind.isDebt) {
        tickerId = form.ticker_identifier.trim() || null;
        qty = 1;
        unit = null;
        purchase_price = 0;
        purchase_date = null;
        principal = numOrNull(form.principal);
        principal_payment = numOrNull(form.principal_payment);
      } else if (kind.isStock) {
        unit = quantity;
        qty = quantity;
        tickerId = form.ticker_identifier.trim() || null;
        interest_rate = null;
      } else {
        // crypto etc
        tickerId = form.ticker_identifier.trim() || null;
      }

      if (kind.isBond || kind.isTd) {
        notes = null;
      }

      const updated = await api.updateInvestment(investmentId, {
        asset_type: form.asset_type,
        currency,
        ticker_name: tickerName,
        ticker_identifier: tickerId,
        quantity: qty,
        unit,
        principal,
        purchase_price,
        purchase_date,
        tenor,
        interest_rate: kind.isDebt || kind.isTd ? interest_rate : null,
        principal_payment: kind.isDebt ? principal_payment : null,
        ytm: kind.isBond ? ytm : null,
        current_price:
          kind.isBond || kind.isRealEstate ? current_price : null,
        expected_coupon: kind.isBond ? expected_coupon : null,
        received_coupon: kind.isBond ? received_coupon : null,
        maturity_date:
          kind.isBond || kind.isTd ? maturity_date : null,
        notes: kind.isBond || kind.isTd ? null : notes,
      });
      onSaved(updated);
    } catch (err) {
      onError(explainError(err));
    } finally {
      setBusy(false);
    }
  }

  if (loading || !form || !kind) {
    return (
      <Panel title="Edit investment">
        <p className="muted">Loading investment…</p>
      </Panel>
    );
  }

  function set<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((f) => (f ? { ...f, [key]: value } : f));
  }

  return (
    <Panel title="Edit investment">
      <form className="stack" onSubmit={onSubmit}>
        <div className="detail-grid">
          <label className="field">
            <span>Asset Type</span>
            <select
              value={form.asset_type}
              onChange={(e) => set("asset_type", e.target.value)}
            >
              {ASSET_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </label>
          <p className="muted small" style={{ gridColumn: "1 / -1" }}>
            Currency: {currency} (auto by asset type)
          </p>

          {kind.isCd ? (
            <>
              <label className="field">
                <span>Principal</span>
                <input
                  type="number"
                  min={0}
                  step={1000}
                  value={form.principal}
                  onChange={(e) => set("principal", e.target.value)}
                />
              </label>
              <label className="field">
                <span>Purchase Date</span>
                <input
                  type="date"
                  value={form.purchase_date}
                  onChange={(e) => set("purchase_date", e.target.value)}
                />
              </label>
            </>
          ) : null}

          {kind.isTd ? (
            <>
              <label className="field">
                <span>Principal</span>
                <input
                  type="number"
                  min={0}
                  step={1000}
                  value={form.principal}
                  onChange={(e) => set("principal", e.target.value)}
                />
              </label>
              <label className="field">
                <span>Buy Date</span>
                <input
                  type="date"
                  value={form.purchase_date}
                  onChange={(e) => set("purchase_date", e.target.value)}
                />
              </label>
              <label className="field">
                <span>Tenor</span>
                <select
                  value={form.tenor}
                  onChange={(e) => set("tenor", e.target.value)}
                >
                  {TERM_TENOR_OPTIONS.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>Interest Rate (%)</span>
                <input
                  type="number"
                  min={0}
                  max={100}
                  step={0.1}
                  value={form.interest_rate}
                  onChange={(e) => set("interest_rate", e.target.value)}
                />
              </label>
              {maturityAuto ? (
                <p className="muted small" style={{ gridColumn: "1 / -1" }}>
                  Maturity Date (auto): {maturityAuto}
                </p>
              ) : null}
            </>
          ) : null}

          {kind.isBond ? (
            <>
              <label className="field">
                <span>Ticker</span>
                <input
                  type="text"
                  value={form.ticker_name}
                  onChange={(e) => set("ticker_name", e.target.value)}
                />
              </label>
              <label className="field">
                <span>Unit</span>
                <input
                  type="number"
                  min={0}
                  step={1}
                  value={form.unit}
                  onChange={(e) => set("unit", e.target.value)}
                />
              </label>
              <label className="field">
                <span>Purchase Date</span>
                <input
                  type="date"
                  value={form.purchase_date}
                  onChange={(e) => set("purchase_date", e.target.value)}
                />
              </label>
              <label className="field">
                <span>Principal</span>
                <input
                  type="number"
                  min={0}
                  step={1000}
                  value={form.principal}
                  onChange={(e) => set("principal", e.target.value)}
                />
              </label>
              <label className="field">
                <span>YTM (%)</span>
                <input
                  type="number"
                  min={0}
                  max={100}
                  step={0.1}
                  value={form.ytm}
                  onChange={(e) => set("ytm", e.target.value)}
                />
              </label>
              <label className="field">
                <span>Current Price</span>
                <input
                  type="number"
                  min={0}
                  step={0.01}
                  value={form.current_price}
                  onChange={(e) => set("current_price", e.target.value)}
                />
              </label>
              <label className="field">
                <span>Expected Coupon (Amount)</span>
                <input
                  type="number"
                  min={0}
                  step={0.01}
                  value={form.expected_coupon}
                  onChange={(e) => set("expected_coupon", e.target.value)}
                />
              </label>
              <label className="field">
                <span>Received Coupon (Amount)</span>
                <input
                  type="number"
                  min={0}
                  step={0.01}
                  value={form.received_coupon}
                  onChange={(e) => set("received_coupon", e.target.value)}
                />
              </label>
              <label className="field">
                <span>Maturity Date</span>
                <input
                  type="date"
                  value={form.maturity_date}
                  onChange={(e) => set("maturity_date", e.target.value)}
                />
              </label>
            </>
          ) : null}

          {kind.isCash ? (
            <label className="field">
              <span>Amount</span>
              <input
                type="number"
                min={0}
                step={1000}
                value={form.principal}
                onChange={(e) => set("principal", e.target.value)}
              />
            </label>
          ) : null}

          {kind.isRealEstate ? (
            <>
              <label className="field">
                <span>Property / Identifier</span>
                <input
                  type="text"
                  value={form.ticker_identifier}
                  onChange={(e) => set("ticker_identifier", e.target.value)}
                />
              </label>
              <label className="field">
                <span>Principal</span>
                <input
                  type="number"
                  min={0}
                  step={1000}
                  value={form.principal}
                  onChange={(e) => set("principal", e.target.value)}
                />
              </label>
              <label className="field">
                <span>Investment Value</span>
                <input
                  type="number"
                  min={0}
                  step={1000}
                  value={form.purchase_price}
                  onChange={(e) => set("purchase_price", e.target.value)}
                />
              </label>
              <label className="field">
                <span>Current Value</span>
                <input
                  type="number"
                  min={0}
                  step={1000}
                  value={form.current_price}
                  onChange={(e) => set("current_price", e.target.value)}
                />
              </label>
            </>
          ) : null}

          {kind.isDebt ? (
            <>
              <label className="field">
                <span>Debt / Identifier</span>
                <input
                  type="text"
                  value={form.ticker_identifier}
                  onChange={(e) => set("ticker_identifier", e.target.value)}
                />
              </label>
              <label className="field">
                <span>Outstanding Balance</span>
                <input
                  type="number"
                  min={0}
                  step={1000}
                  value={form.principal}
                  onChange={(e) => set("principal", e.target.value)}
                />
              </label>
              <label className="field">
                <span>Interest Rate (%)</span>
                <input
                  type="number"
                  min={0}
                  max={100}
                  step={0.1}
                  value={form.interest_rate}
                  onChange={(e) => set("interest_rate", e.target.value)}
                />
              </label>
              <label className="field">
                <span>Principal Payment</span>
                <input
                  type="number"
                  min={0}
                  step={1000}
                  value={form.principal_payment}
                  onChange={(e) => set("principal_payment", e.target.value)}
                />
              </label>
            </>
          ) : null}

          {!kind.isCd &&
          !kind.isTd &&
          !kind.isBond &&
          !kind.isCash &&
          !kind.isRealEstate &&
          !kind.isDebt ? (
            <>
              <label className="field">
                <span>Ticker / Identifier</span>
                <input
                  type="text"
                  value={form.ticker_identifier}
                  onChange={(e) => set("ticker_identifier", e.target.value)}
                />
              </label>
              <label className="field">
                <span>{kind.isStock ? "Unit" : "Quantity"}</span>
                <input
                  type="number"
                  min={0}
                  step={1}
                  value={form.quantity}
                  onChange={(e) => set("quantity", e.target.value)}
                />
              </label>
              <label className="field">
                <span>Purchase Price (per unit)</span>
                <input
                  type="number"
                  min={0}
                  step={0.01}
                  value={form.purchase_price}
                  onChange={(e) => set("purchase_price", e.target.value)}
                />
              </label>
            </>
          ) : null}

          {!kind.isBond && !kind.isTd ? (
            <label className="field">
              <span>Notes</span>
              <textarea
                value={form.notes}
                onChange={(e) => set("notes", e.target.value)}
              />
            </label>
          ) : null}
        </div>

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

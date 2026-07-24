"use client";

import {
  ASSET_TYPES,
  TERM_TENOR_OPTIONS,
  addMonths,
  assetKind,
  defaultCurrencyForAsset,
} from "@/lib/investmentMeta";
import type { InvestmentFormState } from "@/lib/investmentForm";

export function InvestmentFields({
  form,
  set,
  allowAssetTypeChange = true,
  assetTypeOptions = ASSET_TYPES as readonly string[],
}: {
  form: InvestmentFormState;
  set: <K extends keyof InvestmentFormState>(
    key: K,
    value: InvestmentFormState[K],
  ) => void;
  allowAssetTypeChange?: boolean;
  assetTypeOptions?: readonly string[];
}) {
  const kind = assetKind(form.asset_type);
  const currency = defaultCurrencyForAsset(form.asset_type);
  const maturityAuto =
    kind.isTd && form.purchase_date && form.tenor
      ? addMonths(form.purchase_date, parseInt(form.tenor, 10) || 1)
      : null;

  const principalNum = Number(form.principal || 0);
  const rateNum = Number(form.interest_rate || 0);
  const principalPaymentNum = Number(form.principal_payment || 0);
  const estInterest =
    kind.isDebt ? (principalNum * (rateNum / 100)) / 12 : null;
  const totalMonthly =
    kind.isDebt && estInterest != null
      ? principalPaymentNum + estInterest
      : null;

  return (
    <div className="detail-grid">
      {allowAssetTypeChange ? (
        <label className="field">
          <span>Asset Type</span>
          <select
            value={form.asset_type}
            onChange={(e) => set("asset_type", e.target.value)}
          >
            {assetTypeOptions.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>
      ) : null}
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
          {estInterest != null && totalMonthly != null ? (
            <p className="muted small" style={{ gridColumn: "1 / -1" }}>
              Est Interest Payment (auto): {currency}{" "}
              {estInterest.toLocaleString(undefined, {
                maximumFractionDigits: 0,
              })}{" "}
              · Total Monthly Payment (auto): {currency}{" "}
              {totalMonthly.toLocaleString(undefined, {
                maximumFractionDigits: 0,
              })}
            </p>
          ) : null}
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
  );
}

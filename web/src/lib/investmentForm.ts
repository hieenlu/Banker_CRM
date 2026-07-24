/** Shared investment create/edit form state and payload builders. */

import type { Investment } from "@/lib/types";
import {
  TERM_TENOR_OPTIONS,
  addMonths,
  assetKind,
  defaultCurrencyForAsset,
  normalizeAssetType,
  type AssetType,
} from "@/lib/investmentMeta";

export type InvestmentFormState = {
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

export function emptyInvestmentForm(
  assetType: AssetType | string = "VN_Stock",
): InvestmentFormState {
  const today = new Date().toISOString().slice(0, 10);
  return {
    asset_type: normalizeAssetType(assetType),
    ticker_name: "",
    ticker_identifier: "",
    quantity: "0",
    unit: "",
    principal: "",
    purchase_price: "0",
    purchase_date: today,
    tenor: TERM_TENOR_OPTIONS[0],
    interest_rate: "",
    principal_payment: "",
    ytm: "",
    current_price: "",
    expected_coupon: "",
    received_coupon: "",
    maturity_date: today,
    notes: "",
  };
}

export function formFromInvestment(inv: Investment): InvestmentFormState {
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

export type InvestmentPayload = {
  asset_type: string;
  currency: string;
  ticker_name: string | null;
  ticker_identifier: string | null;
  quantity: number;
  unit: number | null;
  principal: number | null;
  purchase_price: number;
  purchase_date: string | null;
  tenor: string | null;
  interest_rate: number | null;
  principal_payment: number | null;
  ytm: number | null;
  current_price: number | null;
  expected_coupon: number | null;
  received_coupon: number | null;
  maturity_date: string | null;
  notes: string | null;
};

export function validateInvestmentForm(
  form: InvestmentFormState,
): string | null {
  const quantity = Number(form.quantity || 0);
  const purchasePrice = Number(form.purchase_price || 0);
  if (quantity < 0 || purchasePrice < 0) {
    return "Quantity and purchase price must be non-negative.";
  }
  return null;
}

export function buildInvestmentPayload(
  form: InvestmentFormState,
): InvestmentPayload {
  const kind = assetKind(form.asset_type);
  const currency = defaultCurrencyForAsset(form.asset_type);
  const quantity = Number(form.quantity || 0);
  const purchasePrice = Number(form.purchase_price || 0);
  const maturityAuto =
    kind.isTd && form.purchase_date && form.tenor
      ? addMonths(form.purchase_date, parseInt(form.tenor, 10) || 1)
      : null;

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
    tickerId = form.ticker_identifier.trim() || null;
  }

  if (kind.isBond || kind.isTd) {
    notes = null;
  }

  return {
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
    current_price: kind.isBond || kind.isRealEstate ? current_price : null,
    expected_coupon: kind.isBond ? expected_coupon : null,
    received_coupon: kind.isBond ? received_coupon : null,
    maturity_date: kind.isBond || kind.isTd ? maturity_date : null,
    notes: kind.isBond || kind.isTd ? null : notes,
  };
}

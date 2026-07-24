/** Streamlit-parity asset types and helpers for investment edit. */

export const ASSET_TYPES = [
  "VN_Stock",
  "US_Stock",
  "Commodity",
  "Real Estate",
  "Bond",
  "Debt",
  "Term Deposit",
  "CD",
  "Crypto",
  "Cash",
] as const;

export type AssetType = (typeof ASSET_TYPES)[number];

/** Cashflow entry types stored as Income rows (Streamlit add expander). */
export const CASHFLOW_TYPES = [
  "Salary",
  "Dividends",
  "Other Incomes",
  "Other Obligations",
] as const;

export type CashflowType = (typeof CASHFLOW_TYPES)[number];

/** Obligation types stored on the client record. */
export const OBLIGATION_TYPES = ["Home Insurance"] as const;

export type ObligationType = (typeof OBLIGATION_TYPES)[number];

export const ADD_ENTRY_OPTIONS = [
  ...ASSET_TYPES,
  ...CASHFLOW_TYPES,
  ...OBLIGATION_TYPES,
] as const;

export type AddEntryOption = (typeof ADD_ENTRY_OPTIONS)[number];

export const INCOME_MODES = ["Actual", "Forecast"] as const;

export const TERM_TENOR_OPTIONS = Array.from({ length: 12 }, (_, i) =>
  i === 0 ? "1 month" : `${i + 1} months`,
);

export function isCashflowType(t: string): t is CashflowType {
  return (CASHFLOW_TYPES as readonly string[]).includes(t);
}

export function isObligationType(t: string): t is ObligationType {
  return (OBLIGATION_TYPES as readonly string[]).includes(t);
}

export function normalizeIncomeType(t: string | null | undefined): CashflowType {
  const s = (t || "").trim();
  if (s === "Others") return "Other Incomes";
  const match = CASHFLOW_TYPES.find((x) => x.toLowerCase() === s.toLowerCase());
  return match || "Other Incomes";
}

export function normalizeAssetType(t: string | null | undefined): AssetType {
  const s = (t || "").trim();
  const lower = s.toLowerCase();
  if (lower === "certificate of deposit") return "CD";
  if (lower === "stock") return "VN_Stock";
  if (lower === "real estate") return "Real Estate";
  if (lower === "debt") return "Debt";
  if (lower === "term deposit") return "Term Deposit";
  const match = ASSET_TYPES.find((a) => a.toLowerCase() === lower);
  return match || "VN_Stock";
}

export function defaultCurrencyForAsset(assetType: string): "USD" | "VND" {
  const k = assetType.trim().toLowerCase();
  return k === "us_stock" || k === "crypto" ? "USD" : "VND";
}

export function assetKind(assetType: string) {
  const k = assetType.trim().toLowerCase();
  return {
    isCd: k === "cd" || k === "certificate of deposit",
    isTd: k === "term deposit",
    isBond: k === "bond",
    isStock: ["stock", "vn_stock", "us_stock", "commodity"].includes(k),
    isRealEstate: k === "real estate",
    isDebt: k === "debt",
    isCash: k === "cash",
    isCrypto: k === "crypto",
  };
}

export function addMonths(isoDate: string, months: number): string {
  const d = new Date(`${isoDate}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return isoDate;
  const year = d.getUTCFullYear() + Math.floor((d.getUTCMonth() + months) / 12);
  const month = (d.getUTCMonth() + months) % 12;
  const day = Math.min(
    d.getUTCDate(),
    new Date(Date.UTC(year, month + 1, 0)).getUTCDate(),
  );
  const mm = String(month + 1).padStart(2, "0");
  const dd = String(day).padStart(2, "0");
  return `${year}-${mm}-${dd}`;
}

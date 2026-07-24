import { marketValue } from "./format";
import type { Investment } from "./types";

export type SubgroupMeta = {
  icon: string;
  color: string;
  m1: string;
  m2: string;
};

export const SUBGROUP_META: Record<string, SubgroupMeta> = {
  "Cash and CDs": { icon: "💵", color: "#ec4899", m1: "Total value", m2: "Principal" },
  Cash: { icon: "💵", color: "#ec4899", m1: "Total value", m2: "Principal" },
  "Term Deposit": { icon: "📅", color: "#f59e0b", m1: "Principal", m2: "Interest" },
  Bond: { icon: "📊", color: "#14b8a6", m1: "Cost", m2: "Unrealized P&L" },
  VN_Stock: { icon: "📈", color: "#8b5cf6", m1: "Market value", m2: "Profit" },
  US_Stock: { icon: "📈", color: "#6366f1", m1: "Market value", m2: "Profit" },
  Commodity: { icon: "🥇", color: "#a855f7", m1: "Market value", m2: "Profit" },
  Crypto: { icon: "₿", color: "#f97316", m1: "Market value", m2: "Profit" },
  "Real Estate": { icon: "🏠", color: "#22c55e", m1: "Investment value", m2: "Current value" },
  Debt: { icon: "🏦", color: "#ef4444", m1: "Outstanding", m2: "Monthly payment" },
};

const DEFAULT_META: SubgroupMeta = {
  icon: "📁",
  color: "#64748b",
  m1: "Total",
  m2: "P&L",
};

export function subgroupMeta(name: string): SubgroupMeta {
  return (
    SUBGROUP_META[name] ||
    SUBGROUP_META[name.replace(" ", "_")] ||
    DEFAULT_META
  );
}

export function normalizeAssetGroup(assetType: string): string {
  const t = (assetType || "").trim();
  if (!t) return "Other";
  if (SUBGROUP_META[t]) return t;
  const lower = t.toLowerCase();
  if (lower.includes("cash") || lower.includes("cd")) return "Cash";
  if (lower.includes("term") || lower.includes("deposit")) return "Term Deposit";
  if (lower.includes("bond")) return "Bond";
  if (lower.includes("vn") && lower.includes("stock")) return "VN_Stock";
  if (lower.includes("us") && lower.includes("stock")) return "US_Stock";
  if (lower.includes("stock") || lower.includes("equity")) return "US_Stock";
  if (lower.includes("crypto")) return "Crypto";
  if (lower.includes("real") || lower.includes("estate") || lower.includes("re "))
    return "Real Estate";
  if (lower.includes("debt") || lower.includes("loan")) return "Debt";
  if (lower.includes("commodity") || lower.includes("gold")) return "Commodity";
  return t;
}

export type GroupTotals = {
  name: string;
  value: number;
  cost: number;
  count: number;
  items: Investment[];
  /** Optional debt monthly payment aggregate for catalog cards. */
  monthly?: number;
};

export function groupInvestments(investments: Investment[]): GroupTotals[] {
  const open = investments.filter((i) => !i.is_done);
  const map = new Map<string, GroupTotals>();
  for (const inv of open) {
    const name = normalizeAssetGroup(inv.asset_type);
    const mv = marketValue(inv);
    const cost = (inv.quantity || 0) * (inv.purchase_price || 0);
    const prev = map.get(name) || {
      name,
      value: 0,
      cost: 0,
      count: 0,
      items: [],
    };
    prev.value += mv;
    prev.cost += cost;
    prev.count += 1;
    prev.items.push(inv);
    map.set(name, prev);
  }
  return Array.from(map.values()).sort((a, b) => b.value - a.value);
}

export function allocationSlices(groups: GroupTotals[], opts?: { excludeDebtRe?: boolean }) {
  const filtered = opts?.excludeDebtRe
    ? groups.filter((g) => g.name !== "Debt" && g.name !== "Real Estate")
    : groups;
  const total = filtered.reduce((s, g) => s + Math.abs(g.value), 0);
  return {
    total,
    slices: filtered.map((g) => ({
      name: g.name,
      value: g.value,
      pct: total > 0 ? (Math.abs(g.value) / total) * 100 : 0,
      color: subgroupMeta(g.name).color,
    })),
  };
}

export function assetsVsDebt(groups: GroupTotals[]) {
  const assets = groups
    .filter((g) => g.name !== "Debt")
    .reduce((s, g) => s + Math.max(0, g.value), 0);
  const debt = groups
    .filter((g) => g.name === "Debt")
    .reduce((s, g) => s + Math.abs(g.value), 0);
  const total = assets + debt;
  return {
    assets,
    debt,
    total,
    slices: [
      { name: "Assets", value: assets, pct: total ? (assets / total) * 100 : 0, color: "#22c55e" },
      { name: "Debt", value: debt, pct: total ? (debt / total) * 100 : 0, color: "#ef4444" },
    ],
  };
}

export function conicGradient(
  slices: Array<{ pct: number; color: string }>,
): string {
  if (!slices.length || slices.every((s) => s.pct <= 0)) {
    return `conic-gradient(#333 0% 100%)`;
  }
  let cursor = 0;
  const parts: string[] = [];
  for (const s of slices) {
    const next = cursor + s.pct;
    parts.push(`${s.color} ${cursor}% ${next}%`);
    cursor = next;
  }
  if (cursor < 100) parts.push(`#333 ${cursor}% 100%`);
  return `conic-gradient(${parts.join(", ")})`;
}

export function formatMoney(
  value: number | null | undefined,
  currency = "VND",
): string {
  if (value == null || Number.isNaN(Number(value))) return "—";
  const amount = Number(value);
  const ccy = (currency || "VND").toUpperCase();
  if (ccy === "VND") {
    return `${new Intl.NumberFormat("vi-VN", {
      maximumFractionDigits: 0,
    }).format(Math.round(amount))} ₫`;
  }
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: ccy,
      maximumFractionDigits: 2,
    }).format(amount);
  } catch {
    return `${amount.toFixed(2)} ${ccy}`;
  }
}

export function formatNumber(value: number | null | undefined): string {
  if (value == null || Number.isNaN(Number(value))) return "—";
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 4 }).format(
    Number(value),
  );
}

export function formatPct(value: number | null | undefined): string {
  if (value == null || Number.isNaN(Number(value))) return "—";
  const n = Number(value);
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(2)}%`;
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function pnlClass(value: number | null | undefined): string {
  if (value == null || Number.isNaN(Number(value))) return "";
  const n = Number(value);
  if (n > 0) return "pnl-pos";
  if (n < 0) return "pnl-neg";
  return "";
}

/** Legacy helper — prefer /portfolio/view for Streamlit-accurate PnL. */
export function marketValue(inv: {
  quantity: number;
  current_price: number | null;
  purchase_price: number;
}): number {
  const px = inv.current_price ?? inv.purchase_price ?? 0;
  return (inv.quantity || 0) * px;
}

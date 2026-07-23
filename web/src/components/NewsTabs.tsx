"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";
import { api } from "@/lib/api";
import { explainError } from "@/components/AuthProvider";
import { PageHeader } from "@/components/ui";

const TABS: Array<{ href: string; label: string; exact?: boolean }> = [
  { href: "/news", label: "Dashboard", exact: true },
  { href: "/news/latest", label: "Latest News" },
  { href: "/news/briefing", label: "Briefing & AI" },
  { href: "/news/archive", label: "Archive" },
];

export function NewsTabs({
  title,
  description,
  children,
  actions,
  onRefreshed,
}: {
  title: string;
  description?: string;
  children: ReactNode;
  actions?: ReactNode;
  onRefreshed?: () => void;
}) {
  const pathname = usePathname();
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function onRefresh() {
    setBusy(true);
    setMsg(null);
    setErr(null);
    try {
      const result = await api.refreshNews();
      if (result.status === "error") {
        setErr(
          result.errors[0] ||
            "News refresh failed. Check feed network access and try again.",
        );
      } else {
        setMsg(
          `Fetched ${result.fetched}, new ${result.new_count}, deduped ${result.deduped}, classified ${result.classified}`,
        );
      }
      onRefreshed?.();
    } catch (error) {
      setErr(explainError(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        title={title}
        description={description}
        actions={
          <>
            <button
              type="button"
              className="btn btn-primary"
              disabled={busy}
              onClick={() => void onRefresh()}
            >
              {busy ? "Refreshing…" : "Refresh News"}
            </button>
            {actions}
          </>
        }
      />
      {msg ? <p className="muted">{msg}</p> : null}
      {err ? (
        <div className="error-banner" role="alert">
          {err}
        </div>
      ) : null}
      <div
        className="segmented"
        style={{ marginBottom: "1rem" }}
        role="tablist"
      >
        {TABS.map((tab) => {
          const active = tab.exact
            ? pathname === tab.href
            : pathname.startsWith(tab.href);
          return (
            <Link
              key={tab.href}
              href={tab.href}
              className={active ? "active" : undefined}
            >
              {tab.label}
            </Link>
          );
        })}
      </div>
      {children}
    </>
  );
}

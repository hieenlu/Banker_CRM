"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
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
}: {
  title: string;
  description?: string;
  children: ReactNode;
  actions?: ReactNode;
}) {
  const pathname = usePathname();
  return (
    <>
      <PageHeader title={title} description={description} actions={actions} />
      <div className="segmented" style={{ marginBottom: "1rem" }} role="tablist">
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

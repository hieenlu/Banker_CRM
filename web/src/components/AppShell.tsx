"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { type ReactNode } from "react";
import { useAuth, useRequireAuth } from "./AuthProvider";

const NAV = [
  { href: "/clients", label: "Clients" },
  { href: "/portfolio", label: "Portfolio" },
  { href: "/reminders", label: "Reminders" },
  { href: "/news", label: "Market News" },
  { href: "/settings", label: "Settings" },
] as const;

/** Shown in header — CI sets NEXT_PUBLIC_WEB_BUILD_ID at image build time. */
export const WEB_BUILD_ID =
  process.env.NEXT_PUBLIC_WEB_BUILD_ID || "dev-local";

function NavLink({ href, label }: { href: string; label: string }) {
  const pathname = usePathname();
  const active =
    pathname === href || (href !== "/" && pathname.startsWith(`${href}/`));
  return (
    <Link
      href={href}
      className={`nav-link ${active ? "nav-link-active" : ""}`}
    >
      {label}
    </Link>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const auth = useRequireAuth();

  if (!auth.ready) {
    return (
      <div className="boot-screen">
        <p className="brand-mark">Banker Personal CRM</p>
        <p className="muted">Connecting…</p>
      </div>
    );
  }

  if (!auth.username) {
    return (
      <div className="boot-screen">
        <p className="brand-mark">Banker Personal CRM</p>
        <p className="muted">Redirecting to login…</p>
      </div>
    );
  }

  return (
    <div className="shell">
      <header className="topnav">
        <div className="topnav-row">
          <div className="topnav-brand">
            <span className="brand-mark">Banker Personal CRM</span>
            <span className="brand-sub">Personal desk</span>
          </div>
          <div className="topnav-meta">
            <span className="muted small hide-sm">
              Signed in as {auth.username}
            </span>
            <span className="muted small hide-sm">Build {WEB_BUILD_ID}</span>
            <button
              type="button"
              className="btn btn-ghost"
              onClick={auth.logout}
            >
              Sign out
            </button>
          </div>
        </div>
        <nav className="topnav-nav" aria-label="Primary">
          {NAV.map((item) => (
            <NavLink key={item.href} {...item} />
          ))}
        </nav>
      </header>
      <main className="content">{children}</main>
    </div>
  );
}

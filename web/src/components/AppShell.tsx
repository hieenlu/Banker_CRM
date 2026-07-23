"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";
import { useAuth, useRequireAuth } from "./AuthProvider";

const NAV = [
  { href: "/clients", label: "Clients" },
  { href: "/portfolio", label: "Portfolio" },
  { href: "/reminders", label: "Reminders" },
  { href: "/news", label: "Market News" },
  { href: "/settings", label: "Settings" },
] as const;

/** Shown in sidebar — CI sets NEXT_PUBLIC_WEB_BUILD_ID at image build time. */
export const WEB_BUILD_ID =
  process.env.NEXT_PUBLIC_WEB_BUILD_ID || "dev-local";

function NavLink({
  href,
  label,
  onNavigate,
}: {
  href: string;
  label: string;
  onNavigate?: () => void;
}) {
  const pathname = usePathname();
  const active =
    pathname === href || (href !== "/" && pathname.startsWith(`${href}/`));
  return (
    <Link
      href={href}
      onClick={onNavigate}
      className={`nav-link ${active ? "nav-link-active" : ""}`}
    >
      {label}
    </Link>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const auth = useRequireAuth();
  const [open, setOpen] = useState(false);

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
      <aside className={`sidebar ${open ? "sidebar-open" : ""}`}>
        <div className="sidebar-brand">
          <span className="brand-mark">Banker Personal CRM</span>
          <span className="brand-sub">Personal desk</span>
        </div>
        <div>
          <p className="sidebar-section-label">Navigation</p>
          <nav className="sidebar-nav" aria-label="Primary">
            {NAV.map((item) => (
              <NavLink
                key={item.href}
                {...item}
                onNavigate={() => setOpen(false)}
              />
            ))}
          </nav>
        </div>
        <div className="sidebar-footer">
          <p className="muted small">Signed in as {auth.username}</p>
          <p className="muted small">Build {WEB_BUILD_ID}</p>
          <button type="button" className="btn btn-ghost" onClick={auth.logout}>
            Sign out
          </button>
        </div>
      </aside>

      {open ? (
        <button
          type="button"
          className="sidebar-backdrop"
          aria-label="Close menu"
          onClick={() => setOpen(false)}
        />
      ) : null}

      <div className="shell-main">
        <header className="topbar">
          <button
            type="button"
            className="btn btn-ghost menu-btn"
            aria-label="Open menu"
            onClick={() => setOpen(true)}
          >
            Menu
          </button>
          <span className="topbar-brand brand-mark">Banker CRM</span>
          <span className="muted small hide-sm">Build {WEB_BUILD_ID}</span>
          <UserChip />
        </header>
        <main className="content">{children}</main>
      </div>
    </div>
  );
}

function UserChip() {
  const { username, logout } = useAuth();
  return (
    <div className="user-chip">
      <span className="muted small hide-sm">{username}</span>
      <button type="button" className="btn btn-ghost hide-sm" onClick={logout}>
        Sign out
      </button>
    </div>
  );
}

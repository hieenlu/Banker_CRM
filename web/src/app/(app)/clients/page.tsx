"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { explainError } from "@/components/AuthProvider";
import {
  EmptyState,
  ErrorBanner,
  LoadingBlock,
  PageHeader,
  Pagination,
  Panel,
} from "@/components/ui";
import { formatDate } from "@/lib/format";
import type { Client } from "@/lib/types";

export default function ClientsPage() {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<Client[]>([]);
  const [pages, setPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.listClients({
        q: query || undefined,
        page,
        page_size: 25,
      });
      setItems(data.items);
      setPages(data.pages);
      setTotal(data.total);
      if (data.items.length) {
        setSelectedId((prev) =>
          prev && data.items.some((c) => c.id === prev)
            ? prev
            : data.items[0].id,
        );
      } else {
        setSelectedId(null);
      }
    } catch (err) {
      setError(explainError(err));
    } finally {
      setLoading(false);
    }
  }, [page, query]);

  useEffect(() => {
    void load();
  }, [load]);

  function onSearch(e: FormEvent) {
    e.preventDefault();
    setPage(1);
    setQuery(q.trim());
  }

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const created = await api.createClient({
        name: name.trim(),
        birthday: null,
        address: null,
        phone_number: null,
        email: null,
        notes: null,
        home_insurance_amount_covered: null,
        home_insurance_expiry_date: null,
        home_insurance_insured_premium: null,
        salary_amount: null,
        salary_concurrent: false,
        salary_note: null,
        dividends_amount: null,
        dividends_concurrent: false,
        dividends_note: null,
        others_income_amount: null,
        others_income_concurrent: false,
        others_income_note: null,
      });
      setName("");
      setShowCreate(false);
      router.push(`/clients/${created.id}`);
    } catch (err) {
      setError(explainError(err));
    } finally {
      setBusy(false);
    }
  }

  const selected = items.find((c) => c.id === selectedId) || null;

  return (
    <>
      <PageHeader
        title="Banker Personal CRM"
        description="Client Actions"
        actions={
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => setShowCreate((v) => !v)}
            aria-label="Add client"
          >
            {showCreate ? "Cancel" : "+"}
          </button>
        }
      />

      {showCreate ? (
        <Panel title="Add client">
          <form className="toolbar" onSubmit={onCreate}>
            <label className="field" style={{ flex: 1, minWidth: 200 }}>
              <span>Full name</span>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
            </label>
            <button type="submit" className="btn btn-primary" disabled={busy}>
              {busy ? "Creating…" : "Create"}
            </button>
          </form>
        </Panel>
      ) : null}

      <Panel>
        <form className="toolbar" onSubmit={onSearch}>
          <input
            className="search-input"
            placeholder="Search by name, email, phone…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            style={{ maxWidth: 360 }}
          />
          <button type="submit" className="btn btn-secondary">
            Search
          </button>
        </form>
      </Panel>

      <ErrorBanner message={error} />

      <Panel>
        {loading ? <LoadingBlock /> : null}
        {!loading && !items.length ? (
          <EmptyState
            title="No clients found"
            description="Create a client or clear your search."
          />
        ) : null}
        {items.length ? (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Birthday</th>
                  <th>Phone</th>
                  <th>Email</th>
                </tr>
              </thead>
              <tbody>
                {items.map((c) => (
                  <tr
                    key={c.id}
                    className="clickable"
                    onClick={() => setSelectedId(c.id)}
                    style={
                      selectedId === c.id
                        ? { background: "rgba(214, 40, 40, 0.08)" }
                        : undefined
                    }
                  >
                    <td>
                      <Link className="linkish" href={`/clients/${c.id}`}>
                        {c.name}
                      </Link>
                    </td>
                    <td>{formatDate(c.birthday)}</td>
                    <td>{c.phone_number || "—"}</td>
                    <td>{c.email || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
        <p className="caption">
          Loaded {total} clients{items.length ? ` · showing ${items.length}` : ""}.
        </p>
        <Pagination
          page={page}
          pages={pages}
          total={total}
          onChange={setPage}
        />
      </Panel>

      <Panel title="Open client">
        <div className="toolbar">
          <label className="field" style={{ flex: 1, minWidth: 220 }}>
            <span>Client</span>
            <select
              value={selectedId ?? ""}
              onChange={(e) => setSelectedId(Number(e.target.value))}
            >
              {items.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                  {c.birthday ? ` · ${c.birthday}` : ""}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            className="btn btn-primary"
            disabled={!selected}
            onClick={() => selected && router.push(`/clients/${selected.id}`)}
          >
            Open client dashboard
          </button>
        </div>
      </Panel>
    </>
  );
}

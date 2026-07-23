"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { explainError } from "@/components/AuthProvider";
import { ArticleList, toggleBookmark } from "@/components/ArticleList";
import { NewsTabs } from "@/components/NewsTabs";
import {
  EmptyState,
  ErrorBanner,
  LoadingBlock,
  Pagination,
  Panel,
} from "@/components/ui";
import type { Article } from "@/lib/types";

/** Archive = stories older than the 14-day Latest window. */
export default function ArchiveNewsPage() {
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<Article[]>([]);
  const [pages, setPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Fetch a broader window, then keep only articles older than 14 days.
      const data = await api.listArticles({
        q: query || undefined,
        sort: "latest",
        max_age_hours: 2160,
        page,
        page_size: 50,
      });
      const cutoff = Date.now() - 14 * 24 * 60 * 60 * 1000;
      const archived = data.items.filter((a) => {
        const ts = new Date(a.published_at || a.fetched_at).getTime();
        return Number.isFinite(ts) && ts < cutoff;
      });
      setItems(archived);
      setPages(data.pages);
      setTotal(archived.length);
    } catch (err) {
      setError(explainError(err));
    } finally {
      setLoading(false);
    }
  }, [page, query]);

  useEffect(() => {
    void load();
  }, [load, tick]);

  function onSearch(e: FormEvent) {
    e.preventDefault();
    setPage(1);
    setQuery(q.trim());
  }

  async function onToggle(article: Article) {
    try {
      const updated = await toggleBookmark(article);
      setItems((rows) =>
        rows.map((r) => (r.id === updated.id ? updated : r)),
      );
    } catch (err) {
      setError(explainError(err));
    }
  }

  return (
    <NewsTabs
      title="Archive"
      description="Stories older than 14 days from the intel corpus."
      onRefreshed={() => setTick((t) => t + 1)}
    >
      <Panel>
        <form className="toolbar" onSubmit={onSearch}>
          <input
            className="search-input"
            style={{ maxWidth: 320 }}
            placeholder="Search archive…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
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
          <EmptyState title="No archived stories on this page" />
        ) : null}
        {items.length ? (
          <ArticleList items={items} onToggleBookmark={onToggle} />
        ) : null}
        <Pagination page={page} pages={pages} total={total} onChange={setPage} />
      </Panel>
    </NewsTabs>
  );
}

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
import { NEWS_CATEGORIES, type Article } from "@/lib/types";

export default function LatestNewsPage() {
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [region, setRegion] = useState("");
  const [category, setCategory] = useState("");
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<Article[]>([]);
  const [pages, setPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.listArticles({
        q: query || undefined,
        region: region || undefined,
        category: category || undefined,
        sort: "latest",
        max_age_hours: 336,
        page,
        page_size: 30,
      });
      setItems(data.items);
      setPages(data.pages);
      setTotal(data.total);
    } catch (err) {
      setError(explainError(err));
    } finally {
      setLoading(false);
    }
  }, [page, query, region, category]);

  useEffect(() => {
    void load();
  }, [load]);

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
      title="Latest News"
      description="Last 14 days, chronological. Filter by region, topic, or search."
    >
      <Panel>
        <form className="toolbar" onSubmit={onSearch}>
          <input
            className="search-input"
            style={{ maxWidth: 280 }}
            placeholder="Search headlines…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          <select
            value={region}
            onChange={(e) => {
              setPage(1);
              setRegion(e.target.value);
            }}
          >
            <option value="">All regions</option>
            <option value="global">Global</option>
            <option value="vietnam">Vietnam</option>
          </select>
          <select
            value={category}
            onChange={(e) => {
              setPage(1);
              setCategory(e.target.value);
            }}
          >
            <option value="">All topics</option>
            {NEWS_CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          <button type="submit" className="btn btn-secondary">
            Apply
          </button>
        </form>
      </Panel>

      <ErrorBanner message={error} />
      <Panel>
        {loading ? <LoadingBlock /> : null}
        {!loading && !items.length ? (
          <EmptyState title="No articles in this window" />
        ) : null}
        {items.length ? (
          <ArticleList items={items} onToggleBookmark={onToggle} />
        ) : null}
        <Pagination page={page} pages={pages} total={total} onChange={setPage} />
      </Panel>
    </NewsTabs>
  );
}

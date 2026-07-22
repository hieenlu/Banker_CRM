"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { explainError } from "@/components/AuthProvider";
import { ArticleList, toggleBookmark } from "@/components/ArticleList";
import { NewsTabs } from "@/components/NewsTabs";
import {
  EmptyState,
  ErrorBanner,
  LoadingBlock,
  Panel,
} from "@/components/ui";
import type { Article, Newspaper } from "@/lib/types";

export default function NewsDashboardPage() {
  const [top, setTop] = useState<Article[]>([]);
  const [vietnam, setVietnam] = useState<Article[]>([]);
  const [paper, setPaper] = useState<Newspaper | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [globalNews, vnNews, today] = await Promise.all([
        api.listArticles({
          sort: "relevance",
          max_age_hours: 48,
          page_size: 8,
        }),
        api.listArticles({
          region: "vietnam",
          sort: "relevance",
          max_age_hours: 72,
          page_size: 6,
        }),
        api.newspaperToday().catch(() => null),
      ]);
      setTop(globalNews.items);
      setVietnam(vnNews.items);
      setPaper(today);
    } catch (err) {
      setError(explainError(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function onToggle(article: Article) {
    try {
      const updated = await toggleBookmark(article);
      setTop((rows) =>
        rows.map((r) => (r.id === updated.id ? updated : r)),
      );
      setVietnam((rows) =>
        rows.map((r) => (r.id === updated.id ? updated : r)),
      );
    } catch (err) {
      setError(explainError(err));
    }
  }

  const regimeClass =
    paper?.market_regime === "Risk-Off"
      ? "regime-off"
      : paper?.market_regime === "Neutral"
        ? "regime-neutral"
        : "";

  return (
    <NewsTabs
      title="Market News"
      description="Desk dashboard — top stories, Vietnam focus, and today’s briefing snapshot."
    >
      <ErrorBanner message={error} />
      {loading ? <LoadingBlock /> : null}

      <div className="metric-grid" style={{ marginBottom: "1rem" }}>
        <div className="metric">
          <div className="metric-label">Top stories (48h)</div>
          <div className="metric-value">{top.length}</div>
        </div>
        <div className="metric">
          <div className="metric-label">Vietnam focus</div>
          <div className="metric-value">{vietnam.length}</div>
        </div>
        <div className="metric">
          <div className="metric-label">Today’s regime</div>
          <div className={`metric-value regime ${regimeClass}`}>
            <span className="regime-dot" />
            {paper?.market_regime || "—"}
          </div>
        </div>
      </div>

      <Panel
        title="Today’s briefing"
        actions={
          <Link href="/news/briefing" className="btn btn-ghost">
            Open briefing
          </Link>
        }
      >
        {paper ? (
          <p className="muted">
            Report date {paper.report_date} · {paper.provider}/{paper.model}
          </p>
        ) : (
          <EmptyState
            title="No newspaper for today"
            description="Generate from the intel pipeline, then refresh."
          />
        )}
      </Panel>

      <Panel
        title="Top stories"
        actions={
          <Link href="/news/latest" className="btn btn-ghost">
            Latest feed
          </Link>
        }
      >
        {top.length ? (
          <ArticleList items={top} onToggleBookmark={onToggle} />
        ) : !loading ? (
          <EmptyState title="No recent stories" />
        ) : null}
      </Panel>

      <Panel title="Vietnam">
        {vietnam.length ? (
          <ArticleList items={vietnam} onToggleBookmark={onToggle} />
        ) : !loading ? (
          <EmptyState title="No Vietnam stories" />
        ) : null}
      </Panel>
    </NewsTabs>
  );
}

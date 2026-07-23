"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { explainError } from "@/components/AuthProvider";
import { ArticleList, toggleBookmark } from "@/components/ArticleList";
import { NewsTabs } from "@/components/NewsTabs";
import {
  EmptyState,
  ErrorBanner,
  LoadingBlock,
} from "@/components/ui";
import type { Article, Newspaper } from "@/lib/types";

const MARKET_PILLS = [
  "All",
  "US",
  "Korea",
  "Taiwan",
  "Equities",
  "Economy",
  "Finance",
  "AI",
  "Crypto",
  "Semiconductor",
] as const;

const VN_PILLS = ["All", "Finance", "Economy", "Real Estate"] as const;
const X_PILLS = ["All", "KobeissiLetter", "citrini"] as const;

function matchesMarketPill(article: Article, pill: string): boolean {
  if (pill === "All") return true;
  const hay = `${article.title} ${article.category} ${article.source} ${article.region}`.toLowerCase();
  const map: Record<string, string[]> = {
    US: ["us", "u.s", "united states", "wall street", "fed ", "nasdaq", "s&p"],
    Korea: ["korea", "korean", "seoul", "kospi", "samsung"],
    Taiwan: ["taiwan", "taipei", "tsmc", "taiex"],
    Equities: ["equity", "equities", "stock", "shares", "nasdaq", "dow"],
    Economy: ["economy", "gdp", "inflation", "macro", "rate"],
    Finance: ["bank", "finance", "credit", "lending", "bond"],
    AI: [" ai", "ai ", "artificial intelligence", "openai", "llm", "chip"],
    Crypto: ["crypto", "bitcoin", "ethereum", "btc", "eth"],
    Semiconductor: ["semi", "chip", "tsmc", "nvidia", "foundry"],
  };
  return (map[pill] || [pill.toLowerCase()]).some((k) => hay.includes(k));
}

function matchesVnPill(article: Article, pill: string): boolean {
  if (pill === "All") return true;
  const hay = `${article.title} ${article.category}`.toLowerCase();
  if (pill === "Real Estate") {
    return ["real estate", "property", "housing", "bđs", "bat dong san"].some(
      (k) => hay.includes(k),
    );
  }
  return hay.includes(pill.toLowerCase());
}

function matchesXPill(article: Article, pill: string): boolean {
  if (pill === "All") return true;
  const hay = `${article.title} ${article.source} ${article.url}`.toLowerCase();
  return hay.includes(pill.toLowerCase());
}

export default function NewsDashboardPage() {
  const [markets, setMarkets] = useState<Article[]>([]);
  const [vietnam, setVietnam] = useState<Article[]>([]);
  const [xItems, setXItems] = useState<Article[]>([]);
  const [paper, setPaper] = useState<Newspaper | null>(null);
  const [marketPill, setMarketPill] = useState<(typeof MARKET_PILLS)[number]>("All");
  const [vnPill, setVnPill] = useState<(typeof VN_PILLS)[number]>("All");
  const [xPill, setXPill] = useState<(typeof X_PILLS)[number]>("All");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Match Streamlit Markets: global+crypto, latest first, same age window as Latest.
      const [globalNews, cryptoNews, vnNews, xNews, today] = await Promise.all([
        api.listArticles({
          region: "global",
          sort: "latest",
          max_age_hours: 336,
          page_size: 80,
        }),
        api.listArticles({
          region: "crypto",
          sort: "latest",
          max_age_hours: 336,
          page_size: 40,
        }),
        api.listArticles({
          region: "vietnam",
          sort: "latest",
          max_age_hours: 336,
          page_size: 40,
        }),
        Promise.all([
          api.listArticles({ q: "Kobeissi", sort: "latest", page_size: 15 }),
          api.listArticles({ q: "citrini", sort: "latest", page_size: 15 }),
        ]).then(([a, b]) => {
          const map = new Map<number, Article>();
          for (const row of [...a.items, ...b.items]) map.set(row.id, row);
          return { items: Array.from(map.values()) };
        }),
        api.newspaperToday().catch(() => null),
      ]);
      const marketMap = new Map<number, Article>();
      for (const row of [...globalNews.items, ...cryptoNews.items]) {
        marketMap.set(row.id, row);
      }
      const marketItems = Array.from(marketMap.values()).sort((a, b) => {
        const ta = a.published_at || a.fetched_at || "";
        const tb = b.published_at || b.fetched_at || "";
        return tb.localeCompare(ta);
      });
      setMarkets(marketItems);
      setVietnam(vnNews.items);
      setXItems(xNews.items);
      setPaper(today);
    } catch (err) {
      setError(explainError(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load, tick]);

  async function onToggle(article: Article) {
    try {
      const updated = await toggleBookmark(article);
      const patch = (rows: Article[]) =>
        rows.map((r) => (r.id === updated.id ? updated : r));
      setMarkets(patch);
      setVietnam(patch);
      setXItems(patch);
    } catch (err) {
      setError(explainError(err));
    }
  }

  const filteredMarkets = useMemo(
    () => markets.filter((a) => matchesMarketPill(a, marketPill)).slice(0, 12),
    [markets, marketPill],
  );
  const filteredVn = useMemo(
    () => vietnam.filter((a) => matchesVnPill(a, vnPill)).slice(0, 12),
    [vietnam, vnPill],
  );
  const filteredX = useMemo(
    () => xItems.filter((a) => matchesXPill(a, xPill)).slice(0, 12),
    [xItems, xPill],
  );

  const regimeClass =
    paper?.market_regime === "Risk-Off"
      ? "regime-off"
      : paper?.market_regime === "Neutral"
        ? "regime-neutral"
        : "";

  return (
    <NewsTabs
      title="AI Financial Intelligence Terminal"
      description="US / Korea / Taiwan · Vietnam · X analysts · briefings"
      onRefreshed={() => setTick((t) => t + 1)}
    >
      <ErrorBanner message={error} />

      <div className="metric-grid" style={{ marginBottom: "1rem" }}>
        <div className="metric">
          <div className="metric-label">Articles</div>
          <div className="metric-value">{markets.length + vietnam.length}</div>
        </div>
        <div className="metric">
          <div className="metric-label">Vietnam</div>
          <div className="metric-value">{vietnam.length}</div>
        </div>
        <div className="metric">
          <div className="metric-label">Regime</div>
          <div className={`metric-value regime ${regimeClass}`}>
            <span className="regime-dot" />
            {paper?.market_regime || "—"}
          </div>
        </div>
      </div>

      {loading ? <LoadingBlock /> : null}

      <div className="news-desk">
        <section className="news-col">
          <h2 className="news-col-title">Markets</h2>
          <p className="news-col-caption">
            US · Korea · Taiwan · Equities · Economy · Finance · AI · Crypto · Semis
          </p>
          <div className="pill-row" style={{ marginBottom: "0.75rem" }}>
            {MARKET_PILLS.map((p) => (
              <button
                key={p}
                type="button"
                className={`pill ${marketPill === p ? "active" : ""}`}
                onClick={() => setMarketPill(p)}
              >
                {p}
              </button>
            ))}
          </div>
          {filteredMarkets.length ? (
            <ArticleList
              items={filteredMarkets}
              onToggleBookmark={onToggle}
              compact
            />
          ) : !loading ? (
            <EmptyState title="No market stories" />
          ) : null}
        </section>

        <section className="news-col">
          <h2 className="news-col-title">Vietnam</h2>
          <p className="news-col-caption">Finance · Economy · Real estate</p>
          <div className="pill-row" style={{ marginBottom: "0.75rem" }}>
            {VN_PILLS.map((p) => (
              <button
                key={p}
                type="button"
                className={`pill ${vnPill === p ? "active" : ""}`}
                onClick={() => setVnPill(p)}
              >
                {p}
              </button>
            ))}
          </div>
          {filteredVn.length ? (
            <ArticleList items={filteredVn} onToggleBookmark={onToggle} compact />
          ) : !loading ? (
            <EmptyState title="No Vietnam stories" />
          ) : null}
        </section>

        <section className="news-col">
          <h2 className="news-col-title">X · Analysts</h2>
          <p className="news-col-caption">
            <a
              className="linkish"
              href="https://x.com/KobeissiLetter"
              target="_blank"
              rel="noreferrer"
            >
              @KobeissiLetter
            </a>
            {" · "}
            <a
              className="linkish"
              href="https://x.com/citrini"
              target="_blank"
              rel="noreferrer"
            >
              @citrini
            </a>
          </p>
          <div className="pill-row" style={{ marginBottom: "0.75rem" }}>
            {X_PILLS.map((p) => (
              <button
                key={p}
                type="button"
                className={`pill ${xPill === p ? "active" : ""}`}
                onClick={() => setXPill(p)}
              >
                {p === "KobeissiLetter" ? "Kobeissi" : p === "citrini" ? "Citrini" : p}
              </button>
            ))}
          </div>
          {filteredX.length ? (
            <ArticleList items={filteredX} onToggleBookmark={onToggle} compact />
          ) : !loading ? (
            <EmptyState
              title="No X posts cached"
              description="Refresh X feeds from Streamlit Market News, then reload this page."
            />
          ) : null}
        </section>
      </div>
    </NewsTabs>
  );
}

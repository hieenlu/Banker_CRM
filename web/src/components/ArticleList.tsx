"use client";

import { api } from "@/lib/api";
import { explainError } from "@/components/AuthProvider";
import { formatDateTime } from "@/lib/format";
import type { Article } from "@/lib/types";

export function ArticleList({
  items,
  onToggleBookmark,
  compact = false,
}: {
  items: Article[];
  onToggleBookmark?: (article: Article) => void;
  compact?: boolean;
}) {
  return (
    <ul className="article-list">
      {items.map((article) => (
        <li key={article.id} className="article-item">
          <div>
            <a
              className="article-title"
              href={article.url}
              target="_blank"
              rel="noreferrer"
            >
              {article.title}
            </a>
            {!compact ? (
              <div className="article-meta" style={{ justifyContent: "flex-start", textAlign: "left" }}>
                {article.category && article.category !== "Uncategorized" ? (
                  <span className="tag">{article.category}</span>
                ) : null}
                <span>{article.source}</span>
              </div>
            ) : null}
          </div>
          <div className={`article-meta ${compact ? "" : "article-meta-side"}`}>
            {compact ? (
              <>
                <span className="tag">{article.category}</span>
                <span>{article.source}</span>
              </>
            ) : (
              <>
                <span>{article.region === "vietnam" ? "Vietnam" : "Global"}</span>
                <span>
                  {formatDateTime(article.published_at || article.fetched_at)}
                </span>
              </>
            )}
            {onToggleBookmark ? (
              <button
                type="button"
                className="btn btn-ghost"
                style={{ minHeight: 28, padding: "0.15rem 0.5rem" }}
                onClick={() => onToggleBookmark(article)}
              >
                {article.bookmarked ? "★" : "☆"}
              </button>
            ) : null}
          </div>
        </li>
      ))}
    </ul>
  );
}

export async function toggleBookmark(article: Article): Promise<Article> {
  try {
    if (article.bookmarked) {
      await api.removeBookmark(article.id);
      return { ...article, bookmarked: false };
    }
    await api.addBookmark(article.id);
    return { ...article, bookmarked: true };
  } catch (err) {
    throw new Error(explainError(err));
  }
}

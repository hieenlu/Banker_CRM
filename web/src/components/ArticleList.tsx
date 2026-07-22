"use client";

import { api } from "@/lib/api";
import { explainError } from "@/components/AuthProvider";
import { formatDateTime } from "@/lib/format";
import type { Article } from "@/lib/types";

export function ArticleList({
  items,
  onToggleBookmark,
}: {
  items: Article[];
  onToggleBookmark?: (article: Article) => void;
}) {
  return (
    <ul className="article-list">
      {items.map((article) => (
        <li key={article.id} className="article-item">
          <div className="toolbar" style={{ justifyContent: "space-between" }}>
            <a
              className="linkish"
              href={article.url}
              target="_blank"
              rel="noreferrer"
            >
              {article.title}
            </a>
            {onToggleBookmark ? (
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => onToggleBookmark(article)}
              >
                {article.bookmarked ? "Unbookmark" : "Bookmark"}
              </button>
            ) : null}
          </div>
          <div className="article-meta">
            <span className="tag">{article.category}</span>
            <span>{article.source}</span>
            <span>{article.region}</span>
            <span>{formatDateTime(article.published_at || article.fetched_at)}</span>
            <span>rel {article.relevance_score.toFixed(2)}</span>
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

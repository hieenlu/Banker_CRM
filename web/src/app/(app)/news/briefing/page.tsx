"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { explainError } from "@/components/AuthProvider";
import { NewsTabs } from "@/components/NewsTabs";
import {
  EmptyState,
  ErrorBanner,
  LoadingBlock,
  Panel,
} from "@/components/ui";
import { formatBytes, formatDateTime } from "@/lib/format";
import type { Newspaper, StoredFile } from "@/lib/types";
import { getToken } from "@/lib/auth";

function asStories(content: Record<string, unknown>): Array<Record<string, unknown>> {
  const raw = content.top_stories;
  return Array.isArray(raw) ? (raw as Array<Record<string, unknown>>) : [];
}

export default function BriefingPage() {
  const [paper, setPaper] = useState<Newspaper | null>(null);
  const [reports, setReports] = useState<StoredFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [syncMsg, setSyncMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [today, files] = await Promise.all([
        api.newspaperToday().catch(() => null),
        api.listTechcombankReports({ page_size: 12 }),
      ]);
      setPaper(today);
      setReports(files.items);
    } catch (err) {
      setError(explainError(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function onSync() {
    setBusy(true);
    setSyncMsg(null);
    setError(null);
    try {
      const result = await api.syncTechcombank(8);
      setSyncMsg(
        `Found ${result.found}, synced ${result.synced}, skipped ${result.skipped}` +
          (result.errors.length ? ` · errors: ${result.errors.join("; ")}` : ""),
      );
      await load();
    } catch (err) {
      setError(explainError(err));
    } finally {
      setBusy(false);
    }
  }

  async function onDownload(file: StoredFile) {
    const url = api.absoluteUrl(file.download_url);
    if (!url) return;
    const token = getToken();
    if (url.includes("/files/") && token) {
      try {
        const res = await fetch(url, {
          headers: { Authorization: `Bearer ${token}` },
          redirect: "follow",
        });
        if (!res.ok) throw new Error("Download failed");
        const blob = await res.blob();
        const objectUrl = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = objectUrl;
        a.download = file.original_filename || `${file.period_yyyymm || file.id}.pdf`;
        a.click();
        URL.revokeObjectURL(objectUrl);
        return;
      } catch (err) {
        setError(explainError(err));
        return;
      }
    }
    window.open(url, "_blank", "noopener,noreferrer");
  }

  const stories = paper ? asStories(paper.content) : [];
  const overview =
    paper && typeof paper.content.market_overview === "string"
      ? paper.content.market_overview
      : paper && typeof paper.content.overview === "string"
        ? paper.content.overview
        : null;

  const regimeClass =
    paper?.market_regime === "Risk-Off"
      ? "regime-off"
      : paper?.market_regime === "Neutral"
        ? "regime-neutral"
        : "";

  return (
    <NewsTabs
      title="Briefing & AI"
      description="Daily newspaper and mirrored Techcombank research PDFs."
      actions={
        <button
          type="button"
          className="btn btn-secondary"
          disabled={busy}
          onClick={() => void onSync()}
        >
          {busy ? "Syncing…" : "Sync Techcombank PDFs"}
        </button>
      }
    >
      <ErrorBanner message={error} />
      {syncMsg ? <p className="muted">{syncMsg}</p> : null}
      {loading ? <LoadingBlock /> : null}

      <Panel title="Today’s newspaper">
        {paper ? (
          <div className="stack">
            <p className={`regime ${regimeClass}`}>
              <span className="regime-dot" />
              {paper.market_regime} · {paper.report_date}
            </p>
            {overview ? <p>{overview}</p> : null}
            {stories.length ? (
              <ul className="article-list">
                {stories.map((story, idx) => (
                  <li key={idx} className="article-item">
                    <strong>
                      {String(story.title || story.headline || `Story ${idx + 1}`)}
                    </strong>
                    {story.summary ? (
                      <p className="muted">{String(story.summary)}</p>
                    ) : null}
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState title="No structured top stories in this report" />
            )}
          </div>
        ) : !loading ? (
          <EmptyState title="No newspaper for today" />
        ) : null}
      </Panel>

      <Panel title="Techcombank reports">
        {reports.length ? (
          <ul className="file-list">
            {reports.map((file) => (
              <li key={file.id} className="file-row">
                <div>
                  <p className="file-name">
                    {file.period_yyyymm || file.original_filename || `Report #${file.id}`}
                  </p>
                  <p className="muted small">
                    {formatBytes(file.size_bytes)} ·{" "}
                    {formatDateTime(file.synced_at || file.created_at)}
                  </p>
                </div>
                <button
                  type="button"
                  className="btn btn-ghost"
                  onClick={() => void onDownload(file)}
                >
                  Download
                </button>
              </li>
            ))}
          </ul>
        ) : !loading ? (
          <EmptyState
            title="No mirrored reports"
            description="Run sync when Techcombank sources are reachable."
          />
        ) : null}
      </Panel>
    </NewsTabs>
  );
}

"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { explainError } from "@/components/AuthProvider";
import { EmptyState, ErrorBanner, LoadingBlock } from "@/components/ui";
import { formatBytes, formatDateTime } from "@/lib/format";
import type { StoredFile } from "@/lib/types";
import { getToken } from "@/lib/auth";

export function AttachmentPanel({ clientId }: { clientId: number }) {
  const [files, setFiles] = useState<StoredFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [label, setLabel] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const page = await api.listAttachments(clientId, { page: 1 });
      setFiles(page.items);
    } catch (err) {
      setError(explainError(err));
    } finally {
      setLoading(false);
    }
  }, [clientId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function onUpload(fileList: FileList | null) {
    if (!fileList?.length) return;
    setBusy(true);
    setError(null);
    try {
      await api.uploadAttachment(clientId, fileList[0], label || undefined);
      setLabel("");
      await load();
    } catch (err) {
      setError(explainError(err));
    } finally {
      setBusy(false);
    }
  }

  async function onDelete(fileId: number) {
    if (!window.confirm("Delete this attachment?")) return;
    setBusy(true);
    setError(null);
    try {
      await api.deleteAttachment(clientId, fileId);
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
    // Local backend requires auth header; open via fetch blob when same-origin API path
    if (url.includes("/files/") && token) {
      try {
        const res = await fetch(url, {
          headers: { Authorization: `Bearer ${token}` },
          redirect: "follow",
        });
        if (!res.ok) throw new Error("Download failed");
        // If redirected to signed URL, browser already followed; may be cross-origin blob
        const blob = await res.blob();
        const objectUrl = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = objectUrl;
        a.download = file.original_filename || `file-${file.id}`;
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

  async function onExport() {
    const token = getToken();
    if (!token) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(api.exportClientZipUrl(clientId), {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Export failed");
      const blob = await res.blob();
      const objectUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = objectUrl;
      a.download = `client-${clientId}-export.zip`;
      a.click();
      URL.revokeObjectURL(objectUrl);
    } catch (err) {
      setError(explainError(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="stack">
      <ErrorBanner message={error} />
      <div className="attach-form">
        <label className="field">
          <span>Label (optional)</span>
          <input
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder="KYC, statement…"
          />
        </label>
        <label className="btn btn-secondary file-btn">
          {busy ? "Working…" : "Upload file"}
          <input
            type="file"
            hidden
            disabled={busy}
            onChange={(e) => {
              void onUpload(e.target.files);
              e.target.value = "";
            }}
          />
        </label>
        <button
          type="button"
          className="btn btn-ghost"
          disabled={busy}
          onClick={() => void onExport()}
        >
          Export ZIP
        </button>
      </div>

      {loading ? <LoadingBlock /> : null}
      {!loading && !files.length ? (
        <EmptyState
          title="No attachments yet"
          description="PDFs, images, and spreadsheets up to 20 MB."
        />
      ) : null}
      {files.length ? (
        <ul className="file-list">
          {files.map((file) => (
            <li key={file.id} className="file-row">
              <div>
                <p className="file-name">
                  {file.label || file.original_filename || `File #${file.id}`}
                </p>
                <p className="muted small">
                  {file.content_type} · {formatBytes(file.size_bytes)} ·{" "}
                  {formatDateTime(file.created_at)}
                </p>
              </div>
              <div className="row-actions">
                <button
                  type="button"
                  className="btn btn-ghost"
                  onClick={() => void onDownload(file)}
                >
                  Download
                </button>
                <button
                  type="button"
                  className="btn btn-ghost danger"
                  onClick={() => void onDelete(file.id)}
                >
                  Delete
                </button>
              </div>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

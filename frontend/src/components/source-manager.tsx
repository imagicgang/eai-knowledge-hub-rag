"use client";

import { AlertTriangle, Database, LoaderCircle, RotateCcw, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

type SourceItem = { name: string; metadata: string; updated_at: string | null; chunks: number };

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

function encodeSourceName(name: string) {
  return name.split("/").map(encodeURIComponent).join("/");
}

function formatDate(value: string | null) {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleString();
}

export function SourceManager() {
  const [sources, setSources] = useState<SourceItem[]>([]);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState("");
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);

  async function fetchSources(): Promise<SourceItem[]> {
    const response = await fetch(`${API_URL}/api/v1/data-sources`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error ?? data.detail ?? "Could not load sources");
    return data.sources ?? [];
  }

  function load() {
    setStatus("loading"); setError("");
    fetchSources()
      .then((list) => { setSources(list); setStatus("ready"); })
      .catch((loadError) => {
        setError(loadError instanceof Error ? loadError.message : "Could not load sources"); setStatus("error");
      });
  }

  useEffect(() => {
    let cancelled = false;
    fetchSources()
      .then((list) => { if (!cancelled) { setSources(list); setStatus("ready"); } })
      .catch((loadError) => {
        if (cancelled) return;
        setError(loadError instanceof Error ? loadError.message : "Could not load sources"); setStatus("error");
      });
    return () => { cancelled = true; };
  }, []);

  async function remove(name: string) {
    setDeleting(name);
    try {
      const response = await fetch(`${API_URL}/api/v1/data-sources/${encodeSourceName(name)}`, { method: "DELETE" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error ?? data.detail ?? "Delete failed");
      setSources((current) => current.filter((item) => item.name !== name));
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : "Delete failed");
    } finally {
      setDeleting(null); setPendingDelete(null);
    }
  }

  return (
    <div className="source-manager">
      <div className="source-manager-head">
        <div>
          <b>Knowledge sources</b>
          <small>Removing a source deletes its indexed knowledge only — no original file is kept on the server.</small>
        </div>
        <button type="button" className="refresh-button" onClick={load} disabled={status === "loading"}>
          <RotateCcw size={13} className={status === "loading" ? "spin" : ""} /> Refresh
        </button>
      </div>

      {status === "loading" && (
        <div className="source-empty"><LoaderCircle className="spin" size={22} /><p>Loading sources…</p></div>
      )}

      {status === "error" && (
        <div className="source-empty error"><AlertTriangle size={22} /><p>{error}</p></div>
      )}

      {status === "ready" && sources.length === 0 && (
        <div className="source-empty"><Database size={22} /><p>No knowledge sources yet</p><small>Files you import will show up here.</small></div>
      )}

      {status === "ready" && sources.length > 0 && (
        <div className="source-list">
          {sources.map((source) => (
            <div className="source-row" key={source.name}>
              <div className="source-info">
                <b>{source.name}</b>
                <small>{source.chunks} chunk{source.chunks === 1 ? "" : "s"} · {formatDate(source.updated_at)}</small>
              </div>
              {pendingDelete === source.name ? (
                <div className="source-confirm">
                  <span>Delete this source?</span>
                  <button type="button" onClick={() => remove(source.name)} disabled={deleting === source.name}>
                    {deleting === source.name ? <LoaderCircle className="spin" size={13} /> : "Delete"}
                  </button>
                  <button type="button" className="cancel" onClick={() => setPendingDelete(null)} disabled={deleting === source.name}>Cancel</button>
                </div>
              ) : (
                <button type="button" className="delete-button" onClick={() => setPendingDelete(source.name)} aria-label={`Delete ${source.name}`}>
                  <Trash2 size={15} />
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {error && status === "ready" && <p className="upload-error">{error}</p>}
    </div>
  );
}

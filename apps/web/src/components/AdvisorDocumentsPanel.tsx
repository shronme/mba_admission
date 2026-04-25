"use client";

import { useEffect, useMemo, useState } from "react";

import { ArtifactDownloadCard } from "@/components/ArtifactDownloadCard";
import { getApiBaseUrl, listArtifacts, listUploadedFiles, type ArtifactListItemDto, type UploadedFileDto } from "@/lib/api";

function statusBadge(status: UploadedFileDto["status"]) {
  switch (status) {
    case "ready":
      return { label: "Verified", className: "bg-emerald-50 text-emerald-700" };
    case "reviewing":
      return { label: "In Review", className: "bg-sky-50 text-sky-700" };
    case "uploading":
      return { label: "Uploading", className: "bg-slate-100 text-slate-700" };
    case "failed":
      return { label: "Failed", className: "bg-rose-50 text-rose-700" };
    case "deleted":
      return { label: "Deleted", className: "bg-slate-100 text-slate-600" };
    default:
      return { label: String(status), className: "bg-slate-100 text-slate-700" };
  }
}

export function AdvisorDocumentsPanel({
  sessionToken,
  candidateEmail,
}: {
  sessionToken: string;
  candidateEmail?: string | null;
}) {
  const [uploaded, setUploaded] = useState<UploadedFileDto[]>([]);
  const [artifacts, setArtifacts] = useState<ArtifactListItemDto[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const uploadedSorted = useMemo(() => {
    const copy = [...uploaded];
    copy.sort((a, b) => (a.original_filename || "").localeCompare(b.original_filename || ""));
    return copy;
  }, [uploaded]);

  const artifactsSorted = useMemo(() => {
    const copy = [...artifacts];
    copy.sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""));
    return copy;
  }, [artifacts]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    const load = async () => {
      try {
        const [files, arts] = await Promise.all([listUploadedFiles(sessionToken), listArtifacts(sessionToken)]);
        if (cancelled) return;
        setUploaded(files);
        setArtifacts(arts);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    void load();

    const id = setInterval(() => {
      void load();
    }, 5000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [sessionToken]);

  const downloadUploaded = async (fileId: string, filename: string) => {
    const root = getApiBaseUrl();
    if (!root) throw new Error("NEXT_PUBLIC_API_URL is not set");
    const res = await fetch(`${root.replace(/\/$/, "")}/files/${fileId}/download`, {
      method: "GET",
      headers: { Authorization: `Bearer ${sessionToken}` },
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`Download failed: ${res.status} ${text}`);
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    try {
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
    } finally {
      URL.revokeObjectURL(url);
    }
  };

  return (
    <div className="rounded-2xl border border-[#c4c6cd]/20 bg-surface-low p-4">
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <div>
          <div className="text-[10px] font-bold uppercase tracking-widest text-neutral-400">Documents</div>
          {candidateEmail ? <div className="mt-1 text-xs font-semibold text-brand-900">{candidateEmail}</div> : null}
        </div>
        <div className="text-xs text-neutral-500">
          {uploaded.length} uploaded · {artifacts.length} generated
        </div>
      </div>

      {error ? (
        <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
          {error}
        </div>
      ) : null}

      {loading ? (
        <div className="rounded-xl bg-white px-4 py-3 text-sm text-neutral-600">Loading documents…</div>
      ) : (
        <div className="space-y-4">
          <section>
            <div className="mb-2 flex items-center justify-between">
              <h3 className="text-xs font-bold uppercase tracking-widest text-neutral-500">User uploaded</h3>
              <button
                type="button"
                onClick={() => (window.location.href = "/documents")}
                className="text-[11px] font-semibold text-brand-700 underline underline-offset-2 hover:text-brand-900"
              >
                Manage
              </button>
            </div>
            {uploadedSorted.length === 0 ? (
              <div className="rounded-xl bg-white px-4 py-3 text-sm text-neutral-600">No uploads yet.</div>
            ) : (
              <div className="space-y-2">
                {uploadedSorted.map((f) => {
                  const badge = statusBadge(f.status);
                  const canDownload = f.status !== "deleted" && f.status !== "failed";
                  return (
                    <div key={f.id} className="flex items-center justify-between gap-3 rounded-xl bg-white px-4 py-3">
                      <div className="min-w-0">
                        <div className="truncate text-sm font-semibold text-brand-900">{f.original_filename}</div>
                        <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-neutral-500">
                          <span className={`rounded-full px-2 py-0.5 font-semibold ${badge.className}`}>
                            {badge.label}
                          </span>
                          {typeof f.uploaded_stage === "number" ? <span>Stage {f.uploaded_stage}</span> : null}
                          {f.document_type ? <span>{String(f.document_type)}</span> : null}
                        </div>
                      </div>
                      <button
                        type="button"
                        disabled={!canDownload}
                        onClick={() => void downloadUploaded(f.id, f.original_filename).catch((e) => setError(String(e)))}
                        className="rounded-lg border border-[#c4c6cd]/25 bg-surface-low px-3 py-1.5 text-xs font-semibold text-brand-900 hover:bg-surface-container disabled:opacity-50"
                      >
                        Download
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
          </section>

          <section>
            <div className="mb-2 flex items-center justify-between">
              <h3 className="text-xs font-bold uppercase tracking-widest text-neutral-500">Advisor generated</h3>
            </div>
            {artifactsSorted.length === 0 ? (
              <div className="rounded-xl bg-white px-4 py-3 text-sm text-neutral-600">
                No generated documents yet.
              </div>
            ) : (
              <div>
                {artifactsSorted.map((a) => (
                  <ArtifactDownloadCard
                    key={a.id}
                    artifactId={a.id}
                    artifactType={a.artifact_type === "essay_draft" ? "essay_draft" : "cv_draft"}
                    title={a.title || "Artifact"}
                    schoolName={a.school_name ?? ""}
                    downloadUrl={a.download_url.startsWith("/api/") ? a.download_url : `/api${a.download_url}`}
                  />
                ))}
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  );
}


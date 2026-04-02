"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { STAGES } from "@/components/StageProgressBar";
import { useSession } from "@/context/SessionContext";
import {
  fetchCandidateProfile,
  getApiBaseUrl,
  listUploadedFiles,
  uploadFiles,
  type UploadedFileDto,
} from "@/lib/api";

const DOCS_POLL_MS = 1000;

export function CandidateDocumentsPage() {
  const router = useRouter();
  const { session, setSession, signOut } = useSession();
  const [loading, setLoading] = useState(true);
  const [filesLoading, setFilesLoading] = useState(true);
  const [files, setFiles] = useState<UploadedFileDto[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadStage, setUploadStage] = useState<number>(1);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const role = session?.role;
  const sessionToken = session?.session_token ?? null;

  const filesByStage = useMemo(() => {
    const out = new Map<number, UploadedFileDto[]>();
    for (const f of files) {
      const s = typeof f.uploaded_stage === "number" && Number.isFinite(f.uploaded_stage) ? f.uploaded_stage : 1;
      const arr = out.get(s) ?? [];
      arr.push(f);
      out.set(s, arr);
    }
    for (const [k, arr] of Array.from(out.entries())) {
      arr.sort((a: UploadedFileDto, b: UploadedFileDto) => a.original_filename.localeCompare(b.original_filename));
      out.set(k, arr);
    }
    return out;
  }, [files]);

  useEffect(() => {
    if (!role || role !== "candidate" || !sessionToken) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    void fetchCandidateProfile(sessionToken)
      .then((c) => {
        if (cancelled) return;
        setSession({
          role: "candidate",
          session_token: sessionToken,
          candidate: c,
        });
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [role, sessionToken, setSession]);

  useEffect(() => {
    if (!sessionToken) return;
    let cancelled = false;
    setFilesLoading(true);
    setError(null);
    void listUploadedFiles(sessionToken)
      .then((out) => {
        if (cancelled) return;
        setFiles(out);
      })
      .catch((e) => {
        if (!cancelled) setError(String(e));
      })
      .finally(() => {
        if (!cancelled) setFilesLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [sessionToken]);

  useEffect(() => {
    if (!sessionToken) return;
    const hasProcessing = files.some(
      (f) => f.status === "uploading" || f.status === "reviewing",
    );
    if (!hasProcessing) return;
    const id = setTimeout(async () => {
      try {
        const out = await listUploadedFiles(sessionToken);
        setFiles(out);
      } catch {
        // ignore polling errors
      }
    }, DOCS_POLL_MS);
    return () => clearTimeout(id);
  }, [files, sessionToken]);

  if (!session || session.role !== "candidate" || !session.candidate) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 text-sm text-neutral-500">
        Please sign in to view your documents.
      </div>
    );
  }

  if (loading || !sessionToken) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 text-sm text-neutral-500">
        Loading your documents…
      </div>
    );
  }

  const candidate = session.candidate;

  const readyCount = files.filter((f) => f.status === "ready").length;
  const totalCount = files.length;

  const doUpload = async (selected: FileList | null) => {
    if (!selected || selected.length === 0 || !sessionToken) return;
    setUploading(true);
    setError(null);
    try {
      await uploadFiles(selected, sessionToken, uploadStage);
      const out = await listUploadedFiles(sessionToken);
      setFiles(out);
      if (fileInputRef.current) fileInputRef.current.value = "";
    } catch (e) {
      setError(String(e));
    } finally {
      setUploading(false);
    }
  };

  const download = async (fileId: string, filename: string) => {
    if (!sessionToken) {
      setError("Please sign in again (missing session token).");
      return;
    }
    const root = getApiBaseUrl();
    if (!root) throw new Error("NEXT_PUBLIC_API_URL is not set");

    const res = await fetch(
      `${root.replace(/\/$/, "")}/files/${fileId}/download`,
      {
        method: "GET",
        headers: { Authorization: `Bearer ${sessionToken}` },
      },
    );
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`Download failed: ${res.status} ${text}`);
    }

    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  const formatBadge = (status: UploadedFileDto["status"]) => {
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
  };

  return (
    <div className="min-h-screen bg-surface text-on-surface">
      <nav className="fixed top-0 z-50 w-full border-b border-[#c4c6cd]/15 bg-surface-low/80 shadow-ambient backdrop-blur-md">
        <div className="flex w-full items-center justify-between px-6 py-4 sm:px-8">
          <div className="flex items-center gap-8">
            <span className="font-serif text-xl font-black italic text-brand-900">
              GradAdvisor
            </span>
            <div className="hidden items-center gap-6 md:flex" aria-label="Primary">
              <button
                type="button"
                onClick={() => router.push("/")}
                className="text-sm font-medium text-brand-500 transition-colors hover:text-brand-900"
              >
                Dashboard
              </button>
              <button
                type="button"
                aria-current="page"
                className="border-b-2 border-accent pb-1 text-sm font-semibold text-brand-900"
              >
                Documents
              </button>
            </div>
          </div>

          <div className="flex items-center gap-4 sm:gap-6">
            <div className="hidden flex-col items-end sm:flex">
              <span className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant">
                Repository Status
              </span>
              <span className="text-xs font-semibold text-brand-900">
                {readyCount}/{totalCount} verified
              </span>
            </div>
            <div
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-[#c4c6cd]/15 bg-surface-container font-serif text-sm font-semibold text-brand-900"
              aria-hidden
            >
              {candidate.full_name
                .split(" ")
                .slice(0, 2)
                .map((p) => p[0])
                .join("")
                .toUpperCase()}
            </div>
            <button type="button" onClick={signOut} className="btn-ghost">
              Sign out
            </button>
          </div>
        </div>
      </nav>

      <main className="pt-24">
        <div className="mx-auto max-w-7xl px-6 py-12 sm:px-8">
          <header className="mb-12">
            <div className="flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
              <div className="max-w-2xl">
                <span className="mb-2 block text-[10px] font-bold uppercase tracking-widest text-brand-500">
                  Archive &amp; Repository
                </span>
                <h1 className="font-serif text-5xl font-black leading-tight text-brand-900">
                  Document Inventory
                </h1>
                <p className="mt-4 text-lg font-light leading-relaxed text-on-surface-variant">
                  Your academic credentials and application materials, organized by stage.
                </p>
                <p className="mt-2 text-xs text-on-surface-variant">
                  Signed in as {candidate.email ?? "—"}
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-3">
                <div className="flex items-center gap-2 rounded-lg bg-surface-container-lowest px-3 py-2 shadow-ambient">
                  <span className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant">
                    Upload stage
                  </span>
                  <select
                    value={uploadStage}
                    onChange={(e) => setUploadStage(Number(e.target.value))}
                    className="rounded-md border border-[#c4c6cd]/15 bg-surface-container-highest px-2 py-1 text-xs font-semibold text-brand-900 focus:outline-none focus:ring-2 focus:ring-accent"
                  >
                    {STAGES.map((s, idx) => (
                      <option key={s.name} value={idx + 1}>
                        {String(idx + 1).padStart(2, "0")}. {s.short}
                      </option>
                    ))}
                  </select>
                </div>

                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploading}
                  className="inline-flex items-center gap-2 rounded-lg bg-brand-900 px-6 py-3 text-xs font-bold uppercase tracking-widest text-white shadow-ambient transition-all hover:bg-brand-800 disabled:opacity-50"
                >
                  Upload New
                </button>
              </div>
            </div>
          </header>

          <input
            ref={fileInputRef}
            type="file"
            multiple
            className="hidden"
            onChange={(e) => void doUpload(e.target.files)}
          />

          {error && <div className="mb-6 error-banner">{error}</div>}

          {filesLoading ? (
            <div className="rounded-xl bg-surface-container-low p-6 text-sm text-on-surface-variant">
              Loading documents…
            </div>
          ) : (
            <div className="space-y-12">
              {STAGES.map((stage, i) => {
                const stageNum = i + 1;
                const stageFiles = filesByStage.get(stageNum) ?? [];
                const isEmpty = stageFiles.length === 0;

                return (
                  <section key={stage.name}>
                    <div className="mb-8 flex items-baseline gap-4 border-b border-[#c4c6cd]/15 pb-4">
                      <h2
                        className={
                          isEmpty
                            ? "text-2xl font-bold text-on-surface/40"
                            : "text-2xl font-bold text-brand-900"
                        }
                      >
                        {String(stageNum).padStart(2, "0")}. {stage.short}
                      </h2>
                      <span
                        className={
                          isEmpty
                            ? "font-serif text-base italic text-on-surface/30"
                            : "font-serif text-base italic text-on-surface/50"
                        }
                      >
                        {stage.name}
                      </span>
                      {isEmpty ? (
                        <span className="ml-auto text-xs font-bold uppercase tracking-widest text-on-surface/40">
                          No documents yet
                        </span>
                      ) : null}
                    </div>

                    <div className="grid grid-cols-1 gap-8 md:grid-cols-2 xl:grid-cols-3">
                      {stageFiles.map((f) => {
                        const badge = formatBadge(f.status);
                        const canDownload = f.status !== "deleted" && f.status !== "failed";
                        return (
                          <div
                            key={f.id}
                            className="group rounded-xl bg-surface-container-lowest p-6 shadow-ambient transition-all duration-300 hover:shadow-[0px_16px_48px_rgba(25,28,29,0.08)]"
                          >
                            <div className="mb-6 flex items-start justify-between">
                              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-surface-container-low text-brand-900">
                                <span className="text-xl font-black">
                                  {f.original_filename.split(".").pop()?.slice(0, 3).toUpperCase() ?? "DOC"}
                                </span>
                              </div>
                              <span
                                className={[
                                  "rounded-full px-3 py-1 text-[10px] font-bold uppercase tracking-wider",
                                  badge.className,
                                ].join(" ")}
                              >
                                {badge.label}
                              </span>
                            </div>

                            <h3 className="mb-1 break-words text-lg font-bold text-brand-900">
                              {f.original_filename}
                            </h3>
                            <p className="text-sm text-on-surface/60">
                              {f.byte_size !== null
                                ? `${(f.byte_size / 1024).toFixed(1)} KB`
                                : "—"}
                              {f.document_type ? ` · ${String(f.document_type)}` : ""}
                            </p>

                            <div className="mt-6 flex justify-end gap-2 border-t border-[#c4c6cd]/10 pt-4 opacity-0 transition-opacity group-hover:opacity-100">
                              <button
                                type="button"
                                onClick={() => void download(f.id, f.original_filename)}
                                disabled={!canDownload || uploading}
                                className="rounded-lg px-2 py-2 text-[11px] font-semibold text-on-surface/50 transition-colors hover:text-brand-900 disabled:opacity-40"
                              >
                                Download
                              </button>
                            </div>
                          </div>
                        );
                      })}
                      {stageFiles.length === 0 ? <div /> : null}
                    </div>
                  </section>
                );
              })}
            </div>
          )}

          <footer className="mt-24 border-t border-[#c4c6cd]/15 pt-12 text-center">
            <p className="text-xs font-medium uppercase tracking-[0.2em] text-on-surface/50">
              Academic admission repository
            </p>
          </footer>
        </div>
      </main>
    </div>
  );
}


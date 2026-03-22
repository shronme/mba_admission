"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import {
  listUploadedFiles,
  uploadFiles,
  type UploadedFileDto,
} from "@/lib/api";
import { STAGES } from "@/components/StageProgressBar";

const STAGE_NAMES = STAGES.map((s) => s.name);

function ChevronIcon({ open }: { open: boolean }) {
  return (
    <svg
      className={`h-3.5 w-3.5 text-neutral-400 transition-transform ${open ? "rotate-180" : ""}`}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
    </svg>
  );
}

function UploadIcon() {
  return (
    <svg
      className="mx-auto h-8 w-8 text-neutral-300"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={1.5}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"
      />
    </svg>
  );
}

function FileIcon() {
  return (
    <svg
      className="h-3.5 w-3.5 shrink-0 text-neutral-400"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={1.5}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"
      />
    </svg>
  );
}

export function SidebarDocuments({
  sessionToken,
  candidateEmail,
  currentStage = 1,
  onFilesUploaded,
}: {
  sessionToken?: string | null;
  candidateEmail: string | null | undefined;
  currentStage?: number;
  onFilesUploaded?: () => void;
}) {
  const [files, setFiles] = useState<UploadedFileDto[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Which stage sections are expanded — default: only current stage
  const [expanded, setExpanded] = useState<Set<number>>(
    () => new Set([currentStage]),
  );

  const canLoad = useMemo(() => Boolean(sessionToken), [sessionToken]);

  useEffect(() => {
    if (!canLoad) return;
    void (async () => {
      try {
        const out = await listUploadedFiles(sessionToken ?? null);
        setFiles(out);
      } catch (e) {
        setError(String(e));
      }
    })();
  }, [sessionToken, canLoad]);

  // Poll while any file is processing
  useEffect(() => {
    const hasProcessing = files.some((f) => f.status === "uploading");
    if (!hasProcessing || !canLoad) return;
    const id = setTimeout(async () => {
      try {
        const out = await listUploadedFiles(sessionToken ?? null);
        setFiles(out);
      } catch {
        // silently ignore polling errors
      }
    }, 3000);
    return () => clearTimeout(id);
  }, [files, canLoad, sessionToken]);

  const doUpload = async (selected: FileList | null) => {
    if (!selected || selected.length === 0) return;
    setBusy(true);
    setError(null);
    try {
      await uploadFiles(selected, sessionToken ?? null);
      const out = await listUploadedFiles(sessionToken ?? null);
      setFiles(out);
      if (fileInputRef.current) fileInputRef.current.value = "";
      onFilesUploaded?.();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const download = async (fileId: string, filename: string) => {
    if (!sessionToken) {
      setError("Please sign in again (missing session token).");
      return;
    }
    const root = process.env.NEXT_PUBLIC_API_URL;
    if (!root) throw new Error("NEXT_PUBLIC_API_URL is not set");

    const res = await fetch(
      `${root.replace(/\/$/, "")}/files/${fileId}/download`,
      {
        method: "GET",
        headers: sessionToken
          ? { Authorization: `Bearer ${sessionToken}` }
          : undefined,
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

  const toggleStage = (stageIdx: number) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(stageIdx)) {
        next.delete(stageIdx);
      } else {
        next.add(stageIdx);
      }
      return next;
    });
  };

  const readyCount = files.filter((f) => f.status === "ready").length;
  const totalCount = files.length;

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="border-b border-neutral-200 px-4 py-3">
        <div className="flex items-baseline justify-between">
          <span className="text-sm font-semibold text-neutral-900">
            My Documents
          </span>
          <span className="text-xs text-neutral-400">
            {readyCount} of {totalCount} ready
          </span>
        </div>
        {candidateEmail && (
          <div className="mt-0.5 text-[11px] text-neutral-400">
            {candidateEmail}
          </div>
        )}
      </div>

      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        className="hidden"
        onChange={(e) => void doUpload(e.target.files)}
      />

      {error && (
        <div className="mx-4 mt-3 error-banner">{error}</div>
      )}

      {/* Stage sections */}
      <div className="flex-1 overflow-auto">
        {STAGE_NAMES.map((stageName, i) => {
          const stageNum = i + 1;
          const isCurrent = stageNum === currentStage;
          const isPast = stageNum < currentStage;
          const isOpen = expanded.has(stageNum);

          const stageNumClass = isCurrent
            ? "sidebar-stage-num sidebar-stage-num-current"
            : isPast
              ? "sidebar-stage-num sidebar-stage-num-past"
              : "sidebar-stage-num sidebar-stage-num-future";

          const uploadAreaClass = [
            "sidebar-upload-area",
            dragging ? "sidebar-upload-dragging" : "sidebar-upload-idle",
            busy ? "pointer-events-none opacity-50" : "",
          ].join(" ");

          return (
            <div
              key={stageName}
              className="border-b border-neutral-100 last:border-0"
            >
              {/* Section header */}
              <button
                type="button"
                onClick={() => toggleStage(stageNum)}
                className="flex w-full items-center justify-between px-4 py-2.5 text-left hover:bg-neutral-50"
              >
                <div className="flex items-center gap-2">
                  <span className={stageNumClass}>{stageNum}</span>
                  <span
                    className={`text-xs font-medium ${isCurrent ? "text-neutral-900" : "text-neutral-500"}`}
                  >
                    {stageName}
                  </span>
                  {isCurrent && (
                    <span className="rounded-full bg-indigo-50 px-1.5 py-0.5 text-[10px] font-semibold text-indigo-600">
                      Current
                    </span>
                  )}
                </div>
                <ChevronIcon open={isOpen} />
              </button>

              {/* Section body */}
              {isOpen && (
                <div className="px-4 pb-3">
                  {/* Upload area — shown only in current stage */}
                  {isCurrent && (
                    <div
                      onDragOver={(e) => {
                        e.preventDefault();
                        setDragging(true);
                      }}
                      onDragLeave={() => setDragging(false)}
                      onDrop={(e) => {
                        e.preventDefault();
                        setDragging(false);
                        void doUpload(e.dataTransfer.files);
                      }}
                      onClick={() => fileInputRef.current?.click()}
                      className={uploadAreaClass}
                    >
                      <UploadIcon />
                      <p className="mt-1.5 text-xs font-medium text-neutral-500">
                        {busy ? "Uploading…" : "Click to upload or drag & drop"}
                      </p>
                      <p className="mt-0.5 text-[10px] text-neutral-400">
                        PDF · DOC · DOCX · PNG · JPG · TXT
                      </p>
                    </div>
                  )}

                  {/* Files in this stage */}
                  {files.length === 0 ? (
                    <p className="text-[11px] text-neutral-400">
                      No documents yet.
                    </p>
                  ) : isCurrent ? (
                    <div className="space-y-2">
                      {files.map((f) => (
                        <div key={f.id} className="sidebar-file-card">
                          <FileIcon />
                          <div className="min-w-0 flex-1">
                            <p className="truncate text-[11px] font-medium text-neutral-800">
                              {f.original_filename}
                            </p>
                            <p className="text-[10px] text-neutral-400">
                              {f.byte_size !== null
                                ? `${(f.byte_size / 1024).toFixed(1)} KB`
                                : ""}
                              {f.status ? ` · ${f.status}` : ""}
                            </p>
                          </div>
                          <button
                            type="button"
                            disabled={!sessionToken || busy}
                            onClick={() =>
                              void download(f.id, f.original_filename)
                            }
                            className="btn-download"
                          >
                            ↓
                          </button>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-[11px] text-neutral-400">
                      No documents uploaded for this stage yet.
                    </p>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

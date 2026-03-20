"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import {
  listUploadedFiles,
  uploadFiles,
  type UploadedFileDto,
} from "@/lib/api";

export function SidebarDocuments({
  sessionToken,
  candidateEmail,
}: {
  sessionToken?: string | null;
  candidateEmail: string | null | undefined;
}) {
  const [files, setFiles] = useState<UploadedFileDto[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

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

  const onFilesSelected = async (selected: FileList | null) => {
    if (!selected || selected.length === 0) return;
    setBusy(true);
    setError(null);
    try {
      await uploadFiles(selected, sessionToken ?? null);
      const out = await listUploadedFiles(sessionToken ?? null);
      setFiles(out);
      // Reset input so selecting the same file again triggers onChange.
      if (fileInputRef.current) fileInputRef.current.value = "";
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

    const res = await fetch(`${root.replace(/\/$/, "")}/files/${fileId}/download`, {
      method: "GET",
      headers: sessionToken ? { Authorization: `Bearer ${sessionToken}` } : undefined,
    });
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

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-neutral-200 px-4 py-4">
        <div className="text-sm font-semibold text-neutral-900">Candidate</div>
        <div className="mt-1 text-xs text-neutral-600">
          {candidateEmail || "—"}
        </div>
      </div>

      <div className="flex-1 overflow-auto px-4 py-4">
        <div className="text-sm font-semibold text-neutral-900">Documents</div>
        <p className="mt-1 text-xs text-neutral-500">
          Upload raw files so the assistant can use them later.
        </p>

        <div className="mt-3">
          <input
            ref={fileInputRef}
            type="file"
            multiple
            className="hidden"
            onChange={(e) => void onFilesSelected(e.target.files)}
          />

          <button
            type="button"
            disabled={busy}
            onClick={() => fileInputRef.current?.click()}
            className="w-full rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm font-medium text-neutral-900 shadow-sm hover:bg-neutral-50 disabled:opacity-50"
          >
            {busy ? "Uploading…" : "Upload documents"}
          </button>
        </div>

        {error && (
          <div className="mt-3 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-900">
            {error}
          </div>
        )}

        <div className="mt-4 space-y-3">
          {files.length === 0 ? (
            <div className="rounded-md border border-neutral-200 bg-neutral-50 px-3 py-3 text-xs text-neutral-600">
              No documents uploaded yet.
            </div>
          ) : (
            files.map((f) => (
              <div
                key={f.id}
                className="rounded-md border border-neutral-200 bg-white px-3 py-3"
              >
                <div className="text-xs font-medium text-neutral-900">
                  {f.original_filename}
                </div>
                <div className="mt-1 text-[11px] text-neutral-500">
                  {f.byte_size !== null ? `${f.byte_size} bytes` : ""}{" "}
                  {f.status ? `· ${f.status}` : ""}
                </div>
                <div className="mt-3 flex gap-2">
                  <button
                    type="button"
                    disabled={!sessionToken || busy}
                    onClick={() => void download(f.id, f.original_filename)}
                    className="flex-1 rounded-md bg-neutral-900 px-2 py-1.5 text-xs font-medium text-white hover:bg-neutral-800"
                  >
                    Download
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}


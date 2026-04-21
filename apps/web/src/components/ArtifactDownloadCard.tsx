"use client";

import { useCallback, useMemo, useState } from "react";

import { useSession } from "@/context/SessionContext";
import { getApiBaseUrl } from "@/lib/api";

export interface ArtifactDownloadCardProps {
  artifactId: string;
  artifactType: "cv_draft" | "essay_draft";
  title: string;
  schoolName: string;
  downloadUrl: string; // relative path, e.g. "/artifacts/<uuid>/download"
}

function safeFilename(title: string, ext: string) {
  const base = (title || "artifact")
    .trim()
    .slice(0, 80)
    .replace(/[^\w\-. ]+/g, "")
    .trim()
    .replace(/\s+/g, "_");
  return `${base || "artifact"}.${ext}`;
}

export function ArtifactDownloadCard({
  artifactId,
  artifactType,
  title,
  schoolName,
  downloadUrl,
}: ArtifactDownloadCardProps): JSX.Element {
  const { session } = useSession();
  const token = session?.session_token ?? "";
  const [downloading, setDownloading] = useState<"docx" | "pdf" | null>(null);
  const apiRoot = useMemo(() => getApiBaseUrl() ?? "/api", []);

  const label = useMemo(() => {
    const prefix = artifactType === "cv_draft" ? "CV Draft saved" : "Essay Draft saved";
    const school = (schoolName || "").trim();
    const t = (title || "").trim();
    if (school && t) return `${prefix}: ${school} — ${t}`;
    if (t) return `${prefix}: ${t}`;
    return `${prefix}`;
  }, [artifactType, schoolName, title]);

  const download = useCallback(
    async (fmt: "docx" | "pdf") => {
      if (!token) throw new Error("Not signed in");
      setDownloading(fmt);
      try {
        const baseUrl = (() => {
          // Support legacy `/artifacts/...` paths and newer `/api/artifacts/...` paths.
          // Also allow an absolute URL if we ever return one from the backend.
          if (/^https?:\/\//i.test(downloadUrl)) return downloadUrl;
          if (downloadUrl.startsWith("/api/")) return downloadUrl;
          return `${apiRoot}${downloadUrl}`;
        })();
        const url = `${baseUrl}?format=${fmt}`;
        const res = await fetch(url, {
          method: "GET",
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) {
          const text = await res.text();
          throw new Error(`Download failed: ${res.status} ${text}`);
        }
        const blob = await res.blob();
        const objectUrl = URL.createObjectURL(blob);
        try {
          const a = document.createElement("a");
          a.href = objectUrl;
          a.download = safeFilename(title, fmt);
          a.rel = "noreferrer";
          document.body.appendChild(a);
          a.click();
          a.remove();
        } finally {
          URL.revokeObjectURL(objectUrl);
        }
      } finally {
        setDownloading(null);
      }
    },
    [apiRoot, downloadUrl, title, token],
  );

  return (
    <div className="mt-3 rounded-xl border border-[#c4c6cd]/20 bg-white px-4 py-3 text-sm shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-xs font-semibold text-neutral-900">{label}</div>
          <div className="mt-1 text-[11px] text-neutral-500">Artifact ID: {artifactId}</div>
          <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-neutral-600">
            <span>Download:</span>
            <button
              type="button"
              onClick={() => void download("docx")}
              disabled={downloading !== null}
              className="underline underline-offset-2 hover:text-neutral-900 disabled:opacity-50"
            >
              Word
            </button>
            <span className="text-neutral-300">/</span>
            <button
              type="button"
              onClick={() => void download("pdf")}
              disabled={downloading !== null}
              className="underline underline-offset-2 hover:text-neutral-900 disabled:opacity-50"
            >
              PDF
            </button>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <button
            type="button"
            onClick={() => void download("docx")}
            aria-label={`Download ${title} as Word`}
            disabled={downloading !== null}
            className="rounded-lg border border-[#c4c6cd]/25 bg-surface-low px-3 py-1.5 text-xs font-semibold text-brand-900 hover:bg-surface-container disabled:opacity-50"
          >
            {downloading === "docx" ? "Downloading…" : "Download as Word"}
          </button>
          <button
            type="button"
            onClick={() => void download("pdf")}
            aria-label={`Download ${title} as PDF`}
            disabled={downloading !== null}
            className="rounded-lg border border-[#c4c6cd]/25 bg-surface-low px-3 py-1.5 text-xs font-semibold text-brand-900 hover:bg-surface-container disabled:opacity-50"
          >
            {downloading === "pdf" ? "Downloading…" : "Download as PDF"}
          </button>
        </div>
      </div>
    </div>
  );
}


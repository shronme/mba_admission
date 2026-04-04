"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { useSession } from "@/context/SessionContext";
import {
  adminGetCandidate,
  adminUploadFiles,
  type AdminFileDto,
} from "@/lib/api";
import { AdmissionEvaluationReadOnly } from "@/components/AdmissionEvaluationPanel";
import { ProfileView } from "./ProfileView";

const STAGE_LABELS: Record<string, string> = {
  intake: "Intake",
  diagnosis: "Diagnosis",
  program_research: "Research",
  strategy: "Strategy",
  narrative: "Narrative",
  school_list: "School List",
  application_work: "Applications",
  iteration: "Iteration",
  interview_preparation: "Interviews",
};

const DOC_TYPE_COLORS: Record<string, string> = {
  cv: "bg-blue-100 text-blue-700",
  life_story: "bg-violet-100 text-violet-700",
  recommendation_letter: "bg-amber-100 text-amber-700",
  grade_sheet: "bg-emerald-100 text-emerald-700",
  irrelevant: "bg-neutral-100 text-neutral-500",
  unclassified: "bg-neutral-100 text-neutral-500",
};

const STATUS_ICONS: Record<string, string> = {
  ready: "✓",
  reviewing: "⏳",
  uploading: "⏳",
  failed: "✗",
  deleted: "✗",
};

function formatBytes(bytes: number | null): string {
  if (bytes === null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function FileRow({ file }: { file: AdminFileDto }) {
  const typeColor = DOC_TYPE_COLORS[file.document_type ?? "unclassified"] ?? "bg-neutral-100 text-neutral-500";
  const statusIcon = STATUS_ICONS[file.status] ?? "?";
  const isReady = file.status === "ready";
  const isInProgress =
    file.status === "uploading" || file.status === "reviewing";

  return (
    <div className="flex items-center gap-3 rounded-lg border border-neutral-200 bg-white p-3">
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-neutral-100 text-neutral-500">
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 002.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 00-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 00.75-.75 2.25 2.25 0 00-.1-.664m-5.8 0A2.251 2.251 0 0113.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25z" />
        </svg>
      </div>
      <div className="flex-1 min-w-0">
        <p className="truncate text-sm font-medium text-neutral-800">{file.original_filename}</p>
        <div className="mt-0.5 flex items-center gap-2">
          <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ${typeColor}`}>
            {file.document_type?.replace(/_/g, " ") ?? "unclassified"}
          </span>
          <span className="text-xs text-neutral-400">{formatBytes(file.byte_size)}</span>
        </div>
      </div>
      <div
        className={`shrink-0 text-xs font-medium ${
          isReady ? "text-emerald-600" : isInProgress ? "text-amber-500" : "text-red-500"
        }`}
      >
        {statusIcon} {file.status}
      </div>
    </div>
  );
}

type Props = {
  candidateId: string;
  onBack: () => void;
};

type AdminDetailTab = "profile" | "school_evaluation";

export function AdminCandidateDetail({ candidateId, onBack }: Props) {
  const { session } = useSession();
  const queryClient = useQueryClient();
  const sessionToken = session?.session_token ?? "";
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<AdminDetailTab>("profile");

  useEffect(() => {
    setActiveTab("profile");
  }, [candidateId]);

  const { data: candidate, isLoading, error } = useQuery({
    queryKey: ["admin-candidate", candidateId],
    queryFn: () => adminGetCandidate(candidateId, sessionToken),
    enabled: !!sessionToken && !!candidateId,
    refetchOnWindowFocus: false,
  });

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    setUploadError(null);
    setUploading(true);
    try {
      await adminUploadFiles(candidateId, files, sessionToken);
      await queryClient.invalidateQueries({ queryKey: ["admin-candidate", candidateId] });
    } catch (err) {
      setUploadError(String(err));
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-slate-50">
      {/* Header */}
      <header className="shrink-0 bg-slate-900">
        <div className="flex items-center gap-3 px-6 py-4">
          <button
            type="button"
            onClick={onBack}
            className="flex items-center gap-1.5 rounded-md border border-slate-700 px-2.5 py-1 text-xs font-medium text-slate-300 transition-colors hover:bg-slate-800"
          >
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
            All Candidates
          </button>
          {candidate && (
            <div className="flex items-baseline gap-2">
              <span className="text-sm font-semibold text-white">{candidate.full_name}</span>
              <span className="text-xs text-slate-400">{candidate.email}</span>
              <span className="rounded-full bg-indigo-600 px-2.5 py-0.5 text-xs font-medium text-white">
                {STAGE_LABELS[candidate.stage] ?? candidate.stage}
              </span>
            </div>
          )}
        </div>
      </header>

      {/* Body */}
      {isLoading && (
        <div className="flex flex-1 items-center justify-center text-sm text-slate-400">
          Loading candidate…
        </div>
      )}

      {error && (
        <div className="m-6 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {String(error)}
        </div>
      )}

      {candidate && (
        <div className="flex flex-1 flex-col gap-0 overflow-hidden">
          <div className="shrink-0 border-b border-neutral-200 bg-white px-6 py-3">
            <nav className="flex gap-1" aria-label="Candidate detail sections">
              <button
                type="button"
                onClick={() => setActiveTab("profile")}
                className={`rounded-md px-3 py-1.5 text-xs font-semibold transition-colors ${
                  activeTab === "profile"
                    ? "bg-slate-900 text-white"
                    : "text-neutral-600 hover:bg-neutral-100"
                }`}
              >
                Profile
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("school_evaluation")}
                className={`rounded-md px-3 py-1.5 text-xs font-semibold transition-colors ${
                  activeTab === "school_evaluation"
                    ? "bg-slate-900 text-white"
                    : "text-neutral-600 hover:bg-neutral-100"
                }`}
              >
                School evaluation
              </button>
            </nav>
          </div>

          <div className="flex min-h-0 flex-1 gap-0 overflow-hidden">
          {/* Left — Profile or evaluation */}
          <div className="flex-1 overflow-y-auto p-6">
            {activeTab === "profile" ? (
              <ProfileView profile={candidate.profile} />
            ) : (
              <AdmissionEvaluationReadOnly
                attributes={(candidate.profile?.attributes ?? {}) as Record<string, unknown>}
              />
            )}
          </div>

          {/* Right — Files */}
          <div className="flex w-80 shrink-0 flex-col overflow-hidden border-l border-neutral-200 bg-white xl:w-96">
            <div className="flex items-center justify-between border-b border-neutral-200 px-5 py-4">
              <div>
                <h3 className="text-sm font-semibold text-neutral-900">Documents</h3>
                <p className="text-xs text-neutral-500">
                  {candidate.files.length} file{candidate.files.length !== 1 ? "s" : ""}
                </p>
              </div>
              <div>
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  className="hidden"
                  onChange={(e) => void handleUpload(e)}
                  disabled={uploading}
                />
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploading}
                  className="flex items-center gap-1.5 rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-indigo-700 disabled:opacity-50"
                >
                  <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                  </svg>
                  {uploading ? "Uploading…" : "Upload"}
                </button>
              </div>
            </div>

            {uploadError && (
              <div className="mx-4 mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
                {uploadError}
              </div>
            )}

            <div className="flex-1 overflow-y-auto p-4 space-y-2">
              {candidate.files.length === 0 && (
                <div className="flex h-32 items-center justify-center text-xs text-neutral-400">
                  No files uploaded yet.
                </div>
              )}
              {candidate.files.map((f: AdminFileDto) => (
                <FileRow key={f.id} file={f} />
              ))}
            </div>
          </div>
          </div>
        </div>
      )}
    </div>
  );
}

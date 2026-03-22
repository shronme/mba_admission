"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { useSession } from "@/context/SessionContext";
import { adminListCandidates, type AdminCandidateListItem } from "@/lib/api";
import { AdminCandidateDetail } from "./AdminCandidateDetail";

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

const STATUS_COLORS: Record<string, string> = {
  active: "bg-emerald-100 text-emerald-800",
  archived: "bg-neutral-100 text-neutral-600",
  prospect: "bg-amber-100 text-amber-800",
};

function StageChip({ stage }: { stage: string }) {
  return (
    <span className="inline-flex items-center rounded-full bg-indigo-100 px-2.5 py-0.5 text-xs font-medium text-indigo-800">
      {STAGE_LABELS[stage] ?? stage}
    </span>
  );
}

function StatusChip({ status }: { status: string }) {
  const color = STATUS_COLORS[status] ?? "bg-neutral-100 text-neutral-600";
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${color}`}>
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
}

function CompletenessBar({ score }: { score: number }) {
  const pct = Math.max(0, Math.min(100, score));
  const color =
    pct >= 80 ? "bg-emerald-500" : pct >= 50 ? "bg-amber-400" : "bg-rose-400";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-24 overflow-hidden rounded-full bg-neutral-200">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs tabular-nums text-neutral-500">{pct}%</span>
    </div>
  );
}

export function AdminDashboard() {
  const { session, signOut } = useSession();
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const sessionToken = session?.session_token ?? "";
  const adminName = session?.admin?.full_name ?? "Admin";

  const { data: candidates, isLoading, error, refetch } = useQuery({
    queryKey: ["admin-candidates"],
    queryFn: () => adminListCandidates(sessionToken),
    enabled: !!sessionToken,
    refetchOnWindowFocus: false,
  });

  if (selectedId) {
    return (
      <AdminCandidateDetail
        candidateId={selectedId}
        onBack={() => setSelectedId(null)}
      />
    );
  }

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-slate-50">
      {/* Header */}
      <header className="shrink-0 bg-slate-900">
        <div className="flex items-center justify-between px-6 py-4">
          <div className="flex items-baseline gap-3">
            <span className="text-sm font-bold tracking-tight text-white">GradAdvisor</span>
            <span className="rounded-full bg-indigo-600 px-2.5 py-0.5 text-xs font-semibold text-white">
              Admin
            </span>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-slate-400">{adminName}</span>
            <button
              type="button"
              onClick={signOut}
              className="rounded-md border border-slate-700 px-3 py-1 text-xs font-medium text-slate-300 transition-colors hover:bg-slate-800"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="flex flex-1 flex-col overflow-hidden p-6">
        <div className="mb-5 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-slate-900">Candidates</h1>
            <p className="mt-0.5 text-sm text-slate-500">
              {candidates ? `${candidates.length} total` : "Loading…"}
            </p>
          </div>
          <button
            type="button"
            onClick={() => void refetch()}
            className="rounded-md border border-neutral-300 bg-white px-3 py-1.5 text-xs font-medium text-neutral-700 shadow-sm hover:bg-neutral-50"
          >
            Refresh
          </button>
        </div>

        {isLoading && (
          <div className="flex flex-1 items-center justify-center">
            <div className="text-sm text-slate-400">Loading candidates…</div>
          </div>
        )}

        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            Failed to load candidates: {String(error)}
          </div>
        )}

        {candidates && candidates.length === 0 && (
          <div className="flex flex-1 items-center justify-center text-sm text-slate-400">
            No candidates yet.
          </div>
        )}

        {candidates && candidates.length > 0 && (
          <div className="overflow-hidden rounded-xl border border-neutral-200 bg-white shadow-sm">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-neutral-200 bg-neutral-50">
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-neutral-500">
                    Name
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-neutral-500">
                    Email
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-neutral-500">
                    Stage
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-neutral-500">
                    Completion
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-neutral-500">
                    Status
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-neutral-500">
                    Program
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100">
                {candidates.map((c: AdminCandidateListItem) => (
                  <tr
                    key={c.id}
                    className="cursor-pointer transition-colors hover:bg-slate-50"
                    onClick={() => setSelectedId(c.id)}
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2.5">
                        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-xs font-bold text-indigo-700">
                          {c.full_name
                            .split(" ")
                            .map((n) => n[0])
                            .slice(0, 2)
                            .join("")
                            .toUpperCase()}
                        </div>
                        <span className="font-medium text-neutral-900">{c.full_name}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-neutral-600">{c.email ?? "—"}</td>
                    <td className="px-4 py-3">
                      <StageChip stage={c.stage} />
                    </td>
                    <td className="px-4 py-3">
                      <CompletenessBar score={c.completeness_score} />
                    </td>
                    <td className="px-4 py-3">
                      <StatusChip status={c.status} />
                    </td>
                    <td className="px-4 py-3 text-neutral-600 capitalize">{c.program_type}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  );
}

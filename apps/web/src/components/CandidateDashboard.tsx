"use client";

import { useSession } from "@/context/SessionContext";
import { BackendPing } from "@/components/BackendPing";
import { SampleJobPanel } from "@/components/SampleJobPanel";
import { WiringSmoke } from "@/components/WiringSmoke";

export function CandidateDashboard() {
  const { session, signOut } = useSession();
  if (!session) return null;

  const { candidate, created } = session;

  return (
    <div className="space-y-8">
      <div className="rounded-lg border border-emerald-200 bg-emerald-50/80 p-5 shadow-sm">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-emerald-800">
              {created ? "Welcome — new candidate" : "Welcome back"}
            </p>
            <h2 className="mt-1 text-xl font-semibold text-neutral-900">
              {candidate.full_name}
            </h2>
            <p className="mt-1 text-sm text-neutral-600">{candidate.email}</p>
            <p className="mt-2 text-xs text-neutral-500">
              Program: <code className="rounded bg-white/80 px-1">{candidate.program_type}</code> ·
              Status:{" "}
              <code className="rounded bg-white/80 px-1">{candidate.status}</code> · ID:{" "}
              <code className="rounded bg-white/80 px-1 text-[11px]">{candidate.id}</code>
            </p>
          </div>
          <button
            type="button"
            onClick={signOut}
            className="shrink-0 rounded-md border border-neutral-300 bg-white px-3 py-1.5 text-sm text-neutral-800 shadow-sm hover:bg-neutral-50"
          >
            Sign out
          </button>
        </div>
        {candidate.profile && (candidate.profile.headline || candidate.profile.summary) && (
          <div className="mt-4 border-t border-emerald-200/80 pt-4 text-sm text-neutral-700">
            {candidate.profile.headline && (
              <p className="font-medium text-neutral-900">{candidate.profile.headline}</p>
            )}
            {candidate.profile.summary && (
              <p className="mt-2 whitespace-pre-wrap text-neutral-600">{candidate.profile.summary}</p>
            )}
          </div>
        )}
      </div>

      <section>
        <h3 className="mb-3 text-sm font-semibold text-neutral-900">API diagnostics</h3>
        <div className="space-y-6">
          <BackendPing />
          <WiringSmoke />
          <SampleJobPanel />
        </div>
      </section>
    </div>
  );
}

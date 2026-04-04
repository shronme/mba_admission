"use client";

import { useCallback, useEffect, useState } from "react";

import { AdmissionEvaluationPanel } from "@/components/AdmissionEvaluationPanel";
import { CandidateIntakeForm } from "@/components/CandidateIntakeForm";
import { CandidateStitchShell, candidateInitials } from "@/components/CandidateStitchShell";
import { useSession } from "@/context/SessionContext";
import type { CandidateDto } from "@/lib/api";
import { fetchCandidateProfile } from "@/lib/api";


export function CandidateDashboard() {
  const { session, setSession, signOut } = useSession();
  const [activeTab, setActiveTab] = useState<"dashboard" | "documents">("dashboard");
  const [intakeSynced, setIntakeSynced] = useState(false);
  const [needsIntake, setNeedsIntake] = useState(false);
  const role = session?.role;
  const sessionTokenRaw = session?.session_token;
  const snapshotCandidate = session?.candidate;

  const handleCandidateUpdate = useCallback(
    (c: CandidateDto) => {
      const token = sessionTokenRaw;
      if (!token) return;
      setSession({
        role: "candidate",
        session_token: token,
        candidate: c,
      });
    },
    [setSession, sessionTokenRaw],
  );

  const computeNeedsIntake = (c: any) => {
    const profile = c?.profile ?? null;
    const attrs = profile?.attributes ?? null;
    const step = Number((attrs as any)?.intake_step_completed ?? 0);
    const stepCompleted = Number.isFinite(step) ? step : 0;
    // Intake is considered done only after Step 4 (chat-based gap filling) is complete.
    return profile?.intake_form_completed !== true || stepCompleted < 4;
  };

  // Sync once per candidate session (token), not on every `candidate` object update. Including
  // `snapshotCandidate` in deps re-ran this after intake completion, re-fetched before step 4
  // was reliably persisted, and set `needsIntake` back to true — bouncing users to this screen.
  useEffect(() => {
    if (!role || role !== "candidate" || !sessionTokenRaw) {
      setIntakeSynced(false);
      return;
    }
    const token = sessionTokenRaw;
    const snapshot = snapshotCandidate;
    let cancelled = false;
    void fetchCandidateProfile(token)
      .then((c) => {
        if (cancelled) return;
        setSession({
          role: "candidate",
          session_token: token,
          candidate: c,
        });
        setNeedsIntake(computeNeedsIntake(c));
        setIntakeSynced(true);
      })
      .catch(() => {
        if (!cancelled) {
          setNeedsIntake(computeNeedsIntake(snapshot));
          setIntakeSynced(true);
        }
      });
    return () => {
      cancelled = true;
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps -- see effect comment: do not re-sync on every candidate update
  }, [role, sessionTokenRaw, setSession]);

  if (!session || session.role !== "candidate" || !session.candidate) return null;

  const candidate = session.candidate;
  const sessionToken = session.session_token ?? null;

  if (!intakeSynced || !sessionToken) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 text-sm text-neutral-500">
        Loading your profile…
      </div>
    );
  }

  if (needsIntake) {
    return (
      <CandidateIntakeForm
        sessionToken={sessionToken}
        initialFullName={candidate.full_name}
        onSignOut={signOut}
        onComplete={(c) => {
          setSession({
            role: "candidate",
            session_token: sessionToken,
            candidate: c,
          });
          setNeedsIntake(false);
        }}
      />
    );
  }

  return (
    <CandidateStitchShell
      userInitials={candidateInitials(candidate.full_name ?? "")}
      activeNav={activeTab}
      onNavDashboard={() => setActiveTab("dashboard")}
      onNavDocuments={() => setActiveTab("documents")}
      activePhaseIndex={1}
      phaseProgressCurrent={2}
      phaseProgressTotal={6}
      onSignOut={signOut}
      mobileMainTab="dashboard"
    >
      <div className="mx-auto w-full max-w-screen-2xl px-4 py-10 sm:px-6 sm:py-12 lg:px-8">
        {activeTab === "dashboard" ? (
          <AdmissionEvaluationPanel
            sessionToken={sessionToken}
            candidate={candidate}
            onCandidateUpdate={handleCandidateUpdate}
          />
        ) : (
          <div className="rounded-2xl border border-[#c4c6cd]/20 bg-surface-card p-8 shadow-sm">
            <span className="mb-1 block text-[10px] font-medium uppercase tracking-widest text-on-surface-variant">
              Documents
            </span>
            <h1 className="font-serif text-2xl text-brand-900">Your files</h1>
            <p className="mt-2 text-sm text-on-surface-variant">
              Upload flow coming soon — use Intake to add CV and life story for now.
            </p>
          </div>
        )}
      </div>
    </CandidateStitchShell>
  );
}

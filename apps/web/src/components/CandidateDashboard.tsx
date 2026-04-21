"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { AdmissionEvaluationPanel } from "@/components/AdmissionEvaluationPanel";
import { CandidateIntakeForm } from "@/components/CandidateIntakeForm";
import { CandidateStitchShell, candidateInitials } from "@/components/CandidateStitchShell";
import { useSession } from "@/context/SessionContext";
import type { CandidateDto } from "@/lib/api";
import { fetchCandidateProfile } from "@/lib/api";


export function CandidateDashboard() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { session, setSession, signOut } = useSession();
  const [activeTab, setActiveTab] = useState<"dashboard" | "documents">("dashboard");
  const [intakeSynced, setIntakeSynced] = useState(false);
  const [needsIntake, setNeedsIntake] = useState(false);
  const [showSelectSchoolsNotice, setShowSelectSchoolsNotice] = useState(false);
  const role = session?.role;
  const sessionTokenRaw = session?.session_token;
  const snapshotCandidate = session?.candidate;

  const notice = useMemo(() => (searchParams ? searchParams.get("notice") : null), [searchParams]);

  useEffect(() => {
    if (notice !== "select-schools") return;
    setShowSelectSchoolsNotice(true);
    router.replace("/");
  }, [notice, router]);

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
  const attrs = (candidate.profile?.attributes ?? null) as Record<string, unknown> | null;
  const hasSelectedSchools = Array.isArray(attrs?.selected_schools) && attrs!.selected_schools.length > 0;
  const stage = (candidate.stage ?? "").toLowerCase();
  const isStrategyOrLater =
    stage === "strategy" ||
    stage === "narrative" ||
    stage === "school_list" ||
    stage === "application_work" ||
    stage === "iteration" ||
    stage === "interview_preparation";
  const phaseIndex = hasSelectedSchools || isStrategyOrLater ? 2 : 1;
  const phaseCurrent = hasSelectedSchools || isStrategyOrLater ? 3 : 2;

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
      activePhaseIndex={phaseIndex}
      phaseProgressCurrent={phaseCurrent}
      phaseProgressTotal={4}
      onSignOut={signOut}
      mobileMainTab="dashboard"
    >
      <div className="mx-auto w-full max-w-screen-2xl px-4 py-10 sm:px-6 sm:py-12 lg:px-8">
        {showSelectSchoolsNotice ? (
          <div className="mb-6 flex items-start justify-between gap-4 rounded-2xl border border-amber-200 bg-amber-50 px-5 py-4 text-sm text-amber-900">
            <div>
              <p className="font-semibold">Select schools to unlock your advisor</p>
              <p className="mt-1 text-amber-900/80">
                Please confirm at least one school in your evaluation first.
              </p>
            </div>
            <button
              type="button"
              className="shrink-0 rounded-lg border border-amber-200 bg-white px-3 py-1.5 text-xs font-semibold text-amber-900 hover:bg-amber-100"
              onClick={() => setShowSelectSchoolsNotice(false)}
              aria-label="Dismiss notice"
            >
              Dismiss
            </button>
          </div>
        ) : null}
        {activeTab === "dashboard" ? (
          <div className="space-y-6">
            {hasSelectedSchools || isStrategyOrLater ? (
              <div className="rounded-2xl border border-[#c4c6cd]/20 bg-surface-card p-6 shadow-sm sm:p-8">
                <p className="text-sm font-semibold text-brand-900">Strategy phase unlocked</p>
                <p className="mt-2 text-sm text-on-surface-variant">
                  Continue with your advisor to turn your evaluation into an action plan.
                </p>
                <button
                  type="button"
                  className="group/btn mt-6 flex items-center justify-center gap-3 rounded-lg bg-accent px-8 py-4 text-sm font-bold text-brand-900 shadow-xl shadow-accent/20 transition-transform hover:scale-[1.02]"
                  onClick={() => router.push("/advisor")}
                >
                  Continue with your advisor <span aria-hidden>→</span>
                </button>
              </div>
            ) : null}

            <AdmissionEvaluationPanel
              sessionToken={sessionToken}
              candidate={candidate}
              onCandidateUpdate={handleCandidateUpdate}
            />
          </div>
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

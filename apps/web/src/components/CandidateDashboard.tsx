"use client";

import { useEffect, useState } from "react";

import { CandidateIntakeForm } from "@/components/CandidateIntakeForm";
import { useSession } from "@/context/SessionContext";
import { fetchCandidateProfile } from "@/lib/api";
import { SidebarDocuments } from "@/components/SidebarDocuments";
import { StageProgressBar } from "@/components/StageProgressBar";


export function CandidateDashboard() {
  const { session, setSession, signOut } = useSession();
  const [currentStage, setCurrentStage] = useState(1);
  const [activeTab, setActiveTab] = useState<"dashboard" | "documents">("dashboard");
  const [lastUploadedAt, setLastUploadedAt] = useState<number | undefined>();
  const [intakeSynced, setIntakeSynced] = useState(false);
  const [needsIntake, setNeedsIntake] = useState(false);
  const role = session?.role;
  const sessionTokenRaw = session?.session_token;
  const snapshotCandidate = session?.candidate;

  const computeNeedsIntake = (c: any) => {
    const profile = c?.profile ?? null;
    const attrs = profile?.attributes ?? null;
    const step = Number((attrs as any)?.intake_step_completed ?? 0);
    const stepCompleted = Number.isFinite(step) ? step : 0;
    // Intake is considered done only after Step 4 (chat-based gap filling) is complete.
    return profile?.intake_form_completed !== true || stepCompleted < 4;
  };

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
  }, [role, sessionTokenRaw, snapshotCandidate, setSession]);

  if (!session || session.role !== "candidate" || !session.candidate) return null;

  const candidate = session.candidate;
  const sessionToken = session.session_token ?? null;

  const handleProfileUpdate = (intakeComplete: boolean) => {
    setCurrentStage(intakeComplete ? 2 : 1);
  };

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
    <div className="dashboard-root">
      <header className="dashboard-header">
        <div className="dashboard-nav">
          <div className="flex items-baseline gap-2">
            <span className="text-sm font-bold tracking-tight text-neutral-900">
              GradAdvisor
            </span>
          </div>

          <nav className="flex items-center gap-2" aria-label="Primary">
            <button
              type="button"
              onClick={() => setActiveTab("dashboard")}
              className={
                activeTab === "dashboard"
                  ? "rounded-md bg-neutral-900 px-3 py-1.5 text-xs font-semibold text-white"
                  : "rounded-md px-3 py-1.5 text-xs font-semibold text-neutral-600 hover:bg-neutral-100"
              }
            >
              Dashboard
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("documents")}
              className={
                activeTab === "documents"
                  ? "rounded-md bg-neutral-900 px-3 py-1.5 text-xs font-semibold text-white"
                  : "rounded-md px-3 py-1.5 text-xs font-semibold text-neutral-600 hover:bg-neutral-100"
              }
            >
              Documents
            </button>
          </nav>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={signOut}
              className="btn-ghost ml-2"
            >
              Sign out
            </button>
          </div>
        </div>

        <StageProgressBar currentStage={currentStage} />
      </header>

      <div className="dashboard-content">
        {activeTab === "dashboard" ? (
          <>
            <main className="dashboard-chat-panel">
              <div className="flex h-full flex-col">
                <div className="border-b border-surface-low bg-surface-low px-4 py-3">
                  <div className="text-sm font-semibold text-neutral-900">Dashboard</div>
                  <div className="mt-0.5 text-[11px] text-neutral-500">
                    Chat is disabled. Upload documents and proceed through the guided steps.
                  </div>
                </div>
                <div className="flex-1 bg-white p-4 text-sm text-neutral-600">
                  Your next actions:
                  <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
                    <li>Upload supporting documents on the right.</li>
                    <li>We’ll extract data and update your profile automatically.</li>
                    <li>Use the Documents tab to track processing status.</li>
                  </ul>
                </div>
              </div>
            </main>

            <aside className="dashboard-sidebar">
              <SidebarDocuments
                sessionToken={sessionToken}
                candidateEmail={candidate.email}
                currentStage={currentStage}
                onFilesUploaded={() => setLastUploadedAt(Date.now())}
              />
            </aside>
          </>
        ) : (
          <main className="flex min-h-0 flex-1 flex-col overflow-hidden bg-white">
            <div className="border-b border-neutral-200 px-6 py-4">
              <h2 className="text-sm font-semibold text-neutral-900">Documents</h2>
              <p className="mt-0.5 text-xs text-neutral-500">
                All documents for your application, grouped by the stage you uploaded them in.
              </p>
            </div>
            <div className="min-h-0 flex-1 overflow-hidden">
              <SidebarDocuments
                sessionToken={sessionToken}
                candidateEmail={candidate.email}
                currentStage={currentStage}
                onFilesUploaded={() => setLastUploadedAt(Date.now())}
              />
            </div>
          </main>
        )}
      </div>
    </div>
  );
}

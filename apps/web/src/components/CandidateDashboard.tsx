"use client";

import { useEffect, useState } from "react";

import { CandidateIntakeForm } from "@/components/CandidateIntakeForm";
import { useSession } from "@/context/SessionContext";
import { fetchCandidateProfile } from "@/lib/api";
import { ChatView } from "@/features/chat/ChatView";
import { SidebarDocuments } from "@/components/SidebarDocuments";
import { StageProgressBar } from "@/components/StageProgressBar";


export function CandidateDashboard() {
  const { session, setSession, signOut } = useSession();
  const [currentStage, setCurrentStage] = useState(1);
  const [lastUploadedAt, setLastUploadedAt] = useState<number | undefined>();
  const [intakeSynced, setIntakeSynced] = useState(false);
  const [needsIntake, setNeedsIntake] = useState(false);

  useEffect(() => {
    if (!session || session.role !== "candidate" || !session.session_token) {
      setIntakeSynced(false);
      return;
    }
    const token = session.session_token;
    const snapshot = session.candidate;
    let cancelled = false;
    void fetchCandidateProfile(token)
      .then((c) => {
        if (cancelled) return;
        setSession({
          role: "candidate",
          session_token: token,
          candidate: c,
        });
        setNeedsIntake(c.profile?.intake_form_completed !== true);
        setIntakeSynced(true);
      })
      .catch(() => {
        if (!cancelled) {
          setNeedsIntake(snapshot?.profile?.intake_form_completed !== true);
          setIntakeSynced(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [session?.role, session?.session_token, setSession]);

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
            <span className="hidden text-xs text-neutral-500 sm:block">
              — AI Consultant
            </span>
          </div>

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
        <main className="dashboard-chat-panel">
          <ChatView
            sessionToken={sessionToken}
            currentStage={currentStage}
            onProfileUpdate={handleProfileUpdate}
            lastUploadedAt={lastUploadedAt}
          />
        </main>

        <aside className="dashboard-sidebar">
          <SidebarDocuments
            sessionToken={sessionToken}
            candidateEmail={candidate.email}
            currentStage={currentStage}
            onFilesUploaded={() => setLastUploadedAt(Date.now())}
          />
        </aside>
      </div>
    </div>
  );
}

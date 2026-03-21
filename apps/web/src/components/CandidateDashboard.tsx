"use client";

import { useState } from "react";

import { useSession } from "@/context/SessionContext";
import { ChatView } from "@/features/chat/ChatView";
import { SidebarDocuments } from "@/components/SidebarDocuments";
import { StageProgressBar } from "@/components/StageProgressBar";


export function CandidateDashboard() {
  const { session, signOut } = useSession();
  const [currentStage, setCurrentStage] = useState(1);

  if (!session) return null;

  const { candidate } = session;
  const sessionToken = session.session_token ?? null;

  const handleProfileUpdate = (intakeComplete: boolean) => {
    setCurrentStage(intakeComplete ? 2 : 1);
  };

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-slate-50">
      {/* ── Dark header ── */}
      <header className="shrink-0 bg-slate-900">
        {/* Top nav row */}
        <div className="flex items-center justify-between px-6 py-3">
          <div className="flex items-baseline gap-2">
            <span className="text-sm font-bold tracking-tight text-white">
              GradAdvisor
            </span>
            <span className="hidden text-xs text-slate-400 sm:block">
              US Graduate Admissions Consultant
            </span>
          </div>

          <div className="flex items-center gap-2">

            <button
              type="button"
              onClick={signOut}
              className="ml-2 rounded-md border border-slate-700 px-3 py-1 text-xs font-medium text-slate-300 transition-colors hover:bg-slate-800"
            >
              Sign out
            </button>
          </div>
        </div>

        {/* Stage progress bar */}
        <StageProgressBar currentStage={currentStage} />
      </header>

      {/* ── Main content ── */}
      <div className="flex flex-1 gap-4 overflow-hidden p-4">
        {/* Chat panel */}
        <main className="flex flex-1 flex-col overflow-hidden rounded-xl border border-neutral-200 bg-white shadow-sm">
          <ChatView
            sessionToken={sessionToken}
            currentStage={currentStage}
            onProfileUpdate={handleProfileUpdate}
          />
        </main>

        {/* Documents sidebar */}
        <aside className="flex w-72 shrink-0 flex-col overflow-hidden rounded-xl border border-neutral-200 bg-white shadow-sm xl:w-80">
          <SidebarDocuments
            sessionToken={sessionToken}
            candidateEmail={candidate.email}
            currentStage={currentStage}
          />
        </aside>
      </div>
    </div>
  );
}

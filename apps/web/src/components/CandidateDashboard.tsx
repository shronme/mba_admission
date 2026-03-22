"use client";

import { useState } from "react";

import { useSession } from "@/context/SessionContext";
import { ChatView } from "@/features/chat/ChatView";
import { SidebarDocuments } from "@/components/SidebarDocuments";
import { StageProgressBar } from "@/components/StageProgressBar";


export function CandidateDashboard() {
  const { session, signOut } = useSession();
  const [currentStage, setCurrentStage] = useState(1);
  const [lastUploadedAt, setLastUploadedAt] = useState<number | undefined>();

  if (!session || session.role !== "candidate" || !session.candidate) return null;

  const candidate = session.candidate;
  const sessionToken = session.session_token ?? null;

  const handleProfileUpdate = (intakeComplete: boolean) => {
    setCurrentStage(intakeComplete ? 2 : 1);
  };

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

"use client";

import { useSession } from "@/context/SessionContext";
import { ChatView } from "@/features/chat/ChatView";
import { SidebarDocuments } from "@/components/SidebarDocuments";

export function CandidateDashboard() {
  const { session, signOut } = useSession();
  if (!session) return null;

  const { candidate, created } = session;
  const sessionToken = session.session_token ?? null;

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 rounded-lg border border-neutral-200 bg-white p-4 shadow-sm sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-neutral-600">
            {created ? "New candidate" : "Welcome back"}
          </p>
          <h2 className="mt-1 text-xl font-semibold text-neutral-900">
            {candidate.full_name}
          </h2>
          <p className="mt-1 text-sm text-neutral-600">{candidate.email}</p>
        </div>
        <button
          type="button"
          onClick={signOut}
          className="rounded-md border border-neutral-300 bg-white px-3 py-1.5 text-sm font-medium text-neutral-800 shadow-sm hover:bg-neutral-50"
        >
          Sign out
        </button>
      </div>

      <div className="grid grid-cols-12 gap-4">
        <aside className="col-span-12 h-[70vh] rounded-lg border border-neutral-200 bg-white sm:col-span-4">
          <SidebarDocuments
            sessionToken={sessionToken}
            candidateEmail={candidate.email}
          />
        </aside>
        <main className="col-span-12 h-[70vh] rounded-lg border border-neutral-200 bg-white sm:col-span-8">
          <ChatView sessionToken={sessionToken} />
        </main>
      </div>
    </div>
  );
}

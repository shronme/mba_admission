"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { CandidateStitchShell, candidateInitials } from "@/components/CandidateStitchShell";
import { AdvisorDocumentsPanel } from "@/components/AdvisorDocumentsPanel";
import { StreamingChat } from "@/components/StreamingChat";
import type { CandidateDto } from "@/lib/api";
import { createAdvisorThread, fetchCandidateProfile, getApiBaseUrl } from "@/lib/api";
import { useSession } from "@/context/SessionContext";

function readSelectedSchools(candidate: CandidateDto): Array<{ school: string; program_display_name?: string }> | null {
  const attrs = (candidate.profile?.attributes ?? null) as Record<string, unknown> | null;
  const raw = attrs?.selected_schools;
  if (!Array.isArray(raw)) return null;
  const out: Array<{ school: string; program_display_name?: string }> = [];
  for (const row of raw) {
    if (!row || typeof row !== "object") continue;
    const r = row as Record<string, unknown>;
    const school = typeof r.school === "string" ? r.school : "";
    const disp = typeof r.program_display_name === "string" ? r.program_display_name : undefined;
    if (!school.trim()) continue;
    out.push({ school, program_display_name: disp });
  }
  return out.length ? out : null;
}

function AdvisorPageInner() {
  const router = useRouter();
  const search = useSearchParams();
  const { session, hydrated, setSession, signOut } = useSession();
  const sessionToken = session?.role === "candidate" ? session.session_token : null;
  const candidate = session?.role === "candidate" ? session.candidate : null;
  const [threadId, setThreadId] = useState<string | null>(null);
  const [prefill, setPrefill] = useState<string | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(true);
  const [streaming, setStreaming] = useState(false);
  const [hasUserMessages, setHasUserMessages] = useState(false);

  const forceNew = useMemo(() => search?.get("new") === "true", [search]);

  useEffect(() => {
    // Wait for SessionContext to rehydrate from localStorage before redirecting.
    // Otherwise a page refresh on /advisor always bounces to "/" (which lands the
    // user on dashboard stage 3) because the first render sees session === null.
    if (!hydrated) return;
    if (!sessionToken || !candidate) {
      router.push("/");
    }
  }, [candidate, hydrated, router, sessionToken]);

  const boot = useCallback(async (tok: string) => {
    setBusy(true);
    setError(null);
    try {
      const c = await fetchCandidateProfile(tok);
      setSession({ role: "candidate", session_token: tok, candidate: c });
      const selected = readSelectedSchools(c);
      if (!selected) {
        // Minimal notice; dashboard already shows the entry point.
        router.push("/?notice=select-schools");
        return;
      }
      const { thread_id } = await createAdvisorThread(tok, { new: forceNew });
      setThreadId(thread_id);

      // Determine whether the thread already has any user messages.
      try {
        const apiRoot = getApiBaseUrl() ?? "/api";
        const res = await fetch(`${apiRoot}/chat/threads/${encodeURIComponent(thread_id)}/messages`, {
          method: "GET",
          cache: "no-store",
          headers: { Authorization: `Bearer ${tok}` },
        });
        const text = await res.text();
        if (res.ok) {
          const data = text ? (JSON.parse(text) as any) : {};
          const msgs = Array.isArray(data?.messages) ? data.messages : [];
          setHasUserMessages(msgs.some((m: any) => String(m?.role ?? "") === "user"));
        }
      } catch {
        // non-blocking
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, [forceNew, router, setSession]);

  useEffect(() => {
    if (!sessionToken) return;
    void boot(sessionToken);
  }, [boot, sessionToken]);

  const selected = useMemo(() => (candidate ? readSelectedSchools(candidate) : null), [candidate]);

  if (!sessionToken || !candidate) return null;

  return (
    <CandidateStitchShell
      userInitials={candidateInitials(candidate.full_name ?? "")}
      activeNav="dashboard"
      onNavDashboard={() => router.push("/")}
      onNavDocuments={() => router.push("/documents")}
      activePhaseIndex={3}
      phaseProgressCurrent={4}
      phaseProgressTotal={4}
      onSignOut={signOut}
      mobileMainTab="dashboard"
    >
      <div className="mx-auto flex min-h-[calc(100vh-5rem)] max-w-6xl flex-col px-4 pb-10 pt-8 sm:px-6 lg:px-10">
        <div className="mb-4 flex flex-col gap-2 border-b border-transparent pb-2">
          <span className="block text-xs font-semibold uppercase tracking-[0.2em] text-brand-500">
            Stage 04 of 04
          </span>
          <h1 className="font-serif text-3xl font-bold text-brand-900 sm:text-4xl">
            Final AI Consultation
          </h1>
          <p className="max-w-xl text-sm text-neutral-600">
            Fine-tuning your narrative. The Advisor is analyzing your documents to identify
            unique storytelling angles for your application.
          </p>
        </div>

        {/* Mobile / small-screen context strip: schools + controls above the chat */}
        <div className="mb-4 flex flex-wrap items-center gap-2 lg:hidden">
          {selected?.map((s, idx) => (
            <span
              key={`m-${s.school}-${idx}`}
              className="rounded-full border border-[#c4c6cd]/25 bg-white px-3 py-1 text-xs font-semibold text-brand-900"
            >
              {s.school}
              {s.program_display_name ? (
                <span className="text-neutral-500"> · {s.program_display_name}</span>
              ) : null}
            </span>
          ))}
          <div className="ml-auto flex items-center gap-2">
            <div className="hidden items-center gap-2 rounded-full bg-surface-low px-3 py-1.5 md:flex">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-accent" />
              </span>
              <span className="text-xs font-medium text-neutral-600">Advisor is active</span>
            </div>
            <button
              type="button"
              className="rounded-lg border border-[#c4c6cd]/25 bg-surface-low px-3 py-1.5 text-xs font-semibold text-brand-900 hover:bg-surface-container disabled:opacity-50"
              disabled={busy}
              onClick={() => router.push("/advisor?new=true")}
            >
              New conversation
            </button>
          </div>
        </div>

        <div className="flex flex-1 flex-col gap-6 lg:flex-row lg:items-start">
          <div className="min-w-0 flex-1">
            {!hasUserMessages ? (
              <div className="mb-4 flex flex-wrap items-center gap-3">
                <span className="text-[10px] font-bold uppercase tracking-widest text-neutral-400">
                  Suggested
                </span>
                <div className="flex flex-wrap gap-2">
                  {[
                    { label: "Improve my CV", value: "Help me improve my CV" },
                    { label: "Review my essay", value: "Review my essay" },
                  ].map((row) => (
                    <button
                      key={row.label}
                      type="button"
                      className="rounded-full border border-[#c4c6cd]/30 bg-white px-3 py-1 text-xs font-semibold text-brand-900 transition-colors hover:bg-surface-high disabled:opacity-50"
                      aria-label={row.label}
                      onClick={() => setPrefill(row.value)}
                      disabled={busy || streaming}
                    >
                      {row.label}
                    </button>
                  ))}
                </div>
              </div>
            ) : null}

            {error ? (
              <div className="rounded-2xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-800">
                <p className="font-semibold">Couldn’t load advisor</p>
                <p className="mt-2">{error}</p>
                <button
                  type="button"
                  className="mt-4 rounded-lg border border-red-200 bg-white px-4 py-2 text-xs font-semibold text-red-800 hover:bg-red-50"
                  onClick={() => void boot(sessionToken)}
                >
                  Try again
                </button>
              </div>
            ) : busy || !threadId ? (
              <div className="flex min-h-[560px] items-center justify-center rounded-2xl bg-surface-low text-sm text-neutral-600 shadow-ambient">
                Loading your advisor conversation…
              </div>
            ) : (
              <StreamingChat
                sessionToken={sessionToken}
                threadId={threadId}
                prefillValue={prefill}
                onPrefillConsumed={() => setPrefill(undefined)}
                onSendingChange={setStreaming}
                onHistoryLoaded={(msgs) => setHasUserMessages(msgs.some((m) => m.role === "user"))}
                inputPlaceholder="Describe what you'd like help with…"
                userInitials={candidateInitials(candidate.full_name ?? "")}
                assistantLabel="The Advisor"
              />
            )}
          </div>

          {/* Desktop sidebar: schools + advisor status + new conversation */}
          <aside className="hidden w-[22rem] shrink-0 flex-col gap-4 lg:flex xl:w-[26rem]">
            <div className="flex items-center gap-2 rounded-full bg-surface-low px-3 py-2">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-accent" />
              </span>
              <span className="text-xs font-medium text-neutral-600">The Advisor is active</span>
            </div>

            {selected ? (
              <div className="rounded-2xl border border-[#c4c6cd]/20 bg-surface-low p-4">
                <span className="mb-2 block text-[10px] font-bold uppercase tracking-widest text-neutral-400">
                  Your schools
                </span>
                <ul className="flex flex-col gap-2">
                  {selected.map((s, idx) => (
                    <li
                      key={`${s.school}-${idx}`}
                      className="rounded-lg border border-[#c4c6cd]/25 bg-white px-3 py-2 text-xs font-semibold text-brand-900"
                    >
                      {s.school}
                      {s.program_display_name ? (
                        <span className="block text-[11px] font-normal text-neutral-500">
                          {s.program_display_name}
                        </span>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            <button
              type="button"
              className="rounded-lg border border-[#c4c6cd]/25 bg-surface-low px-4 py-2 text-xs font-semibold text-brand-900 hover:bg-surface-container disabled:opacity-50"
              disabled={busy}
              onClick={() => router.push("/advisor?new=true")}
            >
              Start new conversation
            </button>

            <AdvisorDocumentsPanel sessionToken={sessionToken} candidateEmail={candidate.email ?? null} />
          </aside>
        </div>
      </div>
    </CandidateStitchShell>
  );
}

export default function AdvisorPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-surface-low text-sm text-neutral-600">
          Loading your advisor conversation…
        </div>
      }
    >
      <AdvisorPageInner />
    </Suspense>
  );
}


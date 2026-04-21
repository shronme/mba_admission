"use client";

import type { ReactNode } from "react";

export const CANDIDATE_APPLICATION_PHASES = [
  "01. Intake",
  "02. Evaluation",
  "03. Positioning",
  "04. Advisor",
] as const;

export type CandidateStitchNavTab = "dashboard" | "documents";

type Props = {
  children: ReactNode;
  userInitials: string;
  activeNav: CandidateStitchNavTab;
  onNavDashboard: () => void;
  onNavDocuments: () => void;
  /** Index into `CANDIDATE_APPLICATION_PHASES` (0–3). */
  activePhaseIndex: number;
  phaseProgressCurrent: number;
  phaseProgressTotal: number;
  onSignOut?: () => void;
  /** Highlights the first icon in the mobile tab bar. */
  mobileMainTab: "intake" | "dashboard";
};

function IconBell({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5} aria-hidden>
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0"
      />
    </svg>
  );
}

function IconSettings({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5} aria-hidden>
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z"
      />
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
    </svg>
  );
}

function IconHelp({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5} aria-hidden>
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M9.879 7.519c1.171-1.025 3.071-1.025 4.242 0 1.172 1.025 1.172 2.687 0 3.712-.203.179-.43.326-.67.442-.745.361-1.45.999-1.45 1.827v.75M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9 5.25h.008v.008H12v-.008z"
      />
    </svg>
  );
}

function IconLogout({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5} aria-hidden>
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15M12 9l-3 3m0 0l3 3m-3-3h12.75"
      />
    </svg>
  );
}

export function candidateInitials(fullName: string): string {
  const parts = fullName.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0]!.slice(0, 2).toUpperCase();
  return (parts[0]![0]! + parts[parts.length - 1]![0]!).toUpperCase();
}

export function CandidateStitchShell({
  children,
  userInitials,
  activeNav,
  onNavDashboard,
  onNavDocuments,
  activePhaseIndex,
  phaseProgressCurrent,
  phaseProgressTotal,
  onSignOut,
  mobileMainTab,
}: Props) {
  const phases = CANDIDATE_APPLICATION_PHASES;
  const safePhaseIndex = Math.max(0, Math.min(activePhaseIndex, phases.length - 1));
  const pct =
    phaseProgressTotal > 0
      ? Math.min(100, Math.round((phaseProgressCurrent / phaseProgressTotal) * 100))
      : 0;
  const mainMobileLabel = mobileMainTab === "intake" ? "Intake" : "Dashboard";

  return (
    <div className="min-h-screen bg-surface pb-24 text-on-surface md:pb-0">
      <header className="fixed left-0 right-0 top-0 z-50 border-b border-[#c4c6cd]/15 bg-surface-low/80 shadow-ambient backdrop-blur-md">
        <div className="mx-auto flex h-20 w-full max-w-screen-2xl items-center justify-between px-6 sm:px-8">
          <div className="flex items-center gap-6 md:gap-8">
            <span className="font-serif text-xl italic text-brand-900">GradAdvisor</span>
            <nav className="flex items-center gap-6" aria-label="Primary">
              <button
                type="button"
                onClick={onNavDashboard}
                className={
                  activeNav === "dashboard"
                    ? "border-b-2 border-accent pb-1 text-sm font-semibold text-brand-900"
                    : "text-sm font-medium text-brand-500 hover:text-brand-900"
                }
              >
                Dashboard
              </button>
              <button
                type="button"
                onClick={onNavDocuments}
                className={
                  activeNav === "documents"
                    ? "border-b-2 border-accent pb-1 text-sm font-semibold text-brand-900"
                    : "text-sm font-medium text-brand-500 hover:text-brand-900"
                }
              >
                Documents
              </button>
            </nav>
          </div>
          <div className="flex items-center gap-4 sm:gap-6">
            <div className="mr-2 hidden flex-col items-end sm:flex">
              <span className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant">
                Overall Application Progress
              </span>
              <div className="flex items-center gap-3">
                <div className="h-1 w-32 overflow-hidden rounded-full bg-surface-highest">
                  <div className="h-full rounded-full bg-accent" style={{ width: `${pct}%` }} />
                </div>
                <span className="text-xs font-semibold text-brand-900">
                  {phaseProgressCurrent}/{phaseProgressTotal} Phases
                </span>
              </div>
            </div>
            <div className="flex gap-3 text-brand-900">
              <span className="inline-flex h-9 w-9 items-center justify-center rounded-full hover:bg-surface-container/80">
                <IconBell className="h-5 w-5" />
              </span>
              <span className="inline-flex h-9 w-9 items-center justify-center rounded-full hover:bg-surface-container/80">
                <IconSettings className="h-5 w-5" />
              </span>
            </div>
            <div
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-[#c4c6cd]/15 bg-surface-container font-serif text-sm font-semibold text-brand-900"
              aria-hidden
            >
              {userInitials}
            </div>
          </div>
        </div>
      </header>

      <aside className="fixed left-0 top-0 hidden h-screen w-64 flex-col border-r border-[#c4c6cd]/15 bg-surface-low py-8 pt-28 md:flex">
        <div className="mb-10 px-6">
          <h2 className="font-serif text-lg text-brand-900">The Advisor</h2>
          <p className="font-sans text-xs font-medium uppercase tracking-widest text-brand-500">Premium Admissions AI</p>
        </div>
        <div className="mb-4 px-6">
          <p className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant">Application Phases</p>
        </div>
        <nav className="no-scrollbar flex-1 space-y-1 overflow-y-auto" aria-label="Application phases">
          {phases.map((label, i) => {
            const active = i === safePhaseIndex;
            return (
              <div
                key={label}
                className={
                  active
                    ? "ml-4 flex items-center gap-3 rounded-l-full border border-r-0 border-[#c4c6cd]/20 border-y-surface-container bg-surface-card py-2.5 pl-4 font-bold text-brand-900 shadow-sm"
                    : "mx-4 flex items-center gap-3 rounded-lg px-4 py-2.5 text-sm text-on-surface-variant transition-colors hover:bg-surface-container"
                }
              >
                <span
                  className={
                    active
                      ? "h-2 w-2 shrink-0 rounded-full bg-accent"
                      : "h-2 w-2 shrink-0 rounded-full border border-[#c4c6cd]/40"
                  }
                />
                <span className="text-sm">{label}</span>
              </div>
            );
          })}
        </nav>
        <div className="mt-auto space-y-4 px-4">
          <button
            type="button"
            className="w-full rounded-xl bg-gradient-to-b from-brand-900 to-brand-800 py-3 text-sm font-semibold text-white shadow-ambient transition-opacity hover:opacity-90"
          >
            Upgrade to Elite
          </button>
          <div className="space-y-1">
            <a className="flex items-center gap-3 px-2 py-1 text-sm text-on-surface-variant hover:text-brand-900" href="#">
              <IconHelp className="h-4 w-4 shrink-0" />
              Help Center
            </a>
            {onSignOut ? (
              <button
                type="button"
                onClick={onSignOut}
                className="flex w-full items-center gap-3 px-2 py-1 text-left text-sm text-on-surface-variant hover:text-red-700"
              >
                <IconLogout className="h-4 w-4 shrink-0" />
                Log Out
              </button>
            ) : null}
          </div>
        </div>
      </aside>

      <main className="min-h-screen pt-20 md:pl-64">{children}</main>

      <div className="fixed bottom-0 left-0 right-0 z-50 flex items-center justify-around border-t border-[#c4c6cd]/20 bg-surface-low/90 px-4 py-3 backdrop-blur-md md:hidden">
        <span className="flex flex-col items-center gap-1 text-brand-900">
          <svg className="h-6 w-6" fill="currentColor" viewBox="0 0 24 24" aria-hidden>
            <path d="M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z" />
          </svg>
          <span className="text-[10px] font-medium uppercase tracking-wider">{mainMobileLabel}</span>
        </span>
        <span className="flex flex-col items-center gap-1 text-on-surface-variant">
          <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5} aria-hidden>
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z"
            />
          </svg>
          <span className="text-[10px] font-medium uppercase tracking-wider">Docs</span>
        </span>
        <span className="flex flex-col items-center gap-1 text-on-surface-variant">
          <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5} aria-hidden>
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z"
            />
          </svg>
          <span className="text-[10px] font-medium uppercase tracking-wider">AI</span>
        </span>
        <span className="flex flex-col items-center gap-1 text-on-surface-variant">
          <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5} aria-hidden>
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z"
            />
          </svg>
          <span className="text-[10px] font-medium uppercase tracking-wider">Profile</span>
        </span>
      </div>
    </div>
  );
}

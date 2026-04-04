"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import type {
  AdmissionEvaluationJobDto,
  AdmissionEvaluationResultDto,
  CandidateDto,
} from "@/lib/api";
import {
  fetchCandidateProfileFresh,
  startAdmissionEvaluation,
} from "@/lib/api";

type Props = {
  sessionToken: string;
  candidate: CandidateDto;
  onCandidateUpdate: (c: CandidateDto) => void;
};

function readAttrs(c: CandidateDto): Record<string, unknown> {
  return (c.profile?.attributes ?? {}) as Record<string, unknown>;
}

function parseJob(raw: unknown): AdmissionEvaluationJobDto | null {
  if (!raw || typeof raw !== "object") return null;
  const j = raw as Record<string, unknown>;
  if (String(j.phase || "") !== "running") return null;
  return {
    ai_run_id: String(j.ai_run_id ?? ""),
    phase: "running",
    message: String(j.message ?? ""),
    updated_at: String(j.updated_at ?? ""),
    current_school: String(j.current_school ?? ""),
    current_program_display_name: String(j.current_program_display_name ?? ""),
    current_program_slug: String(j.current_program_slug ?? ""),
    program_index: Number(j.program_index ?? 0),
    programs_total: Number(j.programs_total ?? 0),
    substep: String(j.substep ?? ""),
    phase_scope: String(j.phase_scope ?? ""),
    progress_percent: Number(j.progress_percent ?? 0),
    programs_completed: Array.isArray(j.programs_completed)
      ? (j.programs_completed as { school: string; program_display_name: string }[])
      : [],
  };
}

function parseResult(raw: unknown): AdmissionEvaluationResultDto | null {
  if (!raw || typeof raw !== "object") return null;
  const r = raw as Record<string, unknown>;
  const st = r.status;
  if (st !== "complete" && st !== "failed") return null;
  return {
    status: st,
    primary: Array.isArray(r.primary) ? (r.primary as AdmissionEvaluationResultDto["primary"]) : [],
    extra: Array.isArray(r.extra) ? (r.extra as AdmissionEvaluationResultDto["extra"]) : [],
    error: r.error === null || r.error === undefined ? null : String(r.error),
  };
}

export function AdmissionEvaluationPanel({ sessionToken, candidate, onCandidateUpdate }: Props) {
  const [error, setError] = useState<string | null>(null);
  const [booting, setBooting] = useState(true);
  const startOnce = useRef(false);

  useEffect(() => {
    startOnce.current = false;
  }, [sessionToken]);

  const attrs = readAttrs(candidate);
  const job = parseJob(attrs.admission_evaluation_job);
  const result = parseResult(attrs.admission_evaluation_result);

  const refresh = useCallback(async () => {
    const c = await fetchCandidateProfileFresh(sessionToken);
    onCandidateUpdate(c);
    return c;
  }, [sessionToken, onCandidateUpdate]);

  const retryStart = useCallback(async () => {
    setError(null);
    startOnce.current = false;
    try {
      await startAdmissionEvaluation(sessionToken);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [refresh, sessionToken]);

  useEffect(() => {
    let cancelled = false;

    async function boot() {
      setError(null);
      let fresh: CandidateDto;
      try {
        fresh = await fetchCandidateProfileFresh(sessionToken);
      } catch {
        fresh = candidate;
      }
      if (cancelled) return;
      onCandidateUpdate(fresh);
      const a = readAttrs(fresh);
      const res = parseResult(a.admission_evaluation_result);
      if (res?.status === "complete") {
        setBooting(false);
        return;
      }
      if (res?.status === "failed") {
        setBooting(false);
        return;
      }
      const j = parseJob(a.admission_evaluation_job);
      if (j) {
        setBooting(false);
        return;
      }
      if (startOnce.current) {
        setBooting(false);
        return;
      }
      startOnce.current = true;
      try {
        await startAdmissionEvaluation(sessionToken);
        if (!cancelled) await refresh();
      } catch (e) {
        if (!cancelled) {
          const msg = e instanceof Error ? e.message : String(e);
          if (msg.includes("already completed")) {
            await refresh();
          } else {
            setError(msg);
          }
        }
      } finally {
        if (!cancelled) setBooting(false);
      }
    }

    void boot();
    return () => {
      cancelled = true;
    };
  }, [sessionToken, onCandidateUpdate, refresh]);

  useEffect(() => {
    if (!job || booting) return;
    let cancelled = false;
    const t = window.setInterval(() => {
      void (async () => {
        try {
          const c = await fetchCandidateProfileFresh(sessionToken);
          if (!cancelled) onCandidateUpdate(c);
          const r = parseResult(readAttrs(c).admission_evaluation_result);
          if (r?.status === "complete" || r?.status === "failed") {
            window.clearInterval(t);
          }
          if (!parseJob(readAttrs(c).admission_evaluation_job)) {
            window.clearInterval(t);
          }
        } catch {
          /* ignore transient poll errors */
        }
      })();
    }, 1800);
    return () => {
      cancelled = true;
      window.clearInterval(t);
    };
  }, [job, booting, sessionToken, onCandidateUpdate]);

  if (booting) {
    return (
      <>
        <EvaluationPageHeader
          title="Admission evaluation"
          subtitle="Preparing your personalized research and program-by-program assessment."
        />
        <div className="relative space-y-8">
          <div className="absolute bottom-8 left-[1.375rem] top-8 hidden w-px bg-surface-container sm:block" aria-hidden />
          <section className="relative">
            <div className="flex flex-col items-stretch gap-6 sm:flex-row sm:items-start sm:gap-8">
              <div className="hidden h-11 w-11 shrink-0 items-center justify-center rounded-lg border border-[#c4c6cd]/20 bg-surface-card font-bold text-on-surface-variant shadow-sm sm:flex">
                1
              </div>
              <div className="flex flex-1 flex-col rounded-2xl border border-[#c4c6cd]/20 bg-surface-card p-8 shadow-sm sm:p-10">
                <p className="text-sm text-on-surface-variant">Preparing evaluation…</p>
              </div>
            </div>
          </section>
        </div>
      </>
    );
  }

  if (result?.status === "failed" && !job) {
    return (
      <>
        <EvaluationPageHeader
          title="Evaluation couldn’t finish"
          subtitle="Something went wrong while running research or scoring. You can try again."
        />
        <div className="rounded-2xl border border-red-200/80 bg-surface-card p-6 shadow-sm sm:p-8">
          <p className="text-sm font-semibold text-red-800">Evaluation failed</p>
          <p className="mt-2 text-sm text-on-surface-variant">{result.error ?? "Unknown error"}</p>
          <button
            type="button"
            className="group/btn mt-6 flex items-center justify-center gap-3 rounded-lg bg-accent px-8 py-4 text-sm font-bold text-brand-900 shadow-xl shadow-accent/20 transition-transform hover:scale-[1.02] sm:w-auto"
            onClick={() => void retryStart()}
          >
            Retry
          </button>
        </div>
      </>
    );
  }

  if (result?.status === "complete") {
    return <EvaluationResultsView result={result} />;
  }

  if (error) {
    return (
      <>
        <EvaluationPageHeader
          title="Couldn’t start evaluation"
          subtitle="Check your connection and try again."
        />
        <div className="rounded-2xl border border-[#c4c6cd]/20 bg-surface-card p-6 shadow-sm sm:p-8">
          <p className="text-sm text-red-700">{error}</p>
          <button
            type="button"
            className="mt-4 rounded-lg border border-[#c4c6cd]/25 bg-surface-low px-4 py-2 text-xs font-semibold text-brand-900 hover:bg-surface-container"
            onClick={() => void retryStart()}
          >
            Try again
          </button>
        </div>
      </>
    );
  }

  return <EvaluationProgressView job={job} />;
}

function EvaluationPageHeader({
  title,
  subtitle,
  variant = "candidate",
}: {
  title: string;
  subtitle: string;
  variant?: "candidate" | "admin";
}) {
  if (variant === "admin") {
    return (
      <header className="mb-8">
        <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
        <p className="mt-1 max-w-3xl text-sm text-slate-600">{subtitle}</p>
      </header>
    );
  }
  return (
    <header className="mb-10 sm:mb-12">
      <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
        <span className="rounded bg-surface-container px-2 py-0.5 font-bold tracking-wide text-on-surface-variant">
          PHASE 02
        </span>
        <span className="text-surface-dim">/</span>
        <span className="font-bold uppercase tracking-widest text-brand-500">Evaluation</span>
      </div>
      <h1 className="mb-2 font-serif text-3xl text-brand-900 sm:text-4xl">{title}</h1>
      <p className="max-w-2xl text-on-surface-variant">{subtitle}</p>
    </header>
  );
}

function IconResearchBrain({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 64 64" fill="none" aria-hidden>
      <path
        className="stroke-brand-900"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M18 42c-4 0-6-2.5-6-6 0-2 .8-3.6 2-4.8-1-1.8-1.5-4-1.5-6.2 0-6.8 5.5-12.2 12.2-12.2 1.2 0 2.4.2 3.5.6C30 10.8 34.8 8 40 8c8.8 0 16 7.2 16 16 0 .8-.2 1.6-.3 2.4 3.6 1.4 6.3 4.8 6.3 8.8 0 3.2-1.8 6-4.5 7.4.3.8.5 1.7.5 2.6 0 4.4-3.6 8-8 8H18z"
      />
      <circle cx="42" cy="24" r="10" className="stroke-brand-900" strokeWidth="2" fill="white" />
      <circle cx="42" cy="24" r="3.5" className="fill-brand-900" />
      <path
        className="stroke-brand-900"
        strokeWidth="1.6"
        strokeLinecap="round"
        d="M42 17v3.5M42 27.5V31M36.2 24h3.5M44.3 24H48M37.5 19.5l2.5 2.5M44 26l2.5 2.5M44 19.5l-2.5 2.5M37.5 26l2.5 2.5"
      />
    </svg>
  );
}

/** Rounded-rect path (viewBox 0 0 100 100) for the orbiting dot; matches square corners when scaled. */
const RESEARCH_FRAME_ORBIT_PATH =
  "M 12,4 L 88,4 A 8,8 0 0 1 96,12 L 96,88 A 8,8 0 0 1 88,96 L 12,96 A 8,8 0 0 1 4,88 L 4,12 A 8,8 0 0 1 12,4";

function EvaluationProgressView({
  job,
  headerVariant = "candidate",
}: {
  job: AdmissionEvaluationJobDto | null;
  headerVariant?: "candidate" | "admin";
}) {
  const scope = job?.phase_scope ?? "primary";
  const activeSchool = job?.current_school ?? "";
  const activeProgram = job?.current_program_display_name ?? "";
  const msg = job?.message ?? "Synthesizing competitive landscape data…";

  const statusLine =
    activeSchool.trim() !== ""
      ? `${activeSchool} — ${activeProgram}`
      : "Preparing your program research pipeline…";

  return (
    <>
      <EvaluationPageHeader
        variant={headerVariant}
        title="Research & scoring"
        subtitle="We’re gathering program context and producing your consolidated evaluation. This can take several minutes."
      />

      <div className="relative overflow-hidden rounded-2xl border border-[#c4c6cd]/20 bg-white p-6 shadow-sm sm:p-8 lg:p-10">
        <div className="pointer-events-none absolute -right-8 -top-12 h-40 w-40 rounded-full bg-amber-200/25 blur-3xl" aria-hidden />
        <div className="pointer-events-none absolute right-16 top-0 h-32 w-32 rounded-full bg-amber-100/30 blur-2xl" aria-hidden />

        <div className="relative flex items-center gap-2.5">
          <span className="h-2 w-2 shrink-0 rounded-full bg-amber-500" aria-hidden />
          <span className="text-xs font-bold uppercase tracking-[0.2em] text-brand-900">
            Research in progress
          </span>
        </div>

        <div className="relative mx-auto mt-10 flex max-w-md justify-center sm:mt-12">
          <div className="relative flex aspect-square w-full max-w-[11rem] items-center justify-center rounded-2xl bg-amber-50/20 p-2 sm:max-w-[12rem]">
            <svg
              className="pointer-events-none absolute inset-0 h-full w-full"
              viewBox="0 0 100 100"
              fill="none"
              aria-hidden
            >
              <path
                d={RESEARCH_FRAME_ORBIT_PATH}
                className="stroke-amber-200/80"
                strokeWidth="1.25"
                strokeLinejoin="round"
              />
              <circle r="4" className="fill-amber-500" stroke="white" strokeWidth="1.25">
                <animateMotion
                  dur="2.8s"
                  repeatCount="indefinite"
                  path={RESEARCH_FRAME_ORBIT_PATH}
                />
              </circle>
            </svg>
            <div className="relative z-10 rounded-xl border border-neutral-200 bg-white p-5 shadow-sm">
              <IconResearchBrain className="mx-auto h-14 w-14 sm:h-16 sm:w-16" />
            </div>
          </div>
        </div>

        <p className="relative mt-8 text-center font-serif text-lg leading-snug text-brand-900 sm:text-xl">
          {msg}
        </p>
        <p className="relative mt-2 text-center text-sm text-neutral-600">{statusLine}</p>

        {scope === "extra" && activeSchool ? (
          <div className="relative mt-6 rounded-xl border border-amber-200/40 bg-neutral-50 px-4 py-4">
            <p className="text-[10px] font-bold uppercase tracking-widest text-brand-900">
              Additional program in progress
            </p>
            <p className="mt-1 text-sm font-semibold text-brand-900">
              {activeSchool} — {activeProgram}
            </p>
            <p className="mt-1 text-sm text-neutral-600">{msg}</p>
          </div>
        ) : null}
      </div>
    </>
  );
}

/** Stitch Consolidated Evaluation Results — band labels when API omits admission_band. */
function admissionBandLabel(score: number | undefined, explicit?: string | null): string {
  const s = explicit?.trim();
  if (s) return s.toUpperCase();
  if (score == null || !Number.isFinite(score)) return "";
  if (score >= 85) return "TARGET";
  if (score >= 70) return "PROBABLE";
  if (score >= 55) return "MODERATE";
  return "STRETCH";
}

function IconCheckCircle({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle cx="12" cy="12" r="10" className="fill-emerald-50 stroke-emerald-600" strokeWidth="1.5" />
      <path
        className="stroke-emerald-700"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M8 12.5l2.5 2.5L16 9"
      />
    </svg>
  );
}

function IconInfo({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle cx="12" cy="12" r="10" className="fill-amber-50 stroke-amber-600" strokeWidth="1.5" />
      <path
        className="stroke-amber-800"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M12 16v-5M12 8h.01"
      />
    </svg>
  );
}

/** Uppercase program line for the header pill (e.g. MPP CANDIDATE). */
function programCandidateBadge(programDisplayName: string): string {
  const t = programDisplayName.trim();
  if (!t) return "CANDIDATE";
  const u = t.toUpperCase().replace(/[()]/g, " ").replace(/\s+/g, " ").trim();
  if (u.length <= 28 && !u.endsWith("CANDIDATE")) return `${u} CANDIDATE`;
  return u;
}

/** Split model text into priority-action lines for the dark card. */
function splitPriorityLines(text: string | undefined): string[] {
  const t = text?.trim();
  if (!t) return [];
  const byNl = t.split(/\n/).map((s) => s.trim()).filter(Boolean);
  if (byNl.length > 1) return byNl;
  const byNum = t.split(/\s*(?:\d+)[.)]\s+/).map((s) => s.trim()).filter(Boolean);
  if (byNum.length > 1) return byNum;
  return [t];
}

function splitStrengthBullets(text: string | undefined): string[] {
  const t = text?.trim();
  if (!t) return ["—"];
  const parts = t.split(/[;•]/).map((s) => s.trim()).filter(Boolean);
  return parts.length ? parts : [t];
}

type EvaluationSectionLabels = {
  strengths: string;
  weaknesses: string;
  narrative: string;
  priorities: string;
};

const DEFAULT_EVAL_SECTION_LABELS: EvaluationSectionLabels = {
  strengths: "Core strengths",
  weaknesses: "Strategic gaps",
  narrative: "Narrative strategy",
  priorities: "Priority actions",
};

function splitPriorityActionsForBanner(items: string[]): [string[], string[]] {
  const safe = items.length ? items : ["—"];
  const mid = Math.ceil(safe.length / 2);
  return [safe.slice(0, mid), safe.slice(mid)];
}

function EvaluationResultProgramSection({
  school,
  programDisplayName,
  strengths,
  weaknesses,
  narrativeStrategy,
  priorityActions,
  scorePercent,
  band,
  labels,
  showNarrative = true,
  metaFooter,
}: {
  school: string;
  programDisplayName: string;
  strengths: string[];
  weaknesses: string[];
  narrativeStrategy: string;
  priorityActions: string[];
  scorePercent: number | null;
  band: string;
  labels?: Partial<EvaluationSectionLabels>;
  showNarrative?: boolean;
  metaFooter?: string | null;
}) {
  const L = { ...DEFAULT_EVAL_SECTION_LABELS, ...labels };
  const narrativeTrim = narrativeStrategy.trim();
  const showNarr = showNarrative && narrativeTrim.length > 0;
  const showMetaOnly = !showNarr && Boolean(metaFooter?.trim());
  const showNarrativeBlock = showNarr || showMetaOnly;
  const [prioCol1, prioCol2] = splitPriorityActionsForBanner(
    priorityActions.length ? priorityActions : ["—"],
  );

  return (
    <section>
      {/* Top: one white card — three equal columns (strengths | gaps | admission chance) */}
      <div className="rounded-2xl border border-[#c4c6cd]/20 bg-white p-5 shadow-sm sm:p-7 lg:p-8">
        <div className="flex flex-wrap items-start justify-between gap-4 border-b border-[#c4c6cd]/15 pb-5 sm:pb-6">
          <h2 className="max-w-[min(100%,28rem)] font-serif text-2xl font-bold leading-tight text-brand-900 sm:text-3xl">
            {school}
          </h2>
          <span className="shrink-0 rounded-full border border-[#c4c6cd]/25 bg-surface-low px-4 py-2 text-center text-[10px] font-bold uppercase tracking-[0.12em] text-brand-900">
            {programCandidateBadge(programDisplayName)}
          </span>
        </div>

        <div className="mt-5 grid gap-3 sm:gap-4 lg:mt-6 lg:grid-cols-3">
          <div className="rounded-xl border border-[#c4c6cd]/15 bg-surface-low/90 p-4 sm:p-5 lg:p-6">
            <h3 className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.18em] text-brand-900">
              <span className="h-2 w-2 shrink-0 rounded-full bg-emerald-500" aria-hidden />
              {L.strengths}
            </h3>
            <ul className="mt-3 space-y-2.5 sm:mt-4 sm:space-y-3">
              {(strengths.length ? strengths : ["—"]).map((s, j) => (
                <li key={j} className="flex gap-2.5 text-sm leading-relaxed text-neutral-700 sm:gap-3">
                  <IconCheckCircle className="mt-0.5 h-5 w-5 shrink-0" />
                  <span>{s}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="rounded-xl border border-[#c4c6cd]/15 bg-surface-low/90 p-4 sm:p-5 lg:p-6">
            <h3 className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.18em] text-brand-900">
              <span className="h-2 w-2 shrink-0 rounded-full bg-amber-500" aria-hidden />
              {L.weaknesses}
            </h3>
            <ul className="mt-3 space-y-2.5 sm:mt-4 sm:space-y-3">
              {(weaknesses.length ? weaknesses : ["—"]).map((s, j) => (
                <li key={j} className="flex gap-2.5 text-sm leading-relaxed text-neutral-700 sm:gap-3">
                  <IconInfo className="mt-0.5 h-5 w-5 shrink-0" />
                  <span>{s}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="flex flex-col rounded-xl border border-[#c4c6cd]/15 bg-surface-low/90 p-4 sm:p-5 lg:p-6">
            <h3 className="text-center text-xs font-bold uppercase tracking-[0.18em] text-brand-900">
              Admission chance
            </h3>
            <div className="mt-3 flex flex-1 flex-col items-center justify-center sm:mt-4">
              <AdmissionChanceDonut percent={scorePercent} band={band} />
            </div>
          </div>
        </div>
      </div>

      {/* Narrative: on page surface, below the white card */}
      {showNarrativeBlock ? (
        <div className="mt-8">
          <h3 className="text-xs font-bold uppercase tracking-[0.18em] text-brand-900">{L.narrative}</h3>
          {showNarr ? (
            <p className="mt-3 max-w-none text-sm leading-relaxed text-neutral-700">{narrativeTrim}</p>
          ) : null}
          {metaFooter?.trim() ? (
            <p className="mt-3 text-xs leading-relaxed text-on-surface-variant">{metaFooter.trim()}</p>
          ) : null}
        </div>
      ) : null}

      {/* Full-width priority banner — two columns, gold numbers */}
      <div className="mt-8 rounded-2xl bg-brand-900 px-5 py-7 shadow-md sm:px-8 sm:py-9 lg:px-10">
        <h3 className="text-xs font-bold uppercase tracking-[0.2em] text-accent">{L.priorities}</h3>
        <div className="mt-6 grid gap-8 sm:grid-cols-2 sm:gap-10 lg:gap-12">
          <ol className="list-none space-y-4 p-0">
            {prioCol1.map((s, i) => (
              <li key={`p1-${i}`} className="flex gap-3 text-sm leading-relaxed text-white">
                <span className="w-8 shrink-0 font-mono text-xs font-bold tabular-nums text-accent">
                  {String(i + 1).padStart(2, "0")}.
                </span>
                <span className="text-white/95">{s}</span>
              </li>
            ))}
          </ol>
          <ol className="list-none space-y-4 p-0">
            {prioCol2.map((s, i) => {
              const n = prioCol1.length + i + 1;
              return (
                <li key={`p2-${i}`} className="flex gap-3 text-sm leading-relaxed text-white">
                  <span className="w-8 shrink-0 font-mono text-xs font-bold tabular-nums text-accent">
                    {String(n).padStart(2, "0")}.
                  </span>
                  <span className="text-white/95">{s}</span>
                </li>
              );
            })}
          </ol>
        </div>
      </div>
    </section>
  );
}

function AdmissionChanceDonut({
  percent,
  band,
}: {
  percent: number | null;
  band: string;
}) {
  const p = percent != null && Number.isFinite(percent) ? Math.min(100, Math.max(0, percent)) : null;
  const radius = 38;
  const c = 2 * Math.PI * radius;
  const arc = p == null ? 0 : (p / 100) * c;
  const dashArray = p == null ? `0 ${c}` : `${arc} ${c}`;

  const ariaLabel =
    p == null
      ? "Admission chance not available"
      : `Admission chance ${Math.round(p)} percent${band ? `, ${band}` : ""}`;

  return (
    <div
      className="relative mx-auto aspect-square w-full max-w-[min(100%,176px)] sm:max-w-[200px]"
      role="img"
      aria-label={ariaLabel}
    >
      <svg className="h-full w-full -rotate-90" viewBox="0 0 100 100" aria-hidden>
        <circle
          cx="50"
          cy="50"
          r={radius}
          fill="none"
          className="stroke-neutral-200"
          strokeWidth="9"
        />
        <circle
          cx="50"
          cy="50"
          r={radius}
          fill="none"
          className="stroke-brand-900"
          strokeWidth="9"
          strokeLinecap="round"
          strokeDasharray={dashArray}
        />
      </svg>
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center">
        {p != null ? (
          <>
            <span className="font-serif text-3xl font-bold tabular-nums text-brand-900 sm:text-4xl">
              {Math.round(p)}%
            </span>
            {band ? (
              <span className="mt-1 text-[10px] font-bold uppercase tracking-[0.2em] text-neutral-500">
                {band}
              </span>
            ) : null}
          </>
        ) : (
          <span className="font-serif text-2xl font-bold text-on-surface-variant">—</span>
        )}
      </div>
    </div>
  );
}

function EvaluationResultsView({
  result,
  headerVariant = "candidate",
  hideFooter = false,
}: {
  result: AdmissionEvaluationResultDto;
  headerVariant?: "candidate" | "admin";
  hideFooter?: boolean;
}) {
  return (
    <>
      <EvaluationPageHeader
        variant={headerVariant}
        title="Consolidated evaluation results"
        subtitle="Programs you selected — strengths, gaps, narrative direction, admission outlook, and priority actions."
      />

      <div className="space-y-12">
        {result.primary.map((p, i) => {
          const score = p.admission_chance_1_100;
          const band = admissionBandLabel(
            typeof score === "number" ? score : undefined,
            p.admission_band,
          );
          const scoreNum = typeof score === "number" && Number.isFinite(score) ? score : null;
          return (
            <EvaluationResultProgramSection
              key={`${p.school}-${p.program_slug}-${i}`}
              school={p.school}
              programDisplayName={p.program_display_name}
              strengths={p.strengths?.length ? p.strengths : ["—"]}
              weaknesses={p.weaknesses?.length ? p.weaknesses : ["—"]}
              narrativeStrategy={p.narrative_strategy ?? "—"}
              priorityActions={p.priority_actions?.length ? p.priority_actions : ["—"]}
              scorePercent={scoreNum}
              band={band}
            />
          );
        })}
      </div>

      {result.extra.length > 0 ? (
        <div className="mt-14 border-t border-[#c4c6cd]/20 pt-12">
          <h2 className="font-serif text-2xl text-brand-900">Additional recommendations</h2>
          <p className="mt-2 text-sm text-on-surface-variant">
            Agent-suggested programs with high secondary alignment.
          </p>
          <div className="mt-10 space-y-12">
            {result.extra.map((e, i) => {
              const score = e.match_strength_1_100;
              const scoreNum = typeof score === "number" && Number.isFinite(score) ? score : null;
              const band =
                admissionBandLabel(scoreNum ?? undefined, null) || (scoreNum != null ? "MATCH" : "ALTERNATE");
              const actLines = splitPriorityLines(e.action_item);
              const priorityActions =
                actLines.length > 0
                  ? actLines
                  : e.action_item?.trim()
                    ? [e.action_item.trim()]
                    : e.key_match?.trim()
                      ? [e.key_match.trim()]
                      : ["—"];
              const metaT = e.meta?.trim() ?? "";
              return (
                <EvaluationResultProgramSection
                  key={`${e.school}-${e.program_slug ?? i}-${i}`}
                  school={e.school}
                  programDisplayName={e.program_display_name}
                  strengths={splitStrengthBullets(e.key_match)}
                  weaknesses={e.action_item?.trim() ? [e.action_item.trim()] : ["—"]}
                  narrativeStrategy={metaT}
                  showNarrative={Boolean(metaT)}
                  priorityActions={priorityActions}
                  scorePercent={scoreNum}
                  band={band}
                  labels={{
                    strengths: "Key match",
                    weaknesses: "Action item",
                    narrative: "Additional context",
                    priorities: "Priority actions",
                  }}
                />
              );
            })}
          </div>
        </div>
      ) : null}

      {!hideFooter ? (
        <footer className="mt-16 flex flex-col gap-3 border-t border-[#c4c6cd]/20 pt-10 sm:flex-row sm:items-center sm:justify-between">
          <button
            type="button"
            disabled
            className="rounded-lg border border-[#c4c6cd]/25 bg-surface-low px-4 py-2.5 text-xs font-semibold uppercase tracking-wider text-on-surface-variant opacity-60"
          >
            Export full report
          </button>
          <button
            type="button"
            disabled
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-brand-900 px-5 py-2.5 text-xs font-semibold uppercase tracking-wider text-white opacity-50"
          >
            Proceed to positioning
            <span aria-hidden>→</span>
          </button>
        </footer>
      ) : null}
    </>
  );
}

/**
 * Read-only snapshot from `profile.attributes` (admin or embedded views).
 * Does not start jobs or poll; refresh the parent query to update.
 */
export function AdmissionEvaluationReadOnly({ attributes }: { attributes: Record<string, unknown> }) {
  const job = parseJob(attributes.admission_evaluation_job);
  const result = parseResult(attributes.admission_evaluation_result);

  if (result?.status === "complete") {
    return (
      <EvaluationResultsView result={result} headerVariant="admin" hideFooter />
    );
  }

  if (result?.status === "failed" && !job) {
    return (
      <>
        <EvaluationPageHeader
          variant="admin"
          title="School evaluation"
          subtitle="The automated evaluation did not complete successfully."
        />
        <div className="rounded-xl border border-red-200 bg-red-50/80 p-5 text-sm text-red-800">
          <p className="font-medium">Evaluation failed</p>
          <p className="mt-2 text-red-700">{result.error ?? "Unknown error"}</p>
        </div>
      </>
    );
  }

  if (job) {
    return <EvaluationProgressView job={job} headerVariant="admin" />;
  }

  return (
    <>
      <EvaluationPageHeader
        variant="admin"
        title="School evaluation"
        subtitle="Per-program research and admission outlook are produced after the candidate completes intake and the evaluation job runs."
      />
      <div className="rounded-xl border border-neutral-200 bg-white p-6 text-sm text-neutral-600 shadow-sm">
        No school evaluation is available yet for this candidate.
      </div>
    </>
  );
}

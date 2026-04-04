"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";

import { format } from "date-fns";
import { DayPicker } from "react-day-picker";

import { CandidateStitchShell } from "@/components/CandidateStitchShell";
import { SearchableMultiSelect } from "@/components/SearchableMultiSelect";
import { SearchableSelect } from "@/components/SearchableSelect";
import type { SearchableOption } from "@/components/SearchableSelect";
import { FinalQuestionsStep } from "@/components/FinalQuestionsStep";
import type {
  CandidateDto,
  CandidateIntakePayload,
  IntakeSchoolProgramSelectionPayload,
  IntakeTestScoresPayload,
} from "@/lib/api";
import type { UploadedFileDto } from "@/lib/api";
import {
  fetchIntakeTargetSchools,
  fetchCandidateProfile,
  listUploadedFiles,
  patchCandidateIntake,
  patchCandidateIntakeDraft,
  patchCandidateIntakeStep,
  uploadFileWithDocumentHint,
} from "@/lib/api";
import { COUNTRY_NAMES } from "@/data/countries";
import { gradProgramFocusLabel } from "@/data/gradProgramFocusOptions";
import { INTAKE_SCORE_CATEGORY_HINT, intakeScoreCategory } from "@/data/intakeTestScores";

import "react-day-picker/style.css";

const COUNTRY_OPTIONS = COUNTRY_NAMES.map((name) => ({ value: name, label: name }));

/** Must match `INTAKE_OTHER_SCHOOL_SENTINEL` in backend `graduate_programs_catalog.py`. */
const FALLBACK_INTAKE_OTHER_SCHOOL = "__intake_other__";
const INTAKE_OTHER_PROGRAM_SLUG = "other_graduate";
const MAX_SCHOOL_PROGRAM_PAIRS = 4;

function buildIntakeSchoolOptions(
  primary: string[],
  secondary: string[],
  otherSchoolValue: string | null,
): SearchableOption[] {
  const ov = otherSchoolValue?.trim() || null;
  const a = [...primary].filter((x) => x !== ov).sort((x, y) => x.localeCompare(y));
  const b = [...secondary].filter((x) => x !== ov).sort((x, y) => x.localeCompare(y));
  const core: SearchableOption[] = [...a, ...b].map((name) => ({ value: name, label: name }));
  if (ov && (primary.includes(ov) || secondary.includes(ov))) {
    core.push({ value: ov, label: "Other — not listed in catalog" });
  }
  return core;
}

type SchoolProgramPairUi = {
  id: string;
  school: string;
  schoolOther: string;
  programSlug: string;
  programOther: string;
};

function numOrNull(s: string): number | null {
  const t = s.trim();
  if (!t) return null;
  const n = Number(t);
  return Number.isFinite(n) ? Math.trunc(n) : null;
}

function floatOrNull(s: string): number | null {
  const t = s.trim();
  if (!t) return null;
  const n = parseFloat(t);
  return Number.isFinite(n) ? Math.round(n * 10) / 10 : null;
}

function packIntakeTestScoresPayload(s: {
  scoresNotFinalYet: boolean;
  nativeEnglishSpeaker: boolean;
  gmatTotal: string;
  greVerbal: string;
  greQuant: string;
  eaTotal: string;
  greWaived: boolean;
  toeflTotal: string;
  ieltsOverall: string;
}): IntakeTestScoresPayload {
  const eng = s.nativeEnglishSpeaker;
  if (s.scoresNotFinalYet) {
    return {
      scores_not_final_yet: true,
      gmat_total: null,
      gre_verbal: null,
      gre_quant: null,
      ea_total: null,
      gre_waived: false,
      toefl_total: eng ? null : numOrNull(s.toeflTotal),
      ielts_overall: eng ? null : floatOrNull(s.ieltsOverall),
      native_english_speaker: eng ? true : false,
    };
  }
  return {
    scores_not_final_yet: false,
    gmat_total: numOrNull(s.gmatTotal),
    gre_verbal: numOrNull(s.greVerbal),
    gre_quant: numOrNull(s.greQuant),
    ea_total: numOrNull(s.eaTotal),
    gre_waived: s.greWaived,
    toefl_total: eng ? null : numOrNull(s.toeflTotal),
    ielts_overall: eng ? null : floatOrNull(s.ieltsOverall),
    native_english_speaker: eng ? true : false,
  };
}

function buildIntakeStep1Payload(
  fullName: string,
  country: string,
  isoDob: string,
  pairs: IntakeSchoolProgramSelectionPayload[],
  intakeTestScores: IntakeTestScoresPayload,
): CandidateIntakePayload {
  return {
    full_name: fullName,
    country_of_residence: country,
    date_of_birth: isoDob,
    school_program_selections: pairs,
    intake_test_scores: intakeTestScores,
  };
}

function pickLatestByDocType(
  files: UploadedFileDto[],
  docType: "cv" | "life_story",
) {
  // Backend returns newest-first, so first match is the latest.
  const primary =
    files.find(
      (f) =>
        f.document_type === docType &&
        (f.status === "ready" || f.status === "reviewing" || f.status === "uploading"),
    ) ?? null;
  if (primary) return primary;
  // Fallback: any match for doc type, regardless of status.
  return files.find((f) => f.document_type === docType) ?? null;
}

/** PDF, Word, and plain text — aligned with backend extraction paths. */
const INTAKE_DOC_ACCEPT =
  ".pdf,.doc,.docx,.txt,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain";

const FILE_STATUS_POLL_MS = 1000;

function isIntakeDocFile(file: File): boolean {
  const n = file.name.toLowerCase();
  if (n.endsWith(".pdf") || n.endsWith(".doc") || n.endsWith(".docx") || n.endsWith(".txt")) {
    return true;
  }
  const t = file.type;
  return (
    t === "application/pdf" ||
    t === "application/msword" ||
    t === "application/vnd.openxmlformats-officedocument.wordprocessingml.document" ||
    t === "text/plain"
  );
}

function IntakeFileDropZone({
  id,
  inputName,
  disabled,
  file,
  onFileChange,
  onInvalidFile,
  acceptHint,
  hideDropZone,
}: {
  id: string;
  inputName: string;
  disabled: boolean;
  file: File | null;
  onFileChange: (file: File | null) => void;
  onInvalidFile: () => void;
  acceptHint?: ReactNode;
  /** When true, hide the dashed drag-and-drop area (e.g. after a file is chosen or while uploading). */
  hideDropZone?: boolean;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const dragDepth = useRef(0);

  const applyFile = (f: File | null) => {
    if (!f) {
      onFileChange(null);
      return;
    }
    if (!isIntakeDocFile(f)) {
      onInvalidFile();
      if (inputRef.current) inputRef.current.value = "";
      onFileChange(null);
      return;
    }
    onFileChange(f);
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const next = e.target.files?.[0] ?? null;
    applyFile(next);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragDepth.current = 0;
    setDragging(false);
    if (disabled) return;
    const next = e.dataTransfer.files?.[0] ?? null;
    applyFile(next);
  };

  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (disabled) return;
    dragDepth.current += 1;
    if (dragDepth.current === 1) setDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragDepth.current -= 1;
    if (dragDepth.current <= 0) {
      dragDepth.current = 0;
      setDragging(false);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (disabled) return;
    e.dataTransfer.dropEffect = "copy";
  };

  const zoneClass = [
    "block rounded-xl border-2 border-dashed px-4 py-8 text-center transition-colors",
    disabled ? "cursor-not-allowed opacity-50" : "cursor-pointer",
    dragging
      ? "border-brand-900 bg-brand-900/5"
      : "border-[#c4c6cd]/35 bg-surface-low/80 hover:border-[#c4c6cd]/55 hover:bg-surface-low",
    "peer-focus-visible:ring-2 peer-focus-visible:ring-brand-900/25 peer-focus-visible:ring-offset-2 peer-focus-visible:ring-offset-surface-card",
  ].join(" ");

  if (hideDropZone) {
    return (
      <div className="mt-1">
        <input
          ref={inputRef}
          id={id}
          name={inputName}
          type="file"
          accept={INTAKE_DOC_ACCEPT}
          disabled={disabled}
          className="peer sr-only disabled:opacity-50"
          onChange={handleInputChange}
        />
        {file ? (
          <div>
            <p className="text-xs text-on-surface-variant">
              Selected: <span className="font-medium text-brand-900">{file.name}</span>
            </p>
            {acceptHint ? (
              <p className="mt-1 text-xs leading-relaxed text-on-surface-variant">{acceptHint}</p>
            ) : null}
            {!disabled ? (
              <button
                type="button"
                onClick={() => inputRef.current?.click()}
                className="mt-2 text-xs font-semibold text-brand-900 underline decoration-brand-900/40 underline-offset-2 hover:decoration-brand-900"
              >
                Replace file
              </button>
            ) : null}
          </div>
        ) : null}
      </div>
    );
  }

  return (
    <div className="mt-1">
      <input
        ref={inputRef}
        id={id}
        name={inputName}
        type="file"
        accept={INTAKE_DOC_ACCEPT}
        disabled={disabled}
        className="peer sr-only disabled:opacity-50"
        onChange={handleInputChange}
      />
      <label
        htmlFor={id}
        className={zoneClass}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
      >
        <p className="text-sm text-on-surface">
          <span className="font-medium text-brand-900">Drag and drop</span> a file here, or{" "}
          <span className="font-semibold text-brand-900 underline decoration-brand-900/40 underline-offset-2">
            choose file
          </span>
          .
        </p>
        {acceptHint ? <div className="mt-2 text-xs leading-relaxed text-on-surface-variant">{acceptHint}</div> : null}
      </label>
      {file ? <p className="mt-2 text-xs text-on-surface-variant">Selected: {file.name}</p> : null}
    </div>
  );
}

function IconLock({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5} aria-hidden>
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M16.5 10.5V6.75a4.5 4.5 0 00-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z"
      />
    </svg>
  );
}

function IconArrowForward({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden>
      <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
    </svg>
  );
}

function IconPersonPin({ className }: { className?: string }) {
  return (
    <svg className={className} fill="currentColor" viewBox="0 0 24 24" aria-hidden>
      <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z" />
    </svg>
  );
}

type Props = {
  sessionToken: string;
  initialFullName: string;
  onComplete: (candidate: CandidateDto) => void;
  onSignOut?: () => void;
};

export function CandidateIntakeForm({ sessionToken, initialFullName, onComplete, onSignOut }: Props) {
  const router = useRouter();
  const [fullName, setFullName] = useState(initialFullName);
  const [country, setCountry] = useState("");
  const [dob, setDob] = useState<Date | undefined>(undefined);
  const [pairs, setPairs] = useState<SchoolProgramPairUi[]>([
    { id: "1", school: "", schoolOther: "", programSlug: "", programOther: "" },
  ]);
  const [scoresNotFinalYet, setScoresNotFinalYet] = useState(false);
  const [gmatTotal, setGmatTotal] = useState("");
  const [greVerbal, setGreVerbal] = useState("");
  const [greQuant, setGreQuant] = useState("");
  const [eaTotal, setEaTotal] = useState("");
  const [greWaived, setGreWaived] = useState(false);
  const [toeflTotal, setToeflTotal] = useState("");
  const [ieltsOverall, setIeltsOverall] = useState("");
  const [nativeEnglishSpeaker, setNativeEnglishSpeaker] = useState(false);
  const [intakeOtherSchoolToken, setIntakeOtherSchoolToken] = useState(FALLBACK_INTAKE_OTHER_SCHOOL);
  const [schoolOptions, setSchoolOptions] = useState<SearchableOption[]>([]);
  const [programsBySchool, setProgramsBySchool] = useState<
    Record<string, { slug: string; label: string }[]>
  >({});
  const [maxSchoolSelections, setMaxSchoolSelections] = useState(24);
  const [schoolsLoading, setSchoolsLoading] = useState(true);
  const [schoolsLoadError, setSchoolsLoadError] = useState<string | null>(null);
  const [cvFile, setCvFile] = useState<File | null>(null);
  const [lifeStoryFile, setLifeStoryFile] = useState<File | null>(null);
  const [cvServerFilename, setCvServerFilename] = useState<string | null>(null);
  const [cvServerStatus, setCvServerStatus] = useState<
    "uploading" | "reviewing" | "ready" | "failed" | "deleted" | null
  >(null);
  const [lifeStoryServerFilename, setLifeStoryServerFilename] = useState<string | null>(null);
  const [lifeStoryServerStatus, setLifeStoryServerStatus] = useState<
    "uploading" | "reviewing" | "ready" | "failed" | "deleted" | null
  >(null);
  const [currentStep, setCurrentStep] = useState<1 | 2 | 3 | 4>(1);
  const [maxStepCompleted, setMaxStepCompleted] = useState<0 | 1 | 2 | 3 | 4>(0);
  const [cvProcessing, setCvProcessing] = useState(false);
  const [cvUploadedFileId, setCvUploadedFileId] = useState<string | null>(null);
  const [lifeStoryProcessing, setLifeStoryProcessing] = useState(false);
  const [lifeStoryUploadedFileId, setLifeStoryUploadedFileId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dobOpen, setDobOpen] = useState(false);
  const [finalChatComplete, setFinalChatComplete] = useState(false);
  const handleFinalChatCompleteChange = useCallback((c: boolean) => {
    setFinalChatComplete(Boolean(c));
  }, []);

  const dobWrapRef = useRef<HTMLDivElement>(null);
  const today = new Date();
  const debugEnabled =
    typeof window !== "undefined" &&
    (process.env.NEXT_PUBLIC_DEBUG_INTAKE === "1" || process.env.NODE_ENV !== "production");
  const debug = (...args: unknown[]) => {
    if (debugEnabled) console.debug("[intake]", ...args);
  };

  const scoreCategory = useMemo(
    () => {
      const first = pairs[0]?.programSlug?.trim() || "";
      return first ? intakeScoreCategory(first) : null;
    },
    [pairs],
  );

  const intakeTestScoresPayload = useMemo(
    () =>
      packIntakeTestScoresPayload({
        scoresNotFinalYet,
        nativeEnglishSpeaker,
        gmatTotal,
        greVerbal,
        greQuant,
        eaTotal,
        greWaived,
        toeflTotal,
        ieltsOverall,
      }),
    [
      scoresNotFinalYet,
      nativeEnglishSpeaker,
      gmatTotal,
      greVerbal,
      greQuant,
      eaTotal,
      greWaived,
      toeflTotal,
      ieltsOverall,
    ],
  );

  const programOptionsBySchool = useMemo(() => {
    const cache: Record<string, SearchableOption[]> = {};
    const allProgramsUnion = () => {
      const seen = new Set<string>();
      const out: SearchableOption[] = [];
      for (const progs of Object.values(programsBySchool)) {
        for (const p of progs) {
          if (!p.slug || seen.has(p.slug)) continue;
          seen.add(p.slug);
          out.push({ value: p.slug, label: p.label || p.slug });
        }
      }
      out.sort((a, b) => a.label.localeCompare(b.label));
      if (!seen.has(INTAKE_OTHER_PROGRAM_SLUG)) out.push({ value: INTAKE_OTHER_PROGRAM_SLUG, label: "Other — describe your program" });
      return out;
    };
    const union = allProgramsUnion();
    for (const opt of schoolOptions) {
      const school = opt.value;
      if (school === intakeOtherSchoolToken) {
        cache[school] = union;
        continue;
      }
      const seen = new Set<string>();
      const rows: SearchableOption[] = [];
      for (const p of programsBySchool[school] ?? []) {
        if (!p.slug || seen.has(p.slug)) continue;
        seen.add(p.slug);
        rows.push({ value: p.slug, label: p.label || p.slug });
      }
      rows.sort((a, b) => a.label.localeCompare(b.label));
      if (!seen.has(INTAKE_OTHER_PROGRAM_SLUG)) rows.push({ value: INTAKE_OTHER_PROGRAM_SLUG, label: "Other — describe your program" });
      cache[school] = rows;
    }
    return cache;
  }, [programsBySchool, schoolOptions, intakeOtherSchoolToken]);

  const firstName = fullName.trim().split(/\s+/)[0] || "there";
  const initials = fullName
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase() ?? "")
    .join("");

  useEffect(() => {
    let cancelled = false;
    setSchoolsLoading(true);
    setSchoolsLoadError(null);
    void (async () => {
      try {
        const data = await fetchIntakeTargetSchools(sessionToken);
        if (cancelled) return;
        const otherTok = data.other_school_value?.trim() || FALLBACK_INTAKE_OTHER_SCHOOL;
        setIntakeOtherSchoolToken(otherTok);
        setSchoolOptions(buildIntakeSchoolOptions(data.tier_1, data.tier_2, otherTok));
        setMaxSchoolSelections(data.max_selections);
        setProgramsBySchool(data.programs_by_school);
      } catch (e) {
        if (!cancelled) setSchoolsLoadError(String(e));
      } finally {
        if (!cancelled) setSchoolsLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [sessionToken]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const c = await fetchCandidateProfile(sessionToken);
        if (cancelled) return;
        if (c.full_name) setFullName(c.full_name);
        const p = c.profile;
        if (p?.country_of_residence) setCountry(p.country_of_residence);
        if (p?.date_of_birth) setDob(new Date(p.date_of_birth));
        const attrs = p?.attributes ?? null;
        const rawPairs = (attrs as any)?.school_program_selections;
        if (Array.isArray(rawPairs) && rawPairs.length) {
          const parsed: SchoolProgramPairUi[] = rawPairs
            .filter((x) => x && typeof x === "object")
            .slice(0, MAX_SCHOOL_PROGRAM_PAIRS)
            .map((x, i) => ({
              id: String(i + 1),
              school: String((x as any).school ?? ""),
              schoolOther: String((x as any).school_other ?? ""),
              programSlug: String((x as any).program_slug ?? ""),
              programOther: String((x as any).program_other ?? ""),
            }));
          if (parsed.length) setPairs(parsed);
        }
        const rawScores = (attrs as Record<string, unknown> | null)?.intake_test_scores;
        if (rawScores && typeof rawScores === "object" && !Array.isArray(rawScores)) {
          const r = rawScores as Record<string, unknown>;
          setScoresNotFinalYet(r.scores_not_final_yet === true);
          setGmatTotal(typeof r.gmat_total === "number" ? String(r.gmat_total) : "");
          setGreVerbal(typeof r.gre_verbal === "number" ? String(r.gre_verbal) : "");
          setGreQuant(typeof r.gre_quant === "number" ? String(r.gre_quant) : "");
          setEaTotal(typeof r.ea_total === "number" ? String(r.ea_total) : "");
          setGreWaived(r.gre_waived === true);
          setToeflTotal(typeof r.toefl_total === "number" ? String(r.toefl_total) : "");
          setIeltsOverall(typeof r.ielts_overall === "number" ? String(r.ielts_overall) : "");
          setNativeEnglishSpeaker(r.native_english_speaker === true);
        }
        const step = Number((attrs as any)?.intake_step_completed ?? 0);
        const stepCompleted = (step === 1 || step === 2 || step === 3 || step === 4 ? step : 0) as
          | 0
          | 1
          | 2
          | 3
          | 4;
        debug("profile hydration", {
          intake_step_completed: stepCompleted,
          has_target_schools: Array.isArray(rawPairs) ? rawPairs.length > 0 : false,
        });
        setMaxStepCompleted((prev) => (prev < stepCompleted ? stepCompleted : prev));
        if (stepCompleted >= 1) {
          setCurrentStep((prev) => (prev < 2 ? 2 : prev));
        }
      } catch {
        // Best-effort hydration only.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [sessionToken]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const files = await listUploadedFiles(sessionToken);
        if (cancelled) return;
        const cv = pickLatestByDocType(files, "cv");
        const life = pickLatestByDocType(files, "life_story");
        debug("files hydration", {
          total: files.length,
          cv: cv ? { id: cv.id, status: cv.status, document_type: cv.document_type, name: cv.original_filename } : null,
          life: life
            ? { id: life.id, status: life.status, document_type: life.document_type, name: life.original_filename }
            : null,
          first_three: files.slice(0, 3).map((f) => ({
            id: f.id,
            status: f.status,
            document_type: f.document_type ?? null,
            name: f.original_filename,
          })),
        });
        setCvServerFilename(cv?.original_filename ?? null);
        setCvServerStatus(cv?.status ?? null);
        setLifeStoryServerFilename(life?.original_filename ?? null);
        setLifeStoryServerStatus(life?.status ?? null);

        // If the user refreshed mid-processing, resume the "locked" UI states.
        if (cv?.status === "uploading") {
          setCvUploadedFileId(cv.id);
          setCvProcessing(true);
          setCurrentStep((prev) => (prev < 2 ? 2 : prev));
        }
        if (life?.status === "uploading") {
          setLifeStoryUploadedFileId(life.id);
          setLifeStoryProcessing(true);
          setCurrentStep((prev) => (prev < 3 ? 3 : prev));
        }

        const hasCv = cv !== null && (cv.status === "ready" || cv.status === "reviewing");
        const hasLife = life !== null && (life.status === "ready" || life.status === "reviewing");
        const derivedStep = hasLife ? 3 : hasCv ? 2 : 0;
        if (derivedStep > 0) {
          setMaxStepCompleted((prev) => (prev < derivedStep ? (derivedStep as 1 | 2 | 3) : prev));
          if (derivedStep >= 1) setCurrentStep((prev) => (prev < 2 ? 2 : prev));
        }
      } catch {
        // Best-effort only.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [sessionToken]);

  useEffect(() => {
    if (!cvProcessing || !cvUploadedFileId) return;
    let cancelled = false;
    void (async () => {
      try {
        const startedAt = Date.now();
        const timeoutMs = 3 * 60 * 1000;
        while (!cancelled && Date.now() - startedAt < timeoutMs) {
          const files = await listUploadedFiles(sessionToken);
          const row = files.find((f) => f.id === cvUploadedFileId);
          if (!row) {
            await new Promise((r) => setTimeout(r, FILE_STATUS_POLL_MS));
            continue;
          }
          setCvServerFilename(row.original_filename ?? null);
          setCvServerStatus(row.status);
          if (row.status === "ready") {
            try {
              await patchCandidateIntakeStep(sessionToken, 2);
            } catch {
              // Non-blocking.
            }
            setMaxStepCompleted((prev) => (prev < 2 ? 2 : prev));
            setCurrentStep(3);
            return;
          }
          if (row.status === "failed") {
            throw new Error("CV processing failed. Please try uploading again.");
          }
          await new Promise((r) => setTimeout(r, FILE_STATUS_POLL_MS));
        }
        if (!cancelled) {
          setError("CV processing is taking longer than expected. Please wait a moment and try again.");
        }
      } catch (err) {
        if (!cancelled) setError(String(err));
      } finally {
        if (!cancelled) setCvProcessing(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [cvProcessing, cvUploadedFileId, sessionToken]);

  useEffect(() => {
    if (!lifeStoryProcessing || !lifeStoryUploadedFileId) return;
    let cancelled = false;
    void (async () => {
      try {
        const startedAt = Date.now();
        const timeoutMs = 3 * 60 * 1000;
        while (!cancelled && Date.now() - startedAt < timeoutMs) {
          const files = await listUploadedFiles(sessionToken);
          const row = files.find((f) => f.id === lifeStoryUploadedFileId);
          if (!row) {
            await new Promise((r) => setTimeout(r, FILE_STATUS_POLL_MS));
            continue;
          }
          setLifeStoryServerFilename(row.original_filename ?? null);
          setLifeStoryServerStatus(row.status);
          if (row.status === "ready") return;
          if (row.status === "failed") {
            throw new Error("Life story processing failed. Please try uploading again.");
          }
          await new Promise((r) => setTimeout(r, FILE_STATUS_POLL_MS));
        }
        if (!cancelled) {
          setError("Life story processing is taking longer than expected. Please wait a moment and try again.");
        }
      } catch (err) {
        if (!cancelled) setError(String(err));
      } finally {
        if (!cancelled) setLifeStoryProcessing(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [lifeStoryProcessing, lifeStoryUploadedFileId, sessionToken]);

  // If the user refreshed mid-processing, the file can be stuck in REVIEWING
  // (doc extracted but profile update still running). Poll until READY.
  useEffect(() => {
    if (cvProcessing) return;
    if (cvServerStatus !== "reviewing") return;
    let cancelled = false;
    void (async () => {
      const startedAt = Date.now();
      const timeoutMs = 3 * 60 * 1000;
      while (!cancelled && Date.now() - startedAt < timeoutMs) {
        try {
          const files = await listUploadedFiles(sessionToken);
          const cv = pickLatestByDocType(files, "cv");
          setCvServerFilename(cv?.original_filename ?? null);
          setCvServerStatus(cv?.status ?? null);
          if (cv?.status === "ready") return;
          if (cv?.status === "failed") {
            setError("CV processing failed. Please try uploading again.");
            return;
          }
        } catch {
          // Best-effort only.
        }
        await new Promise((r) => setTimeout(r, FILE_STATUS_POLL_MS));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [cvProcessing, cvServerStatus, sessionToken]);

  useEffect(() => {
    if (lifeStoryProcessing) return;
    if (lifeStoryServerStatus !== "reviewing") return;
    let cancelled = false;
    void (async () => {
      const startedAt = Date.now();
      const timeoutMs = 3 * 60 * 1000;
      while (!cancelled && Date.now() - startedAt < timeoutMs) {
        try {
          const files = await listUploadedFiles(sessionToken);
          const life = pickLatestByDocType(files, "life_story");
          setLifeStoryServerFilename(life?.original_filename ?? null);
          setLifeStoryServerStatus(life?.status ?? null);
          if (life?.status === "ready") return;
          if (life?.status === "failed") {
            setError("Life story processing failed. Please try uploading again.");
            return;
          }
        } catch {
          // Best-effort only.
        }
        await new Promise((r) => setTimeout(r, FILE_STATUS_POLL_MS));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [lifeStoryProcessing, lifeStoryServerStatus, sessionToken]);

  useEffect(() => {
    if (!dobOpen) return;
    const onDocMouseDown = (e: MouseEvent) => {
      if (!dobWrapRef.current?.contains(e.target as Node)) setDobOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setDobOpen(false);
    };
    document.addEventListener("mousedown", onDocMouseDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocMouseDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [dobOpen]);

  const validateStep1 = () => {
    if (!country.trim()) {
      setError("Please select your country of residence.");
      return false;
    }
    if (!pairs.length || !pairs[0]?.school.trim()) {
      setError("Please select at least one school.");
      return false;
    }
    for (let idx = 0; idx < pairs.length; idx += 1) {
      const p = pairs[idx]!;
      const n = idx + 1;
      if (!p.school.trim()) {
        setError(`Please select a school for selection ${n}.`);
        return false;
      }
      if (p.school === intakeOtherSchoolToken && !p.schoolOther.trim()) {
        setError(`Please describe your school for selection ${n}.`);
        return false;
      }
      if (!p.programSlug.trim()) {
        setError(`Please select a program for selection ${n}.`);
        return false;
      }
      if (p.programSlug === INTAKE_OTHER_PROGRAM_SLUG && !p.programOther.trim()) {
        setError(`Please describe your program for selection ${n}.`);
        return false;
      }
    }
    if (!dob) {
      setError("Please select your date of birth.");
      return false;
    }
    // Scores are optional.
    return true;
  };

  const validateStep2 = () => {
    // Only consider the CV step done once the backend has fully processed it
    // (status=ready implies profile update task finished).
    if (!cvFile && cvServerStatus !== "ready" && cvServerStatus !== "uploading" && cvServerStatus !== "reviewing") {
      setError("Please upload your CV or résumé.");
      return false;
    }
    if (!cvFile && cvServerStatus === "reviewing") {
      setError("Your CV is still being processed. Please wait until it’s ready.");
      return false;
    }
    return true;
  };

  const validateStep3 = () => {
    if (
      !lifeStoryFile &&
      lifeStoryServerStatus !== "ready" &&
      lifeStoryServerStatus !== "uploading"
    ) {
      setError("Please upload your life story document.");
      return false;
    }
    if (!lifeStoryFile && lifeStoryServerStatus === "reviewing") {
      setError("Your life story is still being processed. Please wait until it’s ready.");
      return false;
    }
    return true;
  };

  const handleStep1Continue = (e: React.FormEvent) => {
    e.preventDefault();
    void (async () => {
      setError(null);
      if (!validateStep1()) return;
      const isoDob = format(dob!, "yyyy-MM-dd");
      setBusy(true);
      try {
        const selections: IntakeSchoolProgramSelectionPayload[] = pairs
          .map((p) => ({
            school: p.school.trim(),
            school_other: p.school === intakeOtherSchoolToken ? p.schoolOther.trim() || null : null,
            program_slug: p.programSlug.trim(),
            program_other: p.programSlug === INTAKE_OTHER_PROGRAM_SLUG ? p.programOther.trim() || null : null,
          }))
          .filter((p) => p.school.length > 0 && p.program_slug.length > 0);
        await patchCandidateIntakeDraft(
          sessionToken,
          buildIntakeStep1Payload(
            fullName,
            country,
            isoDob,
            selections,
            intakeTestScoresPayload,
          ),
        );
        setMaxStepCompleted((prev) => (prev < 1 ? 1 : prev));
        setCurrentStep(2);
      } catch (err) {
        setError(String(err));
      } finally {
        setBusy(false);
      }
    })();
  };

  const handleStep2Continue = () => {
    void (async () => {
      setError(null);
      if (!validateStep2()) return;

      if (!cvFile && cvServerStatus === "ready") {
        try {
          await patchCandidateIntakeStep(sessionToken, 2);
        } catch {
          // Non-blocking.
        }
        setMaxStepCompleted((prev) => (prev < 2 ? 2 : prev));
        setCurrentStep(3);
        return;
      }

      setCvProcessing(true);
      setCvUploadedFileId(null);
      try {
        const uploaded = await uploadFileWithDocumentHint(sessionToken, cvFile!, "cv");
        const created = uploaded[0];
        if (!created?.id) throw new Error("CV upload did not return a file id");
        setCvUploadedFileId(created.id);

        const startedAt = Date.now();
        const timeoutMs = 3 * 60 * 1000;

        while (Date.now() - startedAt < timeoutMs) {
          const files = await listUploadedFiles(sessionToken);
          const row = files.find((f) => f.id === created.id);
          if (!row) {
            await new Promise((r) => setTimeout(r, FILE_STATUS_POLL_MS));
            continue;
          }
          if (row.status === "ready") {
            try {
              await patchCandidateIntakeStep(sessionToken, 2);
            } catch {
              // Non-blocking — still allow the candidate to continue.
            }
            setCvServerFilename(row.original_filename ?? null);
            setCvServerStatus(row.status);
            setMaxStepCompleted((prev) => (prev < 2 ? 2 : prev));
            setCurrentStep(3);
            return;
          }
          if (row.status === "failed") {
            throw new Error("CV processing failed. Please try uploading again.");
          }
          await new Promise((r) => setTimeout(r, FILE_STATUS_POLL_MS));
        }

        throw new Error("CV processing is taking longer than expected. Please wait a moment and try again.");
      } catch (err) {
        setError(String(err));
      } finally {
        setCvProcessing(false);
      }
    })();
  };

  const submitFinal = async () => {
    setError(null);
    if (!validateStep1()) return;
    if (!validateStep2()) return;
    if (!validateStep3()) return;

    const isoDob = format(dob!, "yyyy-MM-dd");

    try {
      const selections: IntakeSchoolProgramSelectionPayload[] = pairs
        .map((p) => ({
          school: p.school.trim(),
          school_other: p.school === intakeOtherSchoolToken ? p.schoolOther.trim() || null : null,
          program_slug: p.programSlug.trim(),
          program_other: p.programSlug === INTAKE_OTHER_PROGRAM_SLUG ? p.programOther.trim() || null : null,
        }))
        .filter((p) => p.school.length > 0 && p.program_slug.length > 0);
      if (!lifeStoryFile && lifeStoryServerStatus === "ready") {
        try {
          await patchCandidateIntakeStep(sessionToken, 3);
        } catch {
          // Non-blocking.
        }
        setBusy(true);
        try {
          await patchCandidateIntake(
            sessionToken,
            buildIntakeStep1Payload(
              fullName,
              country,
              isoDob,
              selections,
              intakeTestScoresPayload,
            ),
          );
          setMaxStepCompleted(3);
          setCurrentStep(4);
        } finally {
          setBusy(false);
        }
        return;
      }

      setLifeStoryProcessing(true);
      setLifeStoryUploadedFileId(null);

      const uploaded = await uploadFileWithDocumentHint(sessionToken, lifeStoryFile!, "life_story");
      const created = uploaded[0];
      if (!created?.id) throw new Error("Life story upload did not return a file id");
      setLifeStoryUploadedFileId(created.id);

      const startedAt = Date.now();
      const timeoutMs = 3 * 60 * 1000;

      let finalRow: UploadedFileDto | null = null;
      while (Date.now() - startedAt < timeoutMs) {
        const files = await listUploadedFiles(sessionToken);
        const row = files.find((f) => f.id === created.id);
        if (!row) {
          await new Promise((r) => setTimeout(r, FILE_STATUS_POLL_MS));
          continue;
        }
        if (row.status === "ready") {
          finalRow = row;
          break;
        }
        if (row.status === "failed") {
          throw new Error("Life story processing failed. Please try uploading again.");
        }
        await new Promise((r) => setTimeout(r, FILE_STATUS_POLL_MS));
      }

      if (Date.now() - startedAt >= timeoutMs) {
        throw new Error("Life story processing is taking longer than expected. Please wait a moment and try again.");
      }

      try {
        await patchCandidateIntakeStep(sessionToken, 3);
      } catch {
        // Non-blocking — final completion persists anyway.
      }

      setLifeStoryServerFilename(finalRow?.original_filename ?? lifeStoryFile?.name ?? null);
      setLifeStoryServerStatus(finalRow?.status ?? "ready");
      setBusy(true);
      try {
        // Keep CV upload best-effort; backend can de-dupe if it already exists.
        if (cvFile) await uploadFileWithDocumentHint(sessionToken, cvFile, "cv");
        await patchCandidateIntake(
          sessionToken,
          buildIntakeStep1Payload(
            fullName,
            country,
            isoDob,
            selections,
            intakeTestScoresPayload,
          ),
        );
        setMaxStepCompleted(3);
        setCurrentStep(4);
      } finally {
        setBusy(false);
      }
    } catch (err) {
      setError(String(err));
    } finally {
      setLifeStoryProcessing(false);
    }
  };

  const derivedStepFromFiles =
    lifeStoryServerStatus === "ready"
      ? 3
      : cvServerStatus === "ready"
        ? 2
        : 0;
  const effectiveMaxStepCompleted = (Math.max(maxStepCompleted, derivedStepFromFiles) as 0 | 1 | 2 | 3 | 4);

  useEffect(() => {
    const desired: 1 | 2 | 3 | 4 =
      effectiveMaxStepCompleted >= 3 ? 4 : effectiveMaxStepCompleted >= 2 ? 3 : effectiveMaxStepCompleted >= 1 ? 2 : 1;
    setCurrentStep((prev) => (prev < desired ? desired : prev));
  }, [effectiveMaxStepCompleted]);

  const canAccessStep = (step: 1 | 2 | 3 | 4) => step <= effectiveMaxStepCompleted + 1;
  const canEditStep = (step: 1 | 2 | 3 | 4) => step <= effectiveMaxStepCompleted;
  const uiLocked = busy || cvProcessing || lifeStoryProcessing;

  const fieldShell =
    "mt-1 w-full rounded-lg border-0 bg-surface-highest px-3 py-2.5 text-sm text-on-surface shadow-none ring-1 ring-[#c4c6cd]/15 transition-[box-shadow] placeholder:text-on-surface/40 focus:outline-none focus:ring-2 focus:ring-accent disabled:opacity-50";
  const labelClass = "block text-xs font-medium text-on-surface-variant";

  return (
    <CandidateStitchShell
      userInitials={initials || "?"}
      activeNav="dashboard"
      onNavDashboard={() => router.push("/")}
      onNavDocuments={() => router.push("/documents")}
      activePhaseIndex={0}
      phaseProgressCurrent={1}
      phaseProgressTotal={6}
      onSignOut={onSignOut}
      mobileMainTab="intake"
    >
      <div className="mx-auto max-w-5xl px-6 py-10 sm:px-8 sm:py-12">
          <header className="mb-10 sm:mb-12">
            <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
              <span className="rounded bg-surface-container px-2 py-0.5 font-bold tracking-wide text-on-surface-variant">
                PHASE 01
              </span>
              <span className="text-surface-dim">/</span>
              <span className="font-bold uppercase tracking-widest text-brand-500">Intake</span>
            </div>
            <h1 className="mb-2 font-serif text-3xl text-brand-900 sm:text-4xl">Detailed Intake Process</h1>
            <p className="text-on-surface-variant">
              Phase 1: Gathering the essential components for your Ivy League strategy.
            </p>
          </header>

          <div className="relative space-y-8">
            <div className="absolute bottom-8 left-[1.375rem] top-8 hidden w-px bg-surface-container sm:block" aria-hidden />

            {/* Step 1 — active hero + form */}
            <section className="relative">
              <div className="flex flex-col items-stretch gap-6 sm:flex-row sm:items-start sm:gap-8">
                <div className="hidden h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-accent font-bold text-brand-900 shadow-md sm:flex">
                  1
                </div>
                <div className="relative flex-1 rounded-2xl border border-brand-900/10 bg-brand-800 p-6 shadow-[0px_20px_40px_rgba(4,22,39,0.12)] sm:p-10">
                  <div className="pointer-events-none absolute inset-0 overflow-hidden rounded-2xl" aria-hidden>
                    
                  </div>
                  <div className="relative z-10">
                    <div className="mb-6 flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
                      <div>
                        <span className="mb-1 block text-xs font-bold uppercase tracking-[0.2em] text-accent">
                          Current Intake Task
                        </span>
                        <h2 className="font-serif text-2xl text-white sm:text-3xl">Personal Information &amp; Goals</h2>
                      </div>
                    </div>
                    <p className="mb-8 max-w-2xl text-lg leading-relaxed text-brand-300">
                      Welcome back, {firstName}. To begin your journey, we need to establish your academic narrative and
                      target goals. This is the foundation of your curated strategy.
                    </p>

                    {currentStep === 1 ? (
                      <form id="candidate-intake-form" onSubmit={handleStep1Continue} className="space-y-5">
                        <div className="rounded-xl border border-white/10 bg-surface-card p-5 sm:p-6">
                          <div>
                            <label htmlFor="intake-full-name" className={labelClass}>
                              Full name
                            </label>
                            <input
                              id="intake-full-name"
                              name="full_name"
                              type="text"
                              autoComplete="name"
                              required
                              value={fullName}
                              onChange={(e) => setFullName(e.target.value)}
                              className={fieldShell}
                              disabled={busy}
                            />
                          </div>

                          <div className="mt-5">
                            <SearchableSelect
                              id="intake-country"
                              label="Country of residence"
                              options={COUNTRY_OPTIONS}
                              value={country}
                              onChange={(v) => {
                                setCountry(v);
                                setError((prev) => (prev === "Please select your country of residence." ? null : prev));
                              }}
                              disabled={busy}
                              placeholder="Search countries…"
                              emptyMessage="No country matches"
                              maxVisible={200}
                            />
                          </div>

                          <div ref={dobWrapRef} className="relative mt-5">
                            <span className={labelClass}>Date of birth</span>
                            <button
                              type="button"
                              id="intake-dob-trigger"
                              disabled={busy}
                              aria-expanded={dobOpen}
                              aria-haspopup="dialog"
                              aria-label="Open date of birth calendar"
                              onClick={() => setDobOpen((o) => !o)}
                              className={`${fieldShell} mt-1 flex w-full items-center gap-2 text-left hover:bg-surface-high`}
                            >
                              <span className={dob ? "text-on-surface" : "text-on-surface/40"}>
                                {dob ? format(dob, "MMMM d, yyyy") : "Select date of birth"}
                              </span>
                              <svg
                                className="ml-auto h-4 w-4 shrink-0 text-on-surface-variant"
                                fill="none"
                                viewBox="0 0 24 24"
                                stroke="currentColor"
                                strokeWidth={1.5}
                                aria-hidden
                              >
                                <path
                                  strokeLinecap="round"
                                  strokeLinejoin="round"
                                  d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5a2.25 2.25 0 002.25-2.25m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5a2.25 2.25 0 012.25 2.25v7.5"
                                />
                              </svg>
                            </button>
                            {dobOpen ? (
                              <div
                                role="dialog"
                                aria-label="Choose date of birth"
                                className="absolute left-0 right-0 z-[60] mt-2 flex justify-center sm:left-auto sm:right-0 sm:justify-end"
                              >
                                <div className="intake-dob-popover w-full max-w-[238px] rounded-xl border border-[#c4c6cd]/20 bg-surface-card p-2 shadow-xl ring-1 ring-black/5">
                                  <DayPicker
                                    mode="single"
                                    selected={dob}
                                    onSelect={(d) => {
                                      setDob(d);
                                      setDobOpen(false);
                                      setError((prev) => (prev === "Please select your date of birth." ? null : prev));
                                    }}
                                    captionLayout="dropdown"
                                    startMonth={new Date(1900, 0)}
                                    endMonth={today}
                                    defaultMonth={dob ?? new Date(2000, 0)}
                                    disabled={{ after: today }}
                                    navLayout="after"
                                  />
                                </div>
                              </div>
                            ) : null}
                          </div>

                          <div className="mt-5 space-y-5">
                            {pairs.map((pair, idx) => {
                              const n = idx + 1;
                              const progOptions = pair.school ? programOptionsBySchool[pair.school] ?? [] : [];
                              return (
                                <div key={pair.id} className="rounded-xl border border-white/10 bg-white/5 p-4">
                                  <div className="flex items-center justify-between gap-3">
                                    <p className="text-xs font-bold uppercase tracking-[0.2em] text-on-surface-variant">
                                      School {n}
                                    </p>
                                    {pairs.length > 1 ? (
                                      <button
                                        type="button"
                                        disabled={busy}
                                        onClick={() => {
                                          setPairs((prev) => prev.filter((p) => p.id !== pair.id));
                                        }}
                                        className="rounded-lg border border-[#c4c6cd]/30 bg-surface-highest px-3 py-1.5 text-xs font-semibold text-on-surface hover:bg-surface-high disabled:opacity-50"
                                      >
                                        Remove
                                      </button>
                                    ) : null}
                                  </div>
                                  <div className="mt-3">
                                    <SearchableSelect
                                      id={`intake-school-${pair.id}`}
                                      label="School"
                                      options={schoolOptions}
                                      value={pair.school}
                                      onChange={(v) => {
                                        setPairs((prev) =>
                                          prev.map((p) =>
                                            p.id === pair.id
                                              ? { ...p, school: v, schoolOther: "", programSlug: "", programOther: "" }
                                              : p,
                                          ),
                                        );
                                      }}
                                      disabled={busy || schoolsLoading || Boolean(schoolsLoadError)}
                                      placeholder={schoolsLoading ? "Loading schools…" : "Search schools…"}
                                      emptyMessage="No school matches"
                                      maxVisible={200}
                                    />
                                    {pair.school === intakeOtherSchoolToken ? (
                                      <div className="mt-3">
                                        <label htmlFor={`intake-school-other-${pair.id}`} className={labelClass}>
                                          School name not in the list
                                        </label>
                                        <textarea
                                          id={`intake-school-other-${pair.id}`}
                                          value={pair.schoolOther}
                                          onChange={(e) =>
                                            setPairs((prev) =>
                                              prev.map((p) => (p.id === pair.id ? { ...p, schoolOther: e.target.value } : p)),
                                            )
                                          }
                                          disabled={busy}
                                          rows={2}
                                          placeholder="e.g. London Business School"
                                          className={`${fieldShell} min-h-[4rem] resize-y`}
                                        />
                                      </div>
                                    ) : null}
                                  </div>

                                  {pair.school.trim() ? (
                                    <div className="mt-4">
                                      <SearchableSelect
                                        id={`intake-program-${pair.id}`}
                                        label="Program"
                                        options={progOptions}
                                        value={pair.programSlug}
                                        onChange={(v) => {
                                          setPairs((prev) =>
                                            prev.map((p) =>
                                              p.id === pair.id
                                                ? { ...p, programSlug: v, programOther: v === INTAKE_OTHER_PROGRAM_SLUG ? p.programOther : "" }
                                                : p,
                                            ),
                                          );
                                        }}
                                        disabled={busy || schoolsLoading || Boolean(schoolsLoadError) || progOptions.length === 0}
                                        placeholder="Search programs…"
                                        emptyMessage="No program matches"
                                        maxVisible={200}
                                      />
                                      {pair.programSlug === INTAKE_OTHER_PROGRAM_SLUG ? (
                                        <div className="mt-3">
                                          <label htmlFor={`intake-program-other-${pair.id}`} className={labelClass}>
                                            Describe your program
                                          </label>
                                          <textarea
                                            id={`intake-program-other-${pair.id}`}
                                            value={pair.programOther}
                                            onChange={(e) =>
                                              setPairs((prev) =>
                                                prev.map((p) =>
                                                  p.id === pair.id ? { ...p, programOther: e.target.value } : p,
                                                ),
                                              )
                                            }
                                            disabled={busy}
                                            rows={2}
                                            placeholder="e.g. MSc in Human–Computer Interaction"
                                            className={`${fieldShell} min-h-[4rem] resize-y`}
                                          />
                                        </div>
                                      ) : null}
                                    </div>
                                  ) : null}
                                </div>
                              );
                            })}

                            {pairs.length < MAX_SCHOOL_PROGRAM_PAIRS ? (
                              <button
                                type="button"
                                disabled={busy || schoolsLoading || Boolean(schoolsLoadError)}
                                aria-label="Add another target school and program"
                                onClick={() => {
                                  setPairs((prev) => [
                                    ...prev,
                                    {
                                      id: String(Date.now()),
                                      school: "",
                                      schoolOther: "",
                                      programSlug: "",
                                      programOther: "",
                                    },
                                  ]);
                                }}
                                className="flex w-full items-center justify-center gap-2 rounded-lg border-2 border-dashed border-accent/50 bg-accent/5 px-4 py-3 text-sm font-semibold text-brand-900 shadow-sm hover:bg-accent/10 disabled:opacity-50"
                              >
                                <span className="text-xl font-bold leading-none text-accent" aria-hidden>
                                  +
                                </span>
                                Add another school (up to {MAX_SCHOOL_PROGRAM_PAIRS})
                              </button>
                            ) : null}
                          </div>

                          {schoolsLoadError ? (
                            <p className="mt-5 text-sm text-red-600" role="alert">
                              Could not load school list: {schoolsLoadError}
                            </p>
                          ) : null}

                          {pairs[0]?.programSlug?.trim() ? (
                            <div className="mt-8 border-t border-white/10 pt-6">
                              <h3 className="font-serif text-lg text-brand-900">Standardized tests (optional)</h3>
                              {scoreCategory ? (
                                <p className="mt-1 text-sm text-on-surface-variant">
                                  {INTAKE_SCORE_CATEGORY_HINT[scoreCategory]}
                                </p>
                              ) : null}
                              <label className="mt-4 flex cursor-pointer items-start gap-3 text-sm text-on-surface">
                                <input
                                  type="checkbox"
                                  className="mt-0.5 h-4 w-4 shrink-0 rounded border-[#c4c6cd]/40"
                                  checked={scoresNotFinalYet}
                                  onChange={(e) => setScoresNotFinalYet(e.target.checked)}
                                  disabled={busy}
                                />
                                <span>I don&apos;t have the final score yet (GMAT, GRE, EA, etc.)</span>
                              </label>

                              {!scoresNotFinalYet && scoreCategory === "mba" ? (
                                <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
                                  <div>
                                    <label htmlFor="intake-gmat" className={labelClass}>
                                      GMAT (total)
                                    </label>
                                    <input
                                      id="intake-gmat"
                                      type="text"
                                      inputMode="numeric"
                                      value={gmatTotal}
                                      onChange={(e) => setGmatTotal(e.target.value)}
                                      disabled={busy}
                                      className={fieldShell}
                                      placeholder="e.g. 685"
                                    />
                                  </div>
                                  <div>
                                    <label htmlFor="intake-gre-v-mba" className={labelClass}>
                                      GRE Verbal
                                    </label>
                                    <input
                                      id="intake-gre-v-mba"
                                      type="text"
                                      inputMode="numeric"
                                      value={greVerbal}
                                      onChange={(e) => setGreVerbal(e.target.value)}
                                      disabled={busy}
                                      className={fieldShell}
                                      placeholder="130–170"
                                    />
                                  </div>
                                  <div>
                                    <label htmlFor="intake-gre-q-mba" className={labelClass}>
                                      GRE Quantitative
                                    </label>
                                    <input
                                      id="intake-gre-q-mba"
                                      type="text"
                                      inputMode="numeric"
                                      value={greQuant}
                                      onChange={(e) => setGreQuant(e.target.value)}
                                      disabled={busy}
                                      className={fieldShell}
                                      placeholder="130–170"
                                    />
                                  </div>
                                  <div>
                                    <label htmlFor="intake-ea" className={labelClass}>
                                      Executive Assessment (EA)
                                    </label>
                                    <input
                                      id="intake-ea"
                                      type="text"
                                      inputMode="numeric"
                                      value={eaTotal}
                                      onChange={(e) => setEaTotal(e.target.value)}
                                      disabled={busy}
                                      className={fieldShell}
                                      placeholder="100–200"
                                    />
                                  </div>
                                </div>
                              ) : null}

                              {!scoresNotFinalYet &&
                              (scoreCategory === "masters" || scoreCategory === "other") ? (
                                <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
                                  <div>
                                    <label htmlFor="intake-gre-v-ms" className={labelClass}>
                                      GRE Verbal
                                    </label>
                                    <input
                                      id="intake-gre-v-ms"
                                      type="text"
                                      inputMode="numeric"
                                      value={greVerbal}
                                      onChange={(e) => setGreVerbal(e.target.value)}
                                      disabled={busy}
                                      className={fieldShell}
                                      placeholder="130–170"
                                    />
                                  </div>
                                  <div>
                                    <label htmlFor="intake-gre-q-ms" className={labelClass}>
                                      GRE Quantitative
                                    </label>
                                    <input
                                      id="intake-gre-q-ms"
                                      type="text"
                                      inputMode="numeric"
                                      value={greQuant}
                                      onChange={(e) => setGreQuant(e.target.value)}
                                      disabled={busy}
                                      className={fieldShell}
                                      placeholder="130–170"
                                    />
                                  </div>
                                  <div className="sm:col-span-2">
                                    <label htmlFor="intake-gmat-ms" className={labelClass}>
                                      GMAT (optional)
                                    </label>
                                    <input
                                      id="intake-gmat-ms"
                                      type="text"
                                      inputMode="numeric"
                                      value={gmatTotal}
                                      onChange={(e) => setGmatTotal(e.target.value)}
                                      disabled={busy}
                                      className={fieldShell}
                                      placeholder="Some programs accept GMAT"
                                    />
                                  </div>
                                </div>
                              ) : null}

                              {!scoresNotFinalYet && scoreCategory === "phd" ? (
                                <div className="mt-4 space-y-4">
                                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                                    <div>
                                      <label htmlFor="intake-gre-v-phd" className={labelClass}>
                                        GRE Verbal
                                      </label>
                                      <input
                                        id="intake-gre-v-phd"
                                        type="text"
                                        inputMode="numeric"
                                        value={greVerbal}
                                        onChange={(e) => setGreVerbal(e.target.value)}
                                        disabled={busy || greWaived}
                                        className={fieldShell}
                                        placeholder="130–170"
                                      />
                                    </div>
                                    <div>
                                      <label htmlFor="intake-gre-q-phd" className={labelClass}>
                                        GRE Quantitative
                                      </label>
                                      <input
                                        id="intake-gre-q-phd"
                                        type="text"
                                        inputMode="numeric"
                                        value={greQuant}
                                        onChange={(e) => setGreQuant(e.target.value)}
                                        disabled={busy || greWaived}
                                        className={fieldShell}
                                        placeholder="130–170"
                                      />
                                    </div>
                                  </div>
                                  <label className="flex cursor-pointer items-start gap-3 text-sm text-on-surface">
                                    <input
                                      type="checkbox"
                                      className="mt-0.5 h-4 w-4 shrink-0 rounded border-[#c4c6cd]/40"
                                      checked={greWaived}
                                      onChange={(e) => {
                                        setGreWaived(e.target.checked);
                                        if (e.target.checked) {
                                          setGreVerbal("");
                                          setGreQuant("");
                                        }
                                      }}
                                      disabled={busy}
                                    />
                                    <span>GRE waived or not required for my program</span>
                                  </label>
                                </div>
                              ) : null}

                              <div className="mt-6 border-t border-white/10 pt-4">
                                <p className="text-sm font-medium text-brand-900">English proficiency</p>
                                <p className="mt-1 text-xs text-on-surface-variant">
                                  TOEFL or IELTS if English is not your first language.
                                </p>
                                <label className="mt-3 flex cursor-pointer items-start gap-3 text-sm text-on-surface">
                                  <input
                                    type="checkbox"
                                    className="mt-0.5 h-4 w-4 shrink-0 rounded border-[#c4c6cd]/40"
                                    checked={nativeEnglishSpeaker}
                                    onChange={(e) => {
                                      setNativeEnglishSpeaker(e.target.checked);
                                      if (e.target.checked) {
                                        setToeflTotal("");
                                        setIeltsOverall("");
                                      }
                                    }}
                                    disabled={busy}
                                  />
                                  <span>I am a native English speaker</span>
                                </label>
                                {!nativeEnglishSpeaker ? (
                                  <div className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-2">
                                    <div>
                                      <label htmlFor="intake-toefl" className={labelClass}>
                                        TOEFL iBT (total)
                                      </label>
                                      <input
                                        id="intake-toefl"
                                        type="text"
                                        inputMode="numeric"
                                        value={toeflTotal}
                                        onChange={(e) => setToeflTotal(e.target.value)}
                                        disabled={busy}
                                        className={fieldShell}
                                        placeholder="0–120"
                                      />
                                    </div>
                                    <div>
                                      <label htmlFor="intake-ielts" className={labelClass}>
                                        IELTS (overall band)
                                      </label>
                                      <input
                                        id="intake-ielts"
                                        type="text"
                                        inputMode="decimal"
                                        value={ieltsOverall}
                                        onChange={(e) => setIeltsOverall(e.target.value)}
                                        disabled={busy}
                                        className={fieldShell}
                                        placeholder="e.g. 7.5"
                                      />
                                    </div>
                                  </div>
                                ) : null}
                              </div>
                            </div>
                          ) : null}
                        </div>

                        {error ? (
                          <p className="text-sm text-amber-200" role="alert">
                            {error}
                          </p>
                        ) : null}
                        <div className="flex flex-col items-stretch gap-4 sm:flex-row sm:items-center sm:gap-6">
                          <button
                            type="submit"
                            disabled={
                              busy ||
                              schoolsLoading ||
                              Boolean(schoolsLoadError) ||
                              schoolOptions.length === 0 ||
                              pairs.length === 0 ||
                              !pairs[0]?.school.trim() ||
                              !pairs[0]?.programSlug.trim()
                            }
                            className="group/btn flex w-full items-center justify-center gap-3 rounded-lg bg-accent px-8 py-4 text-sm font-bold text-brand-900 shadow-xl shadow-accent/20 transition-transform hover:scale-[1.02] disabled:opacity-50 sm:w-auto"
                          >
                            Continue
                            <IconArrowForward className="h-5 w-5 transition-transform group-hover/btn:translate-x-1" />
                          </button>
                        </div>
                      </form>
                    ) : (
                      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-white/10 bg-white/5 px-5 py-4">
                        <p className="text-sm text-brand-200/90">
                          Completed: {country || "—"},{" "}
                          {pairs[0]?.programSlug === INTAKE_OTHER_PROGRAM_SLUG
                            ? pairs[0]?.programOther.trim() || "Other program"
                            : gradProgramFocusLabel(pairs[0]?.programSlug) || pairs[0]?.programSlug || "—"}
                          , {pairs.length} school
                          {pairs.length === 1 ? "" : "s"}
                        </p>
                          {canEditStep(1) ? (
                          <button
                            type="button"
                            onClick={() => {
                              setError(null);
                              setCurrentStep(1);
                            }}
                              disabled={uiLocked}
                            className="rounded-lg border border-white/15 bg-white/5 px-4 py-2 text-xs font-semibold text-white hover:bg-white/10"
                          >
                            Edit
                          </button>
                        ) : null}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </section>

            {/* Step 2 */}
            <section className="relative">
              <div className="flex flex-col items-stretch gap-6 sm:flex-row sm:items-start sm:gap-8">
                <div className="hidden h-11 w-11 shrink-0 items-center justify-center rounded-lg border border-[#c4c6cd]/20 bg-surface-card font-bold text-on-surface-variant shadow-sm sm:flex">
                  2
                </div>
                <div className="flex-1 rounded-2xl border border-[#c4c6cd]/20 bg-surface-card p-6 shadow-sm transition-shadow hover:shadow-md sm:p-8">
                  <div className="mb-4 flex justify-between gap-4">
                    <div>
                      <span className="mb-1 block text-[10px] font-medium uppercase tracking-widest text-on-surface-variant">
                        Intake Task 02
                      </span>
                      <h3 id="intake-documents" className="font-serif text-2xl text-brand-900">
                        CV &amp; Documents
                      </h3>
                    </div>
                    {!canAccessStep(2) ? <IconLock className="h-6 w-6 shrink-0 text-surface-dim" /> : null}
                  </div>
                  {currentStep === 2 ? (
                    <>
                      <p className="mb-6 text-on-surface-variant">
                        Upload your existing transcripts and professional history. The Curator AI will analyze your data
                        against Ivy League benchmarks.
                      </p>
                      {!cvFile && cvServerFilename && (cvServerStatus === "ready" || cvServerStatus === "reviewing") ? (
                        <div className="mb-5 rounded-xl border border-[#c4c6cd]/20 bg-surface-low px-4 py-3">
                          <p className="text-sm font-semibold text-brand-900">CV already uploaded</p>
                          <p className="mt-1 text-xs text-on-surface-variant">
                            We found an existing CV on your account: <span className="font-medium">{cvServerFilename}</span>.
                          </p>
                        </div>
                      ) : null}
                      {cvProcessing ? (
                        <div className="mb-5 rounded-xl border border-[#c4c6cd]/20 bg-surface-low px-4 py-3">
                          <p className="text-sm font-semibold text-brand-900">Processing your CV…</p>
                          <p className="mt-1 text-xs text-on-surface-variant">
                            Your file is being processed and your profile is being updated. This can take a couple of
                            minutes — please keep this page open.
                          </p>
                          {cvUploadedFileId ? (
                            <p className="mt-2 text-[11px] text-on-surface-variant">Upload ID: {cvUploadedFileId}</p>
                          ) : null}
                        </div>
                      ) : null}
                      <div>
                        <label htmlFor="intake-cv" className={labelClass}>
                          CV or résumé
                        </label>
                        <IntakeFileDropZone
                          id="intake-cv"
                          inputName="cv"
                          disabled={uiLocked || !canAccessStep(2)}
                          file={cvFile}
                          hideDropZone={Boolean(cvFile) || cvProcessing}
                          onFileChange={(f) => {
                            setError(null);
                            setCvFile(f);
                          }}
                          onInvalidFile={() =>
                            setError("Please upload a PDF, Word, or plain text file.")
                          }
                        />
                      </div>
                      {error ? (
                        <p className="mt-4 text-sm text-red-600" role="alert">
                          {error}
                        </p>
                      ) : null}
                      <div className="mt-6 flex flex-col items-stretch gap-4 sm:flex-row sm:items-center sm:gap-6">
                        <button
                          type="button"
                          onClick={handleStep2Continue}
                          disabled={uiLocked || !canAccessStep(2)}
                          className="group/btn flex w-full items-center justify-center gap-3 rounded-lg bg-accent px-8 py-4 text-sm font-bold text-brand-900 shadow-xl shadow-accent/20 transition-transform hover:scale-[1.02] disabled:opacity-50 sm:w-auto"
                        >
                          {cvProcessing ? "Processing…" : "Continue"}
                          <IconArrowForward className="h-5 w-5 transition-transform group-hover/btn:translate-x-1" />
                        </button>
                      </div>
                    </>
                  ) : (
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <p className="text-sm text-on-surface-variant">
                        {canAccessStep(2)
                          ? effectiveMaxStepCompleted >= 2
                            ? `Completed: ${cvFile?.name ?? cvServerFilename ?? "CV uploaded"}`
                            : "Next: upload your CV"
                          : "Complete Step 1 to unlock"}
                      </p>
                      {canEditStep(2) ? (
                        <button
                          type="button"
                          onClick={() => {
                            setError(null);
                            setCurrentStep(2);
                          }}
                          disabled={uiLocked}
                          className="rounded-lg border border-[#c4c6cd]/25 bg-surface-low px-4 py-2 text-xs font-semibold text-brand-900 hover:bg-surface-container"
                        >
                          Edit
                        </button>
                      ) : null}
                    </div>
                  )}
                </div>
              </div>
            </section>

            {/* Step 3 */}
            <section className="relative">
              <div className="flex flex-col items-stretch gap-6 sm:flex-row sm:items-start sm:gap-8">
                <div className="hidden h-11 w-11 shrink-0 items-center justify-center rounded-lg border border-[#c4c6cd]/20 bg-surface-card font-bold text-on-surface-variant shadow-sm sm:flex">
                  3
                </div>
                <div className="flex-1 rounded-2xl border border-[#c4c6cd]/20 bg-surface-card p-6 shadow-sm transition-shadow hover:shadow-md sm:p-8">
                  <div className="mb-4 flex justify-between gap-4">
                    <div>
                      <span className="mb-1 block text-[10px] font-medium uppercase tracking-widest text-on-surface-variant">
                        Intake Task 03
                      </span>
                      <h3 className="font-serif text-2xl text-brand-900">Life Story Workshop</h3>
                    </div>
                    {!canAccessStep(3) ? <IconLock className="h-6 w-6 shrink-0 text-surface-dim" /> : null}
                  </div>
                  {currentStep === 3 ? (
                    <>
                      <p className="mb-6 text-on-surface-variant">
                        Deep-dive narrative workshop to craft your personal statement and unique value proposition.
                        Upload a document that captures where you grew up, formative experiences, interests and hobbies,
                        and anything admissions committees would find memorable about you as a person.
                      </p>
                      {!lifeStoryFile &&
                      lifeStoryServerFilename &&
                      (lifeStoryServerStatus === "ready" || lifeStoryServerStatus === "reviewing") ? (
                        <div className="mb-5 rounded-xl border border-[#c4c6cd]/20 bg-surface-low px-4 py-3">
                          <p className="text-sm font-semibold text-brand-900">Life story already uploaded</p>
                          <p className="mt-1 text-xs text-on-surface-variant">
                            We found an existing life story on your account:{" "}
                            <span className="font-medium">{lifeStoryServerFilename}</span>.
                          </p>
                        </div>
                      ) : null}
                      {lifeStoryProcessing ? (
                        <div className="mb-5 rounded-xl border border-[#c4c6cd]/20 bg-surface-low px-4 py-3">
                          <p className="text-sm font-semibold text-brand-900">Processing your life story…</p>
                          <p className="mt-1 text-xs text-on-surface-variant">
                            Your file is being processed and your profile is being updated. This can take a couple of
                            minutes — please keep this page open.
                          </p>
                          {lifeStoryUploadedFileId ? (
                            <p className="mt-2 text-[11px] text-on-surface-variant">Upload ID: {lifeStoryUploadedFileId}</p>
                          ) : null}
                        </div>
                      ) : null}
                      <div>
                        <label htmlFor="intake-life" className={labelClass}>
                          Life story
                        </label>
                        <IntakeFileDropZone
                          id="intake-life"
                          inputName="life_story"
                          disabled={uiLocked || !canAccessStep(3)}
                          file={lifeStoryFile}
                          acceptHint="PDF, Word, or plain text is fine."
                          hideDropZone={Boolean(lifeStoryFile) || lifeStoryProcessing}
                          onFileChange={(f) => {
                            setError(null);
                            setLifeStoryFile(f);
                          }}
                          onInvalidFile={() =>
                            setError("Please upload a PDF, Word, or plain text file.")
                          }
                        />
                      </div>
                      {error ? (
                        <p className="mt-4 text-sm text-red-600" role="alert">
                          {error}
                        </p>
                      ) : null}
                      <div className="mt-6 flex flex-col items-stretch gap-4 sm:flex-row sm:items-center sm:gap-6">
                        <button
                          type="button"
                          onClick={() => void submitFinal()}
                          disabled={uiLocked || !canAccessStep(3)}
                          className="group/btn flex w-full items-center justify-center gap-3 rounded-lg bg-accent px-8 py-4 text-sm font-bold text-brand-900 shadow-xl shadow-accent/20 transition-transform hover:scale-[1.02] disabled:opacity-50 sm:w-auto"
                        >
                          {lifeStoryProcessing ? "Processing…" : busy ? "Saving…" : "Continue"}
                          <IconArrowForward className="h-5 w-5 transition-transform group-hover/btn:translate-x-1" />
                        </button>
                      </div>
                    </>
                  ) : (
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <p className="text-sm text-on-surface-variant">
                        {canAccessStep(3)
                          ? effectiveMaxStepCompleted >= 3
                            ? `Completed: ${lifeStoryFile?.name ?? lifeStoryServerFilename ?? "Life story uploaded"}`
                            : "Next: upload your life story"
                          : "Complete Step 2 to unlock"}
                      </p>
                      {canEditStep(3) ? (
                        <button
                          type="button"
                          onClick={() => {
                            setError(null);
                            setCurrentStep(3);
                          }}
                          disabled={uiLocked}
                          className="rounded-lg border border-[#c4c6cd]/25 bg-surface-low px-4 py-2 text-xs font-semibold text-brand-900 hover:bg-surface-container"
                        >
                          Edit
                        </button>
                      ) : null}
                    </div>
                  )}
                </div>
              </div>
            </section>

            {/* Step 4 removed: remaining profile gaps are handled in chat. */}
            {/* Step 4 — Chat-based gap filling */}
            <section className="relative">
              <div className="flex flex-col items-stretch gap-6 sm:flex-row sm:items-start sm:gap-8">
                <div className="hidden h-11 w-11 shrink-0 items-center justify-center rounded-lg border border-[#c4c6cd]/20 bg-surface-card font-bold text-on-surface-variant shadow-sm sm:flex">
                  4
                </div>
                <div className="flex-1 rounded-2xl border border-[#c4c6cd]/20 bg-surface-card p-6 shadow-sm transition-shadow hover:shadow-md sm:p-8">
                  <div className="mb-4 flex justify-between gap-4">
                    <div>
                      <span className="mb-1 block text-[10px] font-medium uppercase tracking-widest text-on-surface-variant">
                        Intake Task 04
                      </span>
                      <h3 className="font-serif text-2xl text-brand-900">Final Questions (Chat)</h3>
                    </div>
                    {!canAccessStep(4) ? <IconLock className="h-6 w-6 shrink-0 text-surface-dim" /> : null}
                  </div>

                  {currentStep === 4 ? (
                    <>
                      <p className="text-on-surface-variant">
                        Answer the remaining questions below. After each response, your profile is re-checked and the next
                        question is shown only if it’s still needed.
                      </p>

                      <div className="mt-5 overflow-hidden rounded-xl border border-[#c4c6cd]/20">
                        <FinalQuestionsStep
                          sessionToken={sessionToken}
                          onCompleteChange={handleFinalChatCompleteChange}
                        />
                      </div>

                      <div className="mt-5 flex flex-col items-stretch gap-3 sm:flex-row sm:items-center">
                        <button
                          type="button"
                          disabled={!finalChatComplete}
                          onClick={() => {
                            void (async () => {
                              setError(null);
                              setBusy(true);
                              try {
                                // Persist step 4 before leaving intake. The dashboard re-fetches profile on
                                // session updates; swallowing this error left the server on step < 4 and
                                // forced the user back into intake after a brief flash of evaluation.
                                const updated = await patchCandidateIntakeStep(sessionToken, 4);
                                setMaxStepCompleted(4);
                                onComplete(updated);
                              } catch (err) {
                                setError(String(err));
                              } finally {
                                setBusy(false);
                              }
                            })();
                          }}
                          className="group/btn flex w-full items-center justify-center gap-3 rounded-lg bg-accent px-8 py-4 text-sm font-bold text-brand-900 shadow-xl shadow-accent/20 transition-transform hover:scale-[1.02] disabled:opacity-50 sm:w-auto"
                        >
                          Continue to evaluation
                          <IconArrowForward className="h-5 w-5 transition-transform group-hover/btn:translate-x-1" />
                        </button>
                        <p className="text-xs text-on-surface-variant">
                          {finalChatComplete
                            ? "Profile complete — you’re ready."
                            : "Complete the remaining profile gaps in chat to unlock Continue."}
                        </p>
                      </div>

                      {error ? (
                        <p className="mt-3 text-sm text-red-600" role="alert">
                          {error}
                        </p>
                      ) : null}
                    </>
                  ) : (
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <p className="text-sm text-on-surface-variant">
                        {canAccessStep(4)
                          ? effectiveMaxStepCompleted >= 4
                            ? "Completed: final questions done"
                            : "Next: chat-based final questions (if any)"
                          : "Complete Step 3 to unlock"}
                      </p>
                      {canEditStep(4) ? (
                        <button
                          type="button"
                          onClick={() => {
                            setError(null);
                            setCurrentStep(4);
                          }}
                          disabled={uiLocked}
                          className="rounded-lg border border-[#c4c6cd]/25 bg-surface-low px-4 py-2 text-xs font-semibold text-brand-900 hover:bg-surface-container"
                        >
                          Open questions
                        </button>
                      ) : null}
                    </div>
                  )}
                </div>
              </div>
            </section>
          </div>

          <footer className="mt-20 flex flex-col items-center justify-between gap-6 border-t border-[#c4c6cd]/20 pt-10 sm:mt-24 md:flex-row">
            <p className="text-sm text-on-surface-variant">© 2026 GradAdvisor. All rights reserved.</p>
            <div className="flex gap-6">
              <a className="text-xs font-medium uppercase tracking-widest text-on-surface-variant hover:text-brand-900" href="#">
                Privacy Policy
              </a>
              <a className="text-xs font-medium uppercase tracking-widest text-on-surface-variant hover:text-brand-900" href="#">
                Terms of Service
              </a>
            </div>
          </footer>
        </div>
    </CandidateStitchShell>
  );
}

"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { format } from "date-fns";
import { DayPicker } from "react-day-picker";

import { SearchableMultiSelect } from "@/components/SearchableMultiSelect";
import { SearchableSelect } from "@/components/SearchableSelect";
import type { SearchableOption } from "@/components/SearchableSelect";
import { FinalQuestionsStep } from "@/components/FinalQuestionsStep";
import type { CandidateDto } from "@/lib/api";
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
import { GRAD_PROGRAM_FOCUS_OPTIONS } from "@/data/gradProgramFocusOptions";

import "react-day-picker/style.css";

const COUNTRY_OPTIONS = COUNTRY_NAMES.map((name) => ({ value: name, label: name }));

function buildIntakeSchoolOptions(primary: string[], secondary: string[]): SearchableOption[] {
  const a = [...primary].sort((x, y) => x.localeCompare(y));
  const b = [...secondary].sort((x, y) => x.localeCompare(y));
  return [...a, ...b].map((name) => ({ value: name, label: name }));
}

function getTargetSchoolsLabel(programFocus: string) {
  const p = programFocus.trim().toLowerCase();
  if (!p) return "Schools you are considering";
  if (/\bmba\b/.test(p) || p.includes("business administration")) {
    return "Schools you are considering (US MBA programs)";
  }
  if (p.includes("master in management") || /\bmim\b/.test(p)) {
    return "Schools you are considering (US MiM programs)";
  }
  return "Schools you are considering (US graduate programs)";
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

const PHASES = [
  "01. Intake",
  "02. Profile Generation",
  "03. Evaluation",
  "04. Positioning",
  "05. Application",
  "06. Validation",
  "07. Submission",
] as const;

const FILE_STATUS_POLL_MS = 1000;

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
  const [programFocus, setProgramFocus] = useState("");
  const [targetSchools, setTargetSchools] = useState<string[]>([]);
  const [schoolOptions, setSchoolOptions] = useState<SearchableOption[]>([]);
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

  const dobWrapRef = useRef<HTMLDivElement>(null);
  const today = new Date();
  const debugEnabled =
    typeof window !== "undefined" &&
    (process.env.NEXT_PUBLIC_DEBUG_INTAKE === "1" || process.env.NODE_ENV !== "production");
  const debug = (...args: unknown[]) => {
    if (debugEnabled) console.debug("[intake]", ...args);
  };

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
        setSchoolOptions(buildIntakeSchoolOptions(data.tier_1, data.tier_2));
        setMaxSchoolSelections(data.max_selections);
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
        if (p?.grad_program_focus) setProgramFocus(p.grad_program_focus);
        const attrs = p?.attributes ?? null;
        const schools = Array.isArray((attrs as any)?.target_schools) ? ((attrs as any).target_schools as string[]) : [];
        if (schools.length) setTargetSchools(schools);
        const step = Number((attrs as any)?.intake_step_completed ?? 0);
        const stepCompleted = (step === 1 || step === 2 || step === 3 || step === 4 ? step : 0) as
          | 0
          | 1
          | 2
          | 3
          | 4;
        debug("profile hydration", {
          intake_step_completed: stepCompleted,
          has_target_schools: Boolean(schools.length),
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
    if (!programFocus) {
      setError("Please select the program you are targeting.");
      return false;
    }
    if (!dob) {
      setError("Please select your date of birth.");
      return false;
    }
    if (targetSchools.length === 0) {
      setError("Please select at least one school you are considering.");
      return false;
    }
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
        await patchCandidateIntakeDraft(sessionToken, {
          full_name: fullName,
          country_of_residence: country,
          date_of_birth: isoDob,
          grad_program_focus: programFocus,
          target_schools: targetSchools,
        });
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
      if (!lifeStoryFile && lifeStoryServerStatus === "ready") {
        try {
          await patchCandidateIntakeStep(sessionToken, 3);
        } catch {
          // Non-blocking.
        }
        setBusy(true);
        try {
          await patchCandidateIntake(sessionToken, {
            full_name: fullName,
            country_of_residence: country,
            date_of_birth: isoDob,
            grad_program_focus: programFocus,
            target_schools: targetSchools,
          });
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
        await patchCandidateIntake(sessionToken, {
          full_name: fullName,
          country_of_residence: country,
          date_of_birth: isoDob,
          grad_program_focus: programFocus,
          target_schools: targetSchools,
        });
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
    <div className="min-h-screen bg-surface pb-24 text-on-surface md:pb-0">
      {/* Top bar — Stitch Intake dashboard */}
      <header className="fixed left-0 right-0 top-0 z-50 border-b border-[#c4c6cd]/15 bg-surface-low/80 shadow-ambient backdrop-blur-md">
        <div className="mx-auto flex h-20 w-full max-w-screen-2xl items-center justify-between px-6 sm:px-8">
          <div className="flex items-center gap-6 md:gap-8">
            <span className="font-serif text-xl italic text-brand-900">GradAdvisor</span>
            <nav className="flex items-center gap-6" aria-label="Primary">
              <button
                type="button"
                onClick={() => {
                  router.push("/");
                }}
                className="border-b-2 border-accent pb-1 text-sm font-semibold text-brand-900"
              >
                Dashboard
              </button>
              <button
                type="button"
                onClick={() => {
                  router.push("/documents");
                }}
                className="text-sm font-medium text-brand-500 hover:text-brand-900"
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
                  <div className="h-full w-[14%] rounded-full bg-accent" />
                </div>
                <span className="text-xs font-semibold text-brand-900">1/7 Phases</span>
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
              {initials || "?"}
            </div>
          </div>
        </div>
      </header>

      {/* Phase sidebar */}
      <aside className="fixed left-0 top-0 hidden h-screen w-64 flex-col border-r border-[#c4c6cd]/15 bg-surface-low py-8 pt-28 md:flex">
        <div className="mb-10 px-6">
          <h2 className="font-serif text-lg text-brand-900">The Curator</h2>
          <p className="font-sans text-xs font-medium uppercase tracking-widest text-brand-500">Premium Admissions AI</p>
        </div>
        <div className="mb-4 px-6">
          <p className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant">Application Phases</p>
        </div>
        <nav className="no-scrollbar flex-1 space-y-1 overflow-y-auto" aria-label="Application phases">
          {PHASES.map((label, i) => {
            const active = i === 0;
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

      <main className="min-h-screen pt-20 md:pl-64">
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

                          <div className="mt-5">
                            <SearchableSelect
                              id="intake-program"
                              label="Program you are targeting"
                              options={GRAD_PROGRAM_FOCUS_OPTIONS}
                              value={programFocus}
                              onChange={(v) => {
                                setProgramFocus(v);
                                setError((prev) =>
                                  prev === "Please select the program you are targeting." ? null : prev,
                                );
                              }}
                              disabled={busy}
                              placeholder="Search programs (MBA, PhD, MS, …)"
                              emptyMessage="No program matches"
                              maxVisible={200}
                            />
                          </div>

                          {schoolsLoadError ? (
                            <p className="mt-5 text-sm text-red-600" role="alert">
                              Could not load school list: {schoolsLoadError}
                            </p>
                          ) : null}
                          <div className="mt-5">
                            <SearchableMultiSelect
                              id="intake-schools"
                              label={getTargetSchoolsLabel(programFocus)}
                              options={schoolOptions}
                              values={targetSchools}
                              onChange={(v) => {
                                setTargetSchools(v);
                                setError((prev) =>
                                  prev === "Please select at least one school you are considering." ? null : prev,
                                );
                              }}
                              disabled={busy || schoolsLoading || Boolean(schoolsLoadError)}
                              placeholder={schoolsLoading ? "Loading schools…" : "Search schools to add…"}
                              emptyMessage="No school matches"
                              maxVisible={200}
                              maxSelections={maxSchoolSelections}
                            />
                          </div>
                        </div>

                        {error ? (
                          <p className="text-sm text-amber-200" role="alert">
                            {error}
                          </p>
                        ) : null}
                        <div className="flex flex-col items-stretch gap-4 sm:flex-row sm:items-center sm:gap-6">
                          <button
                            type="submit"
                            disabled={busy || schoolsLoading || Boolean(schoolsLoadError) || schoolOptions.length === 0}
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
                          Completed: {country || "—"}, {programFocus || "—"}, {targetSchools.length} school
                          {targetSchools.length === 1 ? "" : "s"}
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
                        <input
                          id="intake-cv"
                          name="cv"
                          type="file"
                          accept={INTAKE_DOC_ACCEPT}
                          disabled={uiLocked || !canAccessStep(2)}
                          className="mt-1 block w-full text-sm text-on-surface file:mr-3 file:rounded-md file:border-0 file:bg-brand-900 file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-white hover:file:bg-brand-800 disabled:opacity-50"
                          onChange={(e) => setCvFile(e.target.files?.[0] ?? null)}
                        />
                        {cvFile ? (
                          <p className="mt-2 text-xs text-on-surface-variant">Selected: {cvFile.name}</p>
                        ) : null}
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
                        <p className="mt-0.5 text-xs leading-relaxed text-on-surface-variant">
                          PDF, Word, or plain text is fine.
                        </p>
                        <input
                          id="intake-life"
                          name="life_story"
                          type="file"
                          accept={INTAKE_DOC_ACCEPT}
                          disabled={uiLocked || !canAccessStep(3)}
                          className="mt-2 block w-full text-sm text-on-surface file:mr-3 file:rounded-md file:border-0 file:bg-brand-900 file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-white hover:file:bg-brand-800 disabled:opacity-50"
                          onChange={(e) => setLifeStoryFile(e.target.files?.[0] ?? null)}
                        />
                        {lifeStoryFile ? (
                          <p className="mt-2 text-xs text-on-surface-variant">Selected: {lifeStoryFile.name}</p>
                        ) : null}
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
                          onCompleteChange={(c) => setFinalChatComplete(Boolean(c))}
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
                                try {
                                  await patchCandidateIntakeStep(sessionToken, 4);
                                } catch {
                                  // Non-blocking: allow continue if step-save fails transiently.
                                }
                                const updated = await fetchCandidateProfile(sessionToken);
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
                          Continue to Phase 02
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
      </main>

      {/* Mobile tab bar */}
      <div className="fixed bottom-0 left-0 right-0 z-50 flex items-center justify-around border-t border-[#c4c6cd]/20 bg-surface-low/90 px-4 py-3 backdrop-blur-md md:hidden">
        <span className="flex flex-col items-center gap-1 text-brand-900">
          <svg className="h-6 w-6" fill="currentColor" viewBox="0 0 24 24" aria-hidden>
            <path d="M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z" />
          </svg>
          <span className="text-[10px] font-medium uppercase tracking-wider">Intake</span>
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

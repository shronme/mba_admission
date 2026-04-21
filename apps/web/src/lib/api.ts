/**
 * Base URL for FastAPI. Must be reachable from the **browser** (not from Docker internal hostnames).
 * Use the **API** service’s public URL — not the Next.js frontend URL (GET /health exists only on FastAPI).
 */

/** Candidate + profile from POST /candidates/enter or GET /candidates/me */
export type CandidateProfileDto = {
  headline: string | null;
  summary: string | null;
  attributes: Record<string, unknown> | null;
  profile_complete: boolean;
  completeness_score: number;
  country_of_residence: string | null;
  date_of_birth: string | null;
  intake_form_completed: boolean;
  grad_program_focus: string | null;
};

export type CandidateDto = {
  id: string;
  email: string | null;
  full_name: string;
  program_type: string;
  status: string;
  stage?: string;
  profile: CandidateProfileDto | null;
};

export type AdminDto = {
  id: string;
  email: string;
  full_name: string;
};

/** Unified auth response from POST /auth/enter */
export type AuthEnterResponse = {
  role: "candidate" | "admin";
  session_token: string;
  candidate?: CandidateDto;
  admin?: AdminDto;
  created?: boolean;
};

/** Legacy shape kept for backwards compatibility */
export type EnterResponse = {
  created: boolean;
  candidate: CandidateDto;
  session_token?: string;
};

/** Admin API types */
export type AdminCandidateListItem = {
  id: string;
  email: string | null;
  full_name: string;
  program_type: string;
  status: string;
  stage: string;
  completeness_score: number;
  profile_complete: boolean;
  created_at: string | null;
};

export type AdminFileDto = {
  id: string;
  original_filename: string;
  content_type: string | null;
  byte_size: number | null;
  status: string;
  document_type: string | null;
  created_at: string | null;
};

export type AdminCandidateDetail = {
  id: string;
  email: string | null;
  full_name: string;
  program_type: string;
  status: string;
  stage: string;
  created_at: string | null;
  profile: {
    headline: string | null;
    summary: string | null;
    attributes: Record<string, unknown>;
    profile_complete: boolean;
    completeness_score: number;
    country_of_residence?: string | null;
    date_of_birth?: string | null;
    intake_form_completed?: boolean;
    grad_program_focus?: string | null;
  } | null;
  files: AdminFileDto[];
};

/** Persisted under `profile.attributes.intake_test_scores` (JSON). */
export type IntakeTestScoresPayload = {
  scores_not_final_yet: boolean;
  gmat_total: number | null;
  gre_verbal: number | null;
  gre_quant: number | null;
  ea_total: number | null;
  gre_waived: boolean;
  toefl_total: number | null;
  ielts_overall: number | null;
  native_english_speaker: boolean | null;
};

export type IntakeSchoolProgramSelectionPayload = {
  school: string;
  school_other: string | null;
  program_slug: string;
  program_other: string | null;
};

export type CandidateIntakePayload = {
  full_name: string;
  country_of_residence: string;
  date_of_birth: string;
  /** Up to 4 (school, program) selections for intake step 1. */
  school_program_selections: IntakeSchoolProgramSelectionPayload[];
  /** Optional undergrad GPA (stored in profile.attributes). */
  undergrad_gpa?: number | null;
  /** Optional standardized tests; stored on the profile. */
  intake_test_scores?: IntakeTestScoresPayload | null;
};

export type ProfileGapQuestionDto = {
  key: string;
  question: string;
};

export type ProfileReviewResponseDto = {
  profile_complete: boolean;
  completeness_score: number;
  missing: ProfileGapQuestionDto[];
};

/** Persisted under `profile.attributes` — admission evaluation job progress. */
export type AdmissionEvaluationJobDto = {
  ai_run_id: string;
  phase: string;
  message: string;
  updated_at: string;
  current_school: string;
  current_program_display_name: string;
  current_program_slug: string;
  program_index: number;
  programs_total: number;
  substep: string;
  phase_scope: string;
  progress_percent: number;
  programs_completed: { school: string; program_display_name: string }[];
};

export type AdmissionEvaluationPrimaryRow = {
  school: string;
  program_slug: string;
  program_display_name: string;
  strengths?: string[];
  weaknesses?: string[];
  admission_chance_1_100?: number;
  admission_band?: string;
  narrative_strategy?: string;
  priority_actions?: string[];
};

export type AdmissionEvaluationExtraRow = {
  school: string;
  program_display_name: string;
  program_slug?: string;
  key_match?: string;
  action_item?: string;
  match_strength_1_100?: number;
  meta?: string;
};

export type AdmissionEvaluationResultDto = {
  status: "complete" | "failed";
  primary: AdmissionEvaluationPrimaryRow[];
  extra: AdmissionEvaluationExtraRow[];
  error?: string | null;
};

/** Persisted under `profile.attributes.selected_schools` and used by advisor threads. */
export type SelectedSchoolRow = {
  school: string;
  program_slug: string;
  program_display_name?: string;
};

// Client-side request coalescing to prevent "request storms" when multiple
// components poll the same GET endpoints concurrently (or React dev mode remounts).
const _inflight = new Map<string, Promise<unknown>>();
const _cache = new Map<string, { at: number; value: unknown }>();
const _lastStart = new Map<string, number>();

function inflightKey(parts: Array<string | null | undefined>) {
  return parts.filter(Boolean).join("|");
}

function nowMs() {
  return typeof performance !== "undefined" && typeof performance.now === "function"
    ? performance.now()
    : Date.now();
}

function coalesce<T>(key: string, fn: () => Promise<T>): Promise<T> {
  const existing = _inflight.get(key) as Promise<T> | undefined;
  if (existing) return existing;
  const p = fn().finally(() => {
    _inflight.delete(key);
  });
  _inflight.set(key, p as Promise<unknown>);
  return p;
}

function cached<T>(key: string, ttlMs: number): T | null {
  const hit = _cache.get(key);
  if (!hit) return null;
  if (nowMs() - hit.at > ttlMs) return null;
  return hit.value as T;
}

function setCached(key: string, value: unknown) {
  _cache.set(key, { at: nowMs(), value });
}

function rateLimitKey(parts: Array<string | null | undefined>) {
  return `rl|${inflightKey(parts)}`;
}

function enforceMinInterval(key: string, minMs: number): boolean {
  const last = _lastStart.get(key) ?? 0;
  const t = nowMs();
  if (t - last < minMs) return false;
  _lastStart.set(key, t);
  return true;
}

function parseCandidateProfile(raw: unknown): CandidateProfileDto | null {
  if (raw === null || typeof raw !== "object") return null;
  const p = raw as Record<string, unknown>;
  return {
    headline: (p.headline as string | null) ?? null,
    summary: (p.summary as string | null) ?? null,
    attributes: (p.attributes as Record<string, unknown> | null) ?? null,
    profile_complete: Boolean(p.profile_complete),
    completeness_score: typeof p.completeness_score === "number" ? p.completeness_score : 0,
    country_of_residence: (p.country_of_residence as string | null) ?? null,
    date_of_birth: (p.date_of_birth as string | null) ?? null,
    intake_form_completed: p.intake_form_completed === true,
    grad_program_focus: (p.grad_program_focus as string | null) ?? null,
  };
}

function parseCandidateDto(cand: Record<string, unknown>): CandidateDto {
  return {
    id: String(cand.id ?? ""),
    email: (cand.email as string | null) ?? null,
    full_name: String(cand.full_name ?? ""),
    program_type: String(cand.program_type ?? ""),
    status: String(cand.status ?? ""),
    stage: cand.stage !== undefined ? String(cand.stage) : undefined,
    profile: parseCandidateProfile(cand.profile),
  };
}

/** POST /auth/enter — unified login */
export async function authEnter(body: {
  email: string;
  full_name?: string;
}): Promise<AuthEnterResponse> {
  const root = getApiBaseUrl();
  if (!root) {
    throw new Error(
      "NEXT_PUBLIC_API_URL is not set. Copy apps/web/.env.example to apps/web/.env.local",
    );
  }
  const res = await fetch(`${root}/auth/enter`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email: body.email.trim(),
      full_name: body.full_name?.trim() || undefined,
    }),
    cache: "no-store",
  });
  const text = await res.text();
  let data: unknown;
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    throw new Error(`POST /auth/enter: invalid JSON (${res.status})`);
  }
  if (!res.ok) {
    throw new Error(
      `POST /auth/enter failed: ${res.status} ${typeof data === "object" && data !== null ? JSON.stringify(data) : text}`,
    );
  }
  const raw = data as Record<string, unknown>;
  const base = raw as unknown as AuthEnterResponse;
  if (raw.candidate && typeof raw.candidate === "object") {
    return {
      ...base,
      candidate: parseCandidateDto(raw.candidate as Record<string, unknown>),
    };
  }
  return base;
}

/** Admin API helpers */
export async function adminListCandidates(
  sessionToken: string,
): Promise<AdminCandidateListItem[]> {
  const root = getApiBaseUrl();
  if (!root) throw new Error("NEXT_PUBLIC_API_URL is not set");
  const res = await fetch(`${root}/admin/candidates`, {
    method: "GET",
    cache: "no-store",
    headers: { Authorization: `Bearer ${sessionToken}` },
  });
  const text = await res.text();
  if (!res.ok) throw new Error(`GET /admin/candidates failed: ${res.status} ${text}`);
  const data = JSON.parse(text) as { candidates: AdminCandidateListItem[] };
  return data.candidates ?? [];
}

export async function adminGetCandidate(
  candidateId: string,
  sessionToken: string,
): Promise<AdminCandidateDetail> {
  const root = getApiBaseUrl();
  if (!root) throw new Error("NEXT_PUBLIC_API_URL is not set");
  const res = await fetch(`${root}/admin/candidates/${encodeURIComponent(candidateId)}`, {
    method: "GET",
    cache: "no-store",
    headers: { Authorization: `Bearer ${sessionToken}` },
  });
  const text = await res.text();
  if (!res.ok)
    throw new Error(`GET /admin/candidates/${candidateId} failed: ${res.status} ${text}`);
  return JSON.parse(text) as AdminCandidateDetail;
}

export async function adminUploadFiles(
  candidateId: string,
  files: FileList,
  sessionToken: string,
): Promise<AdminFileDto[]> {
  const root = getApiBaseUrl();
  if (!root) throw new Error("NEXT_PUBLIC_API_URL is not set");
  const form = new FormData();
  for (const file of Array.from(files)) {
    form.append("files", file);
  }
  const res = await fetch(
    `${root}/admin/candidates/${encodeURIComponent(candidateId)}/files/upload`,
    {
      method: "POST",
      body: form,
      headers: { Authorization: `Bearer ${sessionToken}` },
      cache: "no-store",
    },
  );
  const text = await res.text();
  if (!res.ok) throw new Error(`POST admin upload failed: ${res.status} ${text}`);
  const data = JSON.parse(text) as { files: AdminFileDto[] };
  return data.files ?? [];
}

export async function enterWithEmail(body: {
  email: string;
  full_name?: string;
}): Promise<EnterResponse> {
  const root = getApiBaseUrl();
  if (!root) {
    throw new Error(
      "NEXT_PUBLIC_API_URL is not set. Copy apps/web/.env.example to apps/web/.env.local",
    );
  }
  const res = await fetch(`${root}/candidates/enter`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email: body.email.trim(),
      full_name: body.full_name?.trim() || undefined,
    }),
    cache: "no-store",
  });
  const text = await res.text();
  let data: unknown;
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    throw new Error(`POST /candidates/enter: invalid JSON (${res.status})`);
  }
  if (!res.ok) {
    throw new Error(
      `POST /candidates/enter failed: ${res.status} ${typeof data === "object" && data !== null ? JSON.stringify(data) : text}`,
    );
  }
  const obj = data as Record<string, unknown>;
  const created = obj.created === true;
  const sessionToken =
    typeof obj.session_token === "string" ? obj.session_token : undefined;
  const cand = obj.candidate as Record<string, unknown> | undefined;
  if (!cand || typeof cand.id !== "string") {
    throw new Error(`POST /candidates/enter: unexpected shape ${text}`);
  }
  return {
    created,
    session_token: sessionToken,
    candidate: parseCandidateDto(cand),
  };
}

export async function fetchCandidateProfile(
  sessionToken: string,
): Promise<CandidateDto> {
  const root = getApiBaseUrl();
  if (!root) throw new Error("NEXT_PUBLIC_API_URL is not set");
  const url = `${root}/candidates/me`;
  const key = inflightKey(["GET", url, sessionToken]);
  const cachedValue = cached<CandidateDto>(key, 1000);
  if (cachedValue) return cachedValue;
  const rlKey = rateLimitKey(["GET", url, sessionToken]);
  if (!enforceMinInterval(rlKey, 1000)) {
    const maybeCached = cached<CandidateDto>(key, 10_000);
    if (maybeCached) return maybeCached;
  }
  return coalesce(
    key,
    async () => {
      const res = await fetch(url, {
        method: "GET",
        cache: "no-store",
        headers: { Authorization: `Bearer ${sessionToken}` },
      });
      const text = await res.text();
      let data: unknown;
      try {
        data = text ? JSON.parse(text) : {};
      } catch {
        throw new Error(`GET /candidates/me: invalid JSON (${res.status})`);
      }
      if (!res.ok) throw new Error(`GET /candidates/me failed: ${res.status} ${text}`);
      const parsed = parseCandidateDto(data as Record<string, unknown>);
      setCached(key, parsed);
      return parsed;
    },
  );
}

/** GET /candidates/me without client cache — use while polling admission evaluation. */
export async function fetchCandidateProfileFresh(sessionToken: string): Promise<CandidateDto> {
  const root = getApiBaseUrl();
  if (!root) throw new Error("NEXT_PUBLIC_API_URL is not set");
  const res = await fetch(`${root}/candidates/me`, {
    method: "GET",
    cache: "no-store",
    headers: { Authorization: `Bearer ${sessionToken}` },
  });
  const text = await res.text();
  let data: unknown;
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    throw new Error(`GET /candidates/me: invalid JSON (${res.status})`);
  }
  if (!res.ok) throw new Error(`GET /candidates/me failed: ${res.status} ${text}`);
  return parseCandidateDto(data as Record<string, unknown>);
}

export async function startAdmissionEvaluation(sessionToken: string): Promise<{ ai_run_id: string }> {
  const root = getApiBaseUrl();
  if (!root) throw new Error("NEXT_PUBLIC_API_URL is not set");
  const res = await fetch(`${root}/candidates/me/admission-evaluation/start`, {
    method: "POST",
    cache: "no-store",
    headers: { Authorization: `Bearer ${sessionToken}` },
  });
  const text = await res.text();
  let data: unknown;
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    throw new Error(`POST /candidates/me/admission-evaluation/start: invalid JSON (${res.status})`);
  }
  if (res.status === 409) {
    throw new Error("Admission evaluation already completed.");
  }
  if (!res.ok) {
    throw new Error(
      `POST admission-evaluation/start failed: ${res.status} ${typeof data === "object" && data !== null ? JSON.stringify(data) : text}`,
    );
  }
  const o = data as { ai_run_id?: string };
  if (!o.ai_run_id) throw new Error("missing ai_run_id");
  return { ai_run_id: o.ai_run_id };
}

export async function patchCandidateIntake(
  sessionToken: string,
  body: CandidateIntakePayload,
): Promise<CandidateDto> {
  const root = getApiBaseUrl();
  if (!root) throw new Error("NEXT_PUBLIC_API_URL is not set");
  const res = await fetch(`${root}/candidates/me/intake`, {
    method: "PATCH",
    cache: "no-store",
    headers: {
      Authorization: `Bearer ${sessionToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      full_name: body.full_name.trim(),
      country_of_residence: body.country_of_residence.trim(),
      date_of_birth: body.date_of_birth,
      school_program_selections: body.school_program_selections,
      undergrad_gpa: body.undergrad_gpa ?? null,
      intake_test_scores: body.intake_test_scores ?? null,
    }),
  });
  const text = await res.text();
  let data: unknown;
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    throw new Error(`PATCH /candidates/me/intake: invalid JSON (${res.status})`);
  }
  if (!res.ok) {
    throw new Error(
      `PATCH /candidates/me/intake failed: ${res.status} ${typeof data === "object" && data !== null ? JSON.stringify(data) : text}`,
    );
  }
  return parseCandidateDto(data as Record<string, unknown>);
}

/**
 * Draft-save intake answers without completing the intake.
 * (Persists Step 1 answers but does not set `intake_form_completed`.)
 */
export async function patchCandidateIntakeDraft(
  sessionToken: string,
  body: CandidateIntakePayload,
): Promise<CandidateDto> {
  const root = getApiBaseUrl();
  if (!root) throw new Error("NEXT_PUBLIC_API_URL is not set");
  const res = await fetch(`${root}/candidates/me/intake/draft`, {
    method: "PATCH",
    cache: "no-store",
    headers: {
      Authorization: `Bearer ${sessionToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      full_name: body.full_name.trim(),
      country_of_residence: body.country_of_residence.trim(),
      date_of_birth: body.date_of_birth,
      school_program_selections: body.school_program_selections,
      undergrad_gpa: body.undergrad_gpa ?? null,
      intake_test_scores: body.intake_test_scores ?? null,
    }),
  });
  const text = await res.text();
  let data: unknown;
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    throw new Error(`PATCH /candidates/me/intake/draft: invalid JSON (${res.status})`);
  }
  if (!res.ok) {
    throw new Error(`PATCH /candidates/me/intake/draft failed: ${res.status} ${text}`);
  }
  return parseCandidateDto(data as Record<string, unknown>);
}

/** Persist intake step completion in profile.attributes. */
export async function patchCandidateIntakeStep(
  sessionToken: string,
  intakeStepCompleted: 0 | 1 | 2 | 3 | 4,
): Promise<CandidateDto> {
  const root = getApiBaseUrl();
  if (!root) throw new Error("NEXT_PUBLIC_API_URL is not set");
  const res = await fetch(`${root}/candidates/me/intake/step`, {
    method: "PATCH",
    cache: "no-store",
    headers: {
      Authorization: `Bearer ${sessionToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ intake_step_completed: intakeStepCompleted }),
  });
  const text = await res.text();
  let data: unknown;
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    throw new Error(`PATCH /candidates/me/intake/step: invalid JSON (${res.status})`);
  }
  if (!res.ok) {
    throw new Error(`PATCH /candidates/me/intake/step failed: ${res.status} ${text}`);
  }
  return parseCandidateDto(data as Record<string, unknown>);
}

export async function reviewCandidateProfile(sessionToken: string): Promise<ProfileReviewResponseDto> {
  const root = getApiBaseUrl();
  if (!root) throw new Error("NEXT_PUBLIC_API_URL is not set");
  const url = `${root}/candidates/me/profile/review`;
  return coalesce(
    inflightKey(["GET", url, sessionToken]),
    async () => {
      const res = await fetch(url, {
        method: "GET",
        cache: "no-store",
        headers: { Authorization: `Bearer ${sessionToken}` },
      });
      const text = await res.text();
      let data: unknown;
      try {
        data = text ? JSON.parse(text) : {};
      } catch {
        throw new Error(`GET /candidates/me/profile/review: invalid JSON (${res.status})`);
      }
      if (!res.ok) {
        throw new Error(`GET /candidates/me/profile/review failed: ${res.status} ${text}`);
      }
      const obj = data as Partial<ProfileReviewResponseDto> & Record<string, unknown>;
      return {
        profile_complete: Boolean(obj.profile_complete),
        completeness_score: typeof obj.completeness_score === "number" ? obj.completeness_score : 0,
        missing: Array.isArray(obj.missing)
          ? obj.missing.map((x) => ({
              key: String((x as any)?.key ?? ""),
              question: String((x as any)?.question ?? ""),
            }))
          : [],
      };
    },
  );
}

/** POST /chat/threads — create or reuse the latest active intake thread. */
export async function createChatThread(sessionToken: string): Promise<{ thread_id: string }> {
  const root = getApiBaseUrl();
  if (!root) throw new Error("NEXT_PUBLIC_API_URL is not set");
  const res = await fetch(`${root}/chat/threads`, {
    method: "POST",
    cache: "no-store",
    headers: { Authorization: `Bearer ${sessionToken}` },
  });
  const text = await res.text();
  let data: unknown;
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    throw new Error(`POST /chat/threads: invalid JSON (${res.status})`);
  }
  if (!res.ok) {
    throw new Error(
      `POST /chat/threads failed: ${res.status} ${typeof data === "object" && data !== null ? JSON.stringify(data) : text}`,
    );
  }
  const obj = data as Record<string, unknown>;
  const threadId = typeof obj.thread_id === "string" ? obj.thread_id : null;
  if (!threadId) throw new Error("POST /chat/threads: missing thread_id");
  return { thread_id: threadId };
}

export async function confirmSchoolSelection(
  sessionToken: string,
  selectedSchools: SelectedSchoolRow[],
): Promise<{ selected_schools: SelectedSchoolRow[]; stage: string }> {
  const root = getApiBaseUrl();
  if (!root) throw new Error("NEXT_PUBLIC_API_URL is not set");
  const res = await fetch(`${root}/candidates/me/school-selection/confirm`, {
    method: "POST",
    cache: "no-store",
    headers: {
      Authorization: `Bearer ${sessionToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      selected_schools: selectedSchools.map((s) => ({
        school: s.school,
        program_slug: s.program_slug,
      })),
    }),
  });
  const text = await res.text();
  let data: unknown;
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    throw new Error(
      `POST /candidates/me/school-selection/confirm: invalid JSON (${res.status})`,
    );
  }
  if (!res.ok) {
    const hint =
      res.status === 409 ? " (finish your admission evaluation first)" : "";
    throw new Error(
      `Confirm school selection failed: ${res.status}${hint} ${
        typeof data === "object" && data !== null ? JSON.stringify(data) : text
      }`,
    );
  }
  const obj = data as Record<string, unknown>;
  return {
    selected_schools: Array.isArray(obj.selected_schools)
      ? (obj.selected_schools as SelectedSchoolRow[])
      : [],
    stage: typeof obj.stage === "string" ? obj.stage : "strategy",
  };
}

export async function createAdvisorThread(
  sessionToken: string,
  opts?: { new?: boolean },
): Promise<{ thread_id: string; is_new: boolean }> {
  const root = getApiBaseUrl();
  if (!root) throw new Error("NEXT_PUBLIC_API_URL is not set");
  const q = opts?.new ? "?new=true" : "";
  const res = await fetch(`${root}/chat/advisor-threads${q}`, {
    method: "POST",
    cache: "no-store",
    headers: { Authorization: `Bearer ${sessionToken}` },
  });
  const text = await res.text();
  let data: unknown;
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    throw new Error(`POST /chat/advisor-threads: invalid JSON (${res.status})`);
  }
  if (!res.ok) {
    const hint =
      res.status === 409 ? " (confirm at least one school first)" : "";
    throw new Error(
      `Create advisor thread failed: ${res.status}${hint} ${
        typeof data === "object" && data !== null ? JSON.stringify(data) : text
      }`,
    );
  }
  const obj = data as Record<string, unknown>;
  const threadId = typeof obj.thread_id === "string" ? obj.thread_id : null;
  if (!threadId) throw new Error("POST /chat/advisor-threads: missing thread_id");
  return {
    thread_id: threadId,
    is_new: obj.is_new === true,
  };
}

export async function submitCandidateProfileAnswers(
  sessionToken: string,
  answers: Record<string, string>,
): Promise<ProfileReviewResponseDto> {
  const root = getApiBaseUrl();
  if (!root) throw new Error("NEXT_PUBLIC_API_URL is not set");
  const res = await fetch(`${root}/candidates/me/profile/answers`, {
    method: "PATCH",
    cache: "no-store",
    headers: {
      Authorization: `Bearer ${sessionToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ answers }),
  });
  const text = await res.text();
  let data: unknown;
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    throw new Error(`PATCH /candidates/me/profile/answers: invalid JSON (${res.status})`);
  }
  if (!res.ok) {
    throw new Error(`PATCH /candidates/me/profile/answers failed: ${res.status} ${text}`);
  }
  const obj = data as Partial<ProfileReviewResponseDto> & Record<string, unknown>;
  return {
    profile_complete: Boolean(obj.profile_complete),
    completeness_score: typeof obj.completeness_score === "number" ? obj.completeness_score : 0,
    missing: Array.isArray(obj.missing)
      ? obj.missing.map((x) => ({
          key: String((x as any)?.key ?? ""),
          question: String((x as any)?.question ?? ""),
        }))
      : [],
  };
}

/** GET /candidates/intake/target-schools — schools + per-school program slugs (catalog JSON). */
export type IntakeProgramOffering = { slug: string; label: string };

export type IntakeTargetSchoolsResponse = {
  tier_1: string[];
  tier_2: string[];
  max_selections: number;
  programs_by_school: Record<string, IntakeProgramOffering[]>;
  /** Value used for the synthetic "Other school" multi-select row (must match backend). */
  other_school_value: string;
};

function parseIntakeTargetSchoolsPayload(data: unknown): IntakeTargetSchoolsResponse {
  if (data === null || typeof data !== "object") {
    throw new Error("Invalid target schools payload");
  }
  const o = data as Record<string, unknown>;
  if (!Array.isArray(o.tier_1) || !Array.isArray(o.tier_2) || typeof o.max_selections !== "number") {
    throw new Error("Invalid target schools payload shape");
  }
  const rawPrograms = o.programs_by_school;
  if (rawPrograms === null || typeof rawPrograms !== "object" || Array.isArray(rawPrograms)) {
    throw new Error("Invalid target schools payload shape (programs_by_school)");
  }
  const programs_by_school: Record<string, IntakeProgramOffering[]> = {};
  for (const [school, entries] of Object.entries(rawPrograms)) {
    if (!Array.isArray(entries)) continue;
    programs_by_school[school] = entries
      .map((item) => {
        const row = item as Record<string, unknown>;
        return {
          slug: String(row.slug ?? ""),
          label: String(row.label ?? row.slug ?? ""),
        };
      })
      .filter((x) => x.slug.length > 0);
  }
  const otherRaw = o.other_school_value;
  const other_school_value =
    typeof otherRaw === "string" && otherRaw.trim() ? otherRaw.trim() : "__intake_other__";
  return {
    tier_1: o.tier_1.map((x) => String(x)),
    tier_2: o.tier_2.map((x) => String(x)),
    max_selections: o.max_selections,
    programs_by_school,
    other_school_value,
  };
}

export async function fetchIntakeTargetSchools(
  sessionToken: string,
): Promise<IntakeTargetSchoolsResponse> {
  const root = getApiBaseUrl();
  if (!root) throw new Error("NEXT_PUBLIC_API_URL is not set");
  const res = await fetch(`${root}/candidates/intake/target-schools`, {
    method: "GET",
    cache: "no-store",
    headers: { Authorization: `Bearer ${sessionToken}` },
  });
  const text = await res.text();
  let data: unknown;
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    throw new Error(`GET /candidates/intake/target-schools: invalid JSON (${res.status})`);
  }
  if (!res.ok) {
    throw new Error(`GET /candidates/intake/target-schools failed: ${res.status} ${text}`);
  }
  return parseIntakeTargetSchoolsPayload(data);
}

export function getApiBaseUrl(): string | null {
  const raw = process.env.NEXT_PUBLIC_API_URL;
  if (!raw) return null;
  // Always use same-origin proxy to avoid CORS preflights (OPTIONS storms) from the browser.
  // `next.config.mjs` rewrites `/api/*` to the configured FastAPI host.
  if (typeof window !== "undefined") return "/api";

  // Server-side fallback (should be rare since most calls happen in client components).
  let base = raw.trim().replace(/\/$/, "");
  if (!base) return null;
  if (!/^https?:\/\//i.test(base)) base = `https://${base}`;
  return base;
}

export async function fetchHealth(): Promise<unknown> {
  const root = getApiBaseUrl();
  if (!root) {
    throw new Error(
      "NEXT_PUBLIC_API_URL is not set. Copy apps/web/.env.example to apps/web/.env.local",
    );
  }
  const url = `${root}/health`;
  return coalesce(inflightKey(["GET", url]), async () => {
    const res = await fetch(url, {
      method: "GET",
      cache: "no-store",
    });
    if (!res.ok) {
      const hint404 =
        res.status === 404
          ? " (404 usually means NEXT_PUBLIC_API_URL points at the **frontend** host, not the **FastAPI** host — use the API service’s Railway domain.)"
          : "";
      throw new Error(`GET /health failed: ${res.status}${hint404}`);
    }
    return res.json();
  });
}

export async function enqueueWiringSmoke(): Promise<WiringSmokePayload> {
  const root = getApiBaseUrl();
  if (!root) {
    throw new Error(
      "NEXT_PUBLIC_API_URL is not set. Copy apps/web/.env.example to apps/web/.env.local",
    );
  }
  const res = await fetch(`${root}/wiring/smoke`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: "{}",
    cache: "no-store",
  });
  const text = await res.text();
  let data: unknown;
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    throw new Error(`POST /wiring/smoke: invalid JSON (${res.status})`);
  }
  if (!res.ok) {
    throw new Error(
      `POST /wiring/smoke failed: ${res.status} ${typeof data === "object" && data !== null ? JSON.stringify(data) : text}`,
    );
  }
  const obj = data as Record<string, unknown>;
  const dbConnected = Boolean(obj.db_connected);
  return {
    db_connected: dbConnected,
    select_one: obj.select_one,
  };
}

export type WiringSmokePayload = {
  db_connected: boolean;
  select_one?: unknown;
};

/** Task 003 — POST /jobs/sample-sleep */
export type SampleSleepEnqueueResponse = {
  ai_run_id: string;
  celery_task_id: string | null;
};

export async function enqueueSampleSleep(body: {
  candidate_id?: string;
  sleep_seconds?: number;
  correlation_id?: string;
  simulate_transient_fail?: boolean;
}): Promise<SampleSleepEnqueueResponse> {
  const root = getApiBaseUrl();
  if (!root) {
    throw new Error(
      "NEXT_PUBLIC_API_URL is not set. Copy apps/web/.env.example to apps/web/.env.local",
    );
  }
  const payload: Record<string, unknown> = {
    sleep_seconds: body.sleep_seconds ?? 1,
    simulate_transient_fail: body.simulate_transient_fail ?? false,
  };
  if (body.correlation_id?.trim()) {
    payload.correlation_id = body.correlation_id.trim();
  }
  if (body.candidate_id?.trim()) {
    payload.candidate_id = body.candidate_id.trim();
  }
  const res = await fetch(`${root}/jobs/sample-sleep`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    cache: "no-store",
  });
  const text = await res.text();
  let data: unknown;
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    throw new Error(`POST /jobs/sample-sleep: invalid JSON (${res.status})`);
  }
  if (!res.ok) {
    throw new Error(
      `POST /jobs/sample-sleep failed: ${res.status} ${typeof data === "object" && data !== null ? JSON.stringify(data) : text}`,
    );
  }
  const obj = data as Record<string, unknown>;
  const aiRunId = typeof obj.ai_run_id === "string" ? obj.ai_run_id : null;
  const celeryTaskId =
    typeof obj.celery_task_id === "string" ? obj.celery_task_id : null;
  if (!aiRunId) {
    throw new Error(`POST /jobs/sample-sleep: missing ai_run_id in ${text}`);
  }
  return { ai_run_id: aiRunId, celery_task_id: celeryTaskId };
}

/** Task 003 — GET /jobs/ai-runs/{id} */
export type AiRunStatusPayload = {
  id: string;
  candidate_id: string | null;
  run_type: string;
  status: string;
  request: Record<string, unknown> | null;
  response: Record<string, unknown> | null;
  model_name: string | null;
  error_message: string | null;
};

export async function fetchAiRunStatus(
  runId: string,
): Promise<AiRunStatusPayload> {
  const root = getApiBaseUrl();
  if (!root) {
    throw new Error(
      "NEXT_PUBLIC_API_URL is not set. Copy apps/web/.env.example to apps/web/.env.local",
    );
  }
  const res = await fetch(
    `${root}/jobs/ai-runs/${encodeURIComponent(runId)}`,
    { method: "GET", cache: "no-store" },
  );
  const text = await res.text();
  let data: AiRunStatusPayload;
  try {
    data = text ? JSON.parse(text) : ({} as AiRunStatusPayload);
  } catch {
    throw new Error(`GET /jobs/ai-runs/${runId}: invalid JSON (${res.status})`);
  }
  if (!res.ok) {
    throw new Error(`GET /jobs/ai-runs/${runId} failed: ${res.status} ${text}`);
  }
  return data;
}

/** Task 003 — GET /jobs/celery/{task_id} (Celery result backend) */
export type CeleryTaskMetaPayload = {
  task_id: string;
  state: string;
  result?: unknown;
  error?: string;
};

export async function fetchCeleryTaskMeta(
  taskId: string,
): Promise<CeleryTaskMetaPayload> {
  const root = getApiBaseUrl();
  if (!root) {
    throw new Error(
      "NEXT_PUBLIC_API_URL is not set. Copy apps/web/.env.example to apps/web/.env.local",
    );
  }
  const res = await fetch(
    `${root}/jobs/celery/${encodeURIComponent(taskId)}`,
    { method: "GET", cache: "no-store" },
  );
  const text = await res.text();
  let data: CeleryTaskMetaPayload;
  try {
    data = text ? JSON.parse(text) : ({} as CeleryTaskMetaPayload);
  } catch {
    throw new Error(`GET /jobs/celery/${taskId}: invalid JSON (${res.status})`);
  }
  if (!res.ok) {
    throw new Error(`GET /jobs/celery/${taskId} failed: ${res.status} ${text}`);
  }
  return data;
}

/** Candidate docs (uploaded_files metadata) */
export type UploadedFileDto = {
  id: string;
  original_filename: string;
  content_type: string | null;
  byte_size: number | null;
  status: "uploading" | "reviewing" | "ready" | "failed" | "deleted";
  document_type?: "cv" | "life_story" | string | null;
  uploaded_stage?: number | null;
};

export async function listUploadedFiles(sessionToken?: string | null): Promise<
  UploadedFileDto[]
> {
  const root = getApiBaseUrl();
  if (!root) throw new Error("NEXT_PUBLIC_API_URL is not set");

  const url = `${root}/files`;
  return coalesce(
    inflightKey(["GET", url, sessionToken ?? "anon"]),
    async () => {
      const res = await fetch(url, {
        method: "GET",
        cache: "no-store",
        headers: sessionToken ? { Authorization: `Bearer ${sessionToken}` } : undefined,
      });
      const text = await res.text();
      let data: unknown;
      try {
        data = text ? JSON.parse(text) : {};
      } catch {
        throw new Error(`GET /files: invalid JSON (${res.status})`);
      }
      if (!res.ok) {
        throw new Error(`GET /files failed: ${res.status} ${text}`);
      }
      if (
        typeof window !== "undefined" &&
        (process.env.NEXT_PUBLIC_DEBUG_INTAKE === "1" || process.env.NODE_ENV !== "production")
      ) {
        // eslint-disable-next-line no-console
        console.debug("[intake] GET /files raw", data);
      }

      // Allow either `{files:[...]}` or `[...]` shapes.
      if (Array.isArray(data)) return data as UploadedFileDto[];
      if (typeof data === "object" && data !== null) {
        const obj = data as Record<string, unknown>;
        if (Array.isArray(obj.files)) return obj.files as UploadedFileDto[];
      }
      return [];
    },
  );
}

/**
 * Upload a single file with an optional document-type hint (intake CV / life story).
 * The API accepts `document_type_hint` only when exactly one file is sent.
 */
export async function uploadFileWithDocumentHint(
  sessionToken: string,
  file: File,
  documentType: "cv" | "life_story",
  uploadedStage?: number | null,
): Promise<UploadedFileDto[]> {
  const root = getApiBaseUrl();
  if (!root) throw new Error("NEXT_PUBLIC_API_URL is not set");

  const form = new FormData();
  form.append("files", file);
  form.append("document_type_hint", documentType);
  if (typeof uploadedStage === "number" && Number.isFinite(uploadedStage)) {
    form.append("uploaded_stage", String(uploadedStage));
  }

  const res = await fetch(`${root}/files/upload`, {
    method: "POST",
    body: form,
    headers: { Authorization: `Bearer ${sessionToken}` },
    cache: "no-store",
  });

  const text = await res.text();
  let data: unknown;
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    throw new Error(`POST /files/upload: invalid JSON (${res.status})`);
  }
  if (!res.ok) {
    throw new Error(`POST /files/upload failed: ${res.status} ${text}`);
  }

  if (typeof data === "object" && data !== null) {
    const obj = data as Record<string, unknown>;
    if (Array.isArray(obj.files)) return obj.files as UploadedFileDto[];
  }
  return [];
}

export async function uploadFiles(
  files: FileList,
  sessionToken?: string | null,
  uploadedStage?: number | null,
): Promise<UploadedFileDto[]> {
  const root = getApiBaseUrl();
  if (!root) throw new Error("NEXT_PUBLIC_API_URL is not set");

  const form = new FormData();
  for (const file of Array.from(files)) {
    form.append("files", file);
  }
  if (typeof uploadedStage === "number" && Number.isFinite(uploadedStage)) {
    form.append("uploaded_stage", String(uploadedStage));
  }

  const res = await fetch(`${root}/files/upload`, {
    method: "POST",
    body: form,
    headers: sessionToken ? { Authorization: `Bearer ${sessionToken}` } : undefined,
    cache: "no-store",
  });

  const text = await res.text();
  let data: unknown;
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    throw new Error(`POST /files/upload: invalid JSON (${res.status})`);
  }
  if (!res.ok) {
    throw new Error(`POST /files/upload failed: ${res.status} ${text}`);
  }

  if (Array.isArray(data)) return data as UploadedFileDto[];
  if (typeof data === "object" && data !== null) {
    const obj = data as Record<string, unknown>;
    if (Array.isArray(obj.files)) return obj.files as UploadedFileDto[];
    if (Array.isArray(obj.uploaded_files))
      return obj.uploaded_files as UploadedFileDto[];
  }
  return [];
}

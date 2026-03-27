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

export type CandidateIntakePayload = {
  full_name: string;
  country_of_residence: string;
  date_of_birth: string;
  grad_program_focus: string;
};

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
  if (!res.ok)
    throw new Error(`GET /candidates/me failed: ${res.status} ${text}`);
  return parseCandidateDto(data as Record<string, unknown>);
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
      grad_program_focus: body.grad_program_focus,
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

export function getApiBaseUrl(): string | null {
  const raw = process.env.NEXT_PUBLIC_API_URL;
  if (!raw) return null;
  let base = raw.trim().replace(/\/$/, "");
  if (!base) return null;
  // Avoid invalid relative fetches if someone omits the scheme (Railway vars often pasted host-only).
  if (!/^https?:\/\//i.test(base)) {
    base = `https://${base}`;
  }
  return base;
}

export async function fetchHealth(): Promise<unknown> {
  const root = getApiBaseUrl();
  if (!root) {
    throw new Error(
      "NEXT_PUBLIC_API_URL is not set. Copy apps/web/.env.example to apps/web/.env.local",
    );
  }
  const res = await fetch(`${root}/health`, {
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
}

export async function enqueueWiringSmoke(): Promise<{ job_id: string }> {
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
  const jobId =
    typeof data === "object" &&
    data !== null &&
    "job_id" in data &&
    typeof (data as { job_id: unknown }).job_id === "string"
      ? (data as { job_id: string }).job_id
      : null;
  if (!jobId) {
    throw new Error(`POST /wiring/smoke: missing job_id in ${text}`);
  }
  return { job_id: jobId };
}

export type WiringSmokeStatusPayload = {
  job_id: string;
  state: string;
  result?: unknown;
  error?: unknown;
};

/** Task 003 — POST /jobs/sample-sleep */
export type SampleSleepEnqueueResponse = {
  ai_run_id: string;
  celery_task_id: string;
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
  if (!aiRunId || !celeryTaskId) {
    throw new Error(`POST /jobs/sample-sleep: missing ids in ${text}`);
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

export async function fetchWiringSmokeStatus(
  jobId: string,
): Promise<WiringSmokeStatusPayload> {
  const root = getApiBaseUrl();
  if (!root) {
    throw new Error(
      "NEXT_PUBLIC_API_URL is not set. Copy apps/web/.env.example to apps/web/.env.local",
    );
  }
  const res = await fetch(
    `${root}/wiring/smoke/${encodeURIComponent(jobId)}`,
    { method: "GET", cache: "no-store" },
  );
  const text = await res.text();
  let data: WiringSmokeStatusPayload;
  try {
    data = text ? JSON.parse(text) : ({} as WiringSmokeStatusPayload);
  } catch {
    throw new Error(`GET /wiring/smoke/${jobId}: invalid JSON (${res.status})`);
  }
  if (!res.ok) {
    throw new Error(`GET /wiring/smoke/${jobId} failed: ${res.status} ${text}`);
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
};

export async function listUploadedFiles(sessionToken?: string | null): Promise<
  UploadedFileDto[]
> {
  const root = getApiBaseUrl();
  if (!root) throw new Error("NEXT_PUBLIC_API_URL is not set");

  const res = await fetch(`${root}/files`, {
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

  // Allow either `{files:[...]}` or `[...]` shapes.
  if (Array.isArray(data)) return data as UploadedFileDto[];
  if (typeof data === "object" && data !== null) {
    const obj = data as Record<string, unknown>;
    if (Array.isArray(obj.files)) return obj.files as UploadedFileDto[];
  }
  return [];
}

export async function uploadFiles(
  files: FileList,
  sessionToken?: string | null,
): Promise<UploadedFileDto[]> {
  const root = getApiBaseUrl();
  if (!root) throw new Error("NEXT_PUBLIC_API_URL is not set");

  const form = new FormData();
  for (const file of Array.from(files)) {
    form.append("files", file);
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

/** Chat */
export type ChatThreadDto = { id: string };

export type ChatMessageDto = {
  id: string;
  role: string;
  content: string;
  created_at?: string;
};

export async function createChatThread(
  sessionToken?: string | null,
): Promise<ChatThreadDto> {
  const root = getApiBaseUrl();
  if (!root) throw new Error("NEXT_PUBLIC_API_URL is not set");

  const res = await fetch(`${root}/chat/threads`, {
    method: "POST",
    cache: "no-store",
    headers: sessionToken
      ? { Authorization: `Bearer ${sessionToken}` }
      : undefined,
  });
  const text = await res.text();
  let data: unknown;
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    throw new Error(`POST /chat/threads: invalid JSON (${res.status})`);
  }
  if (!res.ok) throw new Error(`POST /chat/threads failed: ${res.status} ${text}`);

  const obj = data as Record<string, unknown>;
  const id =
    (typeof obj.thread_id === "string" && obj.thread_id) ||
    (typeof obj.id === "string" && obj.id) ||
    null;
  if (!id) throw new Error(`POST /chat/threads: missing thread id`);
  return { id };
}

export async function fetchChatMessages(
  threadId: string,
  sessionToken?: string | null,
): Promise<ChatMessageDto[]> {
  const root = getApiBaseUrl();
  if (!root) throw new Error("NEXT_PUBLIC_API_URL is not set");

  const res = await fetch(`${root}/chat/threads/${encodeURIComponent(threadId)}/messages`, {
    method: "GET",
    cache: "no-store",
    headers: sessionToken
      ? { Authorization: `Bearer ${sessionToken}` }
      : undefined,
  });
  const text = await res.text();
  let data: unknown;
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    throw new Error(`GET /chat/threads/{id}/messages: invalid JSON (${res.status})`);
  }
  if (!res.ok) throw new Error(`GET messages failed: ${res.status} ${text}`);

  if (Array.isArray(data)) return data as ChatMessageDto[];
  const obj = data as Record<string, unknown>;
  if (Array.isArray(obj.messages)) return obj.messages as ChatMessageDto[];
  return [];
}

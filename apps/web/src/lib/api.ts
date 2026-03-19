/**
 * Base URL for FastAPI. Must be reachable from the **browser** (not from Docker internal hostnames).
 * Use the **API** service’s public URL — not the Next.js frontend URL (GET /health exists only on FastAPI).
 */
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

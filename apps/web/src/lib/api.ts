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

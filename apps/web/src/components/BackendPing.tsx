"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchHealth, getApiBaseUrl } from "@/lib/api";

export function BackendPing() {
  const base = getApiBaseUrl();
  const q = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    enabled: Boolean(base),
  });

  if (!base) {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
        Set <code className="rounded bg-amber-100 px-1">NEXT_PUBLIC_API_URL</code> in{" "}
        <code className="rounded bg-amber-100 px-1">apps/web/.env.local</code> (see{" "}
        <code className="rounded bg-amber-100 px-1">.env.example</code>).
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-neutral-200 bg-white p-4 shadow-sm">
      <h2 className="text-sm font-semibold text-neutral-900">Backend ping</h2>
      <p className="mt-1 text-xs text-neutral-500">
        API: <code className="rounded bg-neutral-100 px-1">{base}</code>
      </p>
      <div className="mt-3 text-sm">
        {q.isPending && <p className="text-neutral-600">Loading…</p>}
        {q.isError && (
          <p className="text-red-600">
            {(q.error as Error).message}
            <span className="mt-2 block text-xs text-neutral-500">
              <strong>404?</strong> <code className="rounded bg-neutral-100 px-1">NEXT_PUBLIC_API_URL</code> must
              be the <strong>FastAPI</strong> Railway URL (uvicorn), not this Next.js site’s URL.
              <br />
              <strong>Check API directly:</strong>{" "}
              <code className="rounded bg-neutral-100 px-1">curl -i {base}/health</code> — expect{" "}
              <code className="rounded bg-neutral-100 px-1">{`{"status":"ok"}`}</code>
              <br />
              <strong>CORS:</strong> on the API, set{" "}
              <code className="rounded bg-neutral-100 px-1">CORS_ORIGINS</code> to this page’s origin,
              then redeploy the API.
            </span>
          </p>
        )}
        {q.isSuccess && (
          <pre className="overflow-auto rounded bg-neutral-950 p-3 text-xs text-neutral-100">
            {JSON.stringify(q.data, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
}

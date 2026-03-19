"use client";

import { useCallback, useState } from "react";
import {
  enqueueWiringSmoke,
  fetchWiringSmokeStatus,
  getApiBaseUrl,
} from "@/lib/api";

type Phase = "idle" | "running" | "done" | "error";

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

export function WiringSmoke() {
  const base = getApiBaseUrl();
  const [phase, setPhase] = useState<Phase>("idle");
  const [log, setLog] = useState<string>("(not run)");
  const [lastPayload, setLastPayload] = useState<unknown>(null);

  const run = useCallback(async () => {
    if (!base) return;
    setPhase("running");
    setLog("Enqueueing…");
    setLastPayload(null);
    try {
      const { job_id: jobId } = await enqueueWiringSmoke();
      setLog(`Enqueued job_id=${jobId}\nPolling…`);

      const deadline = Date.now() + 60_000;
      let lastState = "";
      while (Date.now() < deadline) {
        const payload = await fetchWiringSmokeStatus(jobId);
        setLastPayload(payload);
        if (payload.state !== lastState) {
          lastState = payload.state;
          setLog((prev) => `${prev}\nState: ${payload.state}`);
        }
        if (
          payload.state === "SUCCESS" ||
          payload.state === "FAILURE" ||
          payload.state === "REVOKED"
        ) {
          setPhase("done");
          return;
        }
        await sleep(1000);
      }
      setPhase("error");
      setLog((prev) => `${prev}\nTimed out after 60s`);
    } catch (e) {
      setPhase("error");
      setLog(String(e));
    }
  }, [base]);

  if (!base) {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
        Set <code className="rounded bg-amber-100 px-1">NEXT_PUBLIC_API_URL</code> in{" "}
        <code className="rounded bg-amber-100 px-1">apps/web/.env.local</code> to run the wiring
        smoke test.
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-neutral-200 bg-white p-4 shadow-sm">
      <h2 className="text-sm font-semibold text-neutral-900">Wiring smoke test</h2>
      <p className="mt-1 text-xs text-neutral-500">
        <code className="rounded bg-neutral-100 px-1">POST /wiring/smoke</code> then poll{" "}
        <code className="rounded bg-neutral-100 px-1">GET /wiring/smoke/&lt;job_id&gt;</code> — same
        as <code className="rounded bg-neutral-100 px-1">scripts/wiring_smoke_test.py</code>.
        Requires a running <strong>Celery worker</strong>.
      </p>
      <div className="mt-3 flex gap-2">
        <button
          type="button"
          onClick={() => void run()}
          disabled={phase === "running"}
          className="rounded-md border border-neutral-300 bg-white px-3 py-1.5 text-sm font-medium text-neutral-900 shadow-sm hover:bg-neutral-50 disabled:opacity-50"
        >
          {phase === "running" ? "Running…" : "Run wiring smoke"}
        </button>
      </div>
      <pre className="mt-3 max-h-40 overflow-auto whitespace-pre-wrap rounded bg-neutral-950 p-3 text-xs text-neutral-100">
        {log}
      </pre>
      {lastPayload !== null && (
        <pre className="mt-2 overflow-auto rounded bg-neutral-100 p-3 text-xs text-neutral-900">
          {JSON.stringify(lastPayload, null, 2)}
        </pre>
      )}
    </div>
  );
}

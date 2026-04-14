"use client";

import { useCallback, useState } from "react";
import { enqueueWiringSmoke, getApiBaseUrl } from "@/lib/api";

type Phase = "idle" | "running" | "done" | "error";

export function WiringSmoke() {
  const base = getApiBaseUrl();
  const [phase, setPhase] = useState<Phase>("idle");
  const [log, setLog] = useState<string>("(not run)");
  const [lastPayload, setLastPayload] = useState<unknown>(null);

  const run = useCallback(async () => {
    if (!base) return;
    setPhase("running");
    setLog("Running…");
    setLastPayload(null);
    try {
      const payload = await enqueueWiringSmoke();
      setLastPayload(payload);
      setPhase("done");
      setLog(
        `Done.\ndb_connected=${payload.db_connected}`,
      );
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
        <code className="rounded bg-neutral-100 px-1">POST /wiring/smoke</code> (in-process Redis
        + DB connectivity check).
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

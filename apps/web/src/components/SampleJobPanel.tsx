"use client";

import { useCallback, useEffect, useState } from "react";

import { useOptionalCandidate } from "@/context/SessionContext";
import {
  enqueueSampleSleep,
  fetchAiRunStatus,
  fetchCeleryTaskMeta,
  getApiBaseUrl,
  type AiRunStatusPayload,
  type CeleryTaskMetaPayload,
} from "@/lib/api";

type Phase = "idle" | "running" | "done" | "error";

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

function isTerminalAiRunStatus(status: string) {
  const s = status.toLowerCase();
  return s === "succeeded" || s === "failed" || s === "cancelled";
}

export function SampleJobPanel() {
  const base = getApiBaseUrl();
  const loggedInCandidate = useOptionalCandidate();
  const [phase, setPhase] = useState<Phase>("idle");
  const [sleepSeconds, setSleepSeconds] = useState("0.5");
  const [simulateTransientFail, setSimulateTransientFail] = useState(false);
  const [correlationId, setCorrelationId] = useState("");
  const [candidateId, setCandidateId] = useState("");

  useEffect(() => {
    if (loggedInCandidate?.id) {
      setCandidateId((prev) => (prev.trim() === "" ? loggedInCandidate.id : prev));
    }
  }, [loggedInCandidate?.id]);
  const [log, setLog] = useState<string>("(not run)");
  const [lastAiRun, setLastAiRun] = useState<AiRunStatusPayload | null>(null);
  const [lastCelery, setLastCelery] = useState<CeleryTaskMetaPayload | null>(
    null,
  );

  const run = useCallback(async () => {
    if (!base) return;
    const sec = Number.parseFloat(sleepSeconds);
    if (Number.isNaN(sec) || sec < 0 || sec > 300) {
      setPhase("error");
      setLog("sleep_seconds must be a number between 0 and 300.");
      return;
    }

    setPhase("running");
    setLog("Enqueueing sample job…");
    setLastAiRun(null);
    setLastCelery(null);

    try {
      const { ai_run_id: aiRunId, celery_task_id: celeryTaskId } =
        await enqueueSampleSleep({
          sleep_seconds: sec,
          simulate_transient_fail: simulateTransientFail,
          correlation_id: correlationId || undefined,
          candidate_id: candidateId.trim() || undefined,
        });
      setLog(
        `Enqueued.\nai_run_id=${aiRunId}\ncelery_task_id=${celeryTaskId}\nPolling ai_run…`,
      );

      const deadline = Date.now() + 120_000;
      let lastStatus = "";
      while (Date.now() < deadline) {
        const ai = await fetchAiRunStatus(aiRunId);
        setLastAiRun(ai);
        if (ai.status !== lastStatus) {
          lastStatus = ai.status;
          setLog((prev) => `${prev}\nai_run.status: ${ai.status}`);
        }
        if (isTerminalAiRunStatus(ai.status)) {
          try {
            const celery = await fetchCeleryTaskMeta(celeryTaskId);
            setLastCelery(celery);
            setLog((prev) => `${prev}\nCelery state: ${celery.state}`);
          } catch {
            setLog((prev) => `${prev}\n(Celery meta fetch skipped or failed)`);
          }
          setPhase("done");
          return;
        }
        await sleep(1000);
      }
      setPhase("error");
      setLog((prev) => `${prev}\nTimed out after 120s (ai_run still not terminal)`);
    } catch (e) {
      setPhase("error");
      setLog(String(e));
    }
  }, [
    base,
    sleepSeconds,
    simulateTransientFail,
    correlationId,
    candidateId,
  ]);

  if (!base) {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
        Set <code className="rounded bg-amber-100 px-1">NEXT_PUBLIC_API_URL</code>{" "}
        to your <strong>FastAPI</strong> Railway URL (build-time var). Add your{" "}
        <strong>frontend origin</strong> to API <code className="rounded bg-amber-100 px-1">CORS_ORIGINS</code>.
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-neutral-200 bg-white p-4 shadow-sm">
      <h2 className="text-sm font-semibold text-neutral-900">
        Sample Celery job (Task 003)
      </h2>
      <p className="mt-1 text-xs text-neutral-500">
        <code className="rounded bg-neutral-100 px-1">POST /jobs/sample-sleep</code>{" "}
        then <code className="rounded bg-neutral-100 px-1">GET /jobs/ai-runs/&lt;id&gt;</code>.
        Needs a running <strong>Celery worker</strong> and <strong>migrated DB</strong> on the API
        (same as Railway: web runs migrations on boot, worker runs tasks).
      </p>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <label className="block text-xs text-neutral-600">
          <span className="font-medium text-neutral-800">sleep_seconds</span>
          <input
            type="text"
            inputMode="decimal"
            value={sleepSeconds}
            onChange={(e) => setSleepSeconds(e.target.value)}
            className="mt-1 w-full rounded border border-neutral-300 px-2 py-1.5 text-sm"
            disabled={phase === "running"}
          />
        </label>
        <label className="block text-xs text-neutral-600">
          <span className="font-medium text-neutral-800">correlation_id (optional)</span>
          <input
            type="text"
            value={correlationId}
            onChange={(e) => setCorrelationId(e.target.value)}
            placeholder="e.g. railway-fe-1"
            className="mt-1 w-full rounded border border-neutral-300 px-2 py-1.5 text-sm"
            disabled={phase === "running"}
          />
        </label>
        <label className="block text-xs text-neutral-600 sm:col-span-2">
          <span className="font-medium text-neutral-800">candidate_id (optional UUID)</span>
          <input
            type="text"
            value={candidateId}
            onChange={(e) => setCandidateId(e.target.value)}
            placeholder="Leave empty unless you have a seeded candidate"
            className="mt-1 w-full rounded border border-neutral-300 px-2 py-1.5 text-sm font-mono text-xs"
            disabled={phase === "running"}
          />
        </label>
        <label className="flex items-center gap-2 text-xs text-neutral-700 sm:col-span-2">
          <input
            type="checkbox"
            checked={simulateTransientFail}
            onChange={(e) => setSimulateTransientFail(e.target.checked)}
            disabled={phase === "running"}
          />
          <span>
            <strong>simulate_transient_fail</strong> (demo: one retry on first attempt)
          </span>
        </label>
      </div>
      <div className="mt-3 flex gap-2">
        <button
          type="button"
          onClick={() => void run()}
          disabled={phase === "running"}
          className="rounded-md border border-neutral-300 bg-white px-3 py-1.5 text-sm font-medium text-neutral-900 shadow-sm hover:bg-neutral-50 disabled:opacity-50"
        >
          {phase === "running" ? "Running…" : "Run sample job"}
        </button>
      </div>
      <pre className="mt-3 max-h-36 overflow-auto whitespace-pre-wrap rounded bg-neutral-950 p-3 text-xs text-neutral-100">
        {log}
      </pre>
      {lastAiRun !== null && (
        <div className="mt-2">
          <p className="text-xs font-medium text-neutral-600">Last ai_run</p>
          <pre className="mt-1 max-h-48 overflow-auto rounded bg-neutral-100 p-3 text-xs text-neutral-900">
            {JSON.stringify(lastAiRun, null, 2)}
          </pre>
        </div>
      )}
      {lastCelery !== null && (
        <div className="mt-2">
          <p className="text-xs font-medium text-neutral-600">Celery task</p>
          <pre className="mt-1 max-h-32 overflow-auto rounded bg-neutral-100 p-3 text-xs text-neutral-900">
            {JSON.stringify(lastCelery, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

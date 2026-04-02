"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { reviewCandidateProfile, submitCandidateProfileAnswers, type ProfileGapQuestionDto } from "@/lib/api";

type Props = {
  sessionToken: string;
  onCompleteChange?: (complete: boolean) => void;
};

export function FinalQuestionsStep({ sessionToken, onCompleteChange }: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reviewLoading, setReviewLoading] = useState(true);
  const [missing, setMissing] = useState<ProfileGapQuestionDto[]>([]);
  const [score, setScore] = useState(0);
  const [complete, setComplete] = useState(false);

  const [answer, setAnswer] = useState("");

  const current = missing[0] ?? null;

  const refresh = useCallback(async () => {
    setError(null);
    setReviewLoading(true);
    try {
      const r = await reviewCandidateProfile(sessionToken);
      setMissing(r.missing ?? []);
      setScore(r.completeness_score ?? 0);
      setComplete(Boolean(r.profile_complete));
      onCompleteChange?.(Boolean(r.profile_complete));
    } catch (e) {
      setError(String(e));
    } finally {
      setReviewLoading(false);
    }
  }, [sessionToken, onCompleteChange]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const progressLabel = useMemo(() => {
    if (complete) return "Profile complete";
    const pct = Math.max(0, Math.min(100, score));
    return `Profile ${pct}% complete`;
  }, [complete, score]);

  const submit = useCallback(async () => {
    if (!current) return;
    const trimmed = answer.trim();
    if (!trimmed) return;

    setBusy(true);
    setError(null);
    try {
      await submitCandidateProfileAnswers(sessionToken, { [current.key]: trimmed });
      setAnswer("");
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }, [answer, current, refresh, sessionToken]);

  return (
    <div className="rounded-xl border border-[#c4c6cd]/20 bg-white">
      <div className="border-b border-[#c4c6cd]/15 bg-surface-low px-4 py-3">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="text-sm font-semibold text-neutral-900">Final Questions</div>
            <div className="mt-0.5 text-[11px] text-neutral-500">
              After each answer, we re-check your profile and only ask what’s still needed.
            </div>
          </div>
          <div className="text-[11px] font-medium text-neutral-500">{progressLabel}</div>
        </div>
      </div>

      <div className="px-4 py-4">
        {reviewLoading ? (
          <div className="text-sm text-neutral-500">Checking what’s missing…</div>
        ) : complete ? (
          <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
            You’re all set — your profile is complete.
          </div>
        ) : current ? (
          <div className="space-y-3">
            <div className="text-sm font-medium text-neutral-900">{current.question}</div>
            <textarea
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              placeholder="Type your answer…"
              className="min-h-[96px] w-full resize-none rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-900 shadow-sm focus:border-neutral-400 focus:outline-none focus:ring-2 focus:ring-neutral-200"
              disabled={busy}
            />
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={() => void submit()}
                disabled={busy || answer.trim().length === 0}
                className="rounded-md bg-neutral-900 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-neutral-800 disabled:opacity-50"
              >
                {busy ? "Saving…" : "Submit answer"}
              </button>
              <button
                type="button"
                onClick={() => void refresh()}
                disabled={busy}
                className="rounded-md border border-neutral-200 bg-white px-4 py-2 text-sm font-semibold text-neutral-800 hover:bg-neutral-50 disabled:opacity-50"
              >
                Re-check
              </button>
              <div className="text-xs text-neutral-500">
                Remaining questions: {missing.length}
              </div>
            </div>
          </div>
        ) : (
          <div className="text-sm text-neutral-600">
            No remaining questions found. Click “Re-check” to refresh.
          </div>
        )}

        {error ? (
          <div className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
            {error}
          </div>
        ) : null}
      </div>
    </div>
  );
}


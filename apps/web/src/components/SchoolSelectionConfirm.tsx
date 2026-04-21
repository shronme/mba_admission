"use client";

import { useCallback, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import type { AdmissionEvaluationResultDto, CandidateDto, SelectedSchoolRow } from "@/lib/api";
import { confirmSchoolSelection, createAdvisorThread } from "@/lib/api";

type Props = {
  sessionToken: string;
  candidate: CandidateDto;
  result: AdmissionEvaluationResultDto;
};

function readSelectedSchoolsFromProfile(candidate: CandidateDto): SelectedSchoolRow[] | null {
  const attrs = (candidate.profile?.attributes ?? null) as Record<string, unknown> | null;
  const raw = attrs?.selected_schools;
  if (!Array.isArray(raw)) return null;
  const out: SelectedSchoolRow[] = [];
  for (const row of raw) {
    if (!row || typeof row !== "object") continue;
    const r = row as Record<string, unknown>;
    const school = typeof r.school === "string" ? r.school : "";
    const slug = typeof r.program_slug === "string" ? r.program_slug : "";
    const disp = typeof r.program_display_name === "string" ? r.program_display_name : undefined;
    if (!school.trim() || !slug.trim()) continue;
    out.push({ school, program_slug: slug, program_display_name: disp });
  }
  return out.length ? out : null;
}

export function SchoolSelectionConfirm({ sessionToken, candidate, result }: Props) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const existingSelected = useMemo(
    () => readSelectedSchoolsFromProfile(candidate),
    [candidate],
  );

  const primaryRows = useMemo(() => {
    return result.primary.map((p) => ({
      school: p.school,
      program_slug: p.program_slug,
      program_display_name: p.program_display_name,
      key: `p|${p.school}|${p.program_slug}`,
      defaultChecked: true,
    }));
  }, [result.primary]);

  const extraRows = useMemo(() => {
    return result.extra.map((e, idx) => ({
      school: e.school,
      program_slug: e.program_slug ?? `extra-${idx}`,
      program_display_name: e.program_display_name,
      key: `e|${e.school}|${e.program_slug ?? idx}`,
      defaultChecked: false,
      disabled: !e.program_slug, // if backend didn't provide, we can't confirm it yet
    }));
  }, [result.extra]);

  const [checked, setChecked] = useState<Record<string, boolean>>(() => {
    const initial: Record<string, boolean> = {};
    for (const row of primaryRows) initial[row.key] = true;
    for (const row of extraRows) initial[row.key] = false;
    return initial;
  });

  const selected = useMemo(() => {
    const items: SelectedSchoolRow[] = [];
    for (const row of primaryRows) {
      if (checked[row.key]) items.push(row);
    }
    for (const row of extraRows) {
      if (row.disabled) continue;
      if (checked[row.key]) items.push(row);
    }
    return items.map((r) => ({
      school: r.school,
      program_slug: r.program_slug,
      program_display_name: r.program_display_name,
    }));
  }, [checked, extraRows, primaryRows]);

  const canConfirm = selected.length > 0 && !busy;

  const confirm = useCallback(async () => {
    if (!canConfirm) return;
    setBusy(true);
    setError(null);
    try {
      await confirmSchoolSelection(sessionToken, selected);
      await createAdvisorThread(sessionToken, { new: false });
      router.push("/advisor");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, [canConfirm, router, selected, sessionToken]);

  if (existingSelected) {
    return (
      <div className="rounded-2xl border border-[#c4c6cd]/20 bg-white p-6 shadow-sm sm:p-8">
        <p className="text-sm font-semibold text-brand-900">You’ve already confirmed your school list.</p>
        <p className="mt-2 text-sm text-on-surface-variant">
          Continue your strategy conversation with your advisor.
        </p>
        <button
          type="button"
          className="group/btn mt-6 flex items-center justify-center gap-3 rounded-lg bg-accent px-8 py-4 text-sm font-bold text-brand-900 shadow-xl shadow-accent/20 transition-transform hover:scale-[1.02]"
          onClick={() => router.push("/advisor")}
        >
          Continue with your advisor <span aria-hidden>→</span>
        </button>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-[#c4c6cd]/20 bg-white p-6 shadow-sm sm:p-8">
      <h3 className="font-serif text-2xl text-brand-900">Confirm your school list</h3>
      <p className="mt-2 text-sm text-on-surface-variant">
        We’ll tailor your next-step advice to the schools you select.
      </p>

      <div className="mt-6 space-y-3">
        {primaryRows.map((row) => (
          <label key={row.key} className="flex cursor-pointer items-start gap-3 rounded-lg border border-[#c4c6cd]/15 bg-surface-low px-4 py-3">
            <input
              type="checkbox"
              className="mt-0.5 h-4 w-4 shrink-0 rounded border-[#c4c6cd]/40"
              checked={Boolean(checked[row.key])}
              onChange={(e) => setChecked((prev) => ({ ...prev, [row.key]: e.target.checked }))}
              disabled={busy}
            />
            <span className="text-sm text-neutral-900">
              <span className="font-semibold">{row.school}</span>
              {row.program_display_name ? (
                <span className="text-on-surface-variant"> — {row.program_display_name}</span>
              ) : null}
            </span>
          </label>
        ))}
      </div>

      {extraRows.length > 0 ? (
        <div className="mt-8 border-t border-[#c4c6cd]/15 pt-6">
          <div className="text-xs font-bold uppercase tracking-widest text-on-surface-variant">
            Additional recommendations
          </div>
          <div className="mt-4 space-y-3">
            {extraRows.map((row) => (
              <label
                key={row.key}
                className={[
                  "flex items-start gap-3 rounded-lg border border-[#c4c6cd]/15 bg-white px-4 py-3",
                  row.disabled ? "opacity-60" : "cursor-pointer hover:bg-surface-low",
                ].join(" ")}
              >
                <input
                  type="checkbox"
                  className="mt-0.5 h-4 w-4 shrink-0 rounded border-[#c4c6cd]/40"
                  checked={Boolean(checked[row.key])}
                  onChange={(e) => setChecked((prev) => ({ ...prev, [row.key]: e.target.checked }))}
                  disabled={busy || row.disabled}
                />
                <span className="text-sm text-neutral-900">
                  <span className="font-semibold">{row.school}</span>
                  {row.program_display_name ? (
                    <span className="text-on-surface-variant"> — {row.program_display_name}</span>
                  ) : null}
                  {row.disabled ? (
                    <span className="ml-2 text-xs text-on-surface-variant">
                      (not available to confirm yet)
                    </span>
                  ) : null}
                </span>
              </label>
            ))}
          </div>
        </div>
      ) : null}

      {error ? (
        <div className="mt-5 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">
          {error}
        </div>
      ) : null}

      <div className="mt-6 flex flex-col items-stretch gap-3 sm:flex-row sm:items-center sm:justify-between">
        <button
          type="button"
          onClick={() => void confirm()}
          disabled={!canConfirm}
          aria-disabled={!canConfirm}
          className="group/btn flex items-center justify-center gap-3 rounded-lg bg-accent px-8 py-4 text-sm font-bold text-brand-900 shadow-xl shadow-accent/20 transition-transform hover:scale-[1.02] disabled:opacity-50"
        >
          {busy ? "Confirming…" : "Confirm & get advice"}
          <span aria-hidden>→</span>
        </button>
        <p className="text-xs text-on-surface-variant">
          {selected.length === 0 ? "Select at least one program to continue." : `${selected.length} selected`}
        </p>
      </div>
    </div>
  );
}


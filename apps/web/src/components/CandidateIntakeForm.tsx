"use client";

import { useEffect, useRef, useState } from "react";

import { format } from "date-fns";
import { DayPicker } from "react-day-picker";

import { SearchableSelect } from "@/components/SearchableSelect";
import type { CandidateDto } from "@/lib/api";
import { patchCandidateIntake } from "@/lib/api";
import { COUNTRY_NAMES } from "@/data/countries";
import { GRAD_PROGRAM_FOCUS_OPTIONS } from "@/data/gradProgramFocusOptions";

import "react-day-picker/style.css";

const COUNTRY_OPTIONS = COUNTRY_NAMES.map((name) => ({ value: name, label: name }));

type Props = {
  sessionToken: string;
  initialFullName: string;
  onComplete: (candidate: CandidateDto) => void;
};

export function CandidateIntakeForm({ sessionToken, initialFullName, onComplete }: Props) {
  const [fullName, setFullName] = useState(initialFullName);
  const [country, setCountry] = useState("");
  const [dob, setDob] = useState<Date | undefined>(undefined);
  const [programFocus, setProgramFocus] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dobOpen, setDobOpen] = useState(false);

  const dobWrapRef = useRef<HTMLDivElement>(null);
  const today = new Date();

  useEffect(() => {
    if (!dobOpen) return;
    const onDocMouseDown = (e: MouseEvent) => {
      if (!dobWrapRef.current?.contains(e.target as Node)) setDobOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setDobOpen(false);
    };
    document.addEventListener("mousedown", onDocMouseDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocMouseDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [dobOpen]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!country.trim()) {
      setError("Please select your country of residence.");
      return;
    }
    if (!programFocus) {
      setError("Please select the program you are targeting.");
      return;
    }
    if (!dob) {
      setError("Please select your date of birth.");
      return;
    }

    const isoDob = format(dob, "yyyy-MM-dd");

    setBusy(true);
    try {
      const updated = await patchCandidateIntake(sessionToken, {
        full_name: fullName,
        country_of_residence: country,
        date_of_birth: isoDob,
        grad_program_focus: programFocus,
      });
      onComplete(updated);
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex min-h-full items-center justify-center overflow-y-auto px-4 py-10">
      {/* Backdrop */}
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 bg-gradient-to-b from-slate-950 via-indigo-950 to-slate-950"
      />
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 bg-[radial-gradient(ellipse_90%_60%_at_50%_-10%,rgba(99,102,241,0.28),transparent_55%)]"
      />
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 bg-[radial-gradient(ellipse_70%_50%_at_100%_100%,rgba(23,114,76,0.12),transparent)]"
      />
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 opacity-[0.35]"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='80' height='80' viewBox='0 0 80 80'%3E%3Cg fill='none' stroke='%23ffffff' stroke-opacity='0.06'%3E%3Cpath d='M0 0h80v80H0z'/%3E%3Cpath d='M40 0v80M0 40h80'/%3E%3C/g%3E%3C/svg%3E")`,
        }}
      />

      <div className="relative my-auto w-full max-w-md">
        <div className="rounded-2xl border border-white/10 bg-white/95 p-6 shadow-2xl shadow-slate-950/40 ring-1 ring-white/20 backdrop-blur-md">
          <h2 className="text-xl font-semibold tracking-tight text-neutral-900">Tell us about you</h2>
          <p className="mt-1.5 text-sm leading-relaxed text-neutral-600">
            A few details so we can tailor your grad-school plan. You only do this once.
          </p>
          <form onSubmit={(e) => void submit(e)} className="mt-6 space-y-4">
            <div>
              <label htmlFor="intake-full-name" className="block text-xs font-medium text-neutral-700">
                Full name
              </label>
              <input
                id="intake-full-name"
                name="full_name"
                type="text"
                autoComplete="name"
                required
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="mt-1 w-full rounded-lg border border-neutral-200 bg-white px-3 py-2.5 text-sm shadow-sm transition-colors focus:border-forest-500 focus:outline-none focus:ring-2 focus:ring-forest-500/20"
                disabled={busy}
              />
            </div>

            <SearchableSelect
              id="intake-country"
              label="Country of residence"
              options={COUNTRY_OPTIONS}
              value={country}
              onChange={setCountry}
              disabled={busy}
              placeholder="Search countries…"
              emptyMessage="No country matches"
              maxVisible={200}
            />

            <div ref={dobWrapRef} className="relative">
              <span className="block text-xs font-medium text-neutral-700">Date of birth</span>
              <button
                type="button"
                id="intake-dob-trigger"
                disabled={busy}
                aria-expanded={dobOpen}
                aria-haspopup="dialog"
                aria-label="Open date of birth calendar"
                onClick={() => setDobOpen((o) => !o)}
                className="mt-1 flex w-full items-center gap-2 rounded-lg border border-neutral-200 bg-white px-3 py-2.5 text-left text-sm shadow-sm transition-colors hover:border-neutral-300 focus:border-forest-500 focus:outline-none focus:ring-2 focus:ring-forest-500/20 disabled:opacity-50"
              >
                <span className={dob ? "text-neutral-900" : "text-neutral-400"}>
                  {dob ? format(dob, "MMMM d, yyyy") : "Select date of birth"}
                </span>
                <svg
                  className="ml-auto h-4 w-4 shrink-0 text-neutral-400"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={1.5}
                  aria-hidden
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5a2.25 2.25 0 002.25-2.25m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5a2.25 2.25 0 012.25 2.25v7.5"
                  />
                </svg>
              </button>
              {dobOpen ? (
                <div
                  role="dialog"
                  aria-label="Choose date of birth"
                  className="absolute left-0 right-0 z-[60] mt-2 flex justify-center sm:left-auto sm:right-0 sm:justify-end"
                >
                  <div className="intake-dob-popover w-full max-w-[238px] rounded-xl border border-neutral-200/90 bg-white p-2 shadow-xl ring-1 ring-black/5">
                    <DayPicker
                      mode="single"
                      selected={dob}
                      onSelect={(d) => {
                        setDob(d);
                        setDobOpen(false);
                      }}
                      captionLayout="dropdown"
                      startMonth={new Date(1900, 0)}
                      endMonth={today}
                      defaultMonth={dob ?? new Date(2000, 0)}
                      disabled={{ after: today }}
                      navLayout="after"
                    />
                  </div>
                </div>
              ) : null}
            </div>

            <SearchableSelect
              id="intake-program"
              label="Program you are targeting"
              options={GRAD_PROGRAM_FOCUS_OPTIONS}
              value={programFocus}
              onChange={setProgramFocus}
              disabled={busy}
              placeholder="Search programs (MBA, PhD, MS, …)"
              emptyMessage="No program matches"
              maxVisible={200}
            />

            {error ? (
              <p className="text-sm text-red-600" role="alert">
                {error}
              </p>
            ) : null}
            <button
              type="submit"
              disabled={busy}
              className="w-full rounded-lg bg-forest-700 px-4 py-2.5 text-sm font-semibold text-white shadow-md transition-colors hover:bg-forest-800 disabled:opacity-50"
            >
              {busy ? "Saving…" : "Continue to dashboard"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

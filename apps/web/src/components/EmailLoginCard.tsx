"use client";

import { useState } from "react";

import { useSession } from "@/context/SessionContext";
import { getApiBaseUrl } from "@/lib/api";

export function EmailLoginCard() {
  const { signIn } = useSession();
  const base = getApiBaseUrl();
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!base) return;
    setBusy(true);
    try {
      await signIn(email);
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  };

  if (!base) {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
        Set <code className="rounded bg-amber-100 px-1">NEXT_PUBLIC_API_URL</code> to your FastAPI
        URL (local or Railway).
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-neutral-200 bg-white p-6 shadow-sm">
      <h2 className="text-lg font-semibold text-neutral-900">Continue with email</h2>
      <p className="mt-1 text-sm text-neutral-600">
        Enter your email to access your dashboard.
      </p>
      <form onSubmit={(e) => void submit(e)} className="mt-4 space-y-4">
        <div>
          <label htmlFor="email" className="block text-xs font-medium text-neutral-700">
            Email
          </label>
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 w-full rounded-md border border-neutral-300 px-3 py-2 text-sm shadow-sm focus:border-neutral-500 focus:outline-none focus:ring-1 focus:ring-neutral-500"
            placeholder="you@school.edu"
            disabled={busy}
          />
        </div>
        {error && (
          <p className="text-sm text-red-600" role="alert">
            {error}
          </p>
        )}
        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-md bg-neutral-900 px-4 py-2.5 text-sm font-medium text-white shadow hover:bg-neutral-800 disabled:opacity-50 sm:w-auto"
        >
          {busy ? "Working…" : "Continue"}
        </button>
      </form>
    </div>
  );
}

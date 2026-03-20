"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import type { CandidateDto, EnterResponse } from "@/lib/api";

const STORAGE_KEY = "mba_admissions_candidate_session_v1";

type SessionState = EnterResponse | null;

type SessionContextValue = {
  session: SessionState;
  setSession: (value: SessionState) => void;
  signOut: () => void;
};

const SessionContext = createContext<SessionContextValue | null>(null);

function readStoredSession(): SessionState {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as EnterResponse;
    // If the cached session is from before `session_token` existed,
    // treat it as unauthenticated so we don't call protected endpoints with no auth header.
    if (!parsed?.candidate?.id) return null;
    if (typeof parsed.session_token !== "string" || !parsed.session_token) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [session, setSessionState] = useState<SessionState>(null);

  useEffect(() => {
    setSessionState(readStoredSession());
  }, []);

  const setSession = useCallback((value: SessionState) => {
    setSessionState(value);
    if (typeof window === "undefined") return;
    if (value === null) {
      localStorage.removeItem(STORAGE_KEY);
    } else {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(value));
    }
  }, []);

  const signOut = useCallback(() => {
    setSession(null);
  }, [setSession]);

  const value = useMemo(
    () => ({ session, setSession, signOut }),
    [session, setSession, signOut],
  );

  return (
    <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
  );
}

export function useSession(): SessionContextValue {
  const ctx = useContext(SessionContext);
  if (!ctx) {
    throw new Error("useSession must be used within SessionProvider");
  }
  return ctx;
}

export function useOptionalCandidate(): CandidateDto | null {
  const ctx = useContext(SessionContext);
  return ctx?.session?.candidate ?? null;
}

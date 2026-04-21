"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import type { AdminDto, AuthEnterResponse, CandidateDto } from "@/lib/api";
import { authEnter } from "@/lib/api";

const STORAGE_KEY = "mba_admissions_session_v2";

export type AppSession = {
  role: "candidate" | "admin";
  session_token: string;
  candidate?: CandidateDto;
  admin?: AdminDto;
};

type SessionContextValue = {
  session: AppSession | null;
  /**
   * True once we've attempted to read the persisted session from localStorage.
   * Until this flips to true, consumers cannot tell the difference between
   * "user is signed out" and "we just haven't rehydrated yet", so route guards
   * must NOT redirect based on `session == null` while `hydrated === false`.
   */
  hydrated: boolean;
  setSession: (value: AppSession | null) => void;
  signIn: (email: string) => Promise<AuthEnterResponse>;
  signOut: () => void;
};

const SessionContext = createContext<SessionContextValue | null>(null);

function readStoredSession(): AppSession | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as AppSession;
    if (!parsed?.role || !parsed?.session_token) return null;
    if (parsed.role === "candidate" && !parsed.candidate?.id) return null;
    if (parsed.role === "admin" && !parsed.admin?.id) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [session, setSessionState] = useState<AppSession | null>(null);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setSessionState(readStoredSession());
    setHydrated(true);
  }, []);

  const setSession = useCallback((value: AppSession | null) => {
    setSessionState(value);
    if (typeof window === "undefined") return;
    if (value === null) {
      localStorage.removeItem(STORAGE_KEY);
    } else {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(value));
    }
  }, []);

  const signIn = useCallback(
    async (email: string): Promise<AuthEnterResponse> => {
      const res = await authEnter({ email });
      const appSession: AppSession = {
        role: res.role,
        session_token: res.session_token,
        candidate: res.candidate,
        admin: res.admin,
      };
      setSession(appSession);
      return res;
    },
    [setSession],
  );

  const signOut = useCallback(() => {
    setSession(null);
  }, [setSession]);

  const value = useMemo(
    () => ({ session, hydrated, setSession, signIn, signOut }),
    [session, hydrated, setSession, signIn, signOut],
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

/** Convenience: returns the candidate dto when role=candidate, else null */
export function useOptionalCandidate(): CandidateDto | null {
  const ctx = useContext(SessionContext);
  if (!ctx?.session || ctx.session.role !== "candidate") return null;
  return ctx.session.candidate ?? null;
}

/** Convenience: returns the admin dto when role=admin, else null */
export function useOptionalAdmin(): AdminDto | null {
  const ctx = useContext(SessionContext);
  if (!ctx?.session || ctx.session.role !== "admin") return null;
  return ctx.session.admin ?? null;
}

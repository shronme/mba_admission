"use client";

import type { ReactNode } from "react";

import { useSession } from "@/context/SessionContext";

export function HomeGate({
  fallback,
  authenticated,
  adminAuthenticated,
}: {
  fallback: ReactNode;
  authenticated: ReactNode;
  adminAuthenticated: ReactNode;
}) {
  const { session } = useSession();

  if (!session) return fallback;
  if (session.role === "admin") return adminAuthenticated;
  return authenticated;
}

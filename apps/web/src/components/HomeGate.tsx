"use client";

import type { ReactNode } from "react";

import { useSession } from "@/context/SessionContext";

export function HomeGate({
  fallback,
  authenticated,
}: {
  fallback: ReactNode;
  authenticated: ReactNode;
}) {
  const { session } = useSession();
  return session ? authenticated : fallback;
}

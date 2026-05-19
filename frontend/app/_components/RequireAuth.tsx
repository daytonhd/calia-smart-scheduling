"use client";

import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { useAuth } from "./AuthProvider";

// Renders children only when the user is authenticated. Returns null while
// loading or after kicking the user to /login — keeps protected pages from
// firing their data-fetching useEffects on behalf of a logged-out visitor.
export function RequireAuth({ children }: { children: ReactNode }) {
  const { isLoading, isAuthenticated } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/login");
    }
  }, [isLoading, isAuthenticated, router]);

  if (isLoading) {
    return <div className="route-loading">Loading…</div>;
  }

  if (!isAuthenticated) {
    return null;
  }

  return <>{children}</>;
}

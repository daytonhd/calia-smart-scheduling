"use client";

import { useRouter } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  ApiError,
  getCurrentUser,
  login as apiLogin,
  signup as apiSignup,
} from "@/lib/api";
import {
  clearStoredToken,
  getStoredToken,
  setStoredToken,
} from "@/lib/auth";
import type { LoginBody, SignupBody, User } from "@/lib/types";

interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (body: LoginBody) => Promise<void>;
  signup: (body: SignupBody) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  // Start in the loading state so RequireAuth doesn't redirect before we
  // have a chance to hydrate from localStorage on mount.
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const token = getStoredToken();
    if (!token) {
      setIsLoading(false);
      return;
    }

    let cancelled = false;
    getCurrentUser()
      .then((u) => {
        if (!cancelled) setUser(u);
      })
      .catch((err) => {
        // Stale or invalid token — wipe it so future requests don't keep
        // sending a header the backend will reject.
        if (err instanceof ApiError && err.status === 401) {
          clearStoredToken();
        }
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(
    async (body: LoginBody) => {
      const res = await apiLogin(body);
      setStoredToken(res.access_token);
      setUser(res.user);
      router.push("/dashboard");
    },
    [router]
  );

  const signup = useCallback(
    async (body: SignupBody) => {
      const res = await apiSignup(body);
      setStoredToken(res.access_token);
      setUser(res.user);
      router.push("/dashboard");
    },
    [router]
  );

  const logout = useCallback(() => {
    clearStoredToken();
    setUser(null);
    // Hard nav to "/" so we don't race RequireAuth's redirect-to-login
    // effect when logging out from a protected page. Logout is rare enough
    // that the full reload cost is fine, and it guarantees a clean slate.
    if (typeof window !== "undefined") {
      window.location.href = "/";
    } else {
      router.push("/");
    }
  }, [router]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isLoading,
      isAuthenticated: user !== null,
      login,
      signup,
      logout,
    }),
    [user, isLoading, login, signup, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}

// Browser-side helpers for the auth bearer token.
//
// Token storage is intentionally minimal: a single localStorage entry that
// the API client reads on every request and the AuthProvider hydrates from
// on mount. No cookies, no refresh tokens — see the auth MVP scope.

const TOKEN_KEY = "calia_auth_token";

export function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setStoredToken(token: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(TOKEN_KEY, token);
  } catch {
    /* storage disabled — auth will simply not persist across reloads */
  }
}

export function clearStoredToken(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* ignore */
  }
}

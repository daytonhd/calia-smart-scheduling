"use client";

import Link from "next/link";

import { useAuth } from "./AuthProvider";
import SiteNav from "./SiteNav";

export default function AppHeader() {
  const { isLoading, isAuthenticated, user, logout } = useAuth();

  // While auth state is still resolving on first paint, show only the brand
  // so we don't briefly flash logged-out nav at users with a valid token.
  if (isLoading) {
    return (
      <header className="app-header">
        <Link href="/" className="app-brand-link">
          <span className="app-brand">Calia</span>
        </Link>
      </header>
    );
  }

  if (!isAuthenticated) {
    return (
      <header className="app-header">
        <Link href="/" className="app-brand-link">
          <span className="app-brand">Calia</span>
        </Link>
        <nav className="app-nav app-nav-public" aria-label="primary">
          <Link href="/login">Log in</Link>
          <Link href="/signup" className="app-nav-cta">
            Create account
          </Link>
        </nav>
      </header>
    );
  }

  return (
    <header className="app-header">
      <Link href="/dashboard" className="app-brand-link">
        <span className="app-brand">Calia</span>
      </Link>
      <SiteNav />
      <div className="app-user-control">
        <span className="app-user-name" title={user?.email ?? undefined}>
          {user?.name || user?.email}
        </span>
        <button
          type="button"
          className="ghost app-logout-btn"
          onClick={logout}
        >
          Log out
        </button>
      </div>
    </header>
  );
}

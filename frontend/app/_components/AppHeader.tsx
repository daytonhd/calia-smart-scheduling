"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { useAuth } from "./AuthProvider";
import SiteNav from "./SiteNav";

export default function AppHeader() {
  const { isLoading, isAuthenticated, user, logout } = useAuth();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const cancelButtonRef = useRef<HTMLButtonElement | null>(null);

  const openConfirm = useCallback(() => setConfirmOpen(true), []);
  const closeConfirm = useCallback(() => setConfirmOpen(false), []);
  const confirmLogout = useCallback(() => {
    setConfirmOpen(false);
    logout();
  }, [logout]);

  // Close on Escape and focus the safer "Cancel" button when the dialog opens.
  useEffect(() => {
    if (!confirmOpen) return;
    cancelButtonRef.current?.focus();
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") closeConfirm();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [confirmOpen, closeConfirm]);

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
    <>
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
            onClick={openConfirm}
          >
            Log out
          </button>
        </div>
      </header>

      {confirmOpen && (
        <div
          className="modal-overlay"
          role="dialog"
          aria-modal="true"
          aria-labelledby="logout-confirm-title"
          aria-describedby="logout-confirm-body"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) closeConfirm();
          }}
        >
          <div className="modal-card modal-confirm">
            <div className="modal-header">
              <h2 id="logout-confirm-title" className="modal-title">
                Log out?
              </h2>
            </div>
            <div className="modal-body">
              <p id="logout-confirm-body" className="modal-confirm-body">
                You&rsquo;ll need to sign in again to access your schedule.
              </p>
            </div>
            <div className="modal-footer">
              <button
                ref={cancelButtonRef}
                type="button"
                className="secondary"
                onClick={closeConfirm}
              >
                Cancel
              </button>
              <button
                type="button"
                className="primary"
                onClick={confirmLogout}
              >
                Log out
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

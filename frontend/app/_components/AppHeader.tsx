"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { useAuth } from "./AuthProvider";
import SiteNav from "./SiteNav";

export default function AppHeader() {
  const { isLoading, isAuthenticated, user, logout } = useAuth();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const cancelButtonRef = useRef<HTMLButtonElement | null>(null);
  const accountRef = useRef<HTMLDivElement | null>(null);

  const closeMenu = useCallback(() => setMenuOpen(false), []);
  const openConfirm = useCallback(() => setConfirmOpen(true), []);
  const closeConfirm = useCallback(() => setConfirmOpen(false), []);
  const confirmLogout = useCallback(() => {
    setConfirmOpen(false);
    logout();
  }, [logout]);

  // Close the account menu on outside click or Escape.
  useEffect(() => {
    if (!menuOpen) return;
    function onPointerDown(e: MouseEvent) {
      if (accountRef.current && !accountRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setMenuOpen(false);
    }
    document.addEventListener("mousedown", onPointerDown);
    window.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      window.removeEventListener("keydown", onKey);
    };
  }, [menuOpen]);

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
        <div className="app-account" ref={accountRef}>
          <button
            type="button"
            className="app-account-trigger"
            aria-haspopup="menu"
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((open) => !open)}
          >
            <span className="app-account-avatar" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="9.25" />
                <circle cx="12" cy="9.75" r="2.9" />
                <path d="M6.6 18.4a5.6 5.6 0 0 1 10.8 0" />
              </svg>
            </span>
            <span className="app-account-name" title={user?.email ?? undefined}>
              {user?.name || user?.email}
            </span>
          </button>

          {menuOpen && (
            <div className="app-account-menu" role="menu">
              <Link
                href="/settings"
                role="menuitem"
                className="app-account-menu-item"
                onClick={closeMenu}
              >
                Settings
              </Link>
              <button
                type="button"
                role="menuitem"
                className="app-account-menu-item"
                onClick={() => {
                  closeMenu();
                  openConfirm();
                }}
              >
                Log out
              </button>
            </div>
          )}
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

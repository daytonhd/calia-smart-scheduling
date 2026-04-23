import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "Smart Scheduling",
  description: "Smart Scheduling System — MVP",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="site-header">
          <h1 className="site-title">Smart Scheduling</h1>
          <nav className="site-nav" aria-label="primary">
            <Link href="/">Home</Link>
            <Link href="/dashboard">Dashboard</Link>
            <Link href="/schedule">Schedule</Link>
            <Link href="/events">Events</Link>
            <Link href="/calendars">Calendars</Link>
            <Link href="/availability">Availability</Link>
          </nav>
        </header>
        <main className="site-main">{children}</main>
      </body>
    </html>
  );
}

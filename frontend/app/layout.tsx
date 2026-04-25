import type { Metadata } from "next";
import type { ReactNode } from "react";
import SiteNav from "./_components/SiteNav";
import "./globals.css";

export const metadata: Metadata = {
  title: "Smart Scheduling",
  description: "Smart Scheduling System — MVP",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="app-header">
          <h1 className="app-brand">Smart Scheduling</h1>
          <SiteNav />
        </header>
        <main className="site-main">{children}</main>
      </body>
    </html>
  );
}

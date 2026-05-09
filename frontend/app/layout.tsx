import type { Metadata } from "next";
import type { ReactNode } from "react";
import SiteNav from "./_components/SiteNav";
import "./globals.css";

export const metadata: Metadata = {
  title: "Calia",
  description:
    "Calia helps you manage events, find open time, and understand your weekly schedule balance.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="app-header">
          <h1 className="app-brand">Calia</h1>
          <SiteNav />
        </header>
        <main className="site-main">{children}</main>
      </body>
    </html>
  );
}

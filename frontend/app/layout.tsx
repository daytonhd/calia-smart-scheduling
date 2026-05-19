import type { Metadata } from "next";
import type { ReactNode } from "react";

import AppHeader from "./_components/AppHeader";
import { AuthProvider } from "./_components/AuthProvider";
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
        <AuthProvider>
          <AppHeader />
          <main className="site-main">{children}</main>
        </AuthProvider>
      </body>
    </html>
  );
}

"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_LINKS: { href: string; label: string }[] = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/schedule", label: "Schedule" },
  { href: "/settings", label: "Settings" },
];

export default function SiteNav() {
  const pathname = usePathname() ?? "";

  return (
    <nav className="app-nav" aria-label="primary">
      {NAV_LINKS.map((link) => {
        const active =
          pathname === link.href || pathname.startsWith(`${link.href}/`);
        return (
          <Link
            key={link.href}
            href={link.href}
            className={active ? "active" : undefined}
            aria-current={active ? "page" : undefined}
          >
            {link.label}
          </Link>
        );
      })}
    </nav>
  );
}

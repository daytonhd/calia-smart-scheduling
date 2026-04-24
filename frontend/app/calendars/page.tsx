import { redirect } from "next/navigation";

// Calendar management now lives under /settings.
// This route is kept temporarily so existing links/bookmarks still work.
export default function CalendarsPage() {
  redirect("/settings");
}

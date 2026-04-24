import Link from "next/link";

export default function HomePage() {
  return (
    <section>
      <h2>Welcome</h2>
      <p>Frontend shell for the Smart Scheduling MVP.</p>
      <ul>
        <li>
          <Link href="/dashboard">Dashboard</Link> — weekly overview, today,
          and upcoming events
        </li>
        <li>
          <Link href="/schedule">Schedule</Link> — main operational workspace
        </li>
        <li>
          <Link href="/settings">Settings</Link> — manage calendars
        </li>
      </ul>
    </section>
  );
}

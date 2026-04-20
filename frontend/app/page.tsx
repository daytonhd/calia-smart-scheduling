import Link from "next/link";

export default function HomePage() {
  return (
    <section>
      <h2>Welcome</h2>
      <p>Frontend shell for the Smart Scheduling MVP.</p>
      <ul>
        <li>
          <Link href="/dashboard">Dashboard</Link> — weekly metrics and
          upcoming events
        </li>
        <li>
          <Link href="/events">Events</Link> — manage calendars and events
        </li>
      </ul>
    </section>
  );
}

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
          <Link href="/schedule">Schedule</Link> — event list by date range
          and calendar
        </li>
        <li>
          <Link href="/events">Events</Link> — create/edit events
        </li>
        <li>
          <Link href="/calendars">Calendars</Link> — manage calendars
        </li>
        <li>
          <Link href="/availability">Availability</Link> — weekly availability
          and blocked times
        </li>
      </ul>
    </section>
  );
}

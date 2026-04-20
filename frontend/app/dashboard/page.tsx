"use client";

import { useEffect, useState } from "react";
import { ApiError, getWeeklyMetrics, listEvents } from "@/lib/api";
import type { Event, WeeklyMetrics } from "@/lib/types";

function formatDateTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export default function DashboardPage() {
  const [metrics, setMetrics] = useState<WeeklyMetrics | null>(null);
  const [upcoming, setUpcoming] = useState<Event[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [m, events] = await Promise.all([
          getWeeklyMetrics(),
          listEvents(),
        ]);
        if (cancelled) return;

        const now = Date.now();
        const next = events
          .filter((e) => new Date(e.end_time).getTime() >= now)
          .slice(0, 10);

        setMetrics(m);
        setUpcoming(next);
      } catch (e) {
        if (cancelled) return;
        const msg =
          e instanceof ApiError
            ? `${e.status}: ${e.message}`
            : e instanceof Error
            ? e.message
            : "Unknown error";
        setError(msg);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <section>
      <h2>Dashboard</h2>

      {loading && <p className="muted">Loading…</p>}

      {error && (
        <div className="error-box" role="alert">
          Failed to load dashboard: {error}
        </div>
      )}

      {!loading && !error && metrics && (
        <>
          <h3>This week</h3>
          <p className="muted">
            {metrics.week_start} → {metrics.week_end}
          </p>
          <div className="card-grid">
            <MetricCard label="Events" value={metrics.total_events} />
            <MetricCard
              label="Scheduled minutes"
              value={metrics.total_scheduled_minutes}
            />
            <MetricCard
              label="Blocked times"
              value={metrics.total_blocked_times}
            />
            <MetricCard
              label="Blocked minutes"
              value={metrics.total_blocked_minutes}
            />
            <MetricCard
              label="Busiest day"
              value={metrics.busiest_day ?? "—"}
              sub={
                metrics.busiest_day
                  ? `${metrics.busiest_day_minutes} min`
                  : undefined
              }
            />
          </div>

          <h3 style={{ marginTop: "2rem" }}>Upcoming events</h3>
          {upcoming.length === 0 ? (
            <p className="muted">No upcoming events.</p>
          ) : (
            <ul className="event-list">
              {upcoming.map((e) => (
                <li key={e.id}>
                  <strong>{e.title}</strong>
                  <span className="muted">
                    {" — "}
                    {formatDateTime(e.start_time)} →{" "}
                    {formatDateTime(e.end_time)}
                  </span>
                </li>
              ))}
            </ul>
          )}

          {/* TODO: today's schedule, blocked times panel, and saved weekly AI
              summary are not yet supported by dedicated backend endpoints. */}
        </>
      )}
    </section>
  );
}

function MetricCard({
  label,
  value,
  sub,
}: {
  label: string;
  value: string | number;
  sub?: string;
}) {
  return (
    <div className="metric-card">
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
      {sub && <div className="metric-sub">{sub}</div>}
    </div>
  );
}

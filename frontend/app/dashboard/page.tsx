"use client";

import { useEffect, useState } from "react";
import {
  ApiError,
  getWeeklyMetrics,
  getWeeklySummary,
  listBlockedTimes,
  listEvents,
} from "@/lib/api";
import type {
  BlockedTime,
  Event,
  ScheduleSummary,
  WeeklyMetrics,
} from "@/lib/types";

function formatDateTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
  });
}

// Returns [startOfTodayISO, startOfTomorrowISO] as ISO strings in local time.
function todayWindowIso(): { start: string; end: string } {
  const now = new Date();
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const end = new Date(start);
  end.setDate(end.getDate() + 1);
  return { start: start.toISOString(), end: end.toISOString() };
}

// Returns the window from start of tomorrow through end of day (today + 7),
// used for the "Upcoming events" list beyond today.
function upcomingWindowIso(): { start: string; end: string } {
  const now = new Date();
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
  const end = new Date(start);
  end.setDate(end.getDate() + 7);
  return { start: start.toISOString(), end: end.toISOString() };
}

function formatDayTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export default function DashboardPage() {
  const [metrics, setMetrics] = useState<WeeklyMetrics | null>(null);
  const [todayEvents, setTodayEvents] = useState<Event[]>([]);
  const [upcomingEvents, setUpcomingEvents] = useState<Event[]>([]);
  const [todayBlocked, setTodayBlocked] = useState<BlockedTime[]>([]);
  const [summary, setSummary] = useState<ScheduleSummary | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      const { start, end } = todayWindowIso();
      const { start: upStart, end: upEnd } = upcomingWindowIso();

      setLoading(true);
      setError(null);
      try {
        const [m, ev, up, bt, ws] = await Promise.all([
          getWeeklyMetrics(),
          listEvents({ startTime: start, endTime: end }),
          listEvents({ startTime: upStart, endTime: upEnd }),
          listBlockedTimes({ startTime: start, endTime: end }),
          getWeeklySummary(),
        ]);
        if (cancelled) return;

        setMetrics(m);
        setTodayEvents(ev);
        setUpcomingEvents(up);
        setTodayBlocked(bt);
        setSummary(ws);
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

          <h3 style={{ marginTop: "2rem" }}>Today&apos;s schedule</h3>
          {todayEvents.length === 0 ? (
            <p className="muted">No events today.</p>
          ) : (
            <ul className="event-list">
              {todayEvents.map((e) => (
                <li key={e.id}>
                  <strong>{e.title}</strong>
                  <span className="muted">
                    {" — "}
                    {formatTime(e.start_time)} → {formatTime(e.end_time)}
                  </span>
                </li>
              ))}
            </ul>
          )}

          <h3 style={{ marginTop: "2rem" }}>Upcoming events</h3>
          {upcomingEvents.length === 0 ? (
            <p className="muted">No upcoming events in the next 7 days.</p>
          ) : (
            <ul className="event-list">
              {upcomingEvents.map((e) => (
                <li key={e.id}>
                  <strong>{e.title}</strong>
                  <span className="muted">
                    {" — "}
                    {formatDayTime(e.start_time)}
                  </span>
                </li>
              ))}
            </ul>
          )}

          <h3 style={{ marginTop: "2rem" }}>Today&apos;s blocked times</h3>
          {todayBlocked.length === 0 ? (
            <p className="muted">No blocked times today.</p>
          ) : (
            <ul className="event-list">
              {todayBlocked.map((b) => (
                <li key={b.id}>
                  <strong>{b.title}</strong>
                  <span className="muted">
                    {" — "}
                    {formatTime(b.start_time)} → {formatTime(b.end_time)}
                    {b.reason ? ` · ${b.reason}` : ""}
                  </span>
                </li>
              ))}
            </ul>
          )}

          <h3 style={{ marginTop: "2rem" }}>Weekly AI summary</h3>
          {summary ? (
            <article className="summary-card">
              <div className="muted">
                Week of {summary.week_start} · generated{" "}
                {formatDateTime(summary.created_at)}
              </div>
              <p style={{ whiteSpace: "pre-wrap" }}>{summary.generated_text}</p>
            </article>
          ) : (
            <p className="muted">No saved summary for this week yet.</p>
          )}
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

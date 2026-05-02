"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  ApiError,
  getScheduleBalance,
  getWeeklyMetrics,
  getWeeklySummary,
  listBlockedTimes,
  listCalendars,
  listEvents,
} from "@/lib/api";
import type {
  BlockedTime,
  Calendar,
  Event,
  ScheduleBalanceDay,
  ScheduleBalanceResponse,
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

// Naive-local ISO: backend rejects tz-aware datetimes per the MVP time contract.
function naiveLocalIso(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
    `T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
  );
}

// Returns [startOfToday, startOfTomorrow] as naive local ISO strings.
function todayWindowIso(): { start: string; end: string } {
  const now = new Date();
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const end = new Date(start);
  end.setDate(end.getDate() + 1);
  return { start: naiveLocalIso(start), end: naiveLocalIso(end) };
}

// Returns the window from start of tomorrow through end of day (today + 7).
function upcomingWindowIso(): { start: string; end: string } {
  const now = new Date();
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
  const end = new Date(start);
  end.setDate(end.getDate() + 7);
  return { start: naiveLocalIso(start), end: naiveLocalIso(end) };
}

function todayLabel(): string {
  return new Date().toLocaleDateString(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
  });
}

// ----- Schedule Balance helpers -----

// Daily Rhythm suggestion window upper bound used for visual scaling.
// The shared bottom scale shows 0h, 4h, 8h.
const BALANCE_SCALE_MAX_MIN = 8 * 60;

// Day-level intensity bucket from total busy minutes.
// Mirrors the OVERLOADED_DAY_BUSY_MINUTES threshold from the backend.
type LoadLevel = "light" | "balanced" | "heavy";

function loadLevel(busyMin: number): LoadLevel {
  if (busyMin >= 6 * 60) return "heavy";
  if (busyMin >= 3 * 60) return "balanced";
  return "light";
}

function loadLevelLabel(level: LoadLevel): string {
  if (level === "heavy") return "Heavy";
  if (level === "balanced") return "Balanced";
  return "Light";
}

function weekdayShort(iso: string): string {
  const d = new Date(`${iso}T00:00:00`);
  return d.toLocaleDateString(undefined, { weekday: "short" });
}

function weekdayLong(iso: string): string {
  const d = new Date(`${iso}T00:00:00`);
  return d.toLocaleDateString(undefined, { weekday: "long" });
}

interface BalanceStatus {
  label: string;   // "Light" | "Balanced" | "Heavy" | "Slightly Heavy" | "Empty"
  detail: string;  // compact interpretation
}

function computeBalanceStatus(days: ScheduleBalanceDay[]): BalanceStatus {
  if (days.length === 0) {
    return { label: "Empty", detail: "No schedule data for this week yet." };
  }

  const totalBusy = days.reduce((s, d) => s + d.total_busy_minutes, 0);
  if (totalBusy === 0) {
    return { label: "Light", detail: "Nothing scheduled this week yet." };
  }

  const avg = totalBusy / days.length;
  const max = days.reduce(
    (m, d) => (d.total_busy_minutes > m.total_busy_minutes ? d : m),
    days[0]
  );
  const heavyDays = days.filter((d) => d.total_busy_minutes >= 6 * 60);

  if (heavyDays.length >= 2) {
    return {
      label: "Heavy",
      detail: "Multiple days are carrying significant scheduled load.",
    };
  }

  if (max.total_busy_minutes >= 6 * 60 && max.total_busy_minutes > avg * 1.8) {
    return {
      label: "Slightly Heavy",
      detail: `${weekdayLong(max.date)} is carrying most of this week's scheduled load.`,
    };
  }

  if (avg < 2 * 60) {
    return {
      label: "Light",
      detail: "Plenty of free room across the week.",
    };
  }

  return {
    label: "Balanced",
    detail: "Load is spread evenly across the week.",
  };
}

export default function DashboardPage() {
  const [metrics, setMetrics] = useState<WeeklyMetrics | null>(null);
  const [todayEvents, setTodayEvents] = useState<Event[]>([]);
  const [upcomingEvents, setUpcomingEvents] = useState<Event[]>([]);
  const [todayBlocked, setTodayBlocked] = useState<BlockedTime[]>([]);
  const [summary, setSummary] = useState<ScheduleSummary | null>(null);
  const [balance, setBalance] = useState<ScheduleBalanceResponse | null>(null);
  const [calendars, setCalendars] = useState<Calendar[]>([]);
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
        const [m, ev, up, bt, ws, sb, cals] = await Promise.all([
          getWeeklyMetrics(),
          listEvents({ startTime: start, endTime: end }),
          listEvents({ startTime: upStart, endTime: upEnd }),
          listBlockedTimes({ startTime: start, endTime: end }),
          getWeeklySummary(),
          getScheduleBalance(),
          listCalendars(),
        ]);
        if (cancelled) return;

        setMetrics(m);
        setTodayEvents(
          [...ev].sort(
            (a, b) =>
              new Date(a.start_time).getTime() -
              new Date(b.start_time).getTime()
          )
        );
        setUpcomingEvents(
          [...up].sort(
            (a, b) =>
              new Date(a.start_time).getTime() -
              new Date(b.start_time).getTime()
          )
        );
        setTodayBlocked(bt);
        setSummary(ws);
        setBalance(sb);
        setCalendars(cals);
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

  const calendarsById = new Map<number, Calendar>();
  calendars.forEach((c) => calendarsById.set(c.id, c));

  return (
    <section>
      <header className="page-header">
        <h2 className="page-title">Dashboard</h2>
        <p className="page-subtitle">
          {todayLabel()} · your week at a glance
        </p>
      </header>

      {error && (
        <div className="error-box" role="alert">
          Failed to load dashboard: {error}
        </div>
      )}

      {loading ? (
        <p className="muted">Loading…</p>
      ) : (
        <>
          {/* Full-width weekly overview / AI summary */}
          <div className="overview-card">
            <div className="overview-icon" aria-hidden>
              ✦
            </div>
            <div className="overview-content">
              <h3 className="overview-title">Weekly Overview</h3>
              {summary ? (
                <>
                  <p className="overview-text">{summary.generated_text}</p>
                  <div className="overview-meta">
                    Week of {summary.week_start} · generated{" "}
                    {formatDateTime(summary.created_at)}
                  </div>
                </>
              ) : (
                <p className="overview-text muted">
                  No saved weekly summary yet. Once one is generated it will
                  appear here.
                </p>
              )}
            </div>
          </div>

          <div className="page-grid">
            {/* Main column: Today's Schedule */}
            <div className="page-main">
              <div className="card today-card">
                <div className="card-header-row">
                  <h3 className="card-title">Today&apos;s Schedule</h3>
                  <span className="pill neutral">
                    {todayEvents.length} event
                    {todayEvents.length === 1 ? "" : "s"}
                  </span>
                </div>

                {todayEvents.length === 0 ? (
                  <div className="empty-state">
                    <span className="empty-state-strong">
                      Nothing scheduled today
                    </span>
                    Time to focus, or{" "}
                    <Link href="/schedule">plan something on Schedule</Link>.
                  </div>
                ) : (
                  <ul className="timeline">
                    {todayEvents.map((e) => {
                      const cal = calendarsById.get(e.calendar_id);
                      return (
                        <li key={e.id} className="timeline-item">
                          <div className="timeline-time">
                            {formatTime(e.start_time)}
                          </div>
                          <span className="timeline-dot" aria-hidden />
                          <div className="timeline-event">
                            <div className="timeline-event-title">
                              {e.title}
                            </div>
                            <div className="timeline-event-meta">
                              {formatTime(e.start_time)} →{" "}
                              {formatTime(e.end_time)}
                              {cal ? ` · ${cal.name}` : ""}
                              {e.location ? ` · ${e.location}` : ""}
                            </div>
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </div>

              {/* Schedule Balance */}
              <div className="card balance-card">
                <div className="card-header-row">
                  <h3 className="card-title">Schedule Balance</h3>
                  {balance && balance.days.length > 0 && (
                    (() => {
                      const status = computeBalanceStatus(balance.days);
                      const cls =
                        status.label === "Heavy"
                          ? "heavy"
                          : status.label === "Slightly Heavy"
                          ? "slight-heavy"
                          : status.label === "Light"
                          ? "light"
                          : "balanced";
                      return (
                        <span className={`pill balance-pill ${cls}`}>
                          {status.label}
                        </span>
                      );
                    })()
                  )}
                </div>

                {!balance || balance.days.length === 0 ? (
                  <div className="empty-state">
                    <span className="empty-state-strong">
                      No schedule data yet
                    </span>
                    Add events or blocked times to see how balanced your week
                    is.
                  </div>
                ) : (
                  (() => {
                    const status = computeBalanceStatus(balance.days);
                    const maxBusy = Math.max(
                      1,
                      ...balance.days.map((d) => d.total_busy_minutes)
                    );
                    return (
                      <>
                        <p className="balance-status">
                          <span className="balance-status-label">
                            {status.label}
                          </span>
                          <span className="balance-status-sep">—</span>
                          <span className="balance-status-detail">
                            {status.detail}
                          </span>
                        </p>

                        <div className="balance-section">
                          <div className="balance-section-title">
                            Free Capacity
                          </div>
                          <div className="capacity-bars">
                            {balance.days.map((d) => {
                              const pct = Math.min(
                                100,
                                (d.free_minutes / BALANCE_SCALE_MAX_MIN) * 100
                              );
                              return (
                                <div className="capacity-row" key={d.date}>
                                  <div className="capacity-day">
                                    {weekdayShort(d.date)}
                                  </div>
                                  <div className="capacity-track">
                                    <div
                                      className="capacity-fill"
                                      style={{ width: `${pct}%` }}
                                    />
                                  </div>
                                </div>
                              );
                            })}
                            <div className="capacity-scale">
                              <span>0h</span>
                              <span>4h</span>
                              <span>8h</span>
                            </div>
                          </div>
                        </div>

                        <div className="balance-section">
                          <div className="balance-section-title">
                            Daily Load
                          </div>
                          <div className="load-bars">
                            {balance.days.map((d) => {
                              const level = loadLevel(d.total_busy_minutes);
                              const h = Math.min(
                                100,
                                (d.total_busy_minutes / maxBusy) * 100
                              );
                              return (
                                <div className="load-col" key={d.date}>
                                  <div className="load-bar-wrap">
                                    <div
                                      className={`load-bar load-${level}`}
                                      style={{ height: `${h}%` }}
                                      title={`${loadLevelLabel(level)} · ${Math.round(d.total_busy_minutes / 60 * 10) / 10}h`}
                                    />
                                  </div>
                                  <div className="load-day">
                                    {weekdayShort(d.date)}
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                          <div className="load-legend">
                            <span className="load-legend-item">
                              <span className="load-swatch load-light" /> Light
                            </span>
                            <span className="load-legend-item">
                              <span className="load-swatch load-balanced" />{" "}
                              Balanced
                            </span>
                            <span className="load-legend-item">
                              <span className="load-swatch load-heavy" /> Heavy
                            </span>
                          </div>
                        </div>

                        {balance.week_warnings.length > 0 && (
                          <ul className="balance-notes">
                            {balance.week_warnings.map((w) => (
                              <li key={w.reason_code}>{w.message}</li>
                            ))}
                          </ul>
                        )}
                      </>
                    );
                  })()
                )}
              </div>
            </div>

            {/* Right sidebar */}
            <aside className="page-side">
              {/* Upcoming */}
              <div className="sidebar-card">
                <div className="sidebar-card-title">
                  <span>Upcoming</span>
                  <Link href="/schedule" className="link">
                    View all →
                  </Link>
                </div>
                {upcomingEvents.length === 0 ? (
                  <div className="empty-state">
                    <span className="empty-state-strong">
                      No upcoming events
                    </span>
                    Nothing scheduled in the next 7 days.
                  </div>
                ) : (
                  <ul className="list-rows">
                    {upcomingEvents.slice(0, 5).map((e) => (
                      <li key={e.id}>
                        <div className="row-icon" aria-hidden>
                          ▣
                        </div>
                        <div className="row-body">
                          <div className="row-title">{e.title}</div>
                          <div className="row-meta">
                            {formatDayTime(e.start_time)}
                          </div>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              {/* Blocked Times Today */}
              <div className="sidebar-card">
                <div className="sidebar-card-title">
                  <span>Blocked Times Today</span>
                </div>
                {todayBlocked.length === 0 ? (
                  <div className="empty-state">
                    <span className="empty-state-strong">
                      No blocked time
                    </span>
                    Today is wide open.
                  </div>
                ) : (
                  <ul className="list-rows">
                    {todayBlocked.map((b) => (
                      <li key={b.id}>
                        <div className="row-icon danger" aria-hidden>
                          ⊘
                        </div>
                        <div className="row-body">
                          <div className="row-title">{b.title}</div>
                          <div className="row-meta">
                            {formatTime(b.start_time)} →{" "}
                            {formatTime(b.end_time)}
                            {b.reason ? ` · ${b.reason}` : ""}
                          </div>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              {/* Weekly Metrics */}
              <div className="sidebar-card">
                <div className="sidebar-card-title">
                  <span>Weekly Metrics</span>
                </div>
                {metrics ? (
                  <div className="metric-rows">
                    <div className="metric-row">
                      <span className="metric-label">Events</span>
                      <span className="metric-value">
                        {metrics.total_events}
                      </span>
                    </div>
                    <div className="metric-row">
                      <span className="metric-label">Scheduled minutes</span>
                      <span className="metric-value">
                        {metrics.total_scheduled_minutes}
                      </span>
                    </div>
                    <div className="metric-row">
                      <span className="metric-label">Blocked minutes</span>
                      <span className="metric-value">
                        {metrics.total_blocked_minutes}
                      </span>
                    </div>
                    <div className="metric-row">
                      <span className="metric-label">Busiest day</span>
                      <span className="metric-value">
                        {metrics.busiest_day ?? "—"}
                      </span>
                    </div>
                    <div className="metric-row">
                      <span className="metric-label muted small">
                        Week range
                      </span>
                      <span className="metric-value muted small">
                        {metrics.week_start} → {metrics.week_end}
                      </span>
                    </div>
                  </div>
                ) : (
                  <div className="empty-state">
                    <span className="empty-state-strong">No metrics yet</span>
                    Metrics will appear once data is available.
                  </div>
                )}
              </div>
            </aside>
          </div>
        </>
      )}
    </section>
  );
}

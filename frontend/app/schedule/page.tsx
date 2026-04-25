"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  ApiError,
  deleteEvent,
  getWeeklyMetrics,
  listCalendars,
  listEvents,
} from "@/lib/api";
import type { Calendar, Event, WeeklyMetrics } from "@/lib/types";

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

function toDateInput(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

// Default range: today through +7 days
function defaultRange(): { start: string; end: string } {
  const start = new Date();
  const end = new Date();
  end.setDate(start.getDate() + 7);
  return { start: toDateInput(start), end: toDateInput(end) };
}

function dateInputToIsoStart(v: string): string {
  const [y, m, d] = v.split("-").map(Number);
  return new Date(y, (m ?? 1) - 1, d ?? 1, 0, 0, 0, 0).toISOString();
}

function dateInputToIsoEndExclusive(v: string): string {
  const [y, m, d] = v.split("-").map(Number);
  return new Date(y, (m ?? 1) - 1, (d ?? 1) + 1, 0, 0, 0, 0).toISOString();
}

function formatTimeRange(startIso: string, endIso: string): string {
  const start = new Date(startIso);
  const end = new Date(endIso);
  const opts: Intl.DateTimeFormatOptions = {
    hour: "numeric",
    minute: "2-digit",
  };
  return `${start.toLocaleTimeString(undefined, opts)} → ${end.toLocaleTimeString(
    undefined,
    opts
  )}`;
}

// Build the array of day keys from start to end (inclusive)
function buildDayKeys(startInput: string, endInput: string): string[] {
  const [sy, sm, sd] = startInput.split("-").map(Number);
  const [ey, em, ed] = endInput.split("-").map(Number);
  const start = new Date(sy, (sm ?? 1) - 1, sd ?? 1);
  const end = new Date(ey, (em ?? 1) - 1, ed ?? 1);
  const out: string[] = [];
  const cursor = new Date(start);
  while (cursor.getTime() <= end.getTime()) {
    out.push(
      `${cursor.getFullYear()}-${pad(cursor.getMonth() + 1)}-${pad(
        cursor.getDate()
      )}`
    );
    cursor.setDate(cursor.getDate() + 1);
  }
  return out;
}

function groupByDay(events: Event[]): Map<string, Event[]> {
  const map = new Map<string, Event[]>();
  for (const ev of events) {
    const d = new Date(ev.start_time);
    const key = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
    const arr = map.get(key) ?? [];
    arr.push(ev);
    map.set(key, arr);
  }
  for (const arr of map.values()) {
    arr.sort(
      (a, b) =>
        new Date(a.start_time).getTime() - new Date(b.start_time).getTime()
    );
  }
  return map;
}

function formatDayHeading(key: string): string {
  const [y, m, d] = key.split("-").map(Number);
  const date = new Date(y, (m ?? 1) - 1, d ?? 1);
  return date.toLocaleDateString(undefined, {
    weekday: "long",
    month: "short",
    day: "numeric",
  });
}

function isToday(key: string): boolean {
  const today = new Date();
  return (
    key ===
    `${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(
      today.getDate()
    )}`
  );
}

export default function SchedulePage() {
  const initial = defaultRange();
  const [startDate, setStartDate] = useState<string>(initial.start);
  const [endDate, setEndDate] = useState<string>(initial.end);
  const [appliedStart, setAppliedStart] = useState<string>(initial.start);
  const [appliedEnd, setAppliedEnd] = useState<string>(initial.end);
  const [calendarFilter, setCalendarFilter] = useState<string>("");

  const [calendars, setCalendars] = useState<Calendar[]>([]);
  const [events, setEvents] = useState<Event[]>([]);
  const [metrics, setMetrics] = useState<WeeklyMetrics | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const calendarsById = useMemo(() => {
    const map = new Map<number, Calendar>();
    calendars.forEach((c) => map.set(c.id, c));
    return map;
  }, [calendars]);

  async function loadEvents(
    start: string,
    end: string,
    calId: string
  ): Promise<void> {
    setLoading(true);
    setError(null);
    try {
      const evs = await listEvents({
        calendarId: calId ? Number(calId) : undefined,
        startTime: dateInputToIsoStart(start),
        endTime: dateInputToIsoEndExclusive(end),
      });
      setEvents(evs);
    } catch (e) {
      setError(describeError(e));
    } finally {
      setLoading(false);
    }
  }

  // Initial load: calendars + events + metrics
  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const [cals, evs, m] = await Promise.all([
          listCalendars(),
          listEvents({
            startTime: dateInputToIsoStart(appliedStart),
            endTime: dateInputToIsoEndExclusive(appliedEnd),
          }),
          getWeeklyMetrics().catch(() => null),
        ]);
        if (cancelled) return;
        setCalendars(cals);
        setEvents(evs);
        setMetrics(m);
      } catch (e) {
        if (cancelled) return;
        setError(describeError(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function onApply(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setFormError(null);
    if (!startDate || !endDate) {
      setFormError("Start and end dates are required.");
      return;
    }
    if (startDate > endDate) {
      setFormError("Start date must be before or equal to end date.");
      return;
    }
    setAppliedStart(startDate);
    setAppliedEnd(endDate);
    loadEvents(startDate, endDate, calendarFilter);
  }

  function onCalendarFilterChange(v: string) {
    setCalendarFilter(v);
    loadEvents(appliedStart, appliedEnd, v);
  }

  async function onDelete(id: number) {
    if (!window.confirm("Delete this event?")) return;
    try {
      await deleteEvent(id);
      await loadEvents(appliedStart, appliedEnd, calendarFilter);
    } catch (err) {
      setError(describeError(err));
    }
  }

  const grouped = useMemo(() => groupByDay(events), [events]);
  const dayKeys = useMemo(
    () => buildDayKeys(appliedStart, appliedEnd),
    [appliedStart, appliedEnd]
  );

  const selectedCalendarName = calendarFilter
    ? calendarsById.get(Number(calendarFilter))?.name ??
      `calendar #${calendarFilter}`
    : null;

  return (
    <section>
      <header className="page-header">
        <h2 className="page-title">Schedule</h2>
        <p className="page-subtitle">
          Plan commitments, availability, and protected time.
        </p>
      </header>

      {error && (
        <div className="error-box" role="alert">
          {error}
        </div>
      )}

      {/* Toolbar */}
      <div className="schedule-toolbar">
        <form onSubmit={onApply} className="toolbar-form">
          <label>
            Start date
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              required
            />
          </label>

          <label>
            End date
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              required
            />
          </label>

          <button type="submit" disabled={loading}>
            {loading ? "Loading…" : "Apply range"}
          </button>
        </form>

        <div className="calendar-filter">
          <span className="filter-label">Calendar filter</span>
          <select
            aria-label="Filter events by calendar"
            value={calendarFilter}
            onChange={(e) => onCalendarFilterChange(e.target.value)}
          >
            <option value="">All calendars</option>
            {calendars.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {formError && (
        <div className="error-box" role="alert">
          {formError}
        </div>
      )}

      <div className="status-row">
        <span className="pill">
          {appliedStart} → {appliedEnd}
        </span>
        <span className="pill neutral">
          {selectedCalendarName ?? "All calendars"}
        </span>
        <span className="muted small">
          {events.length} event{events.length === 1 ? "" : "s"}
        </span>
      </div>

      <div className="page-grid">
        {/* Main: schedule board */}
        <div className="page-main">
          {loading ? (
            <div className="card">
              <p className="muted" style={{ margin: 0 }}>
                Loading schedule…
              </p>
            </div>
          ) : (
            <div className="schedule-board">
              {dayKeys.map((key) => {
                const dayEvents = grouped.get(key) ?? [];
                return (
                  <div key={key} className="day-card">
                    <div className="day-card-header">
                      <h3>
                        {formatDayHeading(key)}
                        {isToday(key) && (
                          <span
                            className="pill"
                            style={{ marginLeft: "0.5rem" }}
                          >
                            Today
                          </span>
                        )}
                      </h3>
                      <span className="day-meta">
                        {dayEvents.length === 0
                          ? "Open"
                          : `${dayEvents.length} event${
                              dayEvents.length === 1 ? "" : "s"
                            }`}
                      </span>
                    </div>

                    {dayEvents.length === 0 ? (
                      <div className="day-empty">No events scheduled.</div>
                    ) : (
                      <ul className="day-events">
                        {dayEvents.map((ev) => {
                          const cal = calendarsById.get(ev.calendar_id);
                          return (
                            <li key={ev.id} className="day-event">
                              <div className="day-event-body">
                                <div className="day-event-title">
                                  {ev.title}
                                </div>
                                <div className="day-event-meta">
                                  {formatTimeRange(ev.start_time, ev.end_time)}
                                </div>
                                <div className="day-event-tags">
                                  {cal ? cal.name : `calendar #${ev.calendar_id}`}
                                  {ev.priority ? ` · ${ev.priority}` : ""}
                                  {ev.category ? ` · ${ev.category}` : ""}
                                  {ev.location ? ` · ${ev.location}` : ""}
                                </div>
                              </div>
                              <div className="day-event-actions">
                                <Link href="/events" className="ghost-link">
                                  <button type="button" className="ghost">
                                    Edit
                                  </button>
                                </Link>
                                <button
                                  type="button"
                                  className="ghost"
                                  onClick={() => onDelete(ev.id)}
                                >
                                  Delete
                                </button>
                              </div>
                            </li>
                          );
                        })}
                      </ul>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Right sidebar */}
        <aside className="page-side">
          {/* Availability entry point */}
          <div className="cta-card">
            <h3>Availability</h3>
            <p>Manage availability windows and blocked times.</p>
            <Link href="/availability" className="cta-link">
              Manage availability
            </Link>
          </div>

          {/* Active filter / status summary */}
          <div className="sidebar-card">
            <div className="sidebar-card-title">
              <span>Current view</span>
            </div>
            <div className="metric-rows">
              <div className="metric-row">
                <span className="metric-label">Range</span>
                <span className="metric-value small">
                  {appliedStart} → {appliedEnd}
                </span>
              </div>
              <div className="metric-row">
                <span className="metric-label">Calendar</span>
                <span className="metric-value">
                  {selectedCalendarName ?? "All calendars"}
                </span>
              </div>
              <div className="metric-row">
                <span className="metric-label">Events</span>
                <span className="metric-value">{events.length}</span>
              </div>
              <div className="metric-row">
                <span className="metric-label">Days</span>
                <span className="metric-value">{dayKeys.length}</span>
              </div>
            </div>
          </div>

          {/* Weekly metrics */}
          {metrics && (
            <div className="sidebar-card">
              <div className="sidebar-card-title">
                <span>Weekly Metrics</span>
              </div>
              <div className="metric-rows">
                <div className="metric-row">
                  <span className="metric-label">Events</span>
                  <span className="metric-value">{metrics.total_events}</span>
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
              </div>
            </div>
          )}
        </aside>
      </div>
    </section>
  );
}

function describeError(e: unknown): string {
  if (e instanceof ApiError) {
    const body = e.body as { detail?: unknown } | null;
    if (body && typeof body === "object" && "detail" in body) {
      const d = body.detail;
      if (typeof d === "string") return `${e.status}: ${d}`;
      if (d && typeof d === "object") {
        try {
          return `${e.status}: ${JSON.stringify(d)}`;
        } catch {
          // fallthrough
        }
      }
    }
    return `${e.status}: ${e.message}`;
  }
  if (e instanceof Error) return e.message;
  return "Unknown error";
}

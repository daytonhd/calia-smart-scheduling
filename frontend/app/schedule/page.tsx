"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  ApiError,
  deleteEvent,
  listCalendars,
  listEvents,
} from "@/lib/api";
import type { Calendar, Event } from "@/lib/types";

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

// Interpret YYYY-MM-DD as the local midnight boundary
function dateInputToIsoStart(v: string): string {
  const [y, m, d] = v.split("-").map(Number);
  return new Date(y, (m ?? 1) - 1, d ?? 1, 0, 0, 0, 0).toISOString();
}

function dateInputToIsoEndExclusive(v: string): string {
  const [y, m, d] = v.split("-").map(Number);
  // end of selected day = start of next day
  return new Date(y, (m ?? 1) - 1, (d ?? 1) + 1, 0, 0, 0, 0).toISOString();
}

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
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
  // sort events within each day
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
    year: "numeric",
  });
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

  // Initial load: calendars + events
  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const [cals, evs] = await Promise.all([
          listCalendars(),
          listEvents({
            startTime: dateInputToIsoStart(appliedStart),
            endTime: dateInputToIsoEndExclusive(appliedEnd),
          }),
        ]);
        if (cancelled) return;
        setCalendars(cals);
        setEvents(evs);
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
    () => Array.from(grouped.keys()).sort(),
    [grouped]
  );

  return (
    <section>
      <h2>Schedule</h2>

      {error && (
        <div className="error-box" role="alert">
          {error}
        </div>
      )}

      <form onSubmit={onApply} className="event-form">
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

        <label>
          Calendar
          <select
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
        </label>

        {formError && (
          <div className="error-box full" role="alert">
            {formError}
          </div>
        )}

        <div className="form-actions full">
          <button type="submit" disabled={loading}>
            {loading ? "Loading…" : "Apply range"}
          </button>
        </div>
      </form>

      <p className="muted small">
        Showing {appliedStart} → {appliedEnd}
        {calendarFilter
          ? ` · filtered by ${
              calendarsById.get(Number(calendarFilter))?.name ??
              `calendar #${calendarFilter}`
            }`
          : " · all calendars"}
        {" · "}
        {events.length} event{events.length === 1 ? "" : "s"}
      </p>

      {loading ? (
        <p className="muted">Loading…</p>
      ) : events.length === 0 ? (
        <p className="muted">No events in this range.</p>
      ) : (
        dayKeys.map((key) => {
          const dayEvents = grouped.get(key) ?? [];
          return (
            <div key={key} style={{ marginTop: "1.25rem" }}>
              <h3 style={{ marginBottom: "0.25rem" }}>
                {formatDayHeading(key)}
              </h3>
              <ul className="event-list">
                {dayEvents.map((ev) => {
                  const cal = calendarsById.get(ev.calendar_id);
                  return (
                    <li key={ev.id} className="event-row">
                      <div>
                        <strong>{ev.title}</strong>
                        <span className="muted">
                          {" — "}
                          {formatDateTime(ev.start_time)} →{" "}
                          {formatDateTime(ev.end_time)}
                        </span>
                        <div className="muted small">
                          {cal ? cal.name : `calendar #${ev.calendar_id}`}
                          {ev.priority ? ` · ${ev.priority}` : ""}
                          {ev.category ? ` · ${ev.category}` : ""}
                          {ev.location ? ` · ${ev.location}` : ""}
                        </div>
                      </div>
                      <div className="row-actions">
                        <a href={`/events`} className="muted small">
                          Edit on Events →
                        </a>
                        <button
                          type="button"
                          onClick={() => onDelete(ev.id)}
                        >
                          Delete
                        </button>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </div>
          );
        })
      )}
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

"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  ApiError,
  createEvent,
  deleteEvent,
  getWeeklyMetrics,
  listCalendars,
  listEvents,
  updateEvent,
} from "@/lib/api";
import type {
  Calendar,
  Event,
  EventCreate,
  WeeklyMetrics,
} from "@/lib/types";

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

function toDateInput(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

// Default range: current week starting Monday, 7 days.
function defaultRange(): { start: string; end: string } {
  const now = new Date();
  const dow = now.getDay(); // 0=Sun..6=Sat
  // Treat Monday as week start.
  const offsetToMonday = (dow + 6) % 7;
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate() - offsetToMonday);
  const end = new Date(start);
  end.setDate(end.getDate() + 6);
  return { start: toDateInput(start), end: toDateInput(end) };
}

// MVP time contract: backend rejects timezone-aware datetimes. Send naive
// local-time ISO strings (no "Z", no offset) for all scheduling fields.
function dateInputToNaiveStart(v: string): string {
  return `${v}T00:00:00`;
}

function dateInputToNaiveEndExclusive(v: string): string {
  const [y, m, d] = v.split("-").map(Number);
  const next = new Date(y, (m ?? 1) - 1, (d ?? 1) + 1);
  return `${toDateInput(next)}T00:00:00`;
}

function fromLocalInputNaive(v: string): string {
  return v.length === 16 ? `${v}:00` : v;
}

function toLocalInput(iso: string): string {
  const d = new Date(iso);
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
    `T${pad(d.getHours())}:${pad(d.getMinutes())}`
  );
}

function shiftDateInput(input: string, days: number): string {
  const [y, m, d] = input.split("-").map(Number);
  const dt = new Date(y, (m ?? 1) - 1, (d ?? 1) + days);
  return toDateInput(dt);
}

function rangeDays(startInput: string, endInput: string): number {
  const [sy, sm, sd] = startInput.split("-").map(Number);
  const [ey, em, ed] = endInput.split("-").map(Number);
  const start = new Date(sy, (sm ?? 1) - 1, sd ?? 1);
  const end = new Date(ey, (em ?? 1) - 1, ed ?? 1);
  return Math.round((end.getTime() - start.getTime()) / 86400000) + 1;
}

function formatRangeLabel(startInput: string, endInput: string): string {
  const [sy, sm, sd] = startInput.split("-").map(Number);
  const [ey, em, ed] = endInput.split("-").map(Number);
  const start = new Date(sy, (sm ?? 1) - 1, sd ?? 1);
  const end = new Date(ey, (em ?? 1) - 1, ed ?? 1);
  const sameYear = start.getFullYear() === end.getFullYear();
  const startFmt = start.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    ...(sameYear ? {} : { year: "numeric" }),
  });
  const endFmt = end.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
  return `${startFmt} – ${endFmt}`;
}

function formatTimeShort(iso: string): string {
  return new Date(iso).toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
  });
}

function formatTimeRange(startIso: string, endIso: string): string {
  return `${formatTimeShort(startIso)} → ${formatTimeShort(endIso)}`;
}

function formatDayTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

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

function isToday(key: string): boolean {
  const today = new Date();
  return (
    key ===
    `${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(
      today.getDate()
    )}`
  );
}

function isWeekend(key: string): boolean {
  const [y, m, d] = key.split("-").map(Number);
  const dow = new Date(y, (m ?? 1) - 1, d ?? 1).getDay();
  return dow === 0 || dow === 6;
}

function dayHeaderParts(key: string): { weekday: string; daynum: string } {
  const [y, m, d] = key.split("-").map(Number);
  const date = new Date(y, (m ?? 1) - 1, d ?? 1);
  return {
    weekday: date.toLocaleDateString(undefined, { weekday: "short" }),
    daynum: date.toLocaleDateString(undefined, { day: "numeric" }),
  };
}

interface FormState {
  calendar_id: string;
  title: string;
  description: string;
  category: string;
  priority: string;
  location: string;
  start_time: string; // datetime-local
  end_time: string;   // datetime-local
}

const EMPTY_FORM: FormState = {
  calendar_id: "",
  title: "",
  description: "",
  category: "",
  priority: "",
  location: "",
  start_time: "",
  end_time: "",
};

interface ConflictDetail {
  reason_code: string;
  message: string;
  conflict_type?: string | null;
  start_time?: string | null;
  end_time?: string | null;
  related_event_id?: number | null;
  related_blocked_time_id?: number | null;
}

export default function SchedulePage() {
  const initial = defaultRange();
  const [appliedStart, setAppliedStart] = useState<string>(initial.start);
  const [appliedEnd, setAppliedEnd] = useState<string>(initial.end);
  const [calendarFilter, setCalendarFilter] = useState<string>("");

  const [calendars, setCalendars] = useState<Calendar[]>([]);
  const [events, setEvents] = useState<Event[]>([]);
  const [metrics, setMetrics] = useState<WeeklyMetrics | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Inline event create/edit panel state.
  const [formOpen, setFormOpen] = useState<boolean>(false);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [formConflicts, setFormConflicts] = useState<ConflictDetail[]>([]);

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
        startTime: dateInputToNaiveStart(start),
        endTime: dateInputToNaiveEndExclusive(end),
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
            startTime: dateInputToNaiveStart(appliedStart),
            endTime: dateInputToNaiveEndExclusive(appliedEnd),
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

  function applyRange(start: string, end: string) {
    setAppliedStart(start);
    setAppliedEnd(end);
    loadEvents(start, end, calendarFilter);
  }

  function shiftWeek(days: number) {
    const start = shiftDateInput(appliedStart, days);
    const end = shiftDateInput(appliedEnd, days);
    applyRange(start, end);
  }

  function goToday() {
    const r = defaultRange();
    applyRange(r.start, r.end);
  }

  function onPickStart(v: string) {
    if (!v) return;
    if (v > appliedEnd) {
      // Snap end to keep range valid (preserve 7-day window).
      const newEnd = shiftDateInput(v, 6);
      applyRange(v, newEnd);
    } else {
      applyRange(v, appliedEnd);
    }
  }

  function onPickEnd(v: string) {
    if (!v) return;
    if (v < appliedStart) {
      applyRange(v, v);
    } else {
      applyRange(appliedStart, v);
    }
  }

  function onCalendarFilterChange(v: string) {
    setCalendarFilter(v);
    loadEvents(appliedStart, appliedEnd, v);
  }

  function resetForm() {
    setForm(EMPTY_FORM);
    setEditingId(null);
    setFormError(null);
    setFormConflicts([]);
  }

  function openCreateForm() {
    resetForm();
    setFormOpen(true);
  }

  function startEdit(ev: Event) {
    setEditingId(ev.id);
    setFormError(null);
    setFormConflicts([]);
    setForm({
      calendar_id: String(ev.calendar_id),
      title: ev.title,
      description: ev.description ?? "",
      category: ev.category ?? "",
      priority: ev.priority ?? "",
      location: ev.location ?? "",
      start_time: toLocalInput(ev.start_time),
      end_time: toLocalInput(ev.end_time),
    });
    setFormOpen(true);
  }

  function cancelForm() {
    resetForm();
    setFormOpen(false);
  }

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setFormError(null);
    setFormConflicts([]);

    if (!form.calendar_id) {
      setFormError("Calendar is required.");
      return;
    }
    if (!form.title.trim()) {
      setFormError("Title is required.");
      return;
    }
    if (!form.start_time || !form.end_time) {
      setFormError("Start and end time are required.");
      return;
    }
    if (new Date(form.start_time) >= new Date(form.end_time)) {
      setFormError("Start time must be before end time.");
      return;
    }

    const payload: EventCreate = {
      calendar_id: Number(form.calendar_id),
      title: form.title.trim(),
      description: form.description.trim() || null,
      category: form.category.trim() || null,
      priority: form.priority.trim() || null,
      location: form.location.trim() || null,
      start_time: fromLocalInputNaive(form.start_time),
      end_time: fromLocalInputNaive(form.end_time),
    };

    setSubmitting(true);
    try {
      if (editingId != null) {
        await updateEvent(editingId, payload);
      } else {
        await createEvent(payload);
      }
      resetForm();
      setFormOpen(false);
      await loadEvents(appliedStart, appliedEnd, calendarFilter);
    } catch (err) {
      const conflicts = extractConflicts(err);
      if (conflicts.length > 0) {
        setFormConflicts(conflicts);
        setFormError("Could not save event — see conflicts below.");
      } else {
        setFormError(describeError(err));
      }
    } finally {
      setSubmitting(false);
    }
  }

  async function onDelete(id: number) {
    if (!window.confirm("Delete this event?")) return;
    try {
      await deleteEvent(id);
      if (editingId === id) resetForm();
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

  const upcoming = useMemo(() => {
    const now = Date.now();
    return [...events]
      .filter((e) => new Date(e.start_time).getTime() >= now)
      .sort(
        (a, b) =>
          new Date(a.start_time).getTime() - new Date(b.start_time).getTime()
      )
      .slice(0, 5);
  }, [events]);

  const totalDays = rangeDays(appliedStart, appliedEnd);

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

      {/* Compact toolbar */}
      <div className="toolbar-bar">
        <div className="toolbar-left">
          <div className="range-nav" role="group" aria-label="Week navigation">
            <button
              type="button"
              onClick={() => shiftWeek(-7)}
              aria-label="Previous week"
              disabled={loading}
            >
              ‹
            </button>
            <button type="button" onClick={goToday} disabled={loading}>
              Today
            </button>
            <button
              type="button"
              onClick={() => shiftWeek(7)}
              aria-label="Next week"
              disabled={loading}
            >
              ›
            </button>
          </div>

          <div className="range-display">
            {formatRangeLabel(appliedStart, appliedEnd)}
          </div>

          <div className="range-pickers">
            <input
              type="date"
              value={appliedStart}
              onChange={(e) => onPickStart(e.target.value)}
              aria-label="Range start"
            />
            <span className="range-sep">→</span>
            <input
              type="date"
              value={appliedEnd}
              onChange={(e) => onPickEnd(e.target.value)}
              aria-label="Range end"
            />
          </div>
        </div>

        <div className="toolbar-right">
          <select
            className="toolbar-select"
            aria-label="Filter by calendar"
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

          <button
            type="button"
            className="primary"
            onClick={openCreateForm}
            disabled={formOpen && editingId == null}
          >
            + Add Event
          </button>

          <Link href="/availability" className="button-link">
            + Add Blocked Time
          </Link>
        </div>
      </div>

      {/* Inline event create/edit panel */}
      {formOpen && (
        <div className="card" style={{ marginBottom: "1.25rem" }}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "baseline",
              marginBottom: "0.75rem",
            }}
          >
            <h3 style={{ margin: 0 }}>
              {editingId != null ? "Edit event" : "New event"}
            </h3>
            <button
              type="button"
              className="ghost"
              onClick={cancelForm}
              disabled={submitting}
            >
              Close
            </button>
          </div>

          <form onSubmit={onSubmit} className="event-form">
            <label>
              Calendar *
              <select
                value={form.calendar_id}
                onChange={(e) =>
                  setForm((f) => ({ ...f, calendar_id: e.target.value }))
                }
                required
              >
                <option value="">Select a calendar…</option>
                {calendars.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </label>

            <label>
              Title *
              <input
                type="text"
                value={form.title}
                onChange={(e) =>
                  setForm((f) => ({ ...f, title: e.target.value }))
                }
                required
              />
            </label>

            <label>
              Start *
              <input
                type="datetime-local"
                value={form.start_time}
                onChange={(e) =>
                  setForm((f) => ({ ...f, start_time: e.target.value }))
                }
                required
              />
            </label>

            <label>
              End *
              <input
                type="datetime-local"
                value={form.end_time}
                onChange={(e) =>
                  setForm((f) => ({ ...f, end_time: e.target.value }))
                }
                required
              />
            </label>

            <label>
              Category
              <input
                type="text"
                value={form.category}
                onChange={(e) =>
                  setForm((f) => ({ ...f, category: e.target.value }))
                }
              />
            </label>

            <label>
              Priority
              <input
                type="text"
                value={form.priority}
                onChange={(e) =>
                  setForm((f) => ({ ...f, priority: e.target.value }))
                }
                placeholder="low / medium / high"
              />
            </label>

            <label>
              Location
              <input
                type="text"
                value={form.location}
                onChange={(e) =>
                  setForm((f) => ({ ...f, location: e.target.value }))
                }
              />
            </label>

            <label className="full">
              Description
              <textarea
                rows={3}
                value={form.description}
                onChange={(e) =>
                  setForm((f) => ({ ...f, description: e.target.value }))
                }
              />
            </label>

            {formError && (
              <div className="error-box full" role="alert">
                {formError}
              </div>
            )}

            {formConflicts.length > 0 && (
              <div className="error-box full" role="alert">
                <strong>Conflicts:</strong>
                <ul style={{ margin: "0.5rem 0 0 1rem", padding: 0 }}>
                  {formConflicts.map((c, i) => (
                    <li key={i}>
                      <span style={{ fontFamily: "monospace" }}>
                        {c.reason_code}
                      </span>
                      {" — "}
                      {c.message}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="form-actions full">
              <button type="submit" className="primary" disabled={submitting}>
                {submitting
                  ? "Saving…"
                  : editingId != null
                  ? "Update event"
                  : "Create event"}
              </button>
              <button
                type="button"
                className="ghost"
                onClick={cancelForm}
                disabled={submitting}
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="page-grid">
        {/* Main: 7-column week board */}
        <div className="page-main">
          {loading ? (
            <div className="card">
              <p className="muted" style={{ margin: 0 }}>
                Loading schedule…
              </p>
            </div>
          ) : (
            <div className="week-grid-wrap">
              <div
                className="week-grid"
                style={{
                  gridTemplateColumns: `repeat(${dayKeys.length}, minmax(140px, 1fr))`,
                }}
              >
                {dayKeys.map((key) => {
                  const dayEvents = grouped.get(key) ?? [];
                  const { weekday, daynum } = dayHeaderParts(key);
                  const today = isToday(key);
                  const weekend = isWeekend(key);
                  const classes = ["week-col"];
                  if (today) classes.push("is-today");
                  if (weekend) classes.push("is-weekend");
                  return (
                    <div key={key} className={classes.join(" ")}>
                      <div className="week-col-header">
                        <div className="week-col-header-left">
                          <span className="week-col-day">{weekday}</span>
                          <span className="week-col-num">{daynum}</span>
                        </div>
                        <span className="week-col-count">
                          {dayEvents.length === 0
                            ? "—"
                            : `${dayEvents.length}`}
                        </span>
                      </div>

                      {dayEvents.length === 0 ? (
                        <div className="week-col-empty">No events</div>
                      ) : (
                        <ul className="week-col-events">
                          {dayEvents.map((ev) => {
                            const cal = calendarsById.get(ev.calendar_id);
                            return (
                              <li key={ev.id} className="week-event">
                                <div className="week-event-time">
                                  {formatTimeRange(ev.start_time, ev.end_time)}
                                </div>
                                <div className="week-event-title">
                                  {ev.title}
                                </div>
                                <div className="week-event-meta">
                                  {cal ? cal.name : `cal #${ev.calendar_id}`}
                                  {ev.priority ? ` · ${ev.priority}` : ""}
                                  {ev.location ? ` · ${ev.location}` : ""}
                                </div>
                                <div className="week-event-actions">
                                  <button
                                    type="button"
                                    className="ghost"
                                    onClick={() => startEdit(ev)}
                                  >
                                    Edit
                                  </button>
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
            </div>
          )}
        </div>

        {/* Right sidebar */}
        <aside className="page-side">
          {/* Upcoming */}
          <div className="sidebar-card">
            <div className="sidebar-card-title">
              <span>Upcoming</span>
              <span className="muted small">
                {upcoming.length} of {events.length}
              </span>
            </div>
            {upcoming.length === 0 ? (
              <div className="empty-state">
                <span className="empty-state-strong">Nothing upcoming</span>
                Nothing scheduled in this range.
              </div>
            ) : (
              <ul className="list-rows">
                {upcoming.map((e) => (
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

          {/* Current view summary */}
          <div className="sidebar-card">
            <div className="sidebar-card-title">
              <span>Current view</span>
            </div>
            <div className="metric-rows">
              <div className="metric-row">
                <span className="metric-label">Days</span>
                <span className="metric-value">{totalDays}</span>
              </div>
              <div className="metric-row">
                <span className="metric-label">Events</span>
                <span className="metric-value">{events.length}</span>
              </div>
              <div className="metric-row">
                <span className="metric-label">Calendar</span>
                <span className="metric-value">
                  {calendarFilter
                    ? calendarsById.get(Number(calendarFilter))?.name ??
                      `#${calendarFilter}`
                    : "All"}
                </span>
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

// Pull structured ConflictDetail entries out of a 409 response body, if any.
function extractConflicts(e: unknown): ConflictDetail[] {
  if (!(e instanceof ApiError) || e.status !== 409) return [];
  const body = e.body as { detail?: unknown } | null;
  if (!body || typeof body !== "object") return [];
  const detail = (body as { detail?: unknown }).detail;
  if (!detail || typeof detail !== "object") return [];
  const conflicts = (detail as { conflicts?: unknown }).conflicts;
  if (!Array.isArray(conflicts)) return [];
  return conflicts.filter(
    (c): c is ConflictDetail =>
      !!c &&
      typeof c === "object" &&
      typeof (c as ConflictDetail).reason_code === "string" &&
      typeof (c as ConflictDetail).message === "string"
  );
}

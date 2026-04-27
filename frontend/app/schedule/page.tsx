"use client";

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

// Default range: today through +7 days
function defaultRange(): { start: string; end: string } {
  const start = new Date();
  const end = new Date();
  end.setDate(start.getDate() + 7);
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

// datetime-local inputs return "YYYY-MM-DDTHH:MM" — already naive local time.
// Ensure trailing seconds for backend ISO-8601 parsing.
function fromLocalInputNaive(v: string): string {
  return v.length === 16 ? `${v}:00` : v;
}

function toLocalInput(iso: string): string {
  // Convert backend ISO (naive) to "YYYY-MM-DDTHH:mm" for <input type="datetime-local">.
  const d = new Date(iso);
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
    `T${pad(d.getHours())}:${pad(d.getMinutes())}`
  );
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
  const [rangeError, setRangeError] = useState<string | null>(null);

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

  function onApply(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setRangeError(null);
    if (!startDate || !endDate) {
      setRangeError("Start and end dates are required.");
      return;
    }
    if (startDate > endDate) {
      setRangeError("Start date must be before or equal to end date.");
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

          {!formOpen && (
            <button
              type="button"
              className="primary"
              onClick={openCreateForm}
              style={{ marginLeft: "0.5rem" }}
            >
              + Add Event
            </button>
          )}
        </div>
      </div>

      {rangeError && (
        <div className="error-box" role="alert">
          {rangeError}
        </div>
      )}

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
          )}
        </div>

        {/* Right sidebar */}
        <aside className="page-side">
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

"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  ApiError,
  createBlockedTime,
  createEvent,
  deleteBlockedTime,
  deleteEvent,
  getWeeklyMetrics,
  listBlockedTimes,
  listCalendars,
  listEvents,
  updateBlockedTime,
  updateEvent,
} from "@/lib/api";
import type {
  BlockedTime,
  BlockedTimeCreate,
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

// Convert a datetime-local input value into the naive ISO string the backend
// expects. Defensively strips any trailing "Z" or timezone offset (datetime-
// local should never produce these, but we guarantee the no-tz invariant) and
// pads ":00" seconds when missing.
function fromLocalInputNaive(v: string): string {
  if (!v) return v;
  let s = v.replace(/Z$/, "").replace(/[+-]\d{2}:?\d{2}$/, "");
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(s)) s = `${s}:00`;
  return s;
}

// Convert an ISO datetime from the backend into a datetime-local input value
// (YYYY-MM-DDTHH:MM). Parses the wall-clock components directly from the
// string when it is naive, so we never let `new Date` apply a local-time
// shift to what we already know is naive.
function toLocalInput(iso: string): string {
  const naive = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(iso);
  if (naive) {
    const [, y, m, d, hh, mm] = naive;
    return `${y}-${m}-${d}T${hh}:${mm}`;
  }
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
  return `${formatTimeShort(startIso)} – ${formatTimeShort(endIso)}`;
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

function formatHourLabel(h: number): string {
  if (h === 0) return "12 AM";
  if (h === 12) return "12 PM";
  if (h < 12) return `${h} AM`;
  return `${h - 12} PM`;
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

function dayKeyOf(iso: string): string {
  const d = new Date(iso);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function dayStartTime(dayKey: string): number {
  const [y, m, d] = dayKey.split("-").map(Number);
  return new Date(y, (m ?? 1) - 1, d ?? 1).getTime();
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

function dayHeaderParts(key: string): { weekday: string; daynum: string } {
  const [y, m, d] = key.split("-").map(Number);
  const date = new Date(y, (m ?? 1) - 1, d ?? 1);
  return {
    weekday: date.toLocaleDateString(undefined, { weekday: "short" }),
    daynum: date.toLocaleDateString(undefined, { day: "numeric" }),
  };
}

// Calendar grid layout constants.
const VISIBLE_START_HOUR = 8; // 8 AM
const VISIBLE_END_HOUR = 18; // 6 PM (exclusive bottom)
const VISIBLE_HOURS = VISIBLE_END_HOUR - VISIBLE_START_HOUR;
const HOUR_HEIGHT = 56; // px per hour
const GRID_HEIGHT = VISIBLE_HOURS * HOUR_HEIGHT;
const HOUR_LABELS = Array.from(
  { length: VISIBLE_HOURS + 1 },
  (_, i) => VISIBLE_START_HOUR + i
);

// Decimal hours of `iso` relative to the given dayKey, clamped to [0, 24].
function hoursOnDay(iso: string, dayKey: string): number {
  const t = new Date(iso).getTime();
  const dayStart = dayStartTime(dayKey);
  const dayEnd = dayStart + 86400000;
  if (t <= dayStart) return 0;
  if (t >= dayEnd) return 24;
  return (t - dayStart) / 3600000;
}

// Return absolute placement for an event/blocked-time on `dayKey`, clipped
// to the visible 8 AM..6 PM window. Returns null if it does not overlap
// the visible window on that day.
function placeOnGrid(
  startIso: string,
  endIso: string,
  dayKey: string
): { top: number; height: number } | null {
  const startH = hoursOnDay(startIso, dayKey);
  const endH = hoursOnDay(endIso, dayKey);
  const visibleStart = Math.max(startH, VISIBLE_START_HOUR);
  const visibleEnd = Math.min(endH, VISIBLE_END_HOUR);
  if (visibleEnd <= visibleStart) return null;
  const top = (visibleStart - VISIBLE_START_HOUR) * HOUR_HEIGHT;
  const height = Math.max(
    18,
    (visibleEnd - visibleStart) * HOUR_HEIGHT
  );
  return { top, height };
}

function overlapsDay(startIso: string, endIso: string, dayKey: string): boolean {
  const dayStart = dayStartTime(dayKey);
  const dayEnd = dayStart + 86400000;
  return new Date(startIso).getTime() < dayEnd &&
    new Date(endIso).getTime() > dayStart;
}

// Restrained event color palette keyed off calendar id.
const EVENT_PALETTE = [
  { bar: "#5d80c4", bg: "#eef3fb", border: "#cfdcef" }, // blue
  { bar: "#7c9b6f", bg: "#eef4ea", border: "#d4e1cb" }, // green
  { bar: "#a07ab8", bg: "#f3edf9", border: "#ddcfea" }, // purple
  { bar: "#c98d54", bg: "#fbf1e6", border: "#eed5b8" }, // amber
  { bar: "#c46868", bg: "#fbeded", border: "#eecaca" }, // red
];

function colorForCalendar(calendarId: number): typeof EVENT_PALETTE[number] {
  const idx = ((calendarId % EVENT_PALETTE.length) + EVENT_PALETTE.length) %
    EVENT_PALETTE.length;
  return EVENT_PALETTE[idx];
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

interface BlockedFormState {
  title: string;
  reason: string;
  notes: string;
  start_time: string; // datetime-local
  end_time: string;   // datetime-local
}

const EMPTY_BLOCKED_FORM: BlockedFormState = {
  title: "",
  reason: "",
  notes: "",
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
  const [blockedTimes, setBlockedTimes] = useState<BlockedTime[]>([]);
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

  // Inline blocked-time create/edit panel state.
  const [blockedFormOpen, setBlockedFormOpen] = useState<boolean>(false);
  const [blockedForm, setBlockedForm] =
    useState<BlockedFormState>(EMPTY_BLOCKED_FORM);
  const [editingBlockedId, setEditingBlockedId] = useState<number | null>(null);
  const [blockedSubmitting, setBlockedSubmitting] = useState<boolean>(false);
  const [blockedFormError, setBlockedFormError] = useState<string | null>(null);

  const calendarsById = useMemo(() => {
    const map = new Map<number, Calendar>();
    calendars.forEach((c) => map.set(c.id, c));
    return map;
  }, [calendars]);

  async function loadSchedule(
    start: string,
    end: string,
    calId: string
  ): Promise<void> {
    setLoading(true);
    setError(null);
    try {
      const startIso = dateInputToNaiveStart(start);
      const endIso = dateInputToNaiveEndExclusive(end);
      const [evs, blocks] = await Promise.all([
        listEvents({
          calendarId: calId ? Number(calId) : undefined,
          startTime: startIso,
          endTime: endIso,
        }),
        listBlockedTimes({ startTime: startIso, endTime: endIso }).catch(
          () => [] as BlockedTime[]
        ),
      ]);
      setEvents(evs);
      setBlockedTimes(blocks);
    } catch (e) {
      setError(describeError(e));
    } finally {
      setLoading(false);
    }
  }

  // Initial load: calendars + events + blocked times + metrics
  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const startIso = dateInputToNaiveStart(appliedStart);
        const endIso = dateInputToNaiveEndExclusive(appliedEnd);
        const [cals, evs, blocks, m] = await Promise.all([
          listCalendars(),
          listEvents({ startTime: startIso, endTime: endIso }),
          listBlockedTimes({ startTime: startIso, endTime: endIso }).catch(
            () => [] as BlockedTime[]
          ),
          getWeeklyMetrics().catch(() => null),
        ]);
        if (cancelled) return;
        setCalendars(cals);
        setEvents(evs);
        setBlockedTimes(blocks);
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
    loadSchedule(start, end, calendarFilter);
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
    loadSchedule(appliedStart, appliedEnd, v);
  }

  function resetForm() {
    setForm(EMPTY_FORM);
    setEditingId(null);
    setFormError(null);
    setFormConflicts([]);
  }

  function openCreateForm() {
    resetForm();
    closeBlockedForm();
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
    closeBlockedForm();
    setFormOpen(true);
  }

  function cancelForm() {
    resetForm();
    setFormOpen(false);
  }

  function resetBlockedForm() {
    setBlockedForm(EMPTY_BLOCKED_FORM);
    setEditingBlockedId(null);
    setBlockedFormError(null);
  }

  function closeBlockedForm() {
    resetBlockedForm();
    setBlockedFormOpen(false);
  }

  function openCreateBlocked() {
    resetBlockedForm();
    // Close the event panel so only one form is open at a time.
    resetForm();
    setFormOpen(false);
    setBlockedFormOpen(true);
  }

  function startEditBlocked(b: BlockedTime) {
    setEditingBlockedId(b.id);
    setBlockedFormError(null);
    setBlockedForm({
      title: b.title,
      reason: b.reason ?? "",
      notes: b.notes ?? "",
      start_time: toLocalInput(b.start_time),
      end_time: toLocalInput(b.end_time),
    });
    // Close the event panel so only one form is open at a time.
    resetForm();
    setFormOpen(false);
    setBlockedFormOpen(true);
  }

  function cancelBlockedForm() {
    closeBlockedForm();
  }

  async function onSubmitBlocked(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBlockedFormError(null);

    if (!blockedForm.title.trim()) {
      setBlockedFormError("Title is required.");
      return;
    }
    if (!blockedForm.start_time || !blockedForm.end_time) {
      setBlockedFormError("Start and end time are required.");
      return;
    }
    if (new Date(blockedForm.start_time) >= new Date(blockedForm.end_time)) {
      setBlockedFormError("Start time must be before end time.");
      return;
    }

    const payload: BlockedTimeCreate = {
      title: blockedForm.title.trim(),
      reason: blockedForm.reason.trim() || null,
      notes: blockedForm.notes.trim() || null,
      start_time: fromLocalInputNaive(blockedForm.start_time),
      end_time: fromLocalInputNaive(blockedForm.end_time),
    };

    setBlockedSubmitting(true);
    try {
      if (editingBlockedId != null) {
        await updateBlockedTime(editingBlockedId, payload);
      } else {
        await createBlockedTime(payload);
      }
      closeBlockedForm();
      await loadSchedule(appliedStart, appliedEnd, calendarFilter);
    } catch (err) {
      setBlockedFormError(describeError(err));
    } finally {
      setBlockedSubmitting(false);
    }
  }

  async function onDeleteBlocked(id: number) {
    if (!window.confirm("Delete this blocked time?")) return;
    try {
      await deleteBlockedTime(id);
      if (editingBlockedId === id) closeBlockedForm();
      await loadSchedule(appliedStart, appliedEnd, calendarFilter);
    } catch (err) {
      setError(describeError(err));
    }
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
      await loadSchedule(appliedStart, appliedEnd, calendarFilter);
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
      await loadSchedule(appliedStart, appliedEnd, calendarFilter);
    } catch (err) {
      setError(describeError(err));
    }
  }

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

          <button
            type="button"
            className="ghost"
            onClick={openCreateBlocked}
            disabled={blockedFormOpen && editingBlockedId == null}
          >
            + Add Blocked Time
          </button>
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

      {/* Inline blocked-time create/edit panel */}
      {blockedFormOpen && (
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
              {editingBlockedId != null
                ? "Edit blocked time"
                : "New blocked time"}
            </h3>
            <button
              type="button"
              className="ghost"
              onClick={cancelBlockedForm}
              disabled={blockedSubmitting}
            >
              Close
            </button>
          </div>

          <form onSubmit={onSubmitBlocked} className="event-form">
            <label>
              Title *
              <input
                type="text"
                value={blockedForm.title}
                onChange={(e) =>
                  setBlockedForm((f) => ({ ...f, title: e.target.value }))
                }
                required
              />
            </label>

            <label>
              Reason
              <input
                type="text"
                value={blockedForm.reason}
                onChange={(e) =>
                  setBlockedForm((f) => ({ ...f, reason: e.target.value }))
                }
                placeholder="e.g. Focus time, PTO"
              />
            </label>

            <label>
              Start *
              <input
                type="datetime-local"
                value={blockedForm.start_time}
                onChange={(e) =>
                  setBlockedForm((f) => ({ ...f, start_time: e.target.value }))
                }
                required
              />
            </label>

            <label>
              End *
              <input
                type="datetime-local"
                value={blockedForm.end_time}
                onChange={(e) =>
                  setBlockedForm((f) => ({ ...f, end_time: e.target.value }))
                }
                required
              />
            </label>

            <label className="full">
              Notes
              <textarea
                rows={3}
                value={blockedForm.notes}
                onChange={(e) =>
                  setBlockedForm((f) => ({ ...f, notes: e.target.value }))
                }
              />
            </label>

            {blockedFormError && (
              <div className="error-box full" role="alert">
                {blockedFormError}
              </div>
            )}

            <div className="form-actions full">
              <button
                type="submit"
                className="primary"
                disabled={blockedSubmitting}
              >
                {blockedSubmitting
                  ? "Saving…"
                  : editingBlockedId != null
                  ? "Update blocked time"
                  : "Create blocked time"}
              </button>
              <button
                type="button"
                className="ghost"
                onClick={cancelBlockedForm}
                disabled={blockedSubmitting}
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="page-grid schedule-page-grid">
        {/* Main: weekly calendar grid */}
        <div className="page-main">
          <div className="cal-panel">
            {/* Day headers */}
            <div className="cal-row cal-header-row">
              <div className="cal-time-cell cal-time-corner" aria-hidden />
              {dayKeys.map((key) => {
                const { weekday, daynum } = dayHeaderParts(key);
                const today = isToday(key);
                return (
                  <div
                    key={key}
                    className={`cal-day-header${today ? " is-today" : ""}`}
                  >
                    <div className="cal-day-header-text">
                      <span className="cal-day-weekday">{weekday}</span>
                      <span className="cal-day-num">{daynum}</span>
                    </div>
                    {today && <span className="cal-today-dot" aria-hidden />}
                  </div>
                );
              })}
            </div>

            {/* All-day row */}
            <div className="cal-row cal-allday-row">
              <div className="cal-time-cell cal-allday-label">All day</div>
              {dayKeys.map((key) => (
                <div key={key} className="cal-allday-cell" />
              ))}
            </div>

            {/* Body: time gutter + day columns with hour grid */}
            <div className="cal-body">
              <div
                className="cal-time-gutter"
                style={{ height: GRID_HEIGHT }}
                aria-hidden
              >
                {HOUR_LABELS.map((h) => (
                  <div
                    key={h}
                    className="cal-hour-label"
                    style={{ top: (h - VISIBLE_START_HOUR) * HOUR_HEIGHT }}
                  >
                    {formatHourLabel(h)}
                  </div>
                ))}
              </div>

              {dayKeys.map((key, idx) => {
                const dayEvents = events.filter((ev) =>
                  overlapsDay(ev.start_time, ev.end_time, key)
                );
                const dayBlocks = blockedTimes.filter((b) =>
                  overlapsDay(b.start_time, b.end_time, key)
                );
                const today = isToday(key);
                const alt = idx % 2 === 1;
                const colClasses = ["cal-day-col"];
                if (alt) colClasses.push("is-alt");
                if (today) colClasses.push("is-today");
                return (
                  <div
                    key={key}
                    className={colClasses.join(" ")}
                    style={{ height: GRID_HEIGHT }}
                  >
                    {/* Blocked / unavailable time */}
                    {dayBlocks.map((b) => {
                      const place = placeOnGrid(
                        b.start_time,
                        b.end_time,
                        key
                      );
                      if (!place) return null;
                      return (
                        <div
                          key={`b-${b.id}-${key}`}
                          className="cal-blocked"
                          style={{ top: place.top, height: place.height }}
                          title={`${b.title} • Blocked`}
                        >
                          <button
                            type="button"
                            className="cal-blocked-inner"
                            onClick={() => startEditBlocked(b)}
                            aria-label={`Edit blocked time ${b.title}`}
                          >
                            <span
                              className="cal-blocked-icon"
                              aria-hidden
                            >
                              ⊘
                            </span>
                            <div className="cal-blocked-text">
                              <div className="cal-blocked-title">
                                {b.title}
                              </div>
                              {place.height >= 40 && (
                                <div className="cal-blocked-time">
                                  {formatTimeRange(b.start_time, b.end_time)}
                                </div>
                              )}
                            </div>
                          </button>
                          <button
                            type="button"
                            className="cal-event-del"
                            onClick={(e) => {
                              e.stopPropagation();
                              onDeleteBlocked(b.id);
                            }}
                            aria-label={`Delete blocked time ${b.title}`}
                            title="Delete"
                          >
                            ×
                          </button>
                        </div>
                      );
                    })}

                    {/* Events */}
                    {dayEvents.map((ev) => {
                      const place = placeOnGrid(
                        ev.start_time,
                        ev.end_time,
                        key
                      );
                      if (!place) return null;
                      const color = colorForCalendar(ev.calendar_id);
                      const cal = calendarsById.get(ev.calendar_id);
                      return (
                        <div
                          key={`e-${ev.id}-${key}`}
                          className="cal-event"
                          style={{
                            top: place.top,
                            height: place.height,
                            background: color.bg,
                            borderColor: color.border,
                            borderLeftColor: color.bar,
                          }}
                        >
                          <button
                            type="button"
                            className="cal-event-body"
                            onClick={() => startEdit(ev)}
                            title={`${ev.title} — ${formatTimeRange(
                              ev.start_time,
                              ev.end_time
                            )}`}
                          >
                            <div className="cal-event-title">{ev.title}</div>
                            {place.height >= 40 && (
                              <div className="cal-event-time">
                                {formatTimeRange(ev.start_time, ev.end_time)}
                              </div>
                            )}
                            {place.height >= 78 && (cal || ev.location) && (
                              <div className="cal-event-meta">
                                {cal ? cal.name : `cal #${ev.calendar_id}`}
                                {ev.location ? ` · ${ev.location}` : ""}
                              </div>
                            )}
                          </button>
                          <button
                            type="button"
                            className="cal-event-del"
                            onClick={(e) => {
                              e.stopPropagation();
                              onDelete(ev.id);
                            }}
                            aria-label={`Delete ${ev.title}`}
                            title="Delete"
                          >
                            ×
                          </button>
                        </div>
                      );
                    })}
                  </div>
                );
              })}
            </div>
          </div>

          {loading && (
            <p className="muted small" style={{ marginTop: "0.6rem" }}>
              Loading schedule…
            </p>
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
                {upcoming.map((e) => {
                  const color = colorForCalendar(e.calendar_id);
                  return (
                    <li key={e.id}>
                      <span
                        className="row-dot"
                        style={{ background: color.bar }}
                        aria-hidden
                      />
                      <div className="row-body">
                        <div className="row-title">{e.title}</div>
                        <div className="row-meta">
                          {formatDayTime(e.start_time)}
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
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

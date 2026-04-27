"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  ApiError,
  createEvent,
  deleteEvent,
  listCalendars,
  listEvents,
  updateEvent,
} from "@/lib/api";
import type { Calendar, Event, EventCreate } from "@/lib/types";

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

function toLocalInput(iso: string): string {
  // Convert ISO to "YYYY-MM-DDTHH:mm" in local time for <input type="datetime-local">.
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
    `T${pad(d.getHours())}:${pad(d.getMinutes())}`
  );
}

function fromLocalInput(v: string): string {
  // datetime-local inputs return "YYYY-MM-DDTHH:MM" — naive local time.
  // Backend MVP time contract rejects tz-aware datetimes, so pass through
  // naively (only adding seconds for ISO-8601 completeness).
  return v.length === 16 ? `${v}:00` : v;
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

export default function EventsPage() {
  const [calendars, setCalendars] = useState<Calendar[]>([]);
  const [events, setEvents] = useState<Event[]>([]);
  const [filterCalendarId, setFilterCalendarId] = useState<string>("");
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const calendarsById = useMemo(() => {
    const map = new Map<number, Calendar>();
    calendars.forEach((c) => map.set(c.id, c));
    return map;
  }, [calendars]);

  async function loadAll(calId?: number) {
    setLoading(true);
    setError(null);
    try {
      const [cals, evs] = await Promise.all([
        listCalendars(),
        listEvents(calId),
      ]);
      setCalendars(cals);
      setEvents(evs);
    } catch (e) {
      setError(describeError(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAll();
  }, []);

  async function reloadEvents(calId?: number) {
    try {
      const evs = await listEvents(calId);
      setEvents(evs);
    } catch (e) {
      setError(describeError(e));
    }
  }

  function onFilterChange(v: string) {
    setFilterCalendarId(v);
    reloadEvents(v ? Number(v) : undefined);
  }

  function resetForm() {
    setForm(EMPTY_FORM);
    setEditingId(null);
    setFormError(null);
  }

  function startEdit(ev: Event) {
    setEditingId(ev.id);
    setFormError(null);
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
  }

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setFormError(null);

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
      start_time: fromLocalInput(form.start_time),
      end_time: fromLocalInput(form.end_time),
    };

    setSubmitting(true);
    try {
      if (editingId != null) {
        await updateEvent(editingId, payload);
      } else {
        await createEvent(payload);
      }
      resetForm();
      await reloadEvents(
        filterCalendarId ? Number(filterCalendarId) : undefined
      );
    } catch (err) {
      setFormError(describeError(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function onDelete(id: number) {
    const ok = window.confirm("Delete this event?");
    if (!ok) return;
    try {
      await deleteEvent(id);
      if (editingId === id) resetForm();
      await reloadEvents(
        filterCalendarId ? Number(filterCalendarId) : undefined
      );
    } catch (err) {
      setError(describeError(err));
    }
  }

  return (
    <section>
      <h2>Calendars & Events</h2>

      {error && (
        <div className="error-box" role="alert">
          {error}
        </div>
      )}

      <h3>Calendars</h3>
      {loading ? (
        <p className="muted">Loading…</p>
      ) : calendars.length === 0 ? (
        <p className="muted">No calendars yet.</p>
      ) : (
        <ul className="event-list">
          {calendars.map((c) => (
            <li key={c.id}>
              <strong>{c.name}</strong>
              {c.color && (
                <span className="muted"> — color {c.color}</span>
              )}
            </li>
          ))}
        </ul>
      )}

      <h3 style={{ marginTop: "2rem" }}>
        {editingId != null ? "Edit event" : "New event"}
      </h3>
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

        <div className="form-actions full">
          <button type="submit" disabled={submitting}>
            {submitting
              ? "Saving…"
              : editingId != null
              ? "Update event"
              : "Create event"}
          </button>
          {editingId != null && (
            <button type="button" onClick={resetForm} disabled={submitting}>
              Cancel
            </button>
          )}
        </div>
      </form>

      <h3 style={{ marginTop: "2rem" }}>Events</h3>
      <label>
        Filter by calendar
        <select
          value={filterCalendarId}
          onChange={(e) => onFilterChange(e.target.value)}
        >
          <option value="">All calendars</option>
          {calendars.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </label>

      {events.length === 0 ? (
        <p className="muted">No events.</p>
      ) : (
        <ul className="event-list">
          {events.map((ev) => {
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
                  <button type="button" onClick={() => startEdit(ev)}>
                    Edit
                  </button>
                  <button type="button" onClick={() => onDelete(ev.id)}>
                    Delete
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
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

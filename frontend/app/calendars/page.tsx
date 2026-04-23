"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  ApiError,
  createCalendar,
  deleteCalendar,
  listCalendars,
  updateCalendar,
} from "@/lib/api";
import type { Calendar, CalendarCreate } from "@/lib/types";

interface FormState {
  name: string;
  color: string;
}

const EMPTY_FORM: FormState = { name: "", color: "" };

export default function CalendarsPage() {
  const [calendars, setCalendars] = useState<Calendar[]>([]);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  async function loadAll() {
    setLoading(true);
    setError(null);
    try {
      const cals = await listCalendars();
      setCalendars(cals);
    } catch (e) {
      setError(describeError(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAll();
  }, []);

  function resetForm() {
    setForm(EMPTY_FORM);
    setEditingId(null);
    setFormError(null);
  }

  function startEdit(c: Calendar) {
    setEditingId(c.id);
    setFormError(null);
    setForm({ name: c.name, color: c.color ?? "" });
  }

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setFormError(null);

    const name = form.name.trim();
    if (!name) {
      setFormError("Name is required.");
      return;
    }

    const payload: CalendarCreate = {
      name,
      color: form.color.trim() || null,
    };

    setSubmitting(true);
    try {
      if (editingId != null) {
        await updateCalendar(editingId, payload);
      } else {
        await createCalendar(payload);
      }
      resetForm();
      await loadAll();
    } catch (err) {
      setFormError(describeError(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function onDelete(id: number) {
    const ok = window.confirm(
      "Delete this calendar? Associated events may be affected."
    );
    if (!ok) return;
    try {
      await deleteCalendar(id);
      if (editingId === id) resetForm();
      await loadAll();
    } catch (err) {
      setError(describeError(err));
    }
  }

  return (
    <section>
      <h2>Calendars</h2>

      {error && (
        <div className="error-box" role="alert">
          {error}
        </div>
      )}

      <h3>{editingId != null ? "Edit calendar" : "New calendar"}</h3>
      <form onSubmit={onSubmit} className="event-form">
        <label>
          Name *
          <input
            type="text"
            value={form.name}
            onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            required
          />
        </label>

        <label>
          Color
          <input
            type="text"
            value={form.color}
            onChange={(e) => setForm((f) => ({ ...f, color: e.target.value }))}
            placeholder="#2563eb or blue"
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
              ? "Update calendar"
              : "Create calendar"}
          </button>
          {editingId != null && (
            <button type="button" onClick={resetForm} disabled={submitting}>
              Cancel
            </button>
          )}
        </div>
      </form>

      <h3 style={{ marginTop: "2rem" }}>All calendars</h3>
      {loading ? (
        <p className="muted">Loading…</p>
      ) : calendars.length === 0 ? (
        <p className="muted">No calendars yet.</p>
      ) : (
        <ul className="event-list">
          {calendars.map((c) => (
            <li key={c.id} className="event-row">
              <div>
                <strong>{c.name}</strong>
                {c.color && (
                  <span className="muted"> — color {c.color}</span>
                )}
                <div className="muted small">id #{c.id}</div>
              </div>
              <div className="row-actions">
                <button type="button" onClick={() => startEdit(c)}>
                  Edit
                </button>
                <button type="button" onClick={() => onDelete(c.id)}>
                  Delete
                </button>
              </div>
            </li>
          ))}
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

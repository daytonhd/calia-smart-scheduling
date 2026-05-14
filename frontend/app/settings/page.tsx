"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  ApiError,
  createCalendar,
  deleteCalendar,
  getDailyRhythm,
  listCalendars,
  updateCalendar,
  updateDailyRhythm,
} from "@/lib/api";
import type {
  Calendar,
  CalendarCreate,
  DailyRhythm,
  DailyRhythmUpdate,
} from "@/lib/types";

interface FormState {
  name: string;
  color: string;
}

const EMPTY_FORM: FormState = { name: "", color: "" };

// Daily Rhythm starting values — only shown until the backend responds.
const EMPTY_RHYTHM: DailyRhythm = {
  awake_start_time: "07:00",
  awake_end_time: "23:00",
  suggestions_start_time: "08:00",
  suggestions_end_time: "21:00",
};

// All times are "HH:MM" 24-hour strings from <input type="time">, which are
// always zero-padded — so plain string comparison is chronological.
function validateRhythm(r: DailyRhythm): string | null {
  const { awake_start_time, awake_end_time } = r;
  const { suggestions_start_time, suggestions_end_time } = r;
  if (
    !awake_start_time ||
    !awake_end_time ||
    !suggestions_start_time ||
    !suggestions_end_time
  ) {
    return "All four times are required.";
  }
  if (awake_start_time >= awake_end_time) {
    return "Awake hours must start before they end.";
  }
  if (suggestions_start_time >= suggestions_end_time) {
    return "Suggestion hours must start before they end.";
  }
  if (suggestions_start_time < awake_start_time) {
    return "Suggestion hours must start at or after your awake hours start.";
  }
  if (suggestions_end_time > awake_end_time) {
    return "Suggestion hours must end at or before your awake hours end.";
  }
  return null;
}

export default function SettingsPage() {
  const [calendars, setCalendars] = useState<Calendar[]>([]);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const [rhythm, setRhythm] = useState<DailyRhythm>(EMPTY_RHYTHM);
  const [rhythmLoading, setRhythmLoading] = useState<boolean>(true);
  const [rhythmSaving, setRhythmSaving] = useState<boolean>(false);
  const [rhythmError, setRhythmError] = useState<string | null>(null);
  const [rhythmSaved, setRhythmSaved] = useState<boolean>(false);

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

  async function loadRhythm() {
    setRhythmLoading(true);
    setRhythmError(null);
    try {
      const r = await getDailyRhythm();
      setRhythm(r);
    } catch (e) {
      setRhythmError(describeError(e));
    } finally {
      setRhythmLoading(false);
    }
  }

  useEffect(() => {
    loadAll();
    loadRhythm();
  }, []);

  function updateRhythmField(field: keyof DailyRhythm, value: string) {
    setRhythm((r) => ({ ...r, [field]: value }));
    setRhythmError(null);
    setRhythmSaved(false);
  }

  async function onSaveRhythm(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setRhythmError(null);
    setRhythmSaved(false);

    const validationError = validateRhythm(rhythm);
    if (validationError) {
      setRhythmError(validationError);
      return;
    }

    const payload: DailyRhythmUpdate = {
      awake_start_time: rhythm.awake_start_time,
      awake_end_time: rhythm.awake_end_time,
      suggestions_start_time: rhythm.suggestions_start_time,
      suggestions_end_time: rhythm.suggestions_end_time,
    };

    setRhythmSaving(true);
    try {
      const updated = await updateDailyRhythm(payload);
      setRhythm(updated);
      setRhythmSaved(true);
    } catch (err) {
      setRhythmError(describeError(err));
    } finally {
      setRhythmSaving(false);
    }
  }

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
      <h2>Settings</h2>

      <h3>Calendars</h3>
      <p className="muted">Create and manage calendars used by your events.</p>

      {error && (
        <div className="error-box" role="alert">
          {error}
        </div>
      )}

      <h4>{editingId != null ? "Edit calendar" : "New calendar"}</h4>
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

      <h4 style={{ marginTop: "2rem" }}>All calendars</h4>
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

      <h3 style={{ marginTop: "2.5rem" }}>Daily Rhythm</h3>
      <p className="muted">
        Set the hours Calia uses to understand your day and suggest open times.
      </p>

      {rhythmLoading ? (
        <p className="muted">Loading…</p>
      ) : (
        <form onSubmit={onSaveRhythm} className="event-form">
          <div className="full">
            <span className="rhythm-field-label">Awake hours</span>
            <div className="rhythm-time-pair">
              <input
                type="time"
                required
                aria-label="Awake hours start"
                value={rhythm.awake_start_time}
                onChange={(e) =>
                  updateRhythmField("awake_start_time", e.target.value)
                }
              />
              <span className="muted">to</span>
              <input
                type="time"
                required
                aria-label="Awake hours end"
                value={rhythm.awake_end_time}
                onChange={(e) =>
                  updateRhythmField("awake_end_time", e.target.value)
                }
              />
            </div>
          </div>

          <div className="full">
            <span className="rhythm-field-label">Suggestions use</span>
            <div className="rhythm-time-pair">
              <input
                type="time"
                required
                aria-label="Suggestions use start"
                value={rhythm.suggestions_start_time}
                onChange={(e) =>
                  updateRhythmField("suggestions_start_time", e.target.value)
                }
              />
              <span className="muted">to</span>
              <input
                type="time"
                required
                aria-label="Suggestions use end"
                value={rhythm.suggestions_end_time}
                onChange={(e) =>
                  updateRhythmField("suggestions_end_time", e.target.value)
                }
              />
            </div>
          </div>

          {rhythmError && (
            <div className="error-box full" role="alert">
              {rhythmError}
            </div>
          )}

          {rhythmSaved && (
            <div className="success-box full" role="status">
              Daily Rhythm saved.
            </div>
          )}

          <div className="form-actions full">
            <button type="submit" disabled={rhythmSaving}>
              {rhythmSaving ? "Saving…" : "Save Daily Rhythm"}
            </button>
          </div>
        </form>
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

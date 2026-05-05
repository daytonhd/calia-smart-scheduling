"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  ApiError,
  createAvailability,
  deleteAvailability,
  listAvailability,
  updateAvailability,
} from "@/lib/api";
import type {
  AvailabilityWindow,
  AvailabilityWindowCreate,
} from "@/lib/types";

const WEEKDAYS = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
];

// ---------- Availability ----------
//
// NOTE: This page is a legacy/transitional surface for AvailabilityWindow rows.
// Day-to-day unavailable periods, commutes, classes, focus blocks, and
// appointments are created as normal events with a category from the Schedule
// page. Active scheduling logic does not depend on AvailabilityWindow rows;
// this surface is retained only for backward compatibility while the
// underlying tables remain.

interface AvailFormState {
  weekday: string;    // "0"-"6"
  start_time: string; // "HH:MM"
  end_time: string;   // "HH:MM"
  active: boolean;
}

const EMPTY_AVAIL_FORM: AvailFormState = {
  weekday: "0",
  start_time: "",
  end_time: "",
  active: true,
};

function toTimeInput(v: string): string {
  // Backend returns "HH:MM:SS". <input type="time"> expects "HH:MM".
  if (!v) return "";
  return v.length >= 5 ? v.slice(0, 5) : v;
}

export default function AvailabilityPage() {
  const [windows, setWindows] = useState<AvailabilityWindow[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Availability form state
  const [availForm, setAvailForm] = useState<AvailFormState>(EMPTY_AVAIL_FORM);
  const [availEditingId, setAvailEditingId] = useState<number | null>(null);
  const [availSubmitting, setAvailSubmitting] = useState<boolean>(false);
  const [availFormError, setAvailFormError] = useState<string | null>(null);

  async function loadAll() {
    setLoading(true);
    setError(null);
    try {
      const a = await listAvailability();
      setWindows(a);
    } catch (e) {
      setError(describeError(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAll();
  }, []);

  // ---------- Availability handlers ----------

  function resetAvailForm() {
    setAvailForm(EMPTY_AVAIL_FORM);
    setAvailEditingId(null);
    setAvailFormError(null);
  }

  function startEditAvail(w: AvailabilityWindow) {
    setAvailEditingId(w.id);
    setAvailFormError(null);
    setAvailForm({
      weekday: String(w.weekday),
      start_time: toTimeInput(w.start_time),
      end_time: toTimeInput(w.end_time),
      active: w.active,
    });
  }

  async function onSubmitAvail(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setAvailFormError(null);

    if (!availForm.start_time || !availForm.end_time) {
      setAvailFormError("Start and end time are required.");
      return;
    }
    if (availForm.start_time >= availForm.end_time) {
      setAvailFormError("Start time must be before end time.");
      return;
    }

    const payload: AvailabilityWindowCreate = {
      weekday: Number(availForm.weekday),
      start_time: availForm.start_time,
      end_time: availForm.end_time,
      active: availForm.active,
    };

    setAvailSubmitting(true);
    try {
      if (availEditingId != null) {
        await updateAvailability(availEditingId, payload);
      } else {
        await createAvailability(payload);
      }
      resetAvailForm();
      await loadAll();
    } catch (err) {
      setAvailFormError(describeError(err));
    } finally {
      setAvailSubmitting(false);
    }
  }

  async function onDeleteAvail(id: number) {
    if (!window.confirm("Delete this availability window?")) return;
    try {
      await deleteAvailability(id);
      if (availEditingId === id) resetAvailForm();
      await loadAll();
    } catch (err) {
      setError(describeError(err));
    }
  }

  return (
    <section>
      <h2>Availability</h2>
      <p className="muted small">
        Legacy weekly availability windows. Day-to-day unavailable periods
        (commute, classes, focus blocks, appointments, etc.) are now created
        as normal events with a category from the Schedule page.
      </p>

      {error && (
        <div className="error-box" role="alert">
          {error}
        </div>
      )}

      <h3>{availEditingId != null ? "Edit availability" : "New availability window"}</h3>
      <p className="muted small">
        Weekly recurring time range when you&apos;re generally available.
      </p>
      <form onSubmit={onSubmitAvail} className="event-form">
        <label>
          Weekday *
          <select
            value={availForm.weekday}
            onChange={(e) =>
              setAvailForm((f) => ({ ...f, weekday: e.target.value }))
            }
            required
          >
            {WEEKDAYS.map((name, idx) => (
              <option key={idx} value={idx}>
                {name}
              </option>
            ))}
          </select>
        </label>

        <label>
          Active
          <select
            value={availForm.active ? "true" : "false"}
            onChange={(e) =>
              setAvailForm((f) => ({ ...f, active: e.target.value === "true" }))
            }
          >
            <option value="true">Yes</option>
            <option value="false">No</option>
          </select>
        </label>

        <label>
          Start *
          <input
            type="time"
            value={availForm.start_time}
            onChange={(e) =>
              setAvailForm((f) => ({ ...f, start_time: e.target.value }))
            }
            required
          />
        </label>

        <label>
          End *
          <input
            type="time"
            value={availForm.end_time}
            onChange={(e) =>
              setAvailForm((f) => ({ ...f, end_time: e.target.value }))
            }
            required
          />
        </label>

        {availFormError && (
          <div className="error-box full" role="alert">
            {availFormError}
          </div>
        )}

        <div className="form-actions full">
          <button type="submit" disabled={availSubmitting}>
            {availSubmitting
              ? "Saving…"
              : availEditingId != null
              ? "Update window"
              : "Create window"}
          </button>
          {availEditingId != null && (
            <button
              type="button"
              onClick={resetAvailForm}
              disabled={availSubmitting}
            >
              Cancel
            </button>
          )}
        </div>
      </form>

      <h3 style={{ marginTop: "1.5rem" }}>Availability windows</h3>
      {loading ? (
        <p className="muted">Loading…</p>
      ) : windows.length === 0 ? (
        <p className="muted">No availability windows yet.</p>
      ) : (
        <ul className="event-list">
          {windows.map((w) => (
            <li key={w.id} className="event-row">
              <div>
                <strong>{WEEKDAYS[w.weekday] ?? `day ${w.weekday}`}</strong>
                <span className="muted">
                  {" — "}
                  {toTimeInput(w.start_time)} → {toTimeInput(w.end_time)}
                </span>
                <div className="muted small">
                  {w.active ? "active" : "inactive"}
                </div>
              </div>
              <div className="row-actions">
                <button type="button" onClick={() => startEditAvail(w)}>
                  Edit
                </button>
                <button type="button" onClick={() => onDeleteAvail(w.id)}>
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

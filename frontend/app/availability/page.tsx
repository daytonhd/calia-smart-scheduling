"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  ApiError,
  createAvailability,
  createBlockedTime,
  deleteAvailability,
  deleteBlockedTime,
  listAvailability,
  listBlockedTimes,
  updateAvailability,
  updateBlockedTime,
} from "@/lib/api";
import type {
  AvailabilityWindow,
  AvailabilityWindowCreate,
  BlockedTime,
  BlockedTimeCreate,
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

// ---------- Blocked Times ----------

interface BlockedFormState {
  title: string;
  reason: string;
  notes: string;
  start_time: string; // datetime-local
  end_time: string;
}

const EMPTY_BLOCKED_FORM: BlockedFormState = {
  title: "",
  reason: "",
  notes: "",
  start_time: "",
  end_time: "",
};

function toLocalInput(iso: string): string {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
    `T${pad(d.getHours())}:${pad(d.getMinutes())}`
  );
}

function fromLocalInput(v: string): string {
  return new Date(v).toISOString();
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

export default function AvailabilityPage() {
  const [windows, setWindows] = useState<AvailabilityWindow[]>([]);
  const [blocked, setBlocked] = useState<BlockedTime[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Availability form state
  const [availForm, setAvailForm] = useState<AvailFormState>(EMPTY_AVAIL_FORM);
  const [availEditingId, setAvailEditingId] = useState<number | null>(null);
  const [availSubmitting, setAvailSubmitting] = useState<boolean>(false);
  const [availFormError, setAvailFormError] = useState<string | null>(null);

  // Blocked form state
  const [blockedForm, setBlockedForm] =
    useState<BlockedFormState>(EMPTY_BLOCKED_FORM);
  const [blockedEditingId, setBlockedEditingId] = useState<number | null>(null);
  const [blockedSubmitting, setBlockedSubmitting] = useState<boolean>(false);
  const [blockedFormError, setBlockedFormError] = useState<string | null>(null);

  async function loadAll() {
    setLoading(true);
    setError(null);
    try {
      const [a, b] = await Promise.all([listAvailability(), listBlockedTimes()]);
      setWindows(a);
      setBlocked(b);
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

  // ---------- Blocked handlers ----------

  function resetBlockedForm() {
    setBlockedForm(EMPTY_BLOCKED_FORM);
    setBlockedEditingId(null);
    setBlockedFormError(null);
  }

  function startEditBlocked(b: BlockedTime) {
    setBlockedEditingId(b.id);
    setBlockedFormError(null);
    setBlockedForm({
      title: b.title,
      reason: b.reason ?? "",
      notes: b.notes ?? "",
      start_time: toLocalInput(b.start_time),
      end_time: toLocalInput(b.end_time),
    });
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
      start_time: fromLocalInput(blockedForm.start_time),
      end_time: fromLocalInput(blockedForm.end_time),
    };

    setBlockedSubmitting(true);
    try {
      if (blockedEditingId != null) {
        await updateBlockedTime(blockedEditingId, payload);
      } else {
        await createBlockedTime(payload);
      }
      resetBlockedForm();
      await loadAll();
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
      if (blockedEditingId === id) resetBlockedForm();
      await loadAll();
    } catch (err) {
      setError(describeError(err));
    }
  }

  return (
    <section>
      <h2>Availability & Blocked Times</h2>

      {error && (
        <div className="error-box" role="alert">
          {error}
        </div>
      )}

      {/* -------- Availability -------- */}

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

      {/* -------- Blocked Times -------- */}

      <h3 style={{ marginTop: "2.5rem" }}>
        {blockedEditingId != null ? "Edit blocked time" : "New blocked time"}
      </h3>
      <p className="muted small">
        Specific time ranges that should be treated as unavailable.
      </p>
      <form onSubmit={onSubmitBlocked} className="event-form">
        <label className="full">
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

        <label>
          Reason
          <input
            type="text"
            value={blockedForm.reason}
            onChange={(e) =>
              setBlockedForm((f) => ({ ...f, reason: e.target.value }))
            }
            placeholder="e.g. PTO, meeting"
          />
        </label>

        <label>
          Notes
          <input
            type="text"
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
          <button type="submit" disabled={blockedSubmitting}>
            {blockedSubmitting
              ? "Saving…"
              : blockedEditingId != null
              ? "Update blocked time"
              : "Create blocked time"}
          </button>
          {blockedEditingId != null && (
            <button
              type="button"
              onClick={resetBlockedForm}
              disabled={blockedSubmitting}
            >
              Cancel
            </button>
          )}
        </div>
      </form>

      <h3 style={{ marginTop: "1.5rem" }}>Blocked times</h3>
      {loading ? (
        <p className="muted">Loading…</p>
      ) : blocked.length === 0 ? (
        <p className="muted">No blocked times yet.</p>
      ) : (
        <ul className="event-list">
          {blocked.map((b) => (
            <li key={b.id} className="event-row">
              <div>
                <strong>{b.title}</strong>
                <span className="muted">
                  {" — "}
                  {formatDateTime(b.start_time)} → {formatDateTime(b.end_time)}
                </span>
                <div className="muted small">
                  {b.reason ? `reason: ${b.reason}` : ""}
                  {b.reason && b.notes ? " · " : ""}
                  {b.notes ? `notes: ${b.notes}` : ""}
                </div>
              </div>
              <div className="row-actions">
                <button type="button" onClick={() => startEditBlocked(b)}>
                  Edit
                </button>
                <button type="button" onClick={() => onDeleteBlocked(b.id)}>
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

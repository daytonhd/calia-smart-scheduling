"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  ApiError,
  createCalendar,
  createCategory,
  deleteCalendar,
  deleteCategory,
  getDailyRhythm,
  listCalendars,
  listCategories,
  updateCalendar,
  updateCategory,
  updateDailyRhythm,
} from "@/lib/api";
import type {
  Calendar,
  CalendarCreate,
  Category,
  CategoryCreate,
  DailyRhythm,
  DailyRhythmUpdate,
} from "@/lib/types";

interface CalendarFormState {
  name: string;
  color: string;
}

interface CategoryFormState {
  name: string;
  color: string;
}

const EMPTY_CALENDAR_FORM: CalendarFormState = { name: "", color: "" };
const EMPTY_CATEGORY_FORM: CategoryFormState = { name: "", color: "" };

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
  // ----- Calendars -----
  const [calendars, setCalendars] = useState<Calendar[]>([]);
  const [calendarForm, setCalendarForm] =
    useState<CalendarFormState>(EMPTY_CALENDAR_FORM);
  const [calendarFormVisible, setCalendarFormVisible] = useState<boolean>(false);
  const [editingCalendarId, setEditingCalendarId] = useState<number | null>(null);
  const [calendarsLoading, setCalendarsLoading] = useState<boolean>(true);
  const [calendarSubmitting, setCalendarSubmitting] = useState<boolean>(false);
  const [calendarsError, setCalendarsError] = useState<string | null>(null);
  const [calendarFormError, setCalendarFormError] = useState<string | null>(null);

  // ----- Categories -----
  const [categories, setCategories] = useState<Category[]>([]);
  const [categoryForm, setCategoryForm] =
    useState<CategoryFormState>(EMPTY_CATEGORY_FORM);
  const [categoryFormVisible, setCategoryFormVisible] = useState<boolean>(false);
  const [editingCategoryId, setEditingCategoryId] = useState<number | null>(null);
  const [categoriesLoading, setCategoriesLoading] = useState<boolean>(true);
  const [categorySubmitting, setCategorySubmitting] = useState<boolean>(false);
  const [categoriesError, setCategoriesError] = useState<string | null>(null);
  const [categoryFormError, setCategoryFormError] = useState<string | null>(null);

  // ----- Daily Rhythm -----
  const [rhythm, setRhythm] = useState<DailyRhythm>(EMPTY_RHYTHM);
  const [rhythmLoading, setRhythmLoading] = useState<boolean>(true);
  const [rhythmSaving, setRhythmSaving] = useState<boolean>(false);
  const [rhythmError, setRhythmError] = useState<string | null>(null);
  const [rhythmSaved, setRhythmSaved] = useState<boolean>(false);

  async function loadCalendars() {
    setCalendarsLoading(true);
    setCalendarsError(null);
    try {
      const cals = await listCalendars();
      setCalendars(cals);
    } catch (e) {
      setCalendarsError(describeError(e));
    } finally {
      setCalendarsLoading(false);
    }
  }

  async function loadCategories() {
    setCategoriesLoading(true);
    setCategoriesError(null);
    try {
      const cats = await listCategories();
      setCategories(cats);
    } catch (e) {
      setCategoriesError(describeError(e));
    } finally {
      setCategoriesLoading(false);
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
    loadCalendars();
    loadCategories();
    loadRhythm();
  }, []);

  // ----- Daily Rhythm handlers -----

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

  // ----- Calendar handlers -----

  function resetCalendarForm() {
    setCalendarForm(EMPTY_CALENDAR_FORM);
    setEditingCalendarId(null);
    setCalendarFormError(null);
    setCalendarFormVisible(false);
  }

  function startCreateCalendar() {
    setCalendarForm(EMPTY_CALENDAR_FORM);
    setEditingCalendarId(null);
    setCalendarFormError(null);
    setCalendarFormVisible(true);
  }

  function startEditCalendar(c: Calendar) {
    setEditingCalendarId(c.id);
    setCalendarFormError(null);
    setCalendarForm({ name: c.name, color: c.color ?? "" });
    setCalendarFormVisible(true);
  }

  async function onSubmitCalendar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setCalendarFormError(null);

    const name = calendarForm.name.trim();
    if (!name) {
      setCalendarFormError("Name is required.");
      return;
    }

    const payload: CalendarCreate = {
      name,
      color: calendarForm.color.trim() || null,
    };

    setCalendarSubmitting(true);
    try {
      if (editingCalendarId != null) {
        await updateCalendar(editingCalendarId, payload);
      } else {
        await createCalendar(payload);
      }
      resetCalendarForm();
      await loadCalendars();
    } catch (err) {
      setCalendarFormError(describeError(err));
    } finally {
      setCalendarSubmitting(false);
    }
  }

  async function onDeleteCalendar(id: number) {
    const ok = window.confirm(
      "Delete this calendar? Associated events may be affected."
    );
    if (!ok) return;
    try {
      await deleteCalendar(id);
      if (editingCalendarId === id) resetCalendarForm();
      await loadCalendars();
    } catch (err) {
      setCalendarsError(describeError(err));
    }
  }

  // ----- Category handlers -----

  function resetCategoryForm() {
    setCategoryForm(EMPTY_CATEGORY_FORM);
    setEditingCategoryId(null);
    setCategoryFormError(null);
    setCategoryFormVisible(false);
  }

  function startCreateCategory() {
    setCategoryForm(EMPTY_CATEGORY_FORM);
    setEditingCategoryId(null);
    setCategoryFormError(null);
    setCategoryFormVisible(true);
  }

  function startEditCategory(c: Category) {
    setEditingCategoryId(c.id);
    setCategoryFormError(null);
    setCategoryForm({ name: c.name, color: c.color ?? "" });
    setCategoryFormVisible(true);
  }

  async function onSubmitCategory(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setCategoryFormError(null);

    const name = categoryForm.name.trim();
    if (!name) {
      setCategoryFormError("Name is required.");
      return;
    }

    const payload: CategoryCreate = {
      name,
      color: categoryForm.color.trim() || null,
    };

    setCategorySubmitting(true);
    try {
      if (editingCategoryId != null) {
        await updateCategory(editingCategoryId, payload);
      } else {
        await createCategory(payload);
      }
      resetCategoryForm();
      await loadCategories();
    } catch (err) {
      setCategoryFormError(describeError(err));
    } finally {
      setCategorySubmitting(false);
    }
  }

  async function onDeleteCategory(id: number) {
    const ok = window.confirm("Delete this category label?");
    if (!ok) return;
    try {
      await deleteCategory(id);
      if (editingCategoryId === id) resetCategoryForm();
      await loadCategories();
    } catch (err) {
      setCategoriesError(describeError(err));
    }
  }

  return (
    <section>
      <h2>Settings</h2>

      {/* ---------- Calendars ---------- */}
      <h3>Calendars</h3>
      <p className="muted">
        Calendars help you organize schedule items into separate streams — for
        example, Work and Personal.
      </p>

      {calendarsError && (
        <div className="error-box" role="alert">
          {calendarsError}
        </div>
      )}

      {calendarFormVisible && (
        <>
          <h4>
            {editingCalendarId != null ? "Edit calendar" : "New calendar"}
          </h4>
          <form onSubmit={onSubmitCalendar} className="event-form">
            <label>
              Name *
              <input
                type="text"
                value={calendarForm.name}
                onChange={(e) =>
                  setCalendarForm((f) => ({ ...f, name: e.target.value }))
                }
                required
              />
            </label>

            <label>
              Color
              <input
                type="text"
                value={calendarForm.color}
                onChange={(e) =>
                  setCalendarForm((f) => ({ ...f, color: e.target.value }))
                }
                placeholder="#2563eb or blue"
              />
            </label>

            {calendarFormError && (
              <div className="error-box full" role="alert">
                {calendarFormError}
              </div>
            )}

            <div className="form-actions full">
              <button type="submit" disabled={calendarSubmitting}>
                {calendarSubmitting
                  ? "Saving…"
                  : editingCalendarId != null
                  ? "Update calendar"
                  : "Create calendar"}
              </button>
              <button
                type="button"
                onClick={resetCalendarForm}
                disabled={calendarSubmitting}
              >
                Cancel
              </button>
            </div>
          </form>
        </>
      )}

      <h4 style={{ marginTop: "2rem" }}>All calendars</h4>
      {calendarsLoading ? (
        <p className="muted">Loading…</p>
      ) : calendars.length === 0 ? (
        <div className="settings-empty">
          <strong className="settings-empty-title">No calendars yet</strong>
          <p className="settings-empty-body">
            Calendars help you organize schedule items into separate streams.
            Create your first calendar to start adding events.
          </p>
          {!calendarFormVisible && (
            <button
              type="button"
              className="primary"
              onClick={startCreateCalendar}
            >
              Create your first calendar
            </button>
          )}
        </div>
      ) : (
        <>
          {!calendarFormVisible && (
            <div className="form-actions" style={{ marginBottom: "0.75rem" }}>
              <button
                type="button"
                className="primary"
                onClick={startCreateCalendar}
              >
                New calendar
              </button>
            </div>
          )}
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
                  <button type="button" onClick={() => startEditCalendar(c)}>
                    Edit
                  </button>
                  <button type="button" onClick={() => onDeleteCalendar(c.id)}>
                    Delete
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </>
      )}

      {/* ---------- Categories ---------- */}
      <h3 style={{ marginTop: "2.5rem" }}>Categories</h3>
      <p className="muted">
        Categories are labels for schedule items — for example, Class, Gym,
        Study, or Personal. They are descriptive only.
      </p>

      {categoriesError && (
        <div className="error-box" role="alert">
          {categoriesError}
        </div>
      )}

      {categoryFormVisible && (
        <>
          <h4>
            {editingCategoryId != null ? "Edit category" : "New category"}
          </h4>
          <form onSubmit={onSubmitCategory} className="event-form">
            <label>
              Name *
              <input
                type="text"
                value={categoryForm.name}
                onChange={(e) =>
                  setCategoryForm((f) => ({ ...f, name: e.target.value }))
                }
                required
              />
            </label>

            <label>
              Color
              <input
                type="text"
                value={categoryForm.color}
                onChange={(e) =>
                  setCategoryForm((f) => ({ ...f, color: e.target.value }))
                }
                placeholder="#10b981 (optional)"
              />
            </label>

            {categoryFormError && (
              <div className="error-box full" role="alert">
                {categoryFormError}
              </div>
            )}

            <div className="form-actions full">
              <button type="submit" disabled={categorySubmitting}>
                {categorySubmitting
                  ? "Saving…"
                  : editingCategoryId != null
                  ? "Update category"
                  : "Create category"}
              </button>
              <button
                type="button"
                onClick={resetCategoryForm}
                disabled={categorySubmitting}
              >
                Cancel
              </button>
            </div>
          </form>
        </>
      )}

      <h4 style={{ marginTop: "2rem" }}>All categories</h4>
      {categoriesLoading ? (
        <p className="muted">Loading…</p>
      ) : categories.length === 0 ? (
        <div className="settings-empty">
          <strong className="settings-empty-title">No categories yet</strong>
          <p className="settings-empty-body">
            Categories are labels you can attach to schedule items — like
            Class, Gym, Study, or Personal. Add the ones that fit how you
            think about your time.
          </p>
          {!categoryFormVisible && (
            <button
              type="button"
              className="primary"
              onClick={startCreateCategory}
            >
              Create your first category
            </button>
          )}
        </div>
      ) : (
        <>
          {!categoryFormVisible && (
            <div className="form-actions" style={{ marginBottom: "0.75rem" }}>
              <button
                type="button"
                className="primary"
                onClick={startCreateCategory}
              >
                New category
              </button>
            </div>
          )}
          <ul className="event-list">
            {categories.map((c) => (
              <li key={c.id} className="event-row">
                <div>
                  <span className="category-row-name">
                    {c.color && (
                      <span
                        className="category-swatch"
                        style={{ backgroundColor: c.color }}
                        aria-hidden="true"
                      />
                    )}
                    <strong>{c.name}</strong>
                  </span>
                  {c.color && (
                    <span className="muted"> — color {c.color}</span>
                  )}
                  <div className="muted small">id #{c.id}</div>
                </div>
                <div className="row-actions">
                  <button type="button" onClick={() => startEditCategory(c)}>
                    Edit
                  </button>
                  <button type="button" onClick={() => onDeleteCategory(c.id)}>
                    Delete
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </>
      )}

      {/* ---------- Daily Rhythm ---------- */}
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

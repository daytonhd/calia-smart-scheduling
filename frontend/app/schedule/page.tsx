"use client";

import {
  FormEvent,
  PointerEvent as ReactPointerEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  ApiError,
  createEvent,
  deleteEvent,
  getProposedRescheduleOptions,
  getRescheduleOptions,
  getWeeklyMetrics,
  listCalendars,
  listEvents,
  updateEvent,
} from "@/lib/api";
import type {
  Calendar,
  Event,
  EventCreate,
  RescheduleOption,
  WeeklyMetrics,
} from "@/lib/types";

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

function toDateInput(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

// The grid is always a 7-day week. `appliedEnd` is treated as the
// exclusive upper bound (start + WEEK_DAYS) — the day after the last
// visible column.
const WEEK_DAYS = 7;

// Default range: current week starting Monday, exclusive end (= Mon + 7).
function defaultRange(): { start: string; end: string } {
  const now = new Date();
  const dow = now.getDay(); // 0=Sun..6=Sat
  // Treat Monday as week start.
  const offsetToMonday = (dow + 6) % 7;
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate() - offsetToMonday);
  const startStr = toDateInput(start);
  return { start: startStr, end: shiftDateInput(startStr, WEEK_DAYS) };
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

function formatLongDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}

function formatShortDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
}

// Format a bare "YYYY-MM-DD" date (e.g. WeeklyMetrics.busiest_day) as
// "Weekday, MM/DD/YY". Built from local date parts so the displayed
// weekday matches the calendar day regardless of timezone.
function formatBusiestDay(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m) return iso;
  const y = Number(m[1]);
  const mo = Number(m[2]);
  const d = Number(m[3]);
  const date = new Date(y, mo - 1, d);
  const weekday = date.toLocaleDateString(undefined, { weekday: "long" });
  return `${weekday}, ${pad(mo)}/${pad(d)}/${String(y).slice(-2)}`;
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

// Always return exactly WEEK_DAYS day-keys starting from `startInput`.
// The grid is a fixed 7-day week — drift in `appliedEnd` must never
// change the column count.
function buildWeekDayKeys(startInput: string): string[] {
  const [y, m, d] = startInput.split("-").map(Number);
  const cursor = new Date(y, (m ?? 1) - 1, d ?? 1);
  const out: string[] = [];
  for (let i = 0; i < WEEK_DAYS; i++) {
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
const VISIBLE_START_HOUR = 7; // 7 AM
const VISIBLE_END_HOUR = 22; // 10 PM (exclusive bottom)
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

// Return absolute placement for an event on `dayKey`, clipped
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
  start_date: string; // YYYY-MM-DD
  start_time: string; // HH:MM
  end_date: string;   // YYYY-MM-DD
  end_time: string;   // HH:MM
}

const EMPTY_FORM: FormState = {
  calendar_id: "",
  title: "",
  description: "",
  category: "",
  priority: "",
  location: "",
  start_date: "",
  start_time: "",
  end_date: "",
  end_time: "",
};

// Split a naive ISO datetime ("YYYY-MM-DDTHH:MM[:SS]") into a date+time pair
// suitable for the modal's split inputs. Falls back to wall-clock components
// of the parsed Date if the value is not in the expected naive shape.
function splitIsoToParts(iso: string): { date: string; time: string } {
  const m = /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/.exec(iso);
  if (m) return { date: m[1], time: m[2] };
  const d = new Date(iso);
  return {
    date: `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`,
    time: `${pad(d.getHours())}:${pad(d.getMinutes())}`,
  };
}

// Compose a naive ISO datetime from a date input + time input pair.
function composeNaiveIso(date: string, time: string): string {
  if (!date || !time) return "";
  const t = /^\d{2}:\d{2}$/.test(time) ? `${time}:00` : time;
  return `${date}T${t}`;
}

interface ConflictDetail {
  reason_code: string;
  message: string;
  conflict_type?: string | null;
  start_time?: string | null;
  end_time?: string | null;
  related_event_id?: number | null;
}

// Floating-panel sizing for the Add/Edit Event modal.
// Below `PANEL_DRAG_THRESHOLD_WIDTH` the panel falls back to a centered
// modal and dragging is disabled.
const PANEL_WIDTH = 520;
const PANEL_DRAG_THRESHOLD_WIDTH = 720;
// Keep the whole panel inside the viewport while dragging, with this
// margin between any panel edge and the viewport edge.
const PANEL_VIEWPORT_MARGIN = 8;
const PANEL_HEIGHT_FALLBACK = 600;

function computeDefaultPanelPos(): { x: number; y: number } | null {
  if (typeof window === "undefined") return null;
  if (window.innerWidth < PANEL_DRAG_THRESHOLD_WIDTH) return null;
  const x = Math.max(16, Math.round((window.innerWidth - PANEL_WIDTH) / 2));
  const y = Math.max(64, Math.round(window.innerHeight * 0.08));
  return { x, y };
}

function clampPanelPos(
  p: { x: number; y: number },
  width: number,
  height: number
): { x: number; y: number } {
  if (typeof window === "undefined") return p;
  const maxX = Math.max(
    PANEL_VIEWPORT_MARGIN,
    window.innerWidth - width - PANEL_VIEWPORT_MARGIN
  );
  const maxY = Math.max(
    PANEL_VIEWPORT_MARGIN,
    window.innerHeight - height - PANEL_VIEWPORT_MARGIN
  );
  return {
    x: Math.max(PANEL_VIEWPORT_MARGIN, Math.min(maxX, p.x)),
    y: Math.max(PANEL_VIEWPORT_MARGIN, Math.min(maxY, p.y)),
  };
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

  // Floating-panel position for the Add/Edit Event modal. `null` means
  // "use CSS-centered fallback" (mobile or before first paint). Set to
  // {x, y} on open at desktop widths; updated while the user drags the
  // panel header.
  const [panelPos, setPanelPos] = useState<{ x: number; y: number } | null>(
    null
  );
  const [dragging, setDragging] = useState<boolean>(false);
  const panelRef = useRef<HTMLDivElement | null>(null);
  const dragOffsetRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });

  // Replacement options state inside the Add/Edit modal (conflict recovery).
  const [formOptions, setFormOptions] = useState<RescheduleOption[] | null>(null);
  const [formOptionsLoading, setFormOptionsLoading] = useState<boolean>(false);
  const [formOptionsError, setFormOptionsError] = useState<string | null>(null);

  // Event Details modal state. View modes: "details" or "options".
  const [detailsEvent, setDetailsEvent] = useState<Event | null>(null);
  const [detailsView, setDetailsView] = useState<"details" | "options">("details");
  const [detailsOptions, setDetailsOptions] =
    useState<RescheduleOption[] | null>(null);
  const [detailsOptionsLoading, setDetailsOptionsLoading] =
    useState<boolean>(false);
  const [detailsOptionsError, setDetailsOptionsError] =
    useState<string | null>(null);

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
      // `end` is already the exclusive upper bound (start + 7 days).
      const endIso = dateInputToNaiveStart(end);
      const evs = await listEvents({
        calendarId: calId ? Number(calId) : undefined,
        startTime: startIso,
        endTime: endIso,
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
        const startIso = dateInputToNaiveStart(appliedStart);
        // `appliedEnd` is already the exclusive upper bound (start + 7 days).
        const endIso = dateInputToNaiveStart(appliedEnd);
        const [cals, evs, m] = await Promise.all([
          listCalendars(),
          listEvents({ startTime: startIso, endTime: endIso }),
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

  // Close the event modal on Escape (only while it's open).
  useEffect(() => {
    if (!formOpen) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape" && !submitting) {
        cancelForm();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [formOpen, submitting]);

  // While the Add/Edit panel is open on desktop, keep its position
  // clamped on resize. Drop to centered fallback if the viewport shrinks
  // below the desktop threshold.
  useEffect(() => {
    if (!formOpen) return;
    function onResize() {
      if (typeof window === "undefined") return;
      if (window.innerWidth < PANEL_DRAG_THRESHOLD_WIDTH) {
        setPanelPos(null);
        return;
      }
      setPanelPos((p) => {
        if (!p) return computeDefaultPanelPos();
        const card = panelRef.current;
        const width = card?.offsetWidth ?? PANEL_WIDTH;
        const height = card?.offsetHeight ?? PANEL_HEIGHT_FALLBACK;
        return clampPanelPos(p, width, height);
      });
    }
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [formOpen]);

  function onPanelHandlePointerDown(
    e: ReactPointerEvent<HTMLDivElement>
  ) {
    if (e.button !== 0) return; // primary button only
    if (typeof window === "undefined") return;
    if (window.innerWidth < PANEL_DRAG_THRESHOLD_WIDTH) return;
    // Don't initiate drag from interactive controls inside the header
    // (e.g. the close button). The header background drags; controls
    // keep their normal click/focus behavior.
    const target = e.target as HTMLElement | null;
    if (
      target &&
      target.closest(
        "button, input, select, textarea, a, label, [contenteditable=true]"
      )
    ) {
      return;
    }
    const card = panelRef.current;
    if (!card) return;
    const rect = card.getBoundingClientRect();
    dragOffsetRef.current = {
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
    };
    setDragging(true);
    e.currentTarget.setPointerCapture(e.pointerId);
    e.preventDefault();
  }

  function onPanelHandlePointerMove(
    e: ReactPointerEvent<HTMLDivElement>
  ) {
    if (!dragging) return;
    const card = panelRef.current;
    if (!card) return;
    const next = clampPanelPos(
      {
        x: e.clientX - dragOffsetRef.current.x,
        y: e.clientY - dragOffsetRef.current.y,
      },
      card.offsetWidth,
      card.offsetHeight
    );
    setPanelPos(next);
  }

  function onPanelHandlePointerUp(
    e: ReactPointerEvent<HTMLDivElement>
  ) {
    if (!dragging) return;
    setDragging(false);
    try {
      e.currentTarget.releasePointerCapture(e.pointerId);
    } catch {
      // pointer capture may already be released
    }
  }

  // Close the event details modal on Escape (only while it's open).
  useEffect(() => {
    if (!detailsEvent) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        closeDetails();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [detailsEvent]);

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
    applyRange(v, shiftDateInput(v, WEEK_DAYS));
  }

  function onPickEnd(_v: string) {
    // End date is derived from start — always clamp back to start + 7 days
    // so the grid stays a fixed 7-column week regardless of what the user
    // selected in the (read-only) end picker.
    applyRange(appliedStart, shiftDateInput(appliedStart, WEEK_DAYS));
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
    setFormOptions(null);
    setFormOptionsLoading(false);
    setFormOptionsError(null);
  }

  function openCreateForm() {
    resetForm();
    setPanelPos(computeDefaultPanelPos());
    setFormOpen(true);
  }

  function startEdit(ev: Event) {
    setEditingId(ev.id);
    setFormError(null);
    setFormConflicts([]);
    setFormOptions(null);
    setFormOptionsError(null);
    const start = splitIsoToParts(ev.start_time);
    const end = splitIsoToParts(ev.end_time);
    setForm({
      calendar_id: String(ev.calendar_id),
      title: ev.title,
      description: ev.description ?? "",
      category: ev.category ?? "",
      priority: ev.priority ?? "",
      location: ev.location ?? "",
      start_date: start.date,
      start_time: start.time,
      end_date: end.date,
      end_time: end.time,
    });
    setPanelPos(computeDefaultPanelPos());
    setFormOpen(true);
  }

  function cancelForm() {
    resetForm();
    setFormOpen(false);
  }

  // ----- Event Details modal -----

  function openDetails(ev: Event) {
    setDetailsEvent(ev);
    setDetailsView("details");
    setDetailsOptions(null);
    setDetailsOptionsError(null);
    setDetailsOptionsLoading(false);
  }

  function closeDetails() {
    setDetailsEvent(null);
    setDetailsView("details");
    setDetailsOptions(null);
    setDetailsOptionsError(null);
    setDetailsOptionsLoading(false);
  }

  function editFromDetails() {
    if (!detailsEvent) return;
    const ev = detailsEvent;
    closeDetails();
    startEdit(ev);
    setFormOpen(true);
  }

  async function deleteFromDetails() {
    if (!detailsEvent) return;
    const id = detailsEvent.id;
    closeDetails();
    await onDelete(id);
  }

  // Build a 14-day search window starting from the event's original start day.
  function searchWindowForEvent(ev: Event): { start: string; end: string } {
    const m = /^(\d{4}-\d{2}-\d{2})T/.exec(ev.start_time);
    const startDay = m ? m[1] : ev.start_time.slice(0, 10);
    const start = `${startDay}T00:00:00`;
    const end = `${shiftDateInput(startDay, 14)}T00:00:00`;
    return { start, end };
  }

  async function loadDetailsOptions() {
    if (!detailsEvent) return;
    setDetailsView("options");
    setDetailsOptions(null);
    setDetailsOptionsError(null);
    setDetailsOptionsLoading(true);
    try {
      const win = searchWindowForEvent(detailsEvent);
      const res = await getRescheduleOptions({
        event_id: detailsEvent.id,
        search_start: win.start,
        search_end: win.end,
        max_results: 5,
      });
      setDetailsOptions(res.options);
    } catch (err) {
      setDetailsOptionsError(describeError(err));
    } finally {
      setDetailsOptionsLoading(false);
    }
  }

  function chooseOptionFromDetails(opt: RescheduleOption) {
    if (!detailsEvent) return;
    const ev = detailsEvent;
    closeDetails();
    // Pre-populate the edit form for this event.
    startEdit(ev);
    // Then overlay the chosen start/end values.
    const s = splitIsoToParts(opt.start_time);
    const e = splitIsoToParts(opt.end_time);
    setForm((f) => ({
      ...f,
      start_date: s.date,
      start_time: s.time,
      end_date: e.date,
      end_time: e.time,
    }));
    setFormOpen(true);
  }

  // ----- Replacement options inside the Add/Edit modal (conflict recovery) -----

  async function loadFormReplacementOptions() {
    setFormOptions(null);
    setFormOptionsError(null);

    if (editingId != null) {
      // Saved-event flow: use the original event's start day (or current
      // form value, or today) as the anchor.
      setFormOptionsLoading(true);
      try {
        const original = events.find((e) => e.id === editingId);
        const anchorIso =
          original?.start_time ??
          (composeNaiveIso(form.start_date, form.start_time) ||
            `${toDateInput(new Date())}T00:00:00`);
        const m = /^(\d{4}-\d{2}-\d{2})T/.exec(anchorIso);
        const anchorDay = m ? m[1] : toDateInput(new Date());
        const search_start = `${anchorDay}T00:00:00`;
        const search_end = `${shiftDateInput(anchorDay, 14)}T00:00:00`;
        const res = await getRescheduleOptions({
          event_id: editingId,
          search_start,
          search_end,
          max_results: 5,
        });
        setFormOptions(res.options);
      } catch (err) {
        setFormOptionsError(describeError(err));
      } finally {
        setFormOptionsLoading(false);
      }
      return;
    }

    // Brand-new (unsaved) proposed-event flow. Validate the form first so
    // we have a concrete proposal to send to the backend.
    if (!form.calendar_id) {
      setFormOptionsError("Calendar is required.");
      return;
    }
    if (!form.title.trim()) {
      setFormOptionsError("Title is required.");
      return;
    }
    if (
      !form.start_date ||
      !form.start_time ||
      !form.end_date ||
      !form.end_time
    ) {
      setFormOptionsError("Start and end date/time are required.");
      return;
    }
    const startIso = fromLocalInputNaive(
      composeNaiveIso(form.start_date, form.start_time)
    );
    const endIso = fromLocalInputNaive(
      composeNaiveIso(form.end_date, form.end_time)
    );
    if (new Date(startIso) >= new Date(endIso)) {
      setFormOptionsError("Start time must be before end time.");
      return;
    }

    const anchorDay = form.start_date;
    const search_start = `${anchorDay}T00:00:00`;
    const search_end = `${shiftDateInput(anchorDay, 14)}T23:59:00`;

    setFormOptionsLoading(true);
    try {
      const res = await getProposedRescheduleOptions({
        calendar_id: Number(form.calendar_id),
        title: form.title.trim(),
        start_time: startIso,
        end_time: endIso,
        search_start,
        search_end,
        max_results: 5,
      });
      setFormOptions(res.options);
    } catch (err) {
      setFormOptionsError(describeError(err));
    } finally {
      setFormOptionsLoading(false);
    }
  }

  function chooseOptionInForm(opt: RescheduleOption) {
    const s = splitIsoToParts(opt.start_time);
    const e = splitIsoToParts(opt.end_time);
    setForm((f) => ({
      ...f,
      start_date: s.date,
      start_time: s.time,
      end_date: e.date,
      end_time: e.time,
    }));
    // Clear stale conflict state — user has picked a candidate.
    setFormConflicts([]);
    setFormError(null);
    setFormOptions(null);
    setFormOptionsError(null);
  }

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    await submitEvent(false);
  }

  // Shared save path for the normal "Save Event" submit and the "Save anyway"
  // overlap override. `allowConflicts` is forwarded to the backend as an
  // explicit request flag — it is never inferred from category or anything
  // else.
  async function submitEvent(allowConflicts: boolean) {
    // A normal submit starts fresh. "Save anyway" deliberately keeps the
    // existing conflict warning visible until the save actually succeeds.
    if (!allowConflicts) {
      setFormConflicts([]);
      setFormOptions(null);
      setFormOptionsError(null);
    }
    setFormError(null);

    if (!form.calendar_id) {
      setFormError("Calendar is required.");
      return;
    }
    if (!form.title.trim()) {
      setFormError("Title is required.");
      return;
    }
    if (
      !form.start_date ||
      !form.start_time ||
      !form.end_date ||
      !form.end_time
    ) {
      setFormError("Start and end date/time are required.");
      return;
    }
    const startIso = composeNaiveIso(form.start_date, form.start_time);
    const endIso = composeNaiveIso(form.end_date, form.end_time);
    if (new Date(startIso) >= new Date(endIso)) {
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
      start_time: fromLocalInputNaive(startIso),
      end_time: fromLocalInputNaive(endIso),
      allow_conflicts: allowConflicts,
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
    () => buildWeekDayKeys(appliedStart),
    [appliedStart]
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
    <section className="schedule-page">
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
              readOnly
              title="End date is derived from start (start + 7 days)"
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
        </div>
      </div>

      {/* Add / Edit Event floating panel */}
      {formOpen && (
        <div
          className={`modal-overlay is-panel${panelPos ? " is-floating" : ""}`}
          role="dialog"
          aria-modal="true"
          aria-labelledby="event-modal-title"
          onMouseDown={(e) => {
            // Close only when the click starts on the backdrop itself,
            // not on a drag that originated inside the modal card.
            if (e.target === e.currentTarget && !submitting) {
              cancelForm();
            }
          }}
        >
          <div
            ref={panelRef}
            className={`modal-card modal-panel${dragging ? " is-dragging" : ""}`}
            style={panelPos ? { top: panelPos.y, left: panelPos.x } : undefined}
          >
            <form onSubmit={onSubmit} className="modal-form-wrapper">
              <div
                className="modal-header modal-drag-header"
                onPointerDown={onPanelHandlePointerDown}
                onPointerMove={onPanelHandlePointerMove}
                onPointerUp={onPanelHandlePointerUp}
                onPointerCancel={onPanelHandlePointerUp}
                title="Drag to move"
              >
                <span className="modal-drag-grip" aria-hidden />
                <h2 id="event-modal-title" className="modal-title">
                  {editingId != null ? "Edit Event" : "Add Event"}
                </h2>
                <button
                  type="button"
                  className="modal-close"
                  onClick={cancelForm}
                  disabled={submitting}
                  aria-label="Close"
                >
                  ✕
                </button>
              </div>

              <div className="modal-body">
                <div className="modal-form">
                  <input
                    id="ev-title"
                    className="title-input"
                    type="text"
                    placeholder="Add title"
                    aria-label="Title"
                    value={form.title}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, title: e.target.value }))
                    }
                    required
                  />

                  <div className="form-field">
                    <label>Start</label>
                    <div className="date-time date-time-wide">
                      <input
                        type="date"
                        aria-label="Start date"
                        value={form.start_date}
                        onChange={(e) =>
                          setForm((f) => ({
                            ...f,
                            start_date: e.target.value,
                          }))
                        }
                        required
                      />
                      <input
                        type="time"
                        aria-label="Start time"
                        value={form.start_time}
                        onChange={(e) =>
                          setForm((f) => ({
                            ...f,
                            start_time: e.target.value,
                          }))
                        }
                        required
                      />
                    </div>
                  </div>

                  <div className="form-field">
                    <label>End</label>
                    <div className="date-time date-time-wide">
                      <input
                        type="date"
                        aria-label="End date"
                        value={form.end_date}
                        onChange={(e) =>
                          setForm((f) => ({ ...f, end_date: e.target.value }))
                        }
                        required
                      />
                      <input
                        type="time"
                        aria-label="End time"
                        value={form.end_time}
                        onChange={(e) =>
                          setForm((f) => ({ ...f, end_time: e.target.value }))
                        }
                        required
                      />
                    </div>
                  </div>

                  <div className="form-secondary">
                    <div className="form-field">
                      <label htmlFor="ev-calendar">Calendar</label>
                      <select
                        id="ev-calendar"
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
                    </div>

                    <div className="form-row">
                      <div className="form-field">
                        <label htmlFor="ev-category">Category</label>
                        <input
                          id="ev-category"
                          type="text"
                          list="ev-category-options"
                          placeholder="Class, Study, Gym..."
                          value={form.category}
                          onChange={(e) =>
                            setForm((f) => ({ ...f, category: e.target.value }))
                          }
                        />
                        <datalist id="ev-category-options">
                          <option value="Class" />
                          <option value="Study" />
                          <option value="Gym" />
                          <option value="Focus block" />
                          <option value="Appointment" />
                          <option value="Commute" />
                          <option value="Personal" />
                        </datalist>
                      </div>

                      <div className="form-field">
                        <label htmlFor="ev-priority">Priority</label>
                        <select
                          id="ev-priority"
                          value={form.priority}
                          onChange={(e) =>
                            setForm((f) => ({ ...f, priority: e.target.value }))
                          }
                        >
                          <option value="">—</option>
                          <option value="low">Low</option>
                          <option value="medium">Medium</option>
                          <option value="high">High</option>
                        </select>
                      </div>
                    </div>

                    <div className="form-field">
                      <label htmlFor="ev-location">Location</label>
                      <input
                        id="ev-location"
                        type="text"
                        placeholder="Location or link"
                        value={form.location}
                        onChange={(e) =>
                          setForm((f) => ({ ...f, location: e.target.value }))
                        }
                      />
                    </div>

                    <div className="form-field">
                      <label htmlFor="ev-description">Notes</label>
                      <textarea
                        id="ev-description"
                        rows={3}
                        placeholder="Notes, agenda, or details"
                        value={form.description}
                        onChange={(e) =>
                          setForm((f) => ({ ...f, description: e.target.value }))
                        }
                      />
                    </div>
                  </div>

                  {formConflicts.length > 0 && (
                    <div className="modal-info danger" role="alert">
                      <span className="modal-info-icon" aria-hidden>
                        !
                      </span>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <strong>This time overlaps another event.</strong>
                        <ul style={{ margin: "0.35rem 0 0 1rem", padding: 0 }}>
                          {formConflicts.map((c, i) => (
                            <li key={i}>{c.message}</li>
                          ))}
                        </ul>
                        <div
                          style={{
                            marginTop: "0.6rem",
                            display: "flex",
                            gap: "0.5rem",
                            flexWrap: "wrap",
                          }}
                        >
                          <button
                            type="button"
                            className="secondary"
                            onClick={loadFormReplacementOptions}
                            disabled={formOptionsLoading}
                          >
                            {formOptionsLoading
                              ? "Loading replacement options…"
                              : "Find replacement times"}
                          </button>
                          <button
                            type="button"
                            className="secondary"
                            onClick={() => submitEvent(true)}
                            disabled={submitting}
                          >
                            {submitting ? "Saving…" : "Save anyway"}
                          </button>
                        </div>
                        <p
                          style={{
                            margin: "0.4rem 0 0",
                            fontSize: "0.85rem",
                            opacity: 0.75,
                          }}
                        >
                          This will keep both events on your schedule.
                        </p>
                      </div>
                    </div>
                  )}

                  {formOptionsError && (
                    <div className="modal-info danger" role="alert">
                      <span className="modal-info-icon" aria-hidden>
                        !
                      </span>
                      <span>
                        Could not load replacement options. {formOptionsError}
                      </span>
                    </div>
                  )}

                  {formOptions !== null && !formOptionsLoading && (
                    formOptions.length === 0 ? (
                      <div className="modal-info muted" aria-live="polite">
                        <span className="modal-info-icon" aria-hidden>
                          ⓘ
                        </span>
                        <span>
                          No replacement times in the next two weeks.
                        </span>
                      </div>
                    ) : (
                      <ul className="replacement-options" aria-live="polite">
                        {formOptions.map((opt) => (
                          <li
                            key={`${opt.rank}-${opt.start_time}`}
                            className="replacement-option"
                          >
                            <div className="replacement-option-when">
                              <span className="replacement-option-date">
                                {formatShortDate(opt.start_time)}
                              </span>
                              <span className="replacement-option-time">
                                {formatTimeRange(
                                  opt.start_time,
                                  opt.end_time
                                )}
                              </span>
                            </div>
                            <button
                              type="button"
                              className="secondary"
                              onClick={() => chooseOptionInForm(opt)}
                            >
                              Use this time
                            </button>
                          </li>
                        ))}
                      </ul>
                    )
                  )}

                  {formError && formConflicts.length === 0 && (
                    <div className="modal-info danger" role="alert">
                      <span className="modal-info-icon" aria-hidden>
                        !
                      </span>
                      <span>{formError}</span>
                    </div>
                  )}

                </div>
              </div>

              <div className="modal-footer">
                <button
                  type="button"
                  className="secondary"
                  onClick={cancelForm}
                  disabled={submitting}
                >
                  Cancel
                </button>
                <button type="submit" className="primary" disabled={submitting}>
                  {submitting ? "Saving…" : "Save Event"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Event Details modal */}
      {detailsEvent && (
        <div
          className="modal-overlay is-panel"
          role="dialog"
          aria-modal="true"
          aria-labelledby="event-details-title"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) closeDetails();
          }}
        >
          <div className="modal-card modal-panel">
            <div className="modal-form-wrapper">
              <div className="modal-header">
                <h2 id="event-details-title" className="modal-title">
                  {detailsView === "options"
                    ? "Replacement options"
                    : detailsEvent.title}
                </h2>
                <p className="modal-subtitle">
                  {detailsView === "options"
                    ? `Originally ${formatShortDate(detailsEvent.start_time)} · ${formatTimeRange(
                        detailsEvent.start_time,
                        detailsEvent.end_time
                      )}`
                    : `${formatLongDate(detailsEvent.start_time)} · ${formatTimeRange(
                        detailsEvent.start_time,
                        detailsEvent.end_time
                      )}`}
                </p>
                <button
                  type="button"
                  className="modal-close"
                  onClick={closeDetails}
                  aria-label="Close"
                >
                  ✕
                </button>
              </div>

              <div className="modal-body">
                {detailsView === "details" ? (
                  <div className="details-grid">
                    {(() => {
                      const cal = calendarsById.get(detailsEvent.calendar_id);
                      const items: { label: string; value: string }[] = [];
                      if (cal) items.push({ label: "Calendar", value: cal.name });
                      if (detailsEvent.category)
                        items.push({ label: "Category", value: detailsEvent.category });
                      if (detailsEvent.priority)
                        items.push({ label: "Priority", value: detailsEvent.priority });
                      if (detailsEvent.location)
                        items.push({ label: "Location", value: detailsEvent.location });
                      return items.map((it) => (
                        <div key={it.label} className="details-row">
                          <span className="details-label">{it.label}</span>
                          <span className="details-value">{it.value}</span>
                        </div>
                      ));
                    })()}
                    {detailsEvent.description && (
                      <div className="details-row details-row-block">
                        <span className="details-label">Description</span>
                        <p className="details-value details-description">
                          {detailsEvent.description}
                        </p>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="modal-form">
                    {detailsOptionsLoading && (
                      <p className="muted small" style={{ margin: 0 }}>
                        Loading replacement options…
                      </p>
                    )}

                    {detailsOptionsError && (
                      <div className="modal-info danger" role="alert">
                        <span className="modal-info-icon" aria-hidden>
                          !
                        </span>
                        <span>
                          Could not load replacement options.{" "}
                          {detailsOptionsError}
                        </span>
                      </div>
                    )}

                    {detailsOptions !== null &&
                      !detailsOptionsLoading &&
                      detailsOptions.length === 0 && (
                        <div className="modal-info muted">
                          <span className="modal-info-icon" aria-hidden>
                            ⓘ
                          </span>
                          <span>
                            No replacement times in the next two weeks.
                          </span>
                        </div>
                      )}

                    {detailsOptions !== null && detailsOptions.length > 0 && (
                      <ul className="replacement-options">
                        {detailsOptions.map((opt) => (
                          <li
                            key={`${opt.rank}-${opt.start_time}`}
                            className="replacement-option"
                          >
                            <div className="replacement-option-when">
                              <span className="replacement-option-date">
                                {formatShortDate(opt.start_time)}
                              </span>
                              <span className="replacement-option-time">
                                {formatTimeRange(opt.start_time, opt.end_time)}
                              </span>
                            </div>
                            <button
                              type="button"
                              className="secondary"
                              onClick={() => chooseOptionFromDetails(opt)}
                            >
                              Use this time
                            </button>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
              </div>

              <div className="modal-footer">
                {detailsView === "options" ? (
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => {
                      setDetailsView("details");
                      setDetailsOptions(null);
                      setDetailsOptionsError(null);
                    }}
                  >
                    Back
                  </button>
                ) : (
                  <>
                    <button
                      type="button"
                      className="secondary"
                      onClick={deleteFromDetails}
                    >
                      Delete
                    </button>
                    <button
                      type="button"
                      className="secondary"
                      onClick={loadDetailsOptions}
                    >
                      Find another time
                    </button>
                    <button
                      type="button"
                      className="primary"
                      onClick={editFromDetails}
                    >
                      Edit Event
                    </button>
                  </>
                )}
              </div>
            </div>
          </div>
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
                            onClick={() => openDetails(ev)}
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
                  <span className="metric-label">Busiest day</span>
                  <span className="metric-value">
                    {metrics.busiest_day
                      ? formatBusiestDay(metrics.busiest_day)
                      : "—"}
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

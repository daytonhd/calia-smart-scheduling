// Thin fetch layer for the Calia backend.
// Exposes small helpers per resource. No heavy abstractions.

import { API_BASE_URL } from "./config";
import type {
  Calendar,
  CalendarCreate,
  CalendarUpdate,
  Category,
  CategoryCreate,
  CategoryUpdate,
  DailyRhythm,
  DailyRhythmUpdate,
  Event,
  EventCreate,
  EventUpdate,
  ProposedRescheduleOptionsRequest,
  ProposedRescheduleOptionsResponse,
  RescheduleOptionsRequest,
  RescheduleOptionsResponse,
  ScheduleBalanceResponse,
  ScheduleSummary,
  WeeklyMetrics,
} from "./types";

export class ApiError extends Error {
  status: number;
  body: unknown;

  constructor(message: string, status: number, body: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${path}`;
  const method = (init?.method ?? "GET").toUpperCase();
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...(init?.headers as Record<string, string> | undefined),
  };
  if (init?.body && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  let res: Response;
  try {
    res = await fetch(url, { ...init, headers, cache: "no-store" });
  } catch (err) {
    // fetch() throws TypeError on network errors (server unreachable,
    // CORS denial, DNS failure, etc.). Surface a useful diagnostic
    // instead of the bare "Failed to fetch" / "Load failed".
    const reason =
      err instanceof Error && err.message ? err.message : "network error";
    throw new ApiError(
      `Could not reach API at ${method} ${url} (${reason}). Is the backend running on ${API_BASE_URL}?`,
      0,
      null
    );
  }

  if (res.status === 204) {
    return undefined as T;
  }

  const text = await res.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }

  if (!res.ok) {
    const detail =
      (data && typeof data === "object" && "detail" in (data as object)
        ? (data as { detail: unknown }).detail
        : null) ?? res.statusText;
    const message =
      typeof detail === "string"
        ? detail
        : `Request failed with status ${res.status}`;
    throw new ApiError(message, res.status, data);
  }

  return data as T;
}

// ----- Calendars -----

export function listCalendars(): Promise<Calendar[]> {
  return request<Calendar[]>("/calendars/");
}

export function createCalendar(body: CalendarCreate): Promise<Calendar> {
  return request<Calendar>("/calendars/", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updateCalendar(
  id: number,
  body: CalendarUpdate
): Promise<Calendar> {
  return request<Calendar>(`/calendars/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function deleteCalendar(id: number): Promise<void> {
  return request<void>(`/calendars/${id}`, { method: "DELETE" });
}

// ----- Categories -----
// User-managed labels for events. Categories are descriptive only and do
// not affect scheduling logic.

export function listCategories(): Promise<Category[]> {
  return request<Category[]>("/categories/");
}

export function createCategory(body: CategoryCreate): Promise<Category> {
  return request<Category>("/categories/", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updateCategory(
  id: number,
  body: CategoryUpdate
): Promise<Category> {
  return request<Category>(`/categories/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function deleteCategory(id: number): Promise<void> {
  return request<void>(`/categories/${id}`, { method: "DELETE" });
}

// ----- Events -----

export interface ListEventsParams {
  calendarId?: number;
  startTime?: string; // ISO datetime
  endTime?: string;   // ISO datetime
}

export function listEvents(params?: ListEventsParams | number): Promise<Event[]> {
  // Back-compat: allow a bare calendar_id argument.
  const p: ListEventsParams =
    typeof params === "number" ? { calendarId: params } : params ?? {};

  const qs = new URLSearchParams();
  if (p.calendarId != null) qs.set("calendar_id", String(p.calendarId));
  if (p.startTime) qs.set("start_time", p.startTime);
  if (p.endTime) qs.set("end_time", p.endTime);

  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return request<Event[]>(`/events/${suffix}`);
}

export function createEvent(body: EventCreate): Promise<Event> {
  return request<Event>("/events/", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updateEvent(id: number, body: EventUpdate): Promise<Event> {
  return request<Event>(`/events/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function deleteEvent(id: number): Promise<void> {
  return request<void>(`/events/${id}`, { method: "DELETE" });
}

// ----- Schedule metrics -----

export function getWeeklyMetrics(): Promise<WeeklyMetrics> {
  return request<WeeklyMetrics>("/schedule/metrics");
}

// ----- Replacement time options for an existing event -----

export function getRescheduleOptions(
  body: RescheduleOptionsRequest
): Promise<RescheduleOptionsResponse> {
  return request<RescheduleOptionsResponse>("/schedule/reschedule-options", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

// ----- Replacement time options for a brand-new (unsaved) proposed event -----

export function getProposedRescheduleOptions(
  body: ProposedRescheduleOptionsRequest
): Promise<ProposedRescheduleOptionsResponse> {
  return request<ProposedRescheduleOptionsResponse>(
    "/schedule/proposed-reschedule-options",
    {
      method: "POST",
      body: JSON.stringify(body),
    }
  );
}

// ----- Schedule Balance (per-day diagnostics for the dashboard) -----
// Hits the existing /schedule/triage endpoint; the UI maps it to Schedule
// Balance / Free Capacity / Daily Load wording.

export function getScheduleBalance(
  weekStart?: string
): Promise<ScheduleBalanceResponse> {
  const qs = weekStart ? `?week_start=${weekStart}` : "";
  return request<ScheduleBalanceResponse>(`/schedule/triage${qs}`);
}

// ----- Daily Rhythm -----
// GET returns the persisted rhythm, or backend defaults when none is saved.
// PATCH validates and persists the four times ("HH:MM" 24-hour strings).

export function getDailyRhythm(): Promise<DailyRhythm> {
  return request<DailyRhythm>("/daily-rhythm");
}

export function updateDailyRhythm(
  body: DailyRhythmUpdate
): Promise<DailyRhythm> {
  return request<DailyRhythm>("/daily-rhythm", {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

// ----- Saved weekly AI summary -----

export async function getWeeklySummary(
  weekStart?: string
): Promise<ScheduleSummary | null> {
  const qs = weekStart ? `?week_start=${weekStart}` : "";
  try {
    return await request<ScheduleSummary>(`/schedule/weekly-summary${qs}`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) {
      return null;
    }
    throw e;
  }
}

// Thin fetch layer for the Smart Scheduling backend.
// Exposes small helpers per resource. No heavy abstractions.

import { API_BASE_URL } from "./config";
import type {
  AvailabilityWindow,
  AvailabilityWindowCreate,
  AvailabilityWindowUpdate,
  BlockedTime,
  BlockedTimeCreate,
  BlockedTimeUpdate,
  Calendar,
  CalendarCreate,
  CalendarUpdate,
  Event,
  EventCreate,
  EventUpdate,
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

// ----- Blocked times -----

export interface ListBlockedTimesParams {
  startTime?: string; // ISO datetime
  endTime?: string;   // ISO datetime
}

export function listBlockedTimes(
  params?: ListBlockedTimesParams
): Promise<BlockedTime[]> {
  const qs = new URLSearchParams();
  if (params?.startTime) qs.set("start_time", params.startTime);
  if (params?.endTime) qs.set("end_time", params.endTime);

  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return request<BlockedTime[]>(`/blocked-times/${suffix}`);
}

export function createBlockedTime(body: BlockedTimeCreate): Promise<BlockedTime> {
  return request<BlockedTime>("/blocked-times/", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updateBlockedTime(
  id: number,
  body: BlockedTimeUpdate
): Promise<BlockedTime> {
  return request<BlockedTime>(`/blocked-times/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function deleteBlockedTime(id: number): Promise<void> {
  return request<void>(`/blocked-times/${id}`, { method: "DELETE" });
}

// ----- Availability windows -----

export function listAvailability(): Promise<AvailabilityWindow[]> {
  return request<AvailabilityWindow[]>("/availability/");
}

export function createAvailability(
  body: AvailabilityWindowCreate
): Promise<AvailabilityWindow> {
  return request<AvailabilityWindow>("/availability/", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updateAvailability(
  id: number,
  body: AvailabilityWindowUpdate
): Promise<AvailabilityWindow> {
  return request<AvailabilityWindow>(`/availability/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function deleteAvailability(id: number): Promise<void> {
  return request<void>(`/availability/${id}`, { method: "DELETE" });
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

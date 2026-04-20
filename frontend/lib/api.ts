// Thin fetch layer for the Smart Scheduling backend.
// Exposes small helpers per resource. No heavy abstractions.

import { API_BASE_URL } from "./config";
import type {
  Calendar,
  CalendarCreate,
  CalendarUpdate,
  Event,
  EventCreate,
  EventUpdate,
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
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...(init?.headers as Record<string, string> | undefined),
  };
  if (init?.body && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(url, { ...init, headers, cache: "no-store" });

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

export function listEvents(calendarId?: number): Promise<Event[]> {
  const qs = calendarId != null ? `?calendar_id=${calendarId}` : "";
  return request<Event[]>(`/events/${qs}`);
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

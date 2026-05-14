// Shared TypeScript types mirroring backend response/request shapes.

export interface Calendar {
  id: number;
  name: string;
  color: string | null;
  created_at: string;
}

export interface CalendarCreate {
  name: string;
  color?: string | null;
}

export interface CalendarUpdate {
  name?: string;
  color?: string | null;
}

export interface Event {
  id: number;
  calendar_id: number;
  title: string;
  description: string | null;
  category: string | null;
  priority: string | null;
  location: string | null;
  start_time: string; // ISO datetime
  end_time: string;   // ISO datetime
  created_at: string;
  updated_at: string;
}

export interface EventCreate {
  calendar_id: number;
  title: string;
  description?: string | null;
  category?: string | null;
  priority?: string | null;
  location?: string | null;
  start_time: string;
  end_time: string;
  // Request-only override: when true, the backend may save an event that
  // overlaps existing events. Not part of the stored Event.
  allow_conflicts?: boolean;
}

export interface EventUpdate {
  calendar_id?: number;
  title?: string;
  description?: string | null;
  category?: string | null;
  priority?: string | null;
  location?: string | null;
  start_time?: string;
  end_time?: string;
  // Request-only override: when true, the backend may save an event that
  // overlaps existing events. Not part of the stored Event.
  allow_conflicts?: boolean;
}

export interface ScheduleSummary {
  id: number;
  user_id: number;
  week_start: string;   // ISO date
  generated_text: string;
  created_at: string;   // ISO datetime
}

export interface WeeklyMetrics {
  week_start: string;         // ISO date
  week_end: string;           // ISO date
  total_events: number;
  total_scheduled_minutes: number;
  busiest_day: string | null; // ISO date or null
  busiest_day_minutes: number;
}

// ----- Schedule Balance (GET /schedule/triage internally) -----
// User-facing wording: Schedule Balance / Free Capacity / Daily Load.
// The internal endpoint name remains /schedule/triage during this transition;
// these types map the diagnostics payload to the Schedule Balance UI.

export interface ScheduleBalanceWarning {
  reason_code: string;
  message: string;
}

export interface ScheduleBalanceDay {
  date: string; // ISO date
  scheduled_minutes: number;
  total_busy_minutes: number;
  free_minutes: number;
  longest_free_window_minutes: number;
  is_overloaded: boolean;
  is_fragmented: boolean;
  has_weak_buffer: boolean;
  warnings: ScheduleBalanceWarning[];
}

export interface ScheduleBalanceResponse {
  week_start: string; // ISO date
  week_end: string;   // ISO date
  days: ScheduleBalanceDay[];
  week_warnings: ScheduleBalanceWarning[];
}

// ----- Reschedule options (POST /schedule/reschedule-options) -----

export interface RescheduleOptionsRequest {
  event_id: number;
  search_start: string; // naive ISO datetime
  search_end: string;   // naive ISO datetime
  max_results?: number;
}

export interface RescheduleOption {
  rank: number;
  start_time: string; // naive ISO datetime
  end_time: string;   // naive ISO datetime
  reason_code: string;
  explanation: string;
  minutes_from_original_start: number;
}

export interface RescheduleOptionsResponse {
  event_id: number;
  event_title: string;
  duration_minutes: number;
  options: RescheduleOption[];
}

// ----- Replacement options for a brand-new (unsaved) proposed event -----
// (POST /schedule/proposed-reschedule-options)

export interface ProposedRescheduleOptionsRequest {
  calendar_id: number;
  title: string;
  start_time: string;   // naive ISO datetime
  end_time: string;     // naive ISO datetime
  search_start: string; // naive ISO datetime
  search_end: string;   // naive ISO datetime
  max_results?: number;
}

export interface ProposedRescheduleOptionsResponse {
  event_title: string;
  duration_minutes: number;
  options: RescheduleOption[];
}

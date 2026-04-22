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
}

export interface BlockedTime {
  id: number;
  user_id: number;
  title: string;
  reason: string | null;
  notes: string | null;
  start_time: string; // ISO datetime
  end_time: string;   // ISO datetime
  created_at: string;
  updated_at: string;
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
  total_blocked_times: number;
  total_scheduled_minutes: number;
  total_blocked_minutes: number;
  busiest_day: string | null; // ISO date or null
  busiest_day_minutes: number;
}

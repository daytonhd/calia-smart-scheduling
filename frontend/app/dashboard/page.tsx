"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  ApiError,
  getDailyRhythm,
  getScheduleBalance,
  getWeeklySummary,
  listEvents,
} from "@/lib/api";
import type {
  DailyRhythm,
  Event,
  ScheduleBalanceDay,
  ScheduleBalanceResponse,
  ScheduleSummary,
} from "@/lib/types";

function formatDateTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
  });
}

function formatDayTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

// Naive-local ISO: backend rejects tz-aware datetimes per the MVP time contract.
function naiveLocalIso(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
    `T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
  );
}

// Returns [startOfToday, startOfTomorrow] as naive local ISO strings.
function todayWindowIso(): { start: string; end: string } {
  const now = new Date();
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const end = new Date(start);
  end.setDate(end.getDate() + 1);
  return { start: naiveLocalIso(start), end: naiveLocalIso(end) };
}

// Returns the window from start of tomorrow through end of day (today + 7).
function upcomingWindowIso(): { start: string; end: string } {
  const now = new Date();
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
  const end = new Date(start);
  end.setDate(end.getDate() + 7);
  return { start: naiveLocalIso(start), end: naiveLocalIso(end) };
}

// ----- Schedule Balance helpers -----

// Daily Rhythm suggestion window upper bound used for visual scaling.
// The shared bottom scale shows 0h, 4h, 8h.
const BALANCE_SCALE_MAX_MIN = 8 * 60;

function weekdayShort(iso: string): string {
  const d = new Date(`${iso}T00:00:00`);
  return d.toLocaleDateString(undefined, { weekday: "short" });
}

function weekdayLong(iso: string): string {
  const d = new Date(`${iso}T00:00:00`);
  return d.toLocaleDateString(undefined, { weekday: "long" });
}

interface BalanceStatus {
  label: string;   // "Light" | "Balanced" | "Heavy" | "Slightly Heavy" | "Empty"
  detail: string;  // compact interpretation
}

function computeBalanceStatus(days: ScheduleBalanceDay[]): BalanceStatus {
  if (days.length === 0) {
    return { label: "Empty", detail: "No schedule data for this week yet." };
  }

  const totalBusy = days.reduce((s, d) => s + d.total_busy_minutes, 0);
  if (totalBusy === 0) {
    return { label: "Light", detail: "Nothing scheduled this week yet." };
  }

  const avg = totalBusy / days.length;
  const max = days.reduce(
    (m, d) => (d.total_busy_minutes > m.total_busy_minutes ? d : m),
    days[0]
  );
  const heavyDays = days.filter((d) => d.total_busy_minutes >= 6 * 60);

  if (heavyDays.length >= 2) {
    return {
      label: "Heavy",
      detail: "Multiple days are carrying significant scheduled load.",
    };
  }

  if (max.total_busy_minutes >= 6 * 60 && max.total_busy_minutes > avg * 1.8) {
    return {
      label: "Slightly Heavy",
      detail: `${weekdayLong(max.date)} is carrying most of this week's scheduled load.`,
    };
  }

  if (avg < 2 * 60) {
    return {
      label: "Light",
      detail: "Plenty of free room across the week.",
    };
  }

  return {
    label: "Balanced",
    detail: "Load is spread evenly across the week.",
  };
}

export default function DashboardPage() {
  const [todayEvents, setTodayEvents] = useState<Event[]>([]);
  const [upcomingEvents, setUpcomingEvents] = useState<Event[]>([]);
  const [summary, setSummary] = useState<ScheduleSummary | null>(null);
  const [balance, setBalance] = useState<ScheduleBalanceResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      const { start, end } = todayWindowIso();
      const { start: upStart, end: upEnd } = upcomingWindowIso();

      setLoading(true);
      setError(null);
      try {
        const [ev, up, ws, sb] = await Promise.all([
          listEvents({ startTime: start, endTime: end }),
          listEvents({ startTime: upStart, endTime: upEnd }),
          getWeeklySummary(),
          getScheduleBalance(),
        ]);
        if (cancelled) return;

        setTodayEvents(
          [...ev].sort(
            (a, b) =>
              new Date(a.start_time).getTime() -
              new Date(b.start_time).getTime()
          )
        );
        setUpcomingEvents(
          [...up].sort(
            (a, b) =>
              new Date(a.start_time).getTime() -
              new Date(b.start_time).getTime()
          )
        );
        setSummary(ws);
        setBalance(sb);
      } catch (e) {
        if (cancelled) return;
        const msg =
          e instanceof ApiError
            ? `${e.status}: ${e.message}`
            : e instanceof Error
            ? e.message
            : "Unknown error";
        setError(msg);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <section>
      {error && (
        <div className="error-box" role="alert">
          Failed to load dashboard: {error}
        </div>
      )}

      {loading ? (
        <p className="muted">Loading…</p>
      ) : (
        <>
          {/* Full-width weekly overview / AI summary */}
          <div className="overview-card">
            <div className="overview-icon" aria-hidden>
              ✦
            </div>
            <div className="overview-content">
              <h3 className="overview-title">Weekly AI Summary</h3>
              {summary ? (
                <>
                  <p className="overview-text">{summary.generated_text}</p>
                  <div className="overview-meta">
                    Week of {summary.week_start} · generated{" "}
                    {formatDateTime(summary.created_at)}
                  </div>
                </>
              ) : (
                <p className="overview-text muted">
                  Generate a weekly summary to see the main patterns, busiest
                  days, and open capacity for this week.
                </p>
              )}
            </div>
          </div>

          <div className="page-grid">
            {/* Main column: Today's Schedule */}
            <div className="page-main">
              {/* Schedule Balance */}
              <div className="card balance-card">
                <div className="card-header-row">
                  <h3 className="card-title">Schedule Balance</h3>
                </div>

                {!balance || balance.days.length === 0 ? (
                  <div className="empty-state">
                    <span className="empty-state-strong">
                      Your week is wide open
                    </span>
                    Once events are added, you&rsquo;ll see how the load is
                    distributed across the week.
                  </div>
                ) : (
                  (() => {
                    const status = computeBalanceStatus(balance.days);
                    // Daily Load y-axis max: round up max busy hours to even number, min 8h.
                    const maxBusyMin = Math.max(
                      ...balance.days.map((d) => d.total_busy_minutes)
                    );
                    const maxAxisHours = Math.max(
                      8,
                      Math.ceil(maxBusyMin / 60 / 2) * 2
                    );
                    const maxAxisMin = maxAxisHours * 60;
                    const peakIdx = balance.days.findIndex(
                      (d) => d.total_busy_minutes === maxBusyMin
                    );
                    // Average busy minutes → marker position on Light↔Heavy gradient.
                    // 0h → 0%, 3h → 50%, 6h → 100%.
                    const avgBusyMin =
                      balance.days.reduce(
                        (s, d) => s + d.total_busy_minutes,
                        0
                      ) / balance.days.length;
                    const markerPct = Math.min(
                      100,
                      Math.max(0, (avgBusyMin / (6 * 60)) * 100)
                    );
                    const yTicks = [0, 0.25, 0.5, 0.75, 1].map((f) =>
                      Math.round(f * maxAxisHours)
                    );
                    return (
                      <>
                        <div className="balance-grid">
                          {/* Free Capacity — horizontal bars */}
                          <div className="balance-subcard">
                            <div className="balance-subcard-head">
                              <h4 className="balance-subcard-title">
                                Free Capacity
                              </h4>
                              <p className="balance-subcard-sub">
                                Longest open window each day
                              </p>
                            </div>
                            <div className="capacity-bars">
                              {balance.days.map((d) => {
                                const pct = Math.min(
                                  100,
                                  (d.longest_free_window_minutes /
                                    BALANCE_SCALE_MAX_MIN) *
                                    100
                                );
                                const tight =
                                  d.has_weak_buffer || d.is_overloaded;
                                return (
                                  <div className="capacity-row" key={d.date}>
                                    <div className="capacity-day">
                                      {weekdayShort(d.date)}
                                    </div>
                                    <div className="capacity-track">
                                      <div
                                        className={`capacity-fill ${
                                          tight ? "tight" : ""
                                        }`}
                                        style={{ width: `${pct}%` }}
                                      />
                                    </div>
                                  </div>
                                );
                              })}
                              <div className="capacity-scale">
                                <span>0h</span>
                                <span>4h</span>
                                <span>8h</span>
                              </div>
                            </div>
                          </div>

                          {/* Daily Load — vertical bars with y-axis */}
                          <div className="balance-subcard">
                            <div className="balance-subcard-head">
                              <h4 className="balance-subcard-title">
                                Daily Load
                              </h4>
                              <p className="balance-subcard-sub">
                                Hours of scheduled time each day.
                              </p>
                            </div>
                            <div className="load-chart">
                              <div className="load-yaxis">
                                {[...yTicks].reverse().map((t) => (
                                  <span key={t} className="load-ytick">
                                    {t}
                                  </span>
                                ))}
                              </div>
                              <div className="load-plot">
                                <div className="load-gridlines" aria-hidden>
                                  {yTicks.map((t) => (
                                    <div key={t} className="load-gridline" />
                                  ))}
                                </div>
                                <div className="load-bars">
                                  {balance.days.map((d, i) => {
                                    const h = Math.min(
                                      100,
                                      (d.total_busy_minutes / maxAxisMin) * 100
                                    );
                                    const isPeak = i === peakIdx && maxBusyMin > 0;
                                    return (
                                      <div className="load-col" key={d.date}>
                                        <div className="load-bar-wrap">
                                          <div
                                            className={`load-bar ${
                                              isPeak ? "peak" : ""
                                            }`}
                                            style={{ height: `${h}%` }}
                                            title={`${Math.round(
                                              (d.total_busy_minutes / 60) * 10
                                            ) / 10}h scheduled`}
                                          />
                                        </div>
                                      </div>
                                    );
                                  })}
                                </div>
                              </div>
                            </div>
                            <div className="load-xaxis">
                              {balance.days.map((d) => (
                                <span key={d.date}>{weekdayShort(d.date)}</span>
                              ))}
                            </div>
                          </div>
                        </div>

                        {/* Bottom strip: Light–Balanced–Heavy gradient + interpretation */}
                        <div className="balance-bottom">
                          <div className="balance-gradient">
                            <div className="balance-gradient-labels">
                              <span>Light</span>
                              <span>Balanced</span>
                              <span>Heavy</span>
                            </div>
                            <div className="balance-gradient-track">
                              <div
                                className="balance-gradient-marker"
                                style={{ left: `${markerPct}%` }}
                              />
                            </div>
                          </div>
                          <div className="balance-interpretation">
                            <div
                              className={`balance-interpretation-label ${
                                status.label === "Heavy"
                                  ? "heavy"
                                  : status.label === "Slightly Heavy"
                                  ? "slight-heavy"
                                  : status.label === "Light"
                                  ? "light"
                                  : "balanced"
                              }`}
                            >
                              {status.label}
                            </div>
                            <p className="balance-interpretation-detail">
                              {status.detail}
                            </p>
                          </div>
                        </div>

                        {balance.week_warnings.length > 0 && (
                          <ul className="balance-notes">
                            {balance.week_warnings.map((w) => (
                              <li key={w.reason_code}>{w.message}</li>
                            ))}
                          </ul>
                        )}
                      </>
                    );
                  })()
                )}
              </div>
            </div>

            {/* Right sidebar */}
            <aside className="page-side">
              {/* Upcoming — carries today/next-event context */}
              {(() => {
                const now = Date.now();
                const nextEvent =
                  upcomingEvents.find(
                    (e) => new Date(e.start_time).getTime() >= now
                  ) ?? upcomingEvents[0];
                return (
                  <div className="sidebar-card upcoming-card">
                    <div className="sidebar-card-title">
                      <span>Upcoming</span>
                    </div>

                    <div className="upcoming-context">
                      <span className="upcoming-today">
                        Today · {todayEvents.length} event
                        {todayEvents.length === 1 ? "" : "s"}
                      </span>
                      {nextEvent && (
                        <span className="upcoming-next">
                          Next: {nextEvent.title} at{" "}
                          {formatTime(nextEvent.start_time)}
                        </span>
                      )}
                    </div>

                    {upcomingEvents.length === 0 ? (
                      <div className="empty-state empty-state-soft">
                        <span className="empty-state-strong">
                          Nothing on the horizon
                        </span>
                        The next seven days are clear.
                      </div>
                    ) : (
                      <ul className="list-rows">
                        {upcomingEvents.slice(0, 4).map((e) => (
                          <li key={e.id}>
                            <div className="row-icon" aria-hidden>
                              ▣
                            </div>
                            <div className="row-body">
                              <div className="row-title">{e.title}</div>
                              <div className="row-meta">
                                {formatDayTime(e.start_time)}
                              </div>
                            </div>
                          </li>
                        ))}
                      </ul>
                    )}

                    <Link href="/schedule" className="upcoming-link">
                      View full schedule →
                    </Link>
                  </div>
                );
              })()}

              {/* Daily Rhythm */}
              <div className="sidebar-card rhythm-card">
                <div className="sidebar-card-title">
                  <span>Daily Rhythm</span>
                </div>
                <div className="rhythm-rows">
                  <div className="rhythm-row">
                    <span className="rhythm-label">Awake hours</span>
                    <span className="rhythm-value">7:00 AM – 11:00 PM</span>
                  </div>
                  <div className="rhythm-row">
                    <span className="rhythm-label">Suggestion window</span>
                    <span className="rhythm-value">8:00 AM – 9:00 PM</span>
                  </div>
                </div>
                <Link
                  href="/settings"
                  className="rhythm-edit-btn"
                  aria-label="Edit Daily Rhythm in settings"
                >
                  Edit rhythm
                </Link>
              </div>
            </aside>
          </div>
        </>
      )}
    </section>
  );
}

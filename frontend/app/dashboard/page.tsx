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

// Derive the [start, end) naive ISO window for the current Schedule
// Balance week from the triage response. Aligning with balance.week_start
// and balance.week_end keeps the category chart and Daily Load showing
// the same days. `week_end` is inclusive, so we bump it by one day for
// the half-open event-list query the backend expects.
function balanceWindowIso(
  balance: ScheduleBalanceResponse
): { start: string; end: string } {
  const startParts = balance.week_start.split("-").map(Number);
  const endParts = balance.week_end.split("-").map(Number);
  const startDate = new Date(
    startParts[0],
    (startParts[1] ?? 1) - 1,
    startParts[2] ?? 1
  );
  const endDate = new Date(
    endParts[0],
    (endParts[1] ?? 1) - 1,
    (endParts[2] ?? 1) + 1
  );
  return { start: naiveLocalIso(startDate), end: naiveLocalIso(endDate) };
}

// ----- Schedule Balance helpers -----

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

// ----- Category breakdown helpers -----

// Restrained palette aligned with the rest of the Calia visual style.
// Order is stable so re-renders don't reshuffle colors.
const CATEGORY_COLORS = [
  "#6592df", // accent blue
  "#7c9b6f", // soft green
  "#c98d54", // warm amber
  "#a07ab8", // muted purple
  "#5d80c4", // deeper blue
  "#c46868", // restrained red
  "#9aa3b2", // neutral slate
];

const UNCATEGORIZED_LABEL = "Uncategorized";

interface CategorySlice {
  label: string;
  minutes: number;
  color: string;
}

// Convert a list of events into one slice per category. Events with no
// category fall under "Uncategorized". Returns slices sorted descending by
// minutes for a stable legend.
function buildCategorySlices(events: Event[]): CategorySlice[] {
  const totals = new Map<string, number>();
  for (const ev of events) {
    const label = (ev.category ?? "").trim() || UNCATEGORIZED_LABEL;
    const minutes = Math.max(
      0,
      Math.round(
        (new Date(ev.end_time).getTime() -
          new Date(ev.start_time).getTime()) /
          60000
      )
    );
    if (minutes === 0) continue;
    totals.set(label, (totals.get(label) ?? 0) + minutes);
  }
  return Array.from(totals.entries())
    .map(([label, minutes], i) => ({
      label,
      minutes,
      color: CATEGORY_COLORS[i % CATEGORY_COLORS.length],
    }))
    .sort((a, b) => b.minutes - a.minutes)
    .map((s, i) => ({
      ...s,
      color: CATEGORY_COLORS[i % CATEGORY_COLORS.length],
    }));
}

function formatMinutes(minutes: number): string {
  if (minutes <= 0) return "0m";
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (h === 0) return `${m}m`;
  if (m === 0) return `${h}h`;
  return `${h}h ${m}m`;
}

// Build an SVG donut arc path for `[startAngle, endAngle)` in radians,
// measured clockwise from 12 o'clock. `r` is the outer radius; the donut
// hole is carved by the second arc with `rInner`.
function donutArcPath(
  cx: number,
  cy: number,
  r: number,
  rInner: number,
  startAngle: number,
  endAngle: number
): string {
  const polar = (radius: number, angle: number) => ({
    x: cx + radius * Math.sin(angle),
    y: cy - radius * Math.cos(angle),
  });
  const sweep = endAngle - startAngle;
  const largeArc = sweep > Math.PI ? 1 : 0;
  const oStart = polar(r, startAngle);
  const oEnd = polar(r, endAngle);
  const iStart = polar(rInner, endAngle);
  const iEnd = polar(rInner, startAngle);
  return [
    `M ${oStart.x} ${oStart.y}`,
    `A ${r} ${r} 0 ${largeArc} 1 ${oEnd.x} ${oEnd.y}`,
    `L ${iStart.x} ${iStart.y}`,
    `A ${rInner} ${rInner} 0 ${largeArc} 0 ${iEnd.x} ${iEnd.y}`,
    "Z",
  ].join(" ");
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
  const [weekEvents, setWeekEvents] = useState<Event[]>([]);
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
        // Fetch Schedule Balance first so the week-events query uses the
        // same Mon–Sun window the backend just summarized.
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

        if (sb) {
          const win = balanceWindowIso(sb);
          const wk = await listEvents({
            startTime: win.start,
            endTime: win.end,
          });
          if (cancelled) return;
          setWeekEvents(wk);
        } else {
          setWeekEvents([]);
        }
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

                {(() => {
                  const balanceDays = balance?.days ?? [];
                  const totalWeekMin = balanceDays.reduce(
                    (s, d) => s + d.total_busy_minutes,
                    0
                  );
                  const isEmptyWeek =
                    balanceDays.length === 0 || totalWeekMin === 0;

                  if (isEmptyWeek) {
                    return (
                      <div className="empty-state">
                        <span className="empty-state-strong">
                          No scheduled time this week yet
                        </span>
                        Create events on the Schedule page to see your weekly
                        breakdown.
                      </div>
                    );
                  }

                  const status = computeBalanceStatus(balanceDays);
                  const slices = buildCategorySlices(weekEvents);
                  const totalSliceMin = slices.reduce(
                    (s, c) => s + c.minutes,
                    0
                  );

                  // Daily Load y-axis: round max busy hours up to the
                  // nearest 2h; floor at 4h so a near-empty week doesn't
                  // stretch the bars vertically.
                  const maxBusyMin = Math.max(
                    ...balanceDays.map((d) => d.total_busy_minutes)
                  );
                  const maxAxisHours = Math.max(
                    4,
                    Math.ceil(maxBusyMin / 60 / 2) * 2
                  );
                  const maxAxisMin = maxAxisHours * 60;
                  const peakIdx = balanceDays.findIndex(
                    (d) => d.total_busy_minutes === maxBusyMin
                  );
                  // Average busy minutes → marker position on Light↔Heavy
                  // gradient. 0h → 0%, 3h → 50%, 6h → 100%.
                  const avgBusyMin = totalWeekMin / balanceDays.length;
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
                        {/* By Category — doughnut chart */}
                        <div className="balance-subcard">
                          <div className="balance-subcard-head">
                            <h4 className="balance-subcard-title">
                              By Category
                            </h4>
                            <p className="balance-subcard-sub">
                              Scheduled time this week, grouped by label.
                            </p>
                          </div>
                          <CategoryDoughnut
                            slices={slices}
                            totalMinutes={totalSliceMin}
                          />
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
                                {balanceDays.map((d, i) => {
                                  const h = Math.min(
                                    100,
                                    (d.total_busy_minutes / maxAxisMin) * 100
                                  );
                                  const isPeak =
                                    i === peakIdx && maxBusyMin > 0;
                                  return (
                                    <div className="load-col" key={d.date}>
                                      <div className="load-bar-wrap">
                                        <div
                                          className={`load-bar ${
                                            isPeak ? "peak" : ""
                                          }`}
                                          style={{ height: `${h}%` }}
                                          title={`${
                                            Math.round(
                                              (d.total_busy_minutes / 60) * 10
                                            ) / 10
                                          }h scheduled`}
                                        />
                                      </div>
                                    </div>
                                  );
                                })}
                              </div>
                            </div>
                          </div>
                          <div className="load-xaxis">
                            {balanceDays.map((d) => (
                              <span key={d.date}>
                                {weekdayShort(d.date)}
                              </span>
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

                      {balance && balance.week_warnings.length > 0 && (
                        <ul className="balance-notes">
                          {balance.week_warnings.map((w) => (
                            <li key={w.reason_code}>{w.message}</li>
                          ))}
                        </ul>
                      )}
                    </>
                  );
                })()}
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

// ----- Category doughnut chart -----
// Small SVG doughnut + legend. Renders nothing alarming when there is no
// data — the parent already shows a quiet empty state for an empty week.

interface CategoryDoughnutProps {
  slices: CategorySlice[];
  totalMinutes: number;
}

function CategoryDoughnut({ slices, totalMinutes }: CategoryDoughnutProps) {
  // Layout constants.
  const SIZE = 168;
  const STROKE = 26;
  const cx = SIZE / 2;
  const cy = SIZE / 2;
  const r = SIZE / 2 - 4;
  const rInner = r - STROKE;

  if (totalMinutes === 0 || slices.length === 0) {
    return (
      <div className="category-chart-empty">
        No categorized time yet for this week.
      </div>
    );
  }

  let acc = 0;
  // A single full-circle slice would degenerate when rendered as an arc
  // (start angle equals end angle). Render it as a complete ring instead.
  const singleSlice = slices.length === 1;

  return (
    <div className="category-chart">
      <svg
        className="category-chart-svg"
        viewBox={`0 0 ${SIZE} ${SIZE}`}
        role="img"
        aria-label="Scheduled time grouped by category"
      >
        {singleSlice ? (
          <>
            <circle
              cx={cx}
              cy={cy}
              r={r}
              fill="none"
              stroke={slices[0].color}
              strokeWidth={STROKE}
            />
          </>
        ) : (
          slices.map((s) => {
            const startAngle = (acc / totalMinutes) * Math.PI * 2;
            acc += s.minutes;
            const endAngle = (acc / totalMinutes) * Math.PI * 2;
            const d = donutArcPath(cx, cy, r, rInner, startAngle, endAngle);
            return <path key={s.label} d={d} fill={s.color} />;
          })
        )}
        <text
          x={cx}
          y={cy - 3}
          className="category-chart-center-num"
          textAnchor="middle"
        >
          {formatMinutes(totalMinutes)}
        </text>
        <text
          x={cx}
          y={cy + 14}
          className="category-chart-center-label"
          textAnchor="middle"
        >
          this week
        </text>
      </svg>
      <ul className="category-legend">
        {slices.map((s) => (
          <li key={s.label} className="category-legend-row">
            <span
              className="category-legend-swatch"
              style={{ background: s.color }}
              aria-hidden
            />
            <span className="category-legend-name">{s.label}</span>
            <span className="category-legend-value">
              {formatMinutes(s.minutes)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

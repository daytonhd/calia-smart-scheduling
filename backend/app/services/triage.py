"""Weekly Schedule Balance — deterministic per-day diagnostics.

Given a target week, summarize per-day busy/free time and surface a few
MVP signals: overloaded days, fragmented days, weak buffer capacity, and
a per-day longest free window. No LLM is involved — all messages are
formatted from named constants and computed facts.

Free capacity is bounded by Daily Rhythm suggestion hours (see
app.services.daily_rhythm) — AvailabilityWindow rows are not consulted.
Free time is computed by subtracting existing events from the daily
suggestion window. The endpoint URL and module names retain the
historical "triage" label for compatibility, but user-facing wording uses
Schedule Balance / Free Capacity / Daily Load language.
"""

from datetime import date, datetime, time, timedelta
from typing import Dict, List, Tuple

from sqlmodel import Session, select

from app.models.event import Event
from app.services.conflict_detection import find_free_windows

# ---------------------------------------------------------------------------
# Thresholds — tweak here to adjust triage sensitivity. All values in minutes
# unless otherwise noted.
# ---------------------------------------------------------------------------
OVERLOADED_DAY_BUSY_MINUTES = 6 * 60        # >= 6h scheduled → overloaded
FRAGMENTED_DAY_FREE_WINDOW_MAX = 45         # free window shorter than this counts as "small"
FRAGMENTED_DAY_MIN_SMALL_WINDOWS = 3        # 3+ small free windows → fragmented
WEAK_BUFFER_FREE_MINUTES = 90               # < 90 min total free → weak buffer
WEAK_WEEKLY_BUFFER_FREE_MINUTES = 5 * 60    # < 5h total weekly free → weak weekly buffer

DAYS_IN_WEEK = 7


def _clip_minutes(
    intervals: List[Tuple[datetime, datetime]],
    day_start: datetime,
    day_end: datetime,
) -> int:
    """Sum minutes of intervals clipped to [day_start, day_end)."""
    total = 0
    for s, e in intervals:
        s_clipped = max(s, day_start)
        e_clipped = min(e, day_end)
        if s_clipped < e_clipped:
            total += int((e_clipped - s_clipped).total_seconds() // 60)
    return total


def compute_weekly_triage(
    session: Session,
    week_start: date,
) -> Dict:
    """Return triage diagnostics for the 7-day window starting at week_start.

    Args:
        session:     Active database session.
        week_start:  First day of the target week (caller decides whether to
                     snap to Monday — the route does that for the MVP).

    Returns:
        Dict matching TriageResponse:
          {
            "week_start": date,
            "week_end": date,                     # inclusive (week_start + 6)
            "days": [TriageDay-shaped dicts ...], # length 7
            "week_warnings": [TriageWarning-shaped dicts ...],
          }

        The ``blocked_minutes`` field on each day is preserved in the
        response shape for frontend compatibility but always returns 0 —
        BlockedTime no longer affects scheduling.
    """
    week_end_inclusive = week_start + timedelta(days=DAYS_IN_WEEK - 1)
    week_end_exclusive_dt = datetime.combine(
        week_start + timedelta(days=DAYS_IN_WEEK), time.min
    )
    week_start_dt = datetime.combine(week_start, time.min)

    # Pull all events that overlap the week, once.
    events = session.exec(
        select(Event).where(
            Event.start_time < week_end_exclusive_dt,
            Event.end_time > week_start_dt,
        )
    ).all()

    event_intervals = [(e.start_time, e.end_time) for e in events]

    # Free windows for the whole week — single helper call, then bucket per day.
    free_windows = find_free_windows(week_start, week_end_inclusive, session)
    free_by_day: Dict[date, List[Tuple[datetime, datetime]]] = {}
    for fw in free_windows:
        free_by_day.setdefault(fw.start_time.date(), []).append(
            (fw.start_time, fw.end_time)
        )

    days: List[Dict] = []
    total_week_free_minutes = 0

    for offset in range(DAYS_IN_WEEK):
        day = week_start + timedelta(days=offset)
        day_start_dt = datetime.combine(day, time.min)
        day_end_dt = datetime.combine(day + timedelta(days=1), time.min)

        scheduled = _clip_minutes(event_intervals, day_start_dt, day_end_dt)
        total_busy = scheduled

        day_free = free_by_day.get(day, [])
        free_durations = [
            int((e - s).total_seconds() // 60) for s, e in day_free
        ]
        free_minutes = sum(free_durations)
        longest_free = max(free_durations) if free_durations else 0
        small_window_count = sum(
            1 for d in free_durations if d < FRAGMENTED_DAY_FREE_WINDOW_MAX
        )

        is_overloaded = total_busy >= OVERLOADED_DAY_BUSY_MINUTES
        is_fragmented = small_window_count >= FRAGMENTED_DAY_MIN_SMALL_WINDOWS
        # Weak buffer only meaningful on a day that has any availability at all
        # (otherwise the day is intentionally off and should not be flagged).
        has_any_availability = bool(day_free) or total_busy > 0
        has_weak_buffer = (
            has_any_availability and free_minutes < WEAK_BUFFER_FREE_MINUTES
        )

        warnings: List[Dict] = []
        if is_overloaded:
            warnings.append({
                "reason_code": "OVERLOADED_DAY",
                "message": (
                    f"This day has {total_busy // 60} hours of occupied time."
                ),
            })
        if is_fragmented:
            warnings.append({
                "reason_code": "FRAGMENTED_DAY",
                "message": (
                    f"This day has {small_window_count} free windows shorter "
                    f"than {FRAGMENTED_DAY_FREE_WINDOW_MAX} minutes."
                ),
            })
        if has_weak_buffer:
            warnings.append({
                "reason_code": "WEAK_BUFFER",
                "message": (
                    f"This day has only {free_minutes} minutes of free time."
                ),
            })

        days.append({
            "date": day,
            "scheduled_minutes": scheduled,
            "blocked_minutes": 0,
            "total_busy_minutes": total_busy,
            "free_minutes": free_minutes,
            "longest_free_window_minutes": longest_free,
            "is_overloaded": is_overloaded,
            "is_fragmented": is_fragmented,
            "has_weak_buffer": has_weak_buffer,
            "warnings": warnings,
        })

        total_week_free_minutes += free_minutes

    week_warnings: List[Dict] = []
    if total_week_free_minutes < WEAK_WEEKLY_BUFFER_FREE_MINUTES:
        week_warnings.append({
            "reason_code": "WEAK_WEEKLY_BUFFER",
            "message": "This week has limited remaining flexible time.",
        })

    return {
        "week_start": week_start,
        "week_end": week_end_inclusive,
        "days": days,
        "week_warnings": week_warnings,
    }

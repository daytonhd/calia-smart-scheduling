"""Weekly scheduling metrics — facts derived from events and blocked times.

Metrics are computed by clipping each event/blocked-time interval to the target
week [week_start 00:00, week_end 00:00) and summing minutes per day. Anything
outside the week is ignored. The busiest day is the calendar day within the
week with the most scheduled event minutes (ties resolved by earliest date).
"""

from datetime import date, datetime, time, timedelta
from typing import List, Optional, Tuple

from sqlmodel import Session, select

from app.models.blocked_time import BlockedTime
from app.models.event import Event
from app.services.conflict_detection import MVP_USER_ID  # noqa: F401  (MVP context)


def monday_of(d: date) -> date:
    """Return the Monday on or before d (weekday convention: 0=Mon)."""
    return d - timedelta(days=d.weekday())


def _clip_minutes_per_day(
    intervals: List[Tuple[datetime, datetime]],
    week_start: date,
    week_end_exclusive: date,
) -> List[int]:
    """Sum minutes per day (length = 7) by clipping each interval to the week.

    Returns a 7-element list indexed by offset from week_start.
    """
    per_day = [0] * 7
    range_start = datetime.combine(week_start, time.min)
    range_end = datetime.combine(week_end_exclusive, time.min)

    for i_start, i_end in intervals:
        s = max(i_start, range_start)
        e = min(i_end, range_end)
        if s >= e:
            continue
        # Walk day-by-day so multi-day intervals attribute minutes to each day.
        cursor = s
        while cursor < e:
            day_idx = (cursor.date() - week_start).days
            next_day = datetime.combine(
                cursor.date() + timedelta(days=1), time.min
            )
            chunk_end = min(e, next_day)
            if 0 <= day_idx < 7:
                per_day[day_idx] += int(
                    (chunk_end - cursor).total_seconds() // 60
                )
            cursor = chunk_end
    return per_day


def compute_weekly_metrics(
    session: Session,
    week_start: Optional[date] = None,
) -> dict:
    """Compute weekly scheduling metrics.

    Args:
        session:     Active database session.
        week_start:  Any date inside the target week; snapped to that week's
                     Monday. Defaults to the current week.

    Returns:
        dict with fields: week_start, week_end, total_events,
        total_blocked_times, total_scheduled_minutes, total_blocked_minutes,
        busiest_day (ISO date string or None), busiest_day_minutes.
    """
    anchor = week_start or date.today()
    ws = monday_of(anchor)
    we_exclusive = ws + timedelta(days=7)
    we_inclusive = ws + timedelta(days=6)

    week_start_dt = datetime.combine(ws, time.min)
    week_end_dt = datetime.combine(we_exclusive, time.min)

    events = session.exec(
        select(Event).where(
            Event.start_time < week_end_dt,
            Event.end_time > week_start_dt,
        )
    ).all()
    blocked = session.exec(
        select(BlockedTime).where(
            BlockedTime.user_id == MVP_USER_ID,
            BlockedTime.start_time < week_end_dt,
            BlockedTime.end_time > week_start_dt,
        )
    ).all()

    event_minutes_per_day = _clip_minutes_per_day(
        [(e.start_time, e.end_time) for e in events], ws, we_exclusive
    )
    blocked_minutes_per_day = _clip_minutes_per_day(
        [(b.start_time, b.end_time) for b in blocked], ws, we_exclusive
    )

    total_scheduled = sum(event_minutes_per_day)
    total_blocked = sum(blocked_minutes_per_day)

    if total_scheduled > 0:
        # argmax over event minutes; earliest day wins ties.
        busiest_idx = max(
            range(7), key=lambda i: (event_minutes_per_day[i], -i)
        )
        busiest_day = ws + timedelta(days=busiest_idx)
        busiest_day_minutes = event_minutes_per_day[busiest_idx]
    else:
        busiest_day = None
        busiest_day_minutes = 0

    return {
        "week_start": ws,
        "week_end": we_inclusive,
        "total_events": len(events),
        "total_blocked_times": len(blocked),
        "total_scheduled_minutes": total_scheduled,
        "total_blocked_minutes": total_blocked,
        "busiest_day": busiest_day,
        "busiest_day_minutes": busiest_day_minutes,
    }

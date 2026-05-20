"""Daily Rhythm — awake hours and suggestion hours.

This module is the source of truth for "when does the user typically want
suggestions to land". The DEFAULT_* constants below are the system defaults.
When a persisted DailyRhythm row exists for the requested user, the
suggestion-window helpers read the saved suggestion hours from it; when no
row exists, they fall back to the defaults.

Daily Rhythm is not "availability" — manual event create/update is never
rejected for falling outside these hours. The suggestion window only bounds
where slot suggestions, replacement options, and Schedule Balance / Free
Capacity scans operate.
"""

from datetime import date, datetime, time, timedelta
from typing import List, Optional, Tuple

from sqlmodel import Session, select

from app.models.daily_rhythm import DailyRhythm

# Awake hours — broader window indicating typical waking time. Defined here
# so future logic (e.g. nudges, end-of-day summaries) has a single source.
DEFAULT_AWAKE_START = time(7, 0)
DEFAULT_AWAKE_END = time(23, 0)

# Suggestion hours — the narrower window inside which slot suggestions and
# free-window scans are constrained. 8 AM to 9 PM by default.
DEFAULT_SUGGESTIONS_START = time(8, 0)
DEFAULT_SUGGESTIONS_END = time(21, 0)


def get_daily_rhythm_settings(
    session: Session, user_id: int
) -> Optional[DailyRhythm]:
    """Return the persisted Daily Rhythm row for the user, or None.

    None means no row has been saved yet for the user — callers should fall
    back to the DEFAULT_* constants.
    """
    return session.exec(
        select(DailyRhythm)
        .where(DailyRhythm.user_id == user_id)
        .order_by(DailyRhythm.id)
    ).first()


def _resolve_suggestion_bounds(
    session: Optional[Session],
    user_id: Optional[int],
) -> Tuple[time, time]:
    """Return the (start, end) suggestion-hours bounds for the user.

    Reads persisted settings when a session and user_id are provided and a
    row exists; otherwise returns the system defaults.
    """
    if session is not None and user_id is not None:
        row = get_daily_rhythm_settings(session, user_id)
        if row is not None:
            return row.suggestions_start_time, row.suggestions_end_time
    return DEFAULT_SUGGESTIONS_START, DEFAULT_SUGGESTIONS_END


def get_suggestion_window_for_date(
    d: date,
    session: Optional[Session] = None,
    user_id: Optional[int] = None,
) -> Tuple[datetime, datetime]:
    """Return the (start_dt, end_dt) suggestion window for a single date.

    When session and user_id are provided, persisted Daily Rhythm suggestion
    hours are used; otherwise the system defaults apply.
    """
    start_t, end_t = _resolve_suggestion_bounds(session, user_id)
    return (
        datetime.combine(d, start_t),
        datetime.combine(d, end_t),
    )


def get_suggestion_windows_for_range(
    start_date: date,
    end_date: date,
    session: Optional[Session] = None,
    user_id: Optional[int] = None,
) -> List[Tuple[datetime, datetime]]:
    """Return one suggestion window per date in [start_date, end_date].

    Inclusive on both ends. Returns [] if end_date < start_date. When
    session and user_id are provided, persisted Daily Rhythm suggestion
    hours are used; otherwise the system defaults apply.
    """
    if end_date < start_date:
        return []
    # Resolve the bounds once for the whole range — one lookup, not one per day.
    start_t, end_t = _resolve_suggestion_bounds(session, user_id)
    windows: List[Tuple[datetime, datetime]] = []
    current = start_date
    while current <= end_date:
        windows.append(
            (
                datetime.combine(current, start_t),
                datetime.combine(current, end_t),
            )
        )
        current += timedelta(days=1)
    return windows

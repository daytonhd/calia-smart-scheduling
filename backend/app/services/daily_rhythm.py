"""Daily Rhythm — awake hours and suggestion hours.

This module is the source of truth for "when does the user typically want
suggestions to land". The DEFAULT_* constants below are the system defaults.
When a persisted DailyRhythm row exists for the MVP user, the suggestion-
window helpers read the saved suggestion hours from it; when no row exists,
they fall back to the defaults.

Daily Rhythm is not "availability" — manual event create/update is never
rejected for falling outside these hours. The suggestion window only bounds
where slot suggestions, replacement options, and Schedule Balance / Free
Capacity scans operate.
"""

from datetime import date, datetime, time, timedelta
from typing import List, Optional, Tuple

from sqlmodel import Session, select

from app.models.daily_rhythm import DailyRhythm

# Single-user MVP user id — auth deferred. There is one active Daily Rhythm
# row per this user.
MVP_USER_ID = 1

# Awake hours — broader window indicating typical waking time. Defined here
# so future logic (e.g. nudges, end-of-day summaries) has a single source.
DEFAULT_AWAKE_START = time(7, 0)
DEFAULT_AWAKE_END = time(23, 0)

# Suggestion hours — the narrower window inside which slot suggestions and
# free-window scans are constrained. 8 AM to 9 PM by default.
DEFAULT_SUGGESTIONS_START = time(8, 0)
DEFAULT_SUGGESTIONS_END = time(21, 0)


def get_daily_rhythm_settings(session: Session) -> Optional[DailyRhythm]:
    """Return the persisted Daily Rhythm row for the MVP user, or None.

    None means no row has been saved yet — callers should fall back to the
    DEFAULT_* constants.
    """
    return session.exec(
        select(DailyRhythm)
        .where(DailyRhythm.user_id == MVP_USER_ID)
        .order_by(DailyRhythm.id)
    ).first()


def _resolve_suggestion_bounds(
    session: Optional[Session],
) -> Tuple[time, time]:
    """Return the (start, end) suggestion-hours bounds.

    Reads persisted settings when a session is provided and a row exists;
    otherwise returns the system defaults.
    """
    if session is not None:
        row = get_daily_rhythm_settings(session)
        if row is not None:
            return row.suggestions_start_time, row.suggestions_end_time
    return DEFAULT_SUGGESTIONS_START, DEFAULT_SUGGESTIONS_END


def get_suggestion_window_for_date(
    d: date,
    session: Optional[Session] = None,
) -> Tuple[datetime, datetime]:
    """Return the (start_dt, end_dt) suggestion window for a single date.

    When session is provided, persisted Daily Rhythm suggestion hours are
    used; otherwise the system defaults apply.
    """
    start_t, end_t = _resolve_suggestion_bounds(session)
    return (
        datetime.combine(d, start_t),
        datetime.combine(d, end_t),
    )


def get_suggestion_windows_for_range(
    start_date: date,
    end_date: date,
    session: Optional[Session] = None,
) -> List[Tuple[datetime, datetime]]:
    """Return one suggestion window per date in [start_date, end_date].

    Inclusive on both ends. Returns [] if end_date < start_date. When
    session is provided, persisted Daily Rhythm suggestion hours are used;
    otherwise the system defaults apply.
    """
    if end_date < start_date:
        return []
    # Resolve the bounds once for the whole range — one lookup, not one per day.
    start_t, end_t = _resolve_suggestion_bounds(session)
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

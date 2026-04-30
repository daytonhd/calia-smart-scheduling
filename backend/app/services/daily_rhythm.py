"""Daily Rhythm — backend defaults for awake hours and suggestion hours.

This module is the source of truth for "when does the user typically want
suggestions to land". There is no database table backing it in this phase —
the constants below define system defaults, and helpers build per-day
suggestion windows for callers (free-window and slot-suggestion logic).

A future phase may introduce a user-configurable settings table; at that
point the helpers here can be extended to read overrides per user. For now,
all callers see a single global rhythm.
"""

from datetime import date, datetime, time, timedelta
from typing import List, Tuple

# Awake hours — broader window indicating typical waking time. Defined here
# so future logic (e.g. nudges, end-of-day summaries) has a single source.
DEFAULT_AWAKE_START = time(7, 0)
DEFAULT_AWAKE_END = time(23, 0)

# Suggestion hours — the narrower window inside which slot suggestions and
# free-window scans are constrained. 8 AM to 9 PM by default.
DEFAULT_SUGGESTIONS_START = time(8, 0)
DEFAULT_SUGGESTIONS_END = time(21, 0)


def get_suggestion_window_for_date(d: date) -> Tuple[datetime, datetime]:
    """Return the (start_dt, end_dt) suggestion window for a single date."""
    return (
        datetime.combine(d, DEFAULT_SUGGESTIONS_START),
        datetime.combine(d, DEFAULT_SUGGESTIONS_END),
    )


def get_suggestion_windows_for_range(
    start_date: date,
    end_date: date,
) -> List[Tuple[datetime, datetime]]:
    """Return one suggestion window per date in [start_date, end_date].

    Inclusive on both ends. Returns [] if end_date < start_date.
    """
    if end_date < start_date:
        return []
    windows: List[Tuple[datetime, datetime]] = []
    current = start_date
    while current <= end_date:
        windows.append(get_suggestion_window_for_date(current))
        current += timedelta(days=1)
    return windows

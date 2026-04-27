"""MVP time contract for scheduling comparisons.

Contract:
- All scheduling datetime fields — event/blocked-time start_time/end_time,
  conflict-check request times, slot-suggestion request times — MUST be naive
  datetimes representing local application time.
- Timezone-aware datetimes are rejected at the API boundary so that downstream
  comparisons never silently mix naive and aware values (which would either
  raise TypeError or, in mixed-tz contexts, return wrong answers).
- Date-only fields (week_start, start_date, end_date) carry no timezone and
  are passed through as-is.
- Internal model timestamps (created_at, updated_at) may remain tz-aware UTC
  because they are bookkeeping fields, not used in scheduling comparisons.

Why naive: the existing scheduling stack — availability windows (datetime.time
wall-clock), event/blocked-time storage, overlap checks, free-window scanning,
slot suggestions, metrics, and triage — all compares naive datetimes today.
Choosing naive-only keeps the contract consistent with the verified codebase
without requiring a full timezone refactor.
"""

from datetime import datetime
from typing import Optional


def ensure_naive_datetime(
    value: Optional[datetime],
    field_name: str = "datetime",
) -> Optional[datetime]:
    """Return value unchanged if naive (or None); raise ValueError if tz-aware.

    Apply this to every scheduling datetime crossing the API boundary so
    downstream service code can assume a single, consistent datetime kind.
    """
    if value is None:
        return None
    if value.tzinfo is not None:
        raise ValueError(
            f"{field_name} must be a naive datetime (no timezone info). "
            "Scheduling MVP contract: send local app time without tz offset."
        )
    return value

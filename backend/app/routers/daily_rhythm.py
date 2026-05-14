"""Daily Rhythm endpoints — read and update the single MVP user's rhythm.

Daily Rhythm is not "availability": these endpoints only store the user's
awake/suggestion hours. Event create/update is never gated on them.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.database import get_session
from app.models.daily_rhythm import DailyRhythm
from app.schemas.daily_rhythm import (
    DailyRhythmRead,
    DailyRhythmUpdate,
    format_hhmm,
    parse_hhmm,
)
from app.services.daily_rhythm import (
    DEFAULT_AWAKE_END,
    DEFAULT_AWAKE_START,
    DEFAULT_SUGGESTIONS_END,
    DEFAULT_SUGGESTIONS_START,
    MVP_USER_ID,
    get_daily_rhythm_settings,
)

router = APIRouter(prefix="/daily-rhythm", tags=["daily-rhythm"])


def _to_read(row: DailyRhythm) -> DailyRhythmRead:
    return DailyRhythmRead(
        awake_start_time=format_hhmm(row.awake_start_time),
        awake_end_time=format_hhmm(row.awake_end_time),
        suggestions_start_time=format_hhmm(row.suggestions_start_time),
        suggestions_end_time=format_hhmm(row.suggestions_end_time),
    )


def _defaults_read() -> DailyRhythmRead:
    return DailyRhythmRead(
        awake_start_time=format_hhmm(DEFAULT_AWAKE_START),
        awake_end_time=format_hhmm(DEFAULT_AWAKE_END),
        suggestions_start_time=format_hhmm(DEFAULT_SUGGESTIONS_START),
        suggestions_end_time=format_hhmm(DEFAULT_SUGGESTIONS_END),
    )


@router.get("", response_model=DailyRhythmRead)
def get_daily_rhythm(session: Session = Depends(get_session)):
    """Return the persisted Daily Rhythm for the MVP user.

    When no row has been saved yet, returns the system defaults
    (07:00–23:00 awake, 08:00–21:00 suggestions) without persisting them.
    """
    row = get_daily_rhythm_settings(session)
    if row is None:
        return _defaults_read()
    return _to_read(row)


@router.patch("", response_model=DailyRhythmRead)
def update_daily_rhythm(
    body: DailyRhythmUpdate,
    session: Session = Depends(get_session),
):
    """Create or update the single MVP user's Daily Rhythm.

    The request body is fully validated (see DailyRhythmUpdate): awake range,
    suggestion range, and suggestion hours fitting inside awake hours.
    """
    row = get_daily_rhythm_settings(session)
    if row is None:
        row = DailyRhythm(user_id=MVP_USER_ID)

    row.awake_start_time = parse_hhmm(body.awake_start_time)
    row.awake_end_time = parse_hhmm(body.awake_end_time)
    row.suggestions_start_time = parse_hhmm(body.suggestions_start_time)
    row.suggestions_end_time = parse_hhmm(body.suggestions_end_time)
    row.updated_at = datetime.now(timezone.utc)

    session.add(row)
    session.commit()
    session.refresh(row)
    return _to_read(row)

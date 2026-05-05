"""Tests for the MVP time contract.

The contract: scheduling datetime fields at the API boundary must be naive.
Timezone-aware values must be rejected by the schemas.
"""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.event import EventCreate, EventUpdate
from app.schemas.schedule import ConflictCheckRequest
from app.services.time_contract import ensure_naive_datetime


def test_ensure_naive_datetime_passes_naive():
    naive = datetime(2026, 4, 27, 9, 0)
    assert ensure_naive_datetime(naive) is naive


def test_ensure_naive_datetime_passes_none():
    assert ensure_naive_datetime(None) is None


def test_ensure_naive_datetime_rejects_aware():
    aware = datetime(2026, 4, 27, 9, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        ensure_naive_datetime(aware, "start_time")


def test_event_create_rejects_tz_aware_start():
    with pytest.raises(ValidationError):
        EventCreate(
            calendar_id=1,
            title="x",
            start_time=datetime(2026, 4, 27, 9, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 4, 27, 10, 0),
        )


def test_event_create_accepts_naive():
    ec = EventCreate(
        calendar_id=1,
        title="x",
        start_time=datetime(2026, 4, 27, 9, 0),
        end_time=datetime(2026, 4, 27, 10, 0),
    )
    assert ec.start_time.tzinfo is None
    assert ec.end_time.tzinfo is None


def test_event_update_rejects_tz_aware_end():
    with pytest.raises(ValidationError):
        EventUpdate(end_time=datetime(2026, 4, 27, 10, 0, tzinfo=timezone.utc))


def test_conflict_check_request_rejects_tz_aware():
    with pytest.raises(ValidationError):
        ConflictCheckRequest(
            calendar_id=1,
            start_time=datetime(2026, 4, 27, 9, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 4, 27, 10, 0),
        )


def test_conflict_check_request_accepts_naive():
    req = ConflictCheckRequest(
        calendar_id=1,
        start_time=datetime(2026, 4, 27, 9, 0),
        end_time=datetime(2026, 4, 27, 10, 0),
    )
    assert req.start_time.tzinfo is None

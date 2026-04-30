"""Tests for the Daily Rhythm service module."""

from datetime import date, datetime, time

from app.services.daily_rhythm import (
    DEFAULT_AWAKE_END,
    DEFAULT_AWAKE_START,
    DEFAULT_SUGGESTIONS_END,
    DEFAULT_SUGGESTIONS_START,
    get_suggestion_window_for_date,
    get_suggestion_windows_for_range,
)


def test_default_constants_match_spec():
    """The product spec fixes these defaults; reading them is part of the contract."""
    assert DEFAULT_AWAKE_START == time(7, 0)
    assert DEFAULT_AWAKE_END == time(23, 0)
    assert DEFAULT_SUGGESTIONS_START == time(8, 0)
    assert DEFAULT_SUGGESTIONS_END == time(21, 0)


def test_get_suggestion_window_for_date_returns_8am_to_9pm():
    d = date(2026, 4, 20)
    start, end = get_suggestion_window_for_date(d)
    assert start == datetime(2026, 4, 20, 8, 0)
    assert end == datetime(2026, 4, 20, 21, 0)


def test_get_suggestion_windows_for_range_one_window_per_day():
    start = date(2026, 4, 20)
    end = date(2026, 4, 22)

    windows = get_suggestion_windows_for_range(start, end)

    assert windows == [
        (datetime(2026, 4, 20, 8, 0), datetime(2026, 4, 20, 21, 0)),
        (datetime(2026, 4, 21, 8, 0), datetime(2026, 4, 21, 21, 0)),
        (datetime(2026, 4, 22, 8, 0), datetime(2026, 4, 22, 21, 0)),
    ]


def test_get_suggestion_windows_for_range_single_day():
    d = date(2026, 4, 20)
    windows = get_suggestion_windows_for_range(d, d)
    assert len(windows) == 1


def test_get_suggestion_windows_for_range_inverted_returns_empty():
    """end_date < start_date → empty result, not an error."""
    assert get_suggestion_windows_for_range(
        date(2026, 4, 22), date(2026, 4, 20)
    ) == []

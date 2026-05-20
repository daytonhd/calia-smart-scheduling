"""Cross-user data isolation tests.

Proves the multi-user contract: a user only ever sees and mutates their own
calendars, events, categories, and scheduling data. These tests drive the
route handlers and services directly (no TestClient), passing each user in
place of the production HTTPBearer dependency.

Anchor date: Monday 2026-04-20.
"""

from datetime import date, datetime

import pytest
from fastapi import HTTPException
from sqlmodel import select

from app.models.calendar import Calendar
from app.models.user import User
from app.routers import calendars as cal_routes
from app.routers import events as event_routes
from app.routers.auth import signup
from app.routers.schedule import check_conflict, weekly_metrics
from app.schemas.auth import SignupRequest
from app.schemas.calendar import CalendarCreate, CalendarUpdate
from app.schemas.event import EventCreate
from app.schemas.schedule import ConflictCheckRequest
from app.services.conflict_detection import check_all_conflicts, find_available_slots
from app.services.metrics import compute_weekly_metrics

MONDAY = date(2026, 4, 20)


def _users(session):
    """Create two fully-provisioned users (each gets a default calendar)."""
    a_resp = signup(
        SignupRequest(name="Alice", email="alice@example.com", password="alice-pass-1"),
        session,
    )
    b_resp = signup(
        SignupRequest(name="Bob", email="bob@example.com", password="bob-pass-12"),
        session,
    )
    return session.get(User, a_resp.user.id), session.get(User, b_resp.user.id)


def _default_calendar(session, user):
    return session.exec(
        select(Calendar).where(Calendar.user_id == user.id)
    ).first()


# ---------------------------------------------------------------------------
# Signup provisioning
# ---------------------------------------------------------------------------


def test_signup_gives_each_user_their_own_single_default_calendar(session):
    alice, bob = _users(session)

    alice_cals = cal_routes.list_calendars(session, alice)
    bob_cals = cal_routes.list_calendars(session, bob)

    assert len(alice_cals) == 1
    assert len(bob_cals) == 1
    # Different rows, different owners.
    assert alice_cals[0].id != bob_cals[0].id
    assert alice_cals[0].user_id == alice.id
    assert bob_cals[0].user_id == bob.id


def test_new_user_has_zero_categories(session):
    from app.routers.categories import list_categories

    alice, _ = _users(session)
    assert list_categories(session, alice) == []


# ---------------------------------------------------------------------------
# Calendar isolation
# ---------------------------------------------------------------------------


def test_user_cannot_list_other_users_calendars(session):
    alice, bob = _users(session)
    cal_routes.create_calendar(CalendarCreate(name="Alice extra"), session, alice)

    bob_cals = cal_routes.list_calendars(session, bob)
    names = {c.name for c in bob_cals}
    assert "Alice extra" not in names
    assert all(c.user_id == bob.id for c in bob_cals)


def test_user_cannot_read_other_users_calendar_by_id(session):
    alice, bob = _users(session)
    alice_cal = _default_calendar(session, alice)

    with pytest.raises(HTTPException) as exc:
        cal_routes.get_calendar(alice_cal.id, session, bob)
    assert exc.value.status_code == 404


def test_user_cannot_update_other_users_calendar(session):
    alice, bob = _users(session)
    alice_cal = _default_calendar(session, alice)

    with pytest.raises(HTTPException) as exc:
        cal_routes.update_calendar(
            alice_cal.id, CalendarUpdate(name="Hijacked"), session, bob
        )
    assert exc.value.status_code == 404
    # Untouched.
    assert session.get(Calendar, alice_cal.id).name == "Main calendar"


def test_user_cannot_delete_other_users_calendar(session):
    alice, bob = _users(session)
    alice_cal = _default_calendar(session, alice)

    with pytest.raises(HTTPException) as exc:
        cal_routes.delete_calendar(alice_cal.id, session, bob)
    assert exc.value.status_code == 404
    assert session.get(Calendar, alice_cal.id) is not None


def test_two_users_may_share_a_calendar_name(session):
    """Names are unique per user, not globally — both may use "Main calendar"."""
    alice, bob = _users(session)
    # Both already have "Main calendar" from signup; creating a second-named
    # calendar with a name the other user owns must succeed.
    cal_routes.create_calendar(CalendarCreate(name="Shared name"), session, alice)
    created = cal_routes.create_calendar(
        CalendarCreate(name="Shared name"), session, bob
    )
    assert created.user_id == bob.id


# ---------------------------------------------------------------------------
# Event isolation
# ---------------------------------------------------------------------------


def _event_body(calendar_id, hour=10):
    return EventCreate(
        calendar_id=calendar_id,
        title="Event",
        start_time=datetime(2026, 4, 20, hour, 0),
        end_time=datetime(2026, 4, 20, hour + 1, 0),
    )


def test_user_cannot_create_event_on_other_users_calendar(session):
    alice, bob = _users(session)
    alice_cal = _default_calendar(session, alice)

    with pytest.raises(HTTPException) as exc:
        event_routes.create_event(_event_body(alice_cal.id), session, bob)
    assert exc.value.status_code == 404


def test_user_cannot_list_other_users_events(session):
    alice, bob = _users(session)
    alice_cal = _default_calendar(session, alice)
    event_routes.create_event(_event_body(alice_cal.id), session, alice)

    bob_events = event_routes.list_events(
        calendar_id=None, start_time=None, end_time=None,
        session=session, current_user=bob,
    )
    assert bob_events == []

    alice_events = event_routes.list_events(
        calendar_id=None, start_time=None, end_time=None,
        session=session, current_user=alice,
    )
    assert len(alice_events) == 1


def test_user_cannot_read_other_users_event_by_id(session):
    alice, bob = _users(session)
    alice_cal = _default_calendar(session, alice)
    ev = event_routes.create_event(_event_body(alice_cal.id), session, alice)

    with pytest.raises(HTTPException) as exc:
        event_routes.get_event(ev.id, session, bob)
    assert exc.value.status_code == 404


def test_user_cannot_delete_other_users_event(session):
    alice, bob = _users(session)
    alice_cal = _default_calendar(session, alice)
    ev = event_routes.create_event(_event_body(alice_cal.id), session, alice)

    with pytest.raises(HTTPException) as exc:
        event_routes.delete_event(ev.id, session, bob)
    assert exc.value.status_code == 404
    assert event_routes.get_event(ev.id, session, alice) is not None


def test_listing_other_users_calendar_filter_is_404(session):
    """Filtering events by a calendar you don't own is a 404, not silent empty."""
    alice, bob = _users(session)
    alice_cal = _default_calendar(session, alice)

    with pytest.raises(HTTPException) as exc:
        event_routes.list_events(
            calendar_id=alice_cal.id, start_time=None, end_time=None,
            session=session, current_user=bob,
        )
    assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# Event creation without categories
# ---------------------------------------------------------------------------


def test_event_creation_works_without_category_and_with_no_categories(session):
    """A brand-new user (zero categories) can create an event with no category."""
    alice, _ = _users(session)
    alice_cal = _default_calendar(session, alice)

    body = EventCreate(
        calendar_id=alice_cal.id,
        title="No category",
        start_time=datetime(2026, 4, 20, 9, 0),
        end_time=datetime(2026, 4, 20, 10, 0),
    )
    ev = event_routes.create_event(body, session, alice)

    assert ev.id is not None
    assert ev.category is None


# ---------------------------------------------------------------------------
# Scheduling isolation — conflicts, suggestions, metrics
# ---------------------------------------------------------------------------


def test_conflict_check_ignores_other_users_events(session):
    """Bob's busy 10:00-11:00 must not conflict with Alice's 10:00-11:00."""
    alice, bob = _users(session)
    bob_cal = _default_calendar(session, bob)
    event_routes.create_event(_event_body(bob_cal.id, hour=10), session, bob)

    body = ConflictCheckRequest(
        calendar_id=_default_calendar(session, alice).id,
        start_time=datetime(2026, 4, 20, 10, 0),
        end_time=datetime(2026, 4, 20, 11, 0),
    )
    resp = check_conflict(body, session, alice)
    assert resp.has_conflicts is False
    assert resp.conflicts == []


def test_service_conflict_check_is_user_scoped(session):
    alice, bob = _users(session)
    bob_cal = _default_calendar(session, bob)
    event_routes.create_event(_event_body(bob_cal.id, hour=10), session, bob)

    # Alice sees no conflict; Bob does.
    alice_conf = check_all_conflicts(
        datetime(2026, 4, 20, 10, 0),
        datetime(2026, 4, 20, 11, 0),
        session,
        user_id=alice.id,
    )
    bob_conf = check_all_conflicts(
        datetime(2026, 4, 20, 10, 0),
        datetime(2026, 4, 20, 11, 0),
        session,
        user_id=bob.id,
    )
    assert alice_conf == []
    assert [c.reason_code for c in bob_conf] == ["EVENT_OVERLAP"]


def test_slot_suggestions_ignore_other_users_events(session):
    """Alice's 10:00 slot stays available even though Bob is busy then."""
    alice, bob = _users(session)
    bob_cal = _default_calendar(session, bob)
    event_routes.create_event(_event_body(bob_cal.id, hour=10), session, bob)

    alice_slots = find_available_slots(
        duration_minutes=60,
        start_date=MONDAY,
        end_date=MONDAY,
        max_results=100,
        session=session,
        user_id=alice.id,
    )
    starts = {s.start_time for s in alice_slots}
    assert datetime(2026, 4, 20, 10, 0) in starts

    bob_slots = find_available_slots(
        duration_minutes=60,
        start_date=MONDAY,
        end_date=MONDAY,
        max_results=100,
        session=session,
        user_id=bob.id,
    )
    bob_starts = {s.start_time for s in bob_slots}
    # Bob is busy 10:00-11:00, so the 10:00 grid slot is gone for him.
    assert datetime(2026, 4, 20, 10, 0) not in bob_starts


def test_weekly_metrics_only_count_current_users_events(session):
    alice, bob = _users(session)
    alice_cal = _default_calendar(session, alice)
    bob_cal = _default_calendar(session, bob)

    # Alice: one 60-min event. Bob: two events.
    event_routes.create_event(_event_body(alice_cal.id, hour=9), session, alice)
    event_routes.create_event(_event_body(bob_cal.id, hour=9), session, bob)
    event_routes.create_event(_event_body(bob_cal.id, hour=11), session, bob)

    alice_m = compute_weekly_metrics(session, user_id=alice.id, week_start=MONDAY)
    bob_m = compute_weekly_metrics(session, user_id=bob.id, week_start=MONDAY)

    assert alice_m["total_events"] == 1
    assert alice_m["total_scheduled_minutes"] == 60
    assert bob_m["total_events"] == 2
    assert bob_m["total_scheduled_minutes"] == 120


def test_metrics_route_is_user_scoped(session):
    alice, bob = _users(session)
    bob_cal = _default_calendar(session, bob)
    event_routes.create_event(_event_body(bob_cal.id, hour=9), session, bob)

    # Alice's metrics endpoint must not see Bob's event.
    alice_metrics = weekly_metrics(week_start=MONDAY, session=session, current_user=alice)
    assert alice_metrics["total_events"] == 0

# Plan: explicit overlap override on event create / update

**Status: plan only — not implemented.** This note records the intended
API/UX direction so the future change is unambiguous. No schema or behavior
change ships in this batch.

## Today's behavior

`POST /events/` and `PATCH /events/{id}` reject overlapping events with a
`409` (`EVENT_OVERLAP`). There is no way for the user to save anyway.
Placements outside Daily Rhythm / suggestion hours are already allowed —
they are not treated as conflicts.

## Planned behavior

- Default create/update behavior still **rejects overlaps**.
- After seeing the conflict, the user can choose **"Save anyway"** in the UI.
- When the user confirms, the frontend sends an explicit request field:
  `allow_conflicts: boolean`.
- The field **defaults to `false`**.
- The backend bypasses overlap conflicts **only when `allow_conflicts` is
  `true`**.
- **Invalid time ranges are never overrideable** — `start_time >= end_time`
  still fails regardless of `allow_conflicts`.
- **Outside Daily Rhythm / suggestion hours does not require an override** —
  it is not a hard conflict and is already permitted.
- The override is **explicit in the request**, never inferred from category,
  priority, or any other field.

## Suggested shape

- Add `allow_conflicts: bool = False` to `EventCreate` and `EventUpdate`.
- In `events.py`, skip the `EVENT_OVERLAP` rejection when `allow_conflicts`
  is true; keep returning `409` otherwise. Time-range validation is
  unchanged.
- Frontend: on a `409`, surface the conflict, then offer "Save anyway",
  which re-issues the request with `allow_conflicts: true`.

## Out of scope for this plan

No new blocking field (`is_blocking` / `blocks_suggestions`), no recurrence,
no auth, no notifications, no database schema change.

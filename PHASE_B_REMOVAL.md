# Phase B removal path: AvailabilityWindow & BlockedTime

This document is the single source of truth for the eventual removal of the
legacy AvailabilityWindow workflow and confirms the already-completed status
of BlockedTime. Phase A keeps the legacy surfaces in place for backward
compatibility; Phase B is the cleanup pass that deletes them.

## Status snapshot

| Component | Phase A state | Phase B action |
|---|---|---|
| `blocked_times` table | Already dropped (migration `c4d5e6f7a8b9`) | None — already done |
| `BlockedTime` model / schema / router | Do not exist in the codebase | None — already done |
| `BLOCKED_TIME_OVERLAP` reason code | Not present in code | None — already done |
| `availability_windows` table | Exists, written to by deprecated router | Drop in Phase B |
| `AvailabilityWindow` model | Exists, only read by `_check_availability` (uninvoked) | Remove in Phase B |
| `AvailabilityCreate`/`Read`/`Update` schemas | Exist, used by deprecated router | Remove in Phase B |
| `/availability` router | Flagged `deprecated=True`; still mounted | Remove in Phase B |
| `_check_availability` helper | Retained, never invoked | Remove in Phase B |
| `OUTSIDE_AVAILABILITY` reason code | Schema-level constant; never returned | Remove in Phase B |
| `frontend/app/availability/page.tsx` | Live page, marked legacy | Delete in Phase B |
| `AvailabilityWindow*` frontend types & API helpers | In `frontend/lib/types.ts` & `frontend/lib/api.ts` | Remove in Phase B |
| Tests asserting `OUTSIDE_AVAILABILITY` is absent | Active regression coverage | Convert / delete in Phase B |

## Entry criteria (when Phase B is allowed to happen)

Phase B may begin only when **all** of the following are true:

1. Category-based Events have been the only occupied-time signal in production
   for at least one full release cycle without scheduling regressions.
2. No active scheduling code path reads `AvailabilityWindow` rows. Verified by:
   - `_check_availability` is never called from `check_all_conflicts`,
     `find_free_windows`, slot suggestions, replacement options, or triage.
   - Grep for `AvailabilityWindow` in `app/services/` and `app/routers/`
     (excluding `app/routers/availability.py`) returns no matches.
3. The deprecated `/availability` endpoints have shown zero traffic from any
   non-test client for a full release cycle (or are explicitly confirmed
   retired by the only client team).
4. The frontend `/availability` page is no longer linked from any active
   navigation surface and analytics show no entry traffic.
5. There is a database backup / restore plan in place that does not depend on
   `availability_windows` continuing to exist.

If any of these is unclear, stay in Phase A.

## Phase A guardrails (do NOT do these prematurely)

To prevent accidentally doing Phase B work in a Phase A change:

- Do not drop the `availability_windows` table.
- Do not delete `app/models/availability_window.py`.
- Do not delete `app/schemas/availability.py`.
- Do not delete or unmount `app/routers/availability.py`.
- Do not delete `_check_availability` from `app/services/conflict_detection.py`.
- Do not delete the `OUTSIDE_AVAILABILITY` constant or related schema docstrings.
- Do not delete `frontend/app/availability/page.tsx` or the `AvailabilityWindow*`
  exports in `frontend/lib/types.ts` / `frontend/lib/api.ts`.
- Do not delete the regression tests that assert `OUTSIDE_AVAILABILITY` never
  appears in active conflict surfaces — they are load-bearing for the
  current contract.

Active scheduling logic must continue to derive occupied time from Events
only; reintroducing AvailabilityWindow into any active code path is also
out of scope for both Phase A and Phase B.

## Phase B work items

### Database

- Add a new alembic migration that drops `availability_windows`.
  - `upgrade()`: `op.drop_table('availability_windows')`.
  - `downgrade()`: recreate the table with the column shape currently defined
    by `app/models/availability_window.py` (mirror the pattern used by
    `c4d5e6f7a8b9_drop_blocked_times_table.py`).
  - The migration must come after the latest head at the time Phase B runs.

### Backend

- Delete `app/models/availability_window.py`.
- Delete `app/schemas/availability.py`.
- Delete `app/routers/availability.py` and remove its import / `include_router`
  call in `app/main.py`.
- In `app/services/conflict_detection.py`:
  - Remove the `_check_availability` helper.
  - Remove the `from app.models.availability_window import AvailabilityWindow`
    import.
  - Remove docstring references to `OUTSIDE_AVAILABILITY` and the legacy helper.
- In `app/schemas/schedule.py`: remove the `OUTSIDE_AVAILABILITY` mention from
  the `ConflictDetail` docstring (the constant itself is not exported as a
  symbol, just referenced in prose).
- Audit `app/services/` and `app/routers/` for any remaining string mentions
  of `OUTSIDE_AVAILABILITY` or `AvailabilityWindow` and remove.

### Frontend

- Delete `frontend/app/availability/` (the whole directory).
- In `frontend/lib/types.ts`: remove `AvailabilityWindow`, `AvailabilityWindowCreate`,
  and any related types.
- In `frontend/lib/api.ts`: remove `createAvailability`, `listAvailability`,
  `updateAvailability`, `deleteAvailability` (and any related helpers).
- Remove any nav links, dashboard cards, or settings entries pointing to
  `/availability`.
- Remove any styles in `frontend/app/globals.css` that are exclusive to the
  availability page.

### Tests

- Delete tests that exist solely to assert `OUTSIDE_AVAILABILITY` is no
  longer emitted (e.g. `backend/tests/test_outside_availability_allowed.py`,
  the `OUTSIDE_AVAILABILITY` blocks in `test_availability_rules.py`,
  `test_conflict_explainability.py`,
  `test_daily_rhythm_zero_availability.py`).
- Update any tests that import from `app.models.availability_window`,
  `app.schemas.availability`, or `app.routers.availability` to remove those
  imports along with the deleted code.
- Update test factories (`backend/tests/factories.py`) to drop
  `make_availability` and any other AvailabilityWindow helpers, plus their
  call sites in remaining tests.
- Run the full backend suite after each deletion batch and confirm green.

## Compatibility & deprecation notes

- The deprecated `/availability` endpoints already return `deprecated=True`
  in OpenAPI. Before Phase B runs, a release note should announce a hard
  removal date so any external consumer has a final warning window.
- The `OUTSIDE_AVAILABILITY` reason code has been off the wire since the
  Daily Rhythm rework. Phase B removes the symbol; clients that still
  hard-coded it should have already been migrated.
- BlockedTime is fully retired: the table is dropped, no model/schema/router
  exists, and `BLOCKED_TIME_OVERLAP` is not in the codebase. Phase B has
  no remaining BlockedTime work — this is documented here so future cleanup
  passes do not waste time looking for it.

## Out of scope

- Reintroducing user-configurable Daily Rhythm overrides (deferred to a
  later phase, not part of Phase B).
- Adding a database-backed Daily Rhythm settings table.
- Bringing back AvailabilityWindow logic in any form.
- Using BlockedTime in active scheduling logic.

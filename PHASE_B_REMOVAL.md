# Phase B removal: AvailabilityWindow — completed

**Status:** Complete. The legacy AvailabilityWindow workflow has been
fully removed from the active product. BlockedTime was already retired
before this pass; no Phase B work was required for it.

## Commits

- `a2a1b23` refactor: remove legacy availability frontend surface
- `37aff03` refactor: remove legacy availability backend routes
- `1cc2108` refactor: remove legacy availability model references
- `b92900f` db: drop legacy availability windows table
- `84d71d3` refactor: remove stale availability schema wording

## What was removed

### Database
- `availability_windows` table dropped via Alembic migration
  `c79d502acb1f_drop_availability_windows_table.py`.

### Backend
- `app/models/availability_window.py`
- `app/schemas/availability.py`
- `app/routers/availability.py` (and its `include_router` call in
  `app/main.py`)
- `_check_availability` helper in `app/services/conflict_detection.py`
- All `AvailabilityWindow` imports in services and routers
- Stale `OUTSIDE_AVAILABILITY` / `AvailabilityWindow` wording in schema
  docstrings

### Frontend
- `frontend/app/availability/` page directory
- `AvailabilityWindow*` types in `frontend/lib/types.ts`
- `createAvailability` / `listAvailability` / `updateAvailability` /
  `deleteAvailability` helpers in `frontend/lib/api.ts`
- Navigation links, dashboard cards, and styles tied to `/availability`

### Tests
- `make_availability` factory and its call sites removed from
  `backend/tests/factories.py` and every test module that referenced it
- Tests whose sole purpose was asserting AvailabilityWindow-row behavior
  deleted; tests verifying current behavior (events as the sole
  occupied-time source, manual events outside Daily Rhythm allowed,
  Daily-Rhythm-driven slot suggestions, replacement options without
  availability rows, metrics/triage capacity from Daily Rhythm,
  `OUTSIDE_AVAILABILITY` not emitted) were preserved

## What remains only in Alembic migration history

- The original `52427ce9417d` migration that created
  `availability_windows` (alongside `blocked_times` and
  `schedule_summaries`) is unchanged. It is now historical only.
- The new `c79d502acb1f` migration's `downgrade()` recreates the
  `availability_windows` table with its prior column shape — this is
  the only place the legacy schema definition still lives.

No active backend, frontend, or test code references AvailabilityWindow.

## Verification performed

- `grep` for `AvailabilityWindow` / `make_availability` /
  `_check_availability` / `OUTSIDE_AVAILABILITY` across active backend
  and frontend code — clean.
- `alembic upgrade head` → `c79d502acb1f (head)`.
- `alembic check` → `No new upgrade operations detected.`
- `pytest` → 139 passed.
- Working tree clean after final commit (`84d71d3`).

## BlockedTime note

BlockedTime was fully retired before this pass: the table was dropped
in migration `c4d5e6f7a8b9`, no model/schema/router existed, and
`BLOCKED_TIME_OVERLAP` was not in the codebase. Documented here so
future cleanup passes do not look for it.

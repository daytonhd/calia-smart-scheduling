"""Seed script for local dev/demo data only.

This script exists so a developer can poke at the app without going through
the signup flow. It is NOT what real users see — every new account created
through POST /auth/signup gets its own default calendar in app/routers/auth.py.

Behavior:
  - Creates one demo user (if missing).
  - Creates one default calendar ("Main calendar") owned by that user.
  - Does NOT create Work/School/Personal calendars — that pattern implied
    every real user got those preset calendars, which is no longer true.
  - Does NOT create categories — those are user-created on demand.

Run from backend/ directory: python seed.py
Idempotent — safe to re-run.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlmodel import Session, select

from app.database import engine
import app.models  # noqa: F401 — registers all SQLModel metadata
from app.models.user import User
from app.models.calendar import Calendar
from app.security import hash_password


DEMO_USER_NAME = "Demo User"
DEMO_USER_EMAIL = "demo@example.com"
# Local-dev demo credentials only. Never use this elsewhere.
DEMO_USER_PASSWORD = "demo-password"

# The single demo calendar mirrors what real users get on signup — no
# Work/School/Personal preset list.
DEMO_CALENDAR_NAME = "Main calendar"


def seed() -> None:
    with Session(engine) as session:
        # Seed user (idempotent by email)
        existing_user = session.exec(
            select(User).where(User.email == DEMO_USER_EMAIL)
        ).first()
        if not existing_user:
            user = User(
                name=DEMO_USER_NAME,
                email=DEMO_USER_EMAIL,
                hashed_password=hash_password(DEMO_USER_PASSWORD),
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            print(f"Created user: {user.name} (id={user.id})")
        else:
            user = existing_user
            print(f"User already exists: {user.name} (id={user.id})")

        # Seed exactly one demo calendar owned by the demo user.
        existing = session.exec(
            select(Calendar).where(
                Calendar.user_id == user.id,
                Calendar.name == DEMO_CALENDAR_NAME,
            )
        ).first()
        if not existing:
            session.add(Calendar(user_id=user.id, name=DEMO_CALENDAR_NAME))
            print(f"Created calendar: {DEMO_CALENDAR_NAME}")
        else:
            print(f"Calendar already exists: {DEMO_CALENDAR_NAME}")

        session.commit()
        print("Seed complete.")


if __name__ == "__main__":
    seed()

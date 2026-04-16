"""Seed script for MVP dev/demo data.

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


DEMO_USER_NAME = "Demo User"
DEMO_USER_EMAIL = "demo@example.com"

SAMPLE_CALENDARS = [
    {"name": "Work", "color": "#3B82F6"},
    {"name": "Personal", "color": "#10B981"},
    {"name": "School", "color": "#F59E0B"},
]


def seed() -> None:
    with Session(engine) as session:
        # Seed user (idempotent by email)
        existing_user = session.exec(
            select(User).where(User.email == DEMO_USER_EMAIL)
        ).first()
        if not existing_user:
            user = User(name=DEMO_USER_NAME, email=DEMO_USER_EMAIL)
            session.add(user)
            session.commit()
            session.refresh(user)
            print(f"Created user: {user.name} (id={user.id})")
        else:
            print(f"User already exists: {existing_user.name} (id={existing_user.id})")

        # Seed calendars (idempotent by name)
        for cal_data in SAMPLE_CALENDARS:
            existing = session.exec(
                select(Calendar).where(Calendar.name == cal_data["name"])
            ).first()
            if not existing:
                calendar = Calendar(**cal_data)
                session.add(calendar)
                print(f"Created calendar: {cal_data['name']}")
            else:
                print(f"Calendar already exists: {cal_data['name']}")

        session.commit()
        print("Seed complete.")


if __name__ == "__main__":
    seed()

"""Import all models so SQLModel.metadata is populated before Alembic runs."""

from app.models.calendar import Calendar  # noqa: F401
from app.models.event import Event  # noqa: F401

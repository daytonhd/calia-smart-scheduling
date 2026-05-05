"""Import all models so SQLModel.metadata is populated before Alembic runs."""

from app.models.availability_window import AvailabilityWindow  # noqa: F401
from app.models.calendar import Calendar  # noqa: F401
from app.models.event import Event  # noqa: F401
from app.models.schedule_summary import ScheduleSummary  # noqa: F401
from app.models.user import User  # noqa: F401

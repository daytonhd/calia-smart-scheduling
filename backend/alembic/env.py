"""Alembic env.py — wired to SQLModel metadata and .env DATABASE_URL."""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

from alembic import context

# ---------- load .env so DATABASE_URL is available ----------
from dotenv import load_dotenv

load_dotenv()  # reads backend/.env when running from backend/

# ---------- import all models so metadata is populated ----------
from app.models import Calendar, Event, ScheduleSummary  # noqa: F401

# ---------- Alembic Config object ----------
config = context.config

# Override sqlalchemy.url from environment variable if set.
# This avoids storing credentials in alembic.ini.
from app.config import DATABASE_URL

config.set_main_option("sqlalchemy.url", DATABASE_URL)

# Logging setup
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# This is the key line: point Alembic at SQLModel's single shared metadata
# so autogenerate can detect table definitions from our models.
target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL without a live DB)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (live DB connection)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

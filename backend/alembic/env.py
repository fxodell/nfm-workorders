"""
Alembic environment configuration for async PostgreSQL migrations.

Supports both ``alembic upgrade head`` (offline SQL generation) and
online migration via an async engine backed by asyncpg.
"""

from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config, create_async_engine

# ---------------------------------------------------------------------------
# Import ALL models so that Base.metadata is fully populated before Alembic
# inspects it for autogenerate.
# ---------------------------------------------------------------------------
import app.models.org          # noqa: F401
import app.models.user         # noqa: F401
import app.models.area         # noqa: F401
import app.models.location     # noqa: F401
import app.models.site         # noqa: F401
import app.models.asset        # noqa: F401
import app.models.work_order   # noqa: F401
import app.models.sla          # noqa: F401
import app.models.part         # noqa: F401
import app.models.pm           # noqa: F401
import app.models.budget       # noqa: F401
import app.models.incentive    # noqa: F401
import app.models.shift        # noqa: F401
import app.models.audit_log    # noqa: F401

from app.core.database import Base

# Alembic Config object — provides access to the .ini file values.
config = context.config

# Set up Python logging from the alembic.ini [loggers] section.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate support.
target_metadata = Base.metadata

# ---------------------------------------------------------------------------
# Database URL resolution
# ---------------------------------------------------------------------------


def _get_database_url() -> str:
    """Return the async database URL.

    Priority:
      1. DATABASE_URL environment variable (must already use the
         ``postgresql+asyncpg://`` scheme).
      2. Constructed from individual DB_* environment variables using the
         asyncpg driver.
      3. Falls back to the value in ``alembic.ini`` (with variable
         interpolation), converted to the asyncpg driver.
    """
    url = os.environ.get("DATABASE_URL")
    if url:
        # Normalise driver to asyncpg if the env var uses a plain postgresql://
        # or psycopg2 scheme.
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        url = url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
        return url

    # Attempt to build from individual env vars.
    db_user = os.environ.get("DB_USER")
    db_pass = os.environ.get("DB_PASS")
    db_host = os.environ.get("DB_HOST")
    db_port = os.environ.get("DB_PORT", "5432")
    db_name = os.environ.get("DB_NAME")

    if all([db_user, db_pass, db_host, db_name]):
        return (
            f"postgresql+asyncpg://{db_user}:{db_pass}"
            f"@{db_host}:{db_port}/{db_name}"
        )

    # Last resort: use whatever is in alembic.ini (with section interpolation).
    ini_url = config.get_main_option("sqlalchemy.url", "")
    if ini_url:
        ini_url = ini_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return ini_url

    raise RuntimeError(
        "No database URL configured.  Set the DATABASE_URL environment "
        "variable or provide DB_USER, DB_PASS, DB_HOST, DB_PORT, and DB_NAME."
    )


# ---------------------------------------------------------------------------
# Offline (SQL script) migrations
# ---------------------------------------------------------------------------


def run_migrations_offline() -> None:
    """Generate SQL scripts without connecting to the database."""
    url = _get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online (async engine) migrations
# ---------------------------------------------------------------------------


def do_run_migrations(connection: Connection) -> None:
    """Run migrations inside a synchronous connection callback."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine, connect, and run migrations."""
    database_url = _get_database_url()

    connectable = create_async_engine(
        database_url,
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations with an online async connection."""
    asyncio.run(run_async_migrations())


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

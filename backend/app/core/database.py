"""
Async SQLAlchemy engine, session factory, and declarative base.

Uses asyncpg as the PostgreSQL driver. Provides:
- ``async_engine``  -- the global async engine
- ``async_session`` -- a sessionmaker that yields ``AsyncSession``
- ``get_db``        -- FastAPI dependency for per-request sessions
- ``Base``          -- declarative base with a UUID primary-key mixin
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

from sqlalchemy import MetaData
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.config import settings

# Naming convention for constraints so Alembic auto-generates sensible names.
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=convention)


class Base(DeclarativeBase):
    """Declarative base used by all ORM models."""

    metadata = metadata


class UUIDPrimaryKeyMixin:
    """Mixin that provides a UUID primary key column named ``id``.

    Include this as the *first* base (before ``Base``) in every model that
    needs a UUID PK::

        class Organization(UUIDPrimaryKeyMixin, Base):
            __tablename__ = "organizations"
            ...
    """

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )


# ── Engine & session factory ────────────────────────────────────────────

_engine_kwargs: dict = {
    "echo": settings.is_development,
}

if settings.DATABASE_URL.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    _engine_kwargs.update(
        pool_size=20,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=3600,
    )

async_engine = create_async_engine(settings.DATABASE_URL, **_engine_kwargs)

async_session = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── FastAPI dependency ──────────────────────────────────────────────────

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session and ensure it is closed afterward."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

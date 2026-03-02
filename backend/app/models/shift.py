"""Shift schedule models."""

from __future__ import annotations

import uuid
from datetime import time
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
    Time,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.area import Area
    from app.models.org import Organization
    from app.models.user import User


class ShiftSchedule(Base):
    __tablename__ = "shift_schedules"
    __table_args__ = (
        Index("ix_shift_schedules_org_id", "org_id"),
        Index("ix_shift_schedules_area_id", "area_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    area_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("areas.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    days_of_week: Mapped[list[int]] = mapped_column(
        JSON, nullable=False
    )
    timezone: Mapped[str] = mapped_column(
        String(50), nullable=False, default="America/Chicago"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    organization: Mapped[Organization] = relationship(
        back_populates="shift_schedules"
    )
    area: Mapped[Area] = relationship(back_populates="shift_schedules")
    user_assignments: Mapped[list[UserShiftAssignment]] = relationship(
        back_populates="shift_schedule", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<ShiftSchedule {self.name!r}>"


class UserShiftAssignment(Base):
    __tablename__ = "user_shift_assignments"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    shift_schedule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shift_schedules.id", ondelete="CASCADE"),
        primary_key=True,
    )

    # Relationships
    user: Mapped[User] = relationship(back_populates="shift_assignments")
    shift_schedule: Mapped[ShiftSchedule] = relationship(
        back_populates="user_assignments"
    )

    def __repr__(self) -> str:
        return (
            f"<UserShiftAssignment user={self.user_id} "
            f"shift={self.shift_schedule_id}>"
        )

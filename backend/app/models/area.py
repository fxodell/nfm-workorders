"""Area model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.budget import AreaBudget
    from app.models.location import Location
    from app.models.org import Organization
    from app.models.shift import ShiftSchedule
    from app.models.user import OnCallSchedule, UserAreaAssignment, UserNotificationPref
    from app.models.work_order import WorkOrder


class Area(Base):
    __tablename__ = "areas"
    __table_args__ = (Index("ix_areas_org_id", "org_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timezone: Mapped[str] = mapped_column(
        String(50), nullable=False, default="America/Chicago"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    # Relationships
    organization: Mapped[Organization] = relationship(back_populates="areas")
    locations: Mapped[list[Location]] = relationship(
        back_populates="area", cascade="all, delete-orphan"
    )
    work_orders: Mapped[list[WorkOrder]] = relationship(
        back_populates="area", cascade="all, delete-orphan"
    )
    user_area_assignments: Mapped[list[UserAreaAssignment]] = relationship(
        back_populates="area", cascade="all, delete-orphan"
    )
    user_notification_prefs: Mapped[list[UserNotificationPref]] = relationship(
        back_populates="area", cascade="all, delete-orphan"
    )
    on_call_schedules: Mapped[list[OnCallSchedule]] = relationship(
        back_populates="area", cascade="all, delete-orphan"
    )
    area_budgets: Mapped[list[AreaBudget]] = relationship(
        back_populates="area", cascade="all, delete-orphan"
    )
    shift_schedules: Mapped[list[ShiftSchedule]] = relationship(
        back_populates="area", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Area {self.name!r}>"

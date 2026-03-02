"""Preventive maintenance models."""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.work_order import WorkOrderPriority

if TYPE_CHECKING:
    from app.models.asset import Asset
    from app.models.org import Organization
    from app.models.site import Site
    from app.models.work_order import WorkOrder


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class RecurrenceType(str, enum.Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    BIWEEKLY = "BIWEEKLY"
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    SEMI_ANNUAL = "SEMI_ANNUAL"
    ANNUAL = "ANNUAL"
    CUSTOM_DAYS = "CUSTOM_DAYS"


class PMAssignedRole(str, enum.Enum):
    TECHNICIAN = "TECHNICIAN"
    OPERATOR = "OPERATOR"
    SUPERVISOR = "SUPERVISOR"


class PMScheduleStatus(str, enum.Enum):
    PENDING = "PENDING"
    GENERATED = "GENERATED"
    SKIPPED = "SKIPPED"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class PMTemplate(Base):
    __tablename__ = "pm_templates"
    __table_args__ = (
        Index("ix_pm_templates_org_id", "org_id"),
        Index("ix_pm_templates_asset_id", "asset_id"),
        Index("ix_pm_templates_site_id", "site_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    asset_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=True,
    )
    site_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PREVENTIVE"
    )
    priority: Mapped[WorkOrderPriority] = mapped_column(
        Enum(
            WorkOrderPriority,
            name="work_order_priority",
            native_enum=False,
            length=10,
            create_constraint=False,
        ),
        nullable=False,
    )
    checklist_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    recurrence_type: Mapped[RecurrenceType] = mapped_column(
        Enum(
            RecurrenceType,
            name="recurrence_type",
            native_enum=False,
            length=15,
        ),
        nullable=False,
    )
    recurrence_interval: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    required_cert: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    assigned_to_role: Mapped[Optional[PMAssignedRole]] = mapped_column(
        Enum(
            PMAssignedRole,
            name="pm_assigned_role",
            native_enum=False,
            length=15,
        ),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    # Relationships
    organization: Mapped[Organization] = relationship(back_populates="pm_templates")
    asset: Mapped[Optional[Asset]] = relationship(back_populates="pm_templates")
    site: Mapped[Optional[Site]] = relationship(back_populates="pm_templates")
    schedules: Mapped[list[PMSchedule]] = relationship(
        back_populates="pm_template", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<PMTemplate {self.title!r}>"


class PMSchedule(Base):
    __tablename__ = "pm_schedules"
    __table_args__ = (
        Index("ix_pm_schedules_pm_template_id", "pm_template_id"),
        Index("ix_pm_schedules_org_id", "org_id"),
        Index("ix_pm_schedules_due_date", "due_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    pm_template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pm_templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    generated_work_order_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("work_orders.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[PMScheduleStatus] = mapped_column(
        Enum(
            PMScheduleStatus,
            name="pm_schedule_status",
            native_enum=False,
            length=12,
        ),
        nullable=False,
        default=PMScheduleStatus.PENDING,
    )
    skip_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    pm_template: Mapped[PMTemplate] = relationship(back_populates="schedules")
    organization: Mapped[Organization] = relationship(back_populates="pm_schedules")
    generated_work_order: Mapped[Optional[WorkOrder]] = relationship(
        back_populates="generated_pm_schedules"
    )

    def __repr__(self) -> str:
        return f"<PMSchedule due={self.due_date} status={self.status.value}>"

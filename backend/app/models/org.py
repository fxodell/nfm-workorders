"""Organization and work-order counter models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.area import Area
    from app.models.asset import Asset
    from app.models.audit_log import AuditLog
    from app.models.budget import AreaBudget
    from app.models.incentive import IncentiveProgram
    from app.models.location import Location
    from app.models.part import Part
    from app.models.pm import PMSchedule, PMTemplate
    from app.models.shift import ShiftSchedule
    from app.models.site import Site
    from app.models.sla import SLAEvent
    from app.models.user import OnCallSchedule, User
    from app.models.work_order import Attachment, LaborLog, TimelineEvent, WorkOrder


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    logo_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    currency_code: Mapped[str] = mapped_column(
        String(3), nullable=False, default="USD"
    )
    config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    # Relationships
    wo_counters: Mapped[list[WOCounter]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    users: Mapped[list[User]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    areas: Mapped[list[Area]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    locations: Mapped[list[Location]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    sites: Mapped[list[Site]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    assets: Mapped[list[Asset]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    work_orders: Mapped[list[WorkOrder]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    timeline_events: Mapped[list[TimelineEvent]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    attachments: Mapped[list[Attachment]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    labor_logs: Mapped[list[LaborLog]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    sla_events: Mapped[list[SLAEvent]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    parts: Mapped[list[Part]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    pm_templates: Mapped[list[PMTemplate]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    pm_schedules: Mapped[list[PMSchedule]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    area_budgets: Mapped[list[AreaBudget]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    incentive_programs: Mapped[list[IncentiveProgram]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    shift_schedules: Mapped[list[ShiftSchedule]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    on_call_schedules: Mapped[list[OnCallSchedule]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[list[AuditLog]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Organization {self.slug!r}>"


class WOCounter(Base):
    """Per-org, per-year work-order counter for human-readable numbering."""

    __tablename__ = "wo_counters"
    __table_args__ = (
        UniqueConstraint("org_id", "year", name="uq_wo_counter_org_year"),
        Index("ix_wo_counters_org_id", "org_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    counter: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Relationships
    organization: Mapped[Organization] = relationship(back_populates="wo_counters")

    def __repr__(self) -> str:
        return f"<WOCounter org={self.org_id} year={self.year} counter={self.counter}>"

"""Work order and related models."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.area import Area
    from app.models.asset import Asset
    from app.models.location import Location
    from app.models.org import Organization
    from app.models.part import Part
    from app.models.pm import PMSchedule
    from app.models.site import Site
    from app.models.sla import SLAEvent
    from app.models.user import User


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class WorkOrderType(str, enum.Enum):
    REACTIVE = "REACTIVE"
    PREVENTIVE = "PREVENTIVE"
    INSPECTION = "INSPECTION"
    CORRECTIVE = "CORRECTIVE"


class WorkOrderPriority(str, enum.Enum):
    IMMEDIATE = "IMMEDIATE"
    URGENT = "URGENT"
    SCHEDULED = "SCHEDULED"
    DEFERRED = "DEFERRED"


class WorkOrderStatus(str, enum.Enum):
    NEW = "NEW"
    ASSIGNED = "ASSIGNED"
    ACCEPTED = "ACCEPTED"
    IN_PROGRESS = "IN_PROGRESS"
    WAITING_ON_OPS = "WAITING_ON_OPS"
    WAITING_ON_PARTS = "WAITING_ON_PARTS"
    RESOLVED = "RESOLVED"
    VERIFIED = "VERIFIED"
    CLOSED = "CLOSED"
    ESCALATED = "ESCALATED"
    CANCELLED = "CANCELLED"


class TimelineEventType(str, enum.Enum):
    STATUS_CHANGE = "STATUS_CHANGE"
    MESSAGE = "MESSAGE"
    ATTACHMENT = "ATTACHMENT"
    PARTS_ADDED = "PARTS_ADDED"
    LABOR_LOGGED = "LABOR_LOGGED"
    NOTE = "NOTE"
    ASSIGNMENT_CHANGE = "ASSIGNMENT_CHANGE"
    SLA_BREACH = "SLA_BREACH"
    ESCALATION = "ESCALATION"
    GPS_SNAPSHOT = "GPS_SNAPSHOT"
    SAFETY_FLAG_SET = "SAFETY_FLAG_SET"
    ESCALATED = "ESCALATED"
    CANCELLED = "CANCELLED"
    ATTACHMENT_ADDED = "ATTACHMENT_ADDED"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class WorkOrder(Base):
    __tablename__ = "work_orders"
    __table_args__ = (
        Index("ix_work_orders_org_id", "org_id"),
        Index("ix_work_orders_area_id", "area_id"),
        Index("ix_work_orders_location_id", "location_id"),
        Index("ix_work_orders_site_id", "site_id"),
        Index("ix_work_orders_asset_id", "asset_id"),
        Index("ix_work_orders_assigned_to", "assigned_to"),
        Index("ix_work_orders_status", "status"),
        Index(
            "ix_work_orders_org_human_readable",
            "org_id",
            "human_readable_number",
            unique=True,
        ),
        Index("ix_work_orders_idempotency_key", "idempotency_key", unique=True),
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
    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="CASCADE"),
        nullable=False,
    )
    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
    )
    asset_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Human-readable identifier (e.g. "WO-2026-00001")
    human_readable_number: Mapped[str] = mapped_column(
        String(30), nullable=False
    )

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    type: Mapped[WorkOrderType] = mapped_column(
        Enum(WorkOrderType, name="work_order_type", native_enum=False, length=20),
        nullable=False,
    )
    priority: Mapped[WorkOrderPriority] = mapped_column(
        Enum(
            WorkOrderPriority,
            name="work_order_priority",
            native_enum=False,
            length=10,
        ),
        nullable=False,
    )
    status: Mapped[WorkOrderStatus] = mapped_column(
        Enum(
            WorkOrderStatus,
            name="work_order_status",
            native_enum=False,
            length=20,
        ),
        nullable=False,
        default=WorkOrderStatus.NEW,
    )

    # People
    requested_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
    )
    assigned_to: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    accepted_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    verified_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    closed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    assigned_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    accepted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    in_progress_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    verified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    escalated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # SLA / scheduling
    ack_deadline: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    first_update_deadline: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    due_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    eta_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Resolution
    resolution_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolution_details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Safety
    safety_flag: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    safety_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    required_cert: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )

    # GPS snapshots (controlled by org config)
    gps_lat_accept: Mapped[Optional[float]] = mapped_column(
        Numeric(precision=10, scale=7), nullable=True
    )
    gps_lng_accept: Mapped[Optional[float]] = mapped_column(
        Numeric(precision=10, scale=7), nullable=True
    )
    gps_lat_start: Mapped[Optional[float]] = mapped_column(
        Numeric(precision=10, scale=7), nullable=True
    )
    gps_lng_start: Mapped[Optional[float]] = mapped_column(
        Numeric(precision=10, scale=7), nullable=True
    )
    gps_lat_resolve: Mapped[Optional[float]] = mapped_column(
        Numeric(precision=10, scale=7), nullable=True
    )
    gps_lng_resolve: Mapped[Optional[float]] = mapped_column(
        Numeric(precision=10, scale=7), nullable=True
    )

    # Extensibility
    tags: Mapped[Optional[list[str]]] = mapped_column(
        JSON, nullable=True
    )
    custom_fields: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(
        String(255), unique=True, nullable=True
    )

    # -----------------------------------------------------------------------
    # Relationships
    # -----------------------------------------------------------------------
    organization: Mapped[Organization] = relationship(back_populates="work_orders")
    area: Mapped[Area] = relationship(back_populates="work_orders")
    location: Mapped[Location] = relationship(back_populates="work_orders")
    site: Mapped[Site] = relationship(back_populates="work_orders")
    asset: Mapped[Optional[Asset]] = relationship(back_populates="work_orders")

    requester: Mapped[User] = relationship(
        back_populates="requested_work_orders",
        foreign_keys=[requested_by],
    )
    assignee: Mapped[Optional[User]] = relationship(
        back_populates="assigned_work_orders",
        foreign_keys=[assigned_to],
    )

    timeline_events: Mapped[list[TimelineEvent]] = relationship(
        back_populates="work_order", cascade="all, delete-orphan"
    )
    attachments: Mapped[list[Attachment]] = relationship(
        back_populates="work_order", cascade="all, delete-orphan"
    )
    parts_used: Mapped[list[WorkOrderPartUsed]] = relationship(
        back_populates="work_order", cascade="all, delete-orphan"
    )
    labor_logs: Mapped[list[LaborLog]] = relationship(
        back_populates="work_order", cascade="all, delete-orphan"
    )
    sla_events: Mapped[list[SLAEvent]] = relationship(
        back_populates="work_order", cascade="all, delete-orphan"
    )
    generated_pm_schedules: Mapped[list[PMSchedule]] = relationship(
        back_populates="generated_work_order",
    )

    def __repr__(self) -> str:
        return f"<WorkOrder {self.human_readable_number!r} [{self.status.value}]>"


class TimelineEvent(Base):
    __tablename__ = "timeline_events"
    __table_args__ = (
        Index("ix_timeline_events_work_order_id", "work_order_id"),
        Index("ix_timeline_events_org_id", "org_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    work_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("work_orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    event_type: Mapped[TimelineEventType] = mapped_column(
        Enum(
            TimelineEventType,
            name="timeline_event_type",
            native_enum=False,
            length=25,
        ),
        nullable=False,
    )
    payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    # Relationships
    work_order: Mapped[WorkOrder] = relationship(back_populates="timeline_events")
    organization: Mapped[Organization] = relationship(
        back_populates="timeline_events"
    )
    user: Mapped[Optional[User]] = relationship(back_populates="timeline_events")

    def __repr__(self) -> str:
        return f"<TimelineEvent {self.event_type.value} on WO {self.work_order_id}>"


class Attachment(Base):
    __tablename__ = "attachments"
    __table_args__ = (
        Index("ix_attachments_work_order_id", "work_order_id"),
        Index("ix_attachments_org_id", "org_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    work_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("work_orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
    )
    s3_key: Mapped[str] = mapped_column(Text, nullable=False)
    s3_bucket: Mapped[str] = mapped_column(String(255), nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    caption: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    # Relationships
    work_order: Mapped[WorkOrder] = relationship(back_populates="attachments")
    organization: Mapped[Organization] = relationship(back_populates="attachments")

    def __repr__(self) -> str:
        return f"<Attachment {self.filename!r}>"


class WorkOrderPartUsed(Base):
    __tablename__ = "work_order_parts_used"
    __table_args__ = (
        Index("ix_work_order_parts_used_work_order_id", "work_order_id"),
        Index("ix_work_order_parts_used_org_id", "org_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    work_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("work_orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    part_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("parts.id", ondelete="SET NULL"),
        nullable=True,
    )
    part_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_cost: Mapped[Optional[float]] = mapped_column(
        Numeric(precision=12, scale=2), nullable=True
    )

    # Relationships
    work_order: Mapped[WorkOrder] = relationship(back_populates="parts_used")
    part: Mapped[Optional[Part]] = relationship(back_populates="work_order_usages")

    def __repr__(self) -> str:
        return f"<WorkOrderPartUsed part={self.part_number} qty={self.quantity}>"


class LaborLog(Base):
    __tablename__ = "labor_logs"
    __table_args__ = (
        Index("ix_labor_logs_work_order_id", "work_order_id"),
        Index("ix_labor_logs_org_id", "org_id"),
        Index("ix_labor_logs_user_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    work_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("work_orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    logged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    # Relationships
    work_order: Mapped[WorkOrder] = relationship(back_populates="labor_logs")
    organization: Mapped[Organization] = relationship(back_populates="labor_logs")
    user: Mapped[User] = relationship(back_populates="labor_logs")

    def __repr__(self) -> str:
        return f"<LaborLog {self.minutes}min by user={self.user_id}>"

"""SLA event models."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.org import Organization
    from app.models.work_order import WorkOrder


class SLAEventType(str, enum.Enum):
    ACK_BREACH = "ACK_BREACH"
    FIRST_UPDATE_BREACH = "FIRST_UPDATE_BREACH"
    RESOLVE_BREACH = "RESOLVE_BREACH"
    MANUAL_ESCALATION = "MANUAL_ESCALATION"
    ACKNOWLEDGED = "ACKNOWLEDGED"


class SLAEvent(Base):
    __tablename__ = "sla_events"
    __table_args__ = (
        Index("ix_sla_events_work_order_id", "work_order_id"),
        Index("ix_sla_events_org_id", "org_id"),
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
    event_type: Mapped[SLAEventType] = mapped_column(
        Enum(SLAEventType, name="sla_event_type", native_enum=False, length=25),
        nullable=False,
    )
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    acknowledged_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    work_order: Mapped[WorkOrder] = relationship(back_populates="sla_events")
    organization: Mapped[Organization] = relationship(back_populates="sla_events")

    def __repr__(self) -> str:
        return f"<SLAEvent {self.event_type.value} on WO {self.work_order_id}>"

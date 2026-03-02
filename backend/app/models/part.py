"""Part and PartTransaction models."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.org import Organization
    from app.models.work_order import WorkOrder, WorkOrderPartUsed


class TransactionType(str, enum.Enum):
    IN = "IN"
    OUT = "OUT"
    ADJUSTMENT = "ADJUSTMENT"


class Part(Base):
    __tablename__ = "parts"
    __table_args__ = (
        UniqueConstraint("org_id", "part_number", name="uq_parts_org_part_number"),
        Index("ix_parts_org_id", "org_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    part_number: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    unit_cost: Mapped[Optional[float]] = mapped_column(
        Numeric(precision=12, scale=2), nullable=True
    )
    barcode_value: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    supplier_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    supplier_part_number: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    stock_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reorder_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    storage_location: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    qr_code_token: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    # Relationships
    organization: Mapped[Organization] = relationship(back_populates="parts")
    transactions: Mapped[list[PartTransaction]] = relationship(
        back_populates="part", cascade="all, delete-orphan"
    )
    work_order_usages: Mapped[list[WorkOrderPartUsed]] = relationship(
        back_populates="part"
    )

    def __repr__(self) -> str:
        return f"<Part {self.part_number!r}>"


class PartTransaction(Base):
    __tablename__ = "part_transactions"
    __table_args__ = (
        Index("ix_part_transactions_part_id", "part_id"),
        Index("ix_part_transactions_org_id", "org_id"),
        Index("ix_part_transactions_work_order_id", "work_order_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    part_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("parts.id", ondelete="CASCADE"),
        nullable=False,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    work_order_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("work_orders.id", ondelete="SET NULL"),
        nullable=True,
    )
    transaction_type: Mapped[TransactionType] = mapped_column(
        Enum(
            TransactionType,
            name="transaction_type",
            native_enum=False,
            length=15,
        ),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    # Relationships
    part: Mapped[Part] = relationship(back_populates="transactions")
    organization: Mapped[Organization] = relationship()
    work_order: Mapped[Optional[WorkOrder]] = relationship()

    def __repr__(self) -> str:
        return (
            f"<PartTransaction {self.transaction_type.value} "
            f"qty={self.quantity} part={self.part_id}>"
        )

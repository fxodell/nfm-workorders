"""Incentive program models."""

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
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.org import Organization
    from app.models.user import User


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class IncentiveMetric(str, enum.Enum):
    MTTR = "MTTR"
    FIRST_TIME_FIX = "FIRST_TIME_FIX"
    SLA_COMPLIANCE = "SLA_COMPLIANCE"
    WO_COMPLETION_RATE = "WO_COMPLETION_RATE"
    SAFETY_SCORE = "SAFETY_SCORE"
    CUSTOMER_SATISFACTION = "CUSTOMER_SATISFACTION"


class IncentivePeriodType(str, enum.Enum):
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    ANNUAL = "ANNUAL"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class IncentiveProgram(Base):
    __tablename__ = "incentive_programs"
    __table_args__ = (Index("ix_incentive_programs_org_id", "org_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    metric: Mapped[IncentiveMetric] = mapped_column(
        Enum(
            IncentiveMetric,
            name="incentive_metric",
            native_enum=False,
            length=25,
        ),
        nullable=False,
    )
    target_value: Mapped[float] = mapped_column(
        Numeric(precision=12, scale=4), nullable=False
    )
    bonus_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    period_type: Mapped[IncentivePeriodType] = mapped_column(
        Enum(
            IncentivePeriodType,
            name="incentive_period_type",
            native_enum=False,
            length=12,
        ),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    organization: Mapped[Organization] = relationship(
        back_populates="incentive_programs"
    )
    scores: Mapped[list[UserIncentiveScore]] = relationship(
        back_populates="program", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<IncentiveProgram {self.name!r}>"


class UserIncentiveScore(Base):
    __tablename__ = "user_incentive_scores"
    __table_args__ = (
        Index("ix_user_incentive_scores_user_id", "user_id"),
        Index("ix_user_incentive_scores_program_id", "program_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    program_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incentive_programs.id", ondelete="CASCADE"),
        nullable=False,
    )
    period_label: Mapped[str] = mapped_column(String(50), nullable=False)
    score: Mapped[float] = mapped_column(
        Numeric(precision=12, scale=4), nullable=False
    )
    achieved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    # Relationships
    user: Mapped[User] = relationship(back_populates="incentive_scores")
    program: Mapped[IncentiveProgram] = relationship(back_populates="scores")

    def __repr__(self) -> str:
        return (
            f"<UserIncentiveScore user={self.user_id} "
            f"period={self.period_label} score={self.score}>"
        )

"""Budget models."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    ForeignKey,
    Index,
    Integer,
    Numeric,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.area import Area
    from app.models.org import Organization


class AreaBudget(Base):
    __tablename__ = "area_budgets"
    __table_args__ = (
        UniqueConstraint(
            "org_id", "area_id", "year", "month",
            name="uq_area_budget_org_area_year_month",
        ),
        Index("ix_area_budgets_org_id", "org_id"),
        Index("ix_area_budgets_area_id", "area_id"),
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
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    budget_amount: Mapped[float] = mapped_column(
        Numeric(precision=14, scale=2), nullable=False, default=0
    )
    actual_spend: Mapped[float] = mapped_column(
        Numeric(precision=14, scale=2), nullable=False, default=0
    )

    # Relationships
    organization: Mapped[Organization] = relationship(back_populates="area_budgets")
    area: Mapped[Area] = relationship(back_populates="area_budgets")

    def __repr__(self) -> str:
        return (
            f"<AreaBudget area={self.area_id} "
            f"{self.year}-{self.month:02d} "
            f"budget={self.budget_amount} actual={self.actual_spend}>"
        )

"""Budget schemas."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AreaBudgetCreate(BaseModel):
    """Set or update a monthly budget for an area."""

    area_id: UUID
    year: int = Field(..., ge=2000, le=2100)
    month: int = Field(..., ge=1, le=12)
    budget_amount: float = Field(..., ge=0)


class AreaBudgetResponse(BaseModel):
    """Read-only area budget record."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    org_id: UUID
    area_id: UUID
    year: int
    month: int
    budget_amount: float
    actual_spend: float = 0.0


class AreaBudgetSummaryItem(BaseModel):
    """Budget vs. actual for a single area."""

    model_config = ConfigDict(from_attributes=True)

    area_id: UUID
    area_name: Optional[str] = None
    budget_amount: float
    actual_spend: float


class BudgetSummaryResponse(BaseModel):
    """Aggregated budget overview across all areas."""

    model_config = ConfigDict(from_attributes=True)

    total_budget: float
    total_spend: float
    by_area: list[AreaBudgetSummaryItem]

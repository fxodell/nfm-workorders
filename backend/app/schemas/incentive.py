"""Incentive-program schemas."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class IncentiveMetric(str, enum.Enum):
    """Metric used to evaluate incentive program performance."""

    WO_CLOSED_COUNT = "WO_CLOSED_COUNT"
    AVG_RESOLUTION_MINUTES = "AVG_RESOLUTION_MINUTES"
    SLA_COMPLIANCE_PCT = "SLA_COMPLIANCE_PCT"
    FIRST_TIME_FIX_PCT = "FIRST_TIME_FIX_PCT"
    SAFETY_INCIDENT_COUNT = "SAFETY_INCIDENT_COUNT"
    CUSTOMER_RATING_AVG = "CUSTOMER_RATING_AVG"


class IncentivePeriodType(str, enum.Enum):
    """Time period over which incentive metrics are measured."""

    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    ANNUAL = "ANNUAL"


# ---------------------------------------------------------------------------
# Incentive Program CRUD
# ---------------------------------------------------------------------------

class IncentiveProgramCreate(BaseModel):
    """Payload for creating a new incentive program."""

    name: str = Field(..., min_length=1, max_length=255)
    metric: IncentiveMetric
    target_value: float = Field(..., gt=0)
    bonus_description: Optional[str] = Field(default=None, max_length=500)
    period_type: IncentivePeriodType

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("bonus_description", mode="before")
    @classmethod
    def strip_bonus_description(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v


class IncentiveProgramUpdate(BaseModel):
    """Fields that may be updated on an incentive program.  All optional."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    metric: Optional[IncentiveMetric] = None
    target_value: Optional[float] = Field(default=None, gt=0)
    bonus_description: Optional[str] = Field(default=None, max_length=500)
    period_type: Optional[IncentivePeriodType] = None
    is_active: Optional[bool] = None

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v

    @field_validator("bonus_description", mode="before")
    @classmethod
    def strip_bonus_description(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v


class IncentiveProgramResponse(BaseModel):
    """Read-only incentive program representation."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    org_id: UUID
    name: str
    metric: IncentiveMetric
    target_value: float
    bonus_description: Optional[str] = None
    period_type: IncentivePeriodType
    is_active: bool = True
    created_at: datetime
    updated_at: Optional[datetime] = None


class UserIncentiveScoreResponse(BaseModel):
    """A user's current score against an incentive program."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    incentive_program_id: UUID
    user_id: UUID
    org_id: UUID
    period_start: datetime
    period_end: datetime
    current_value: float
    target_value: float
    achieved: bool = False
    created_at: datetime
    updated_at: Optional[datetime] = None

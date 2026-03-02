"""Preventive-maintenance template and schedule schemas."""

from __future__ import annotations

import enum
from datetime import date, datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.work_order import WOPriority


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class RecurrenceType(str, enum.Enum):
    """How a PM template recurs."""

    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    BIWEEKLY = "BIWEEKLY"
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    SEMIANNUAL = "SEMIANNUAL"
    ANNUAL = "ANNUAL"
    CUSTOM_DAYS = "CUSTOM_DAYS"


class PMScheduleStatus(str, enum.Enum):
    """Lifecycle status of a single PM schedule instance."""

    PENDING = "PENDING"
    GENERATED = "GENERATED"
    SKIPPED = "SKIPPED"
    OVERDUE = "OVERDUE"


# ---------------------------------------------------------------------------
# PM Template CRUD
# ---------------------------------------------------------------------------

class PMTemplateCreate(BaseModel):
    """Payload for creating a new preventive-maintenance template."""

    asset_id: Optional[UUID] = None
    site_id: Optional[UUID] = None
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    priority: WOPriority = WOPriority.SCHEDULED
    checklist_json: Optional[list[dict[str, Any]]] = None
    recurrence_type: RecurrenceType
    recurrence_interval: int = Field(default=1, gt=0)
    required_cert: Optional[str] = Field(default=None, max_length=255)
    assigned_to_role: Optional[str] = Field(default=None, max_length=50)

    @field_validator("title", mode="before")
    @classmethod
    def strip_title(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("description", mode="before")
    @classmethod
    def strip_description(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v

    @field_validator("required_cert", mode="before")
    @classmethod
    def strip_required_cert(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v

    @field_validator("assigned_to_role", mode="before")
    @classmethod
    def strip_assigned_to_role(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v


class PMTemplateUpdate(BaseModel):
    """Fields that may be updated on a PM template.  All optional."""

    asset_id: Optional[UUID] = None
    site_id: Optional[UUID] = None
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    priority: Optional[WOPriority] = None
    checklist_json: Optional[list[dict[str, Any]]] = None
    recurrence_type: Optional[RecurrenceType] = None
    recurrence_interval: Optional[int] = Field(default=None, gt=0)
    required_cert: Optional[str] = Field(default=None, max_length=255)
    assigned_to_role: Optional[str] = Field(default=None, max_length=50)
    is_active: Optional[bool] = None

    @field_validator("title", mode="before")
    @classmethod
    def strip_title(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v

    @field_validator("description", mode="before")
    @classmethod
    def strip_description(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v

    @field_validator("required_cert", mode="before")
    @classmethod
    def strip_required_cert(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v

    @field_validator("assigned_to_role", mode="before")
    @classmethod
    def strip_assigned_to_role(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v


class PMTemplateResponse(BaseModel):
    """Read-only PM template representation."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    org_id: UUID
    asset_id: Optional[UUID] = None
    site_id: Optional[UUID] = None
    title: str
    description: Optional[str] = None
    priority: WOPriority
    checklist_json: Optional[list[dict[str, Any]]] = None
    recurrence_type: RecurrenceType
    recurrence_interval: int
    required_cert: Optional[str] = None
    assigned_to_role: Optional[str] = None
    is_active: bool = True
    created_at: datetime
    updated_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# PM Schedule
# ---------------------------------------------------------------------------

class PMScheduleResponse(BaseModel):
    """Read-only PM schedule instance."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    pm_template_id: UUID
    org_id: UUID
    due_date: date
    generated_work_order_id: Optional[UUID] = None
    status: PMScheduleStatus
    skip_reason: Optional[str] = None


class PMScheduleSkip(BaseModel):
    """Skip a pending PM schedule instance."""

    skip_reason: str = Field(..., min_length=1, max_length=1000)

    @field_validator("skip_reason", mode="before")
    @classmethod
    def strip_skip_reason(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v

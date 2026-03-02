"""Work-order schemas including timeline, attachments, parts, labor, and messages."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class WOType(str, enum.Enum):
    """Work order type."""

    REACTIVE = "REACTIVE"
    PREVENTIVE = "PREVENTIVE"
    INSPECTION = "INSPECTION"
    CORRECTIVE = "CORRECTIVE"


class WOPriority(str, enum.Enum):
    """Work order priority level."""

    IMMEDIATE = "IMMEDIATE"
    URGENT = "URGENT"
    SCHEDULED = "SCHEDULED"
    DEFERRED = "DEFERRED"


class WOStatus(str, enum.Enum):
    """Work order lifecycle status."""

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


class TimelineEventType(str, enum.Enum):
    """Types of events that appear on the work-order timeline."""

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


# ---------------------------------------------------------------------------
# Work-order CRUD
# ---------------------------------------------------------------------------

class WorkOrderCreate(BaseModel):
    """Payload for creating a new work order."""

    area_id: UUID
    site_id: UUID
    asset_id: Optional[UUID] = None
    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=20)
    type: WOType
    priority: WOPriority
    safety_flag: bool = False
    safety_notes: Optional[str] = None
    required_cert: Optional[str] = Field(default=None, max_length=255)
    tags: list[str] = Field(default_factory=list)
    custom_fields: Optional[dict[str, Any]] = None

    @field_validator("title", mode="before")
    @classmethod
    def strip_title(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("description", mode="before")
    @classmethod
    def strip_description(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("safety_notes", mode="before")
    @classmethod
    def strip_safety_notes(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v

    @field_validator("required_cert", mode="before")
    @classmethod
    def strip_required_cert(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v

    @field_validator("tags", mode="before")
    @classmethod
    def strip_tags(cls, v: list[str]) -> list[str]:
        if isinstance(v, list):
            return [t.strip() for t in v if isinstance(t, str) and t.strip()]
        return v

    @model_validator(mode="after")
    def safety_notes_required_when_flagged(self) -> WorkOrderCreate:
        if self.safety_flag and not self.safety_notes:
            raise ValueError(
                "safety_notes is required when safety_flag is True"
            )
        return self


class WorkOrderUpdate(BaseModel):
    """Fields that may be updated on an existing work order."""

    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, min_length=20)
    priority: Optional[WOPriority] = None
    safety_flag: Optional[bool] = None
    safety_notes: Optional[str] = None
    required_cert: Optional[str] = None
    tags: Optional[list[str]] = None
    custom_fields: Optional[dict[str, Any]] = None

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

    @field_validator("tags", mode="before")
    @classmethod
    def strip_tags(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        if isinstance(v, list):
            return [t.strip() for t in v if isinstance(t, str) and t.strip()]
        return v


class WorkOrderResponse(BaseModel):
    """Complete read-only work order representation."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    org_id: UUID
    area_id: UUID
    location_id: Optional[UUID] = None
    site_id: UUID
    asset_id: Optional[UUID] = None
    human_readable_number: Optional[str] = None

    title: str
    description: str
    type: WOType
    priority: WOPriority
    status: WOStatus

    safety_flag: bool = False
    safety_notes: Optional[str] = None
    required_cert: Optional[str] = None
    tags: Optional[list[str]] = None
    custom_fields: Optional[dict[str, Any]] = None

    requested_by: Optional[UUID] = None
    assigned_to: Optional[UUID] = None
    accepted_by: Optional[UUID] = None
    verified_by: Optional[UUID] = None
    closed_by: Optional[UUID] = None

    # Resolved names for convenience
    area_name: Optional[str] = None
    site_name: Optional[str] = None
    asset_name: Optional[str] = None
    assigned_to_name: Optional[str] = None
    created_by_name: Optional[str] = None

    eta_minutes: Optional[int] = None
    resolution_summary: Optional[str] = None
    resolution_details: Optional[str] = None

    sla_response_due_at: Optional[datetime] = None
    sla_resolve_due_at: Optional[datetime] = None
    sla_response_breached: bool = False
    sla_resolve_breached: bool = False

    escalated: bool = False
    escalated_at: Optional[datetime] = None
    escalation_reason: Optional[str] = None

    accepted_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    reopened_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class WorkOrderListResponse(BaseModel):
    """Paginated list of work orders."""

    model_config = ConfigDict(from_attributes=True)

    items: list[WorkOrderResponse]
    total: int
    page: int
    per_page: int


# ---------------------------------------------------------------------------
# State-transition actions
# ---------------------------------------------------------------------------

class WorkOrderAssign(BaseModel):
    """Assign a work order to a technician."""

    assigned_to: UUID


class WorkOrderAccept(BaseModel):
    """Accept an assigned work order. ETA is required for IMMEDIATE/URGENT."""

    eta_minutes: Optional[int] = Field(default=None, gt=0)


class WorkOrderResolve(BaseModel):
    """Mark a work order as resolved."""

    resolution_summary: str = Field(..., min_length=1, max_length=1000)
    resolution_details: Optional[str] = None

    @field_validator("resolution_summary", mode="before")
    @classmethod
    def strip_resolution_summary(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("resolution_details", mode="before")
    @classmethod
    def strip_resolution_details(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v


class WorkOrderReopen(BaseModel):
    """Reopen a resolved or closed work order."""

    reason: str = Field(..., min_length=1, max_length=1000)

    @field_validator("reason", mode="before")
    @classmethod
    def strip_reason(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v


class WorkOrderEscalate(BaseModel):
    """Escalate a work order."""

    reason: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("reason", mode="before")
    @classmethod
    def strip_reason(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v


# ---------------------------------------------------------------------------
# Timeline events
# ---------------------------------------------------------------------------

class TimelineEventCreate(BaseModel):
    """Add a manual note or message to the work-order timeline."""

    event_type: TimelineEventType = Field(
        ..., description="Must be NOTE or MESSAGE for manual entries"
    )
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("event_type")
    @classmethod
    def restrict_manual_event_types(cls, v: TimelineEventType) -> TimelineEventType:
        allowed = {TimelineEventType.NOTE, TimelineEventType.MESSAGE}
        if v not in allowed:
            raise ValueError(
                f"Only {', '.join(a.value for a in allowed)} event types "
                "can be created manually"
            )
        return v


class TimelineEventResponse(BaseModel):
    """Read-only timeline event."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    work_order_id: UUID
    user_id: Optional[UUID] = None
    event_type: TimelineEventType
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


# ---------------------------------------------------------------------------
# Attachments
# ---------------------------------------------------------------------------

class AttachmentResponse(BaseModel):
    """Read-only attachment metadata (file stored in S3)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    work_order_id: UUID
    uploaded_by: Optional[UUID] = None
    filename: str
    mime_type: str
    size_bytes: int
    caption: Optional[str] = None
    created_at: datetime
    download_url: Optional[str] = None


# ---------------------------------------------------------------------------
# Work-order parts
# ---------------------------------------------------------------------------

class WorkOrderPartCreate(BaseModel):
    """Record a part used on a work order."""

    part_id: Optional[UUID] = None
    part_number: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    quantity: int = Field(..., gt=0)
    unit_cost: Optional[float] = Field(default=None, ge=0)

    @field_validator("part_number", mode="before")
    @classmethod
    def strip_part_number(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("description", mode="before")
    @classmethod
    def strip_description(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v


class WorkOrderPartResponse(BaseModel):
    """Read-only part usage record on a work order."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    work_order_id: UUID
    part_id: Optional[UUID] = None
    part_number: str
    description: Optional[str] = None
    quantity: int
    unit_cost: Optional[float] = None


# ---------------------------------------------------------------------------
# Labor logs
# ---------------------------------------------------------------------------

class LaborLogCreate(BaseModel):
    """Log labor time against a work order."""

    minutes: int = Field(..., gt=0)
    notes: Optional[str] = None

    @field_validator("notes", mode="before")
    @classmethod
    def strip_notes(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v


class LaborLogResponse(BaseModel):
    """Read-only labor log entry."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    work_order_id: UUID
    user_id: UUID
    minutes: int
    notes: Optional[str] = None
    logged_at: datetime


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

class MessageCreate(BaseModel):
    """Send a message on a work-order thread."""

    content: str = Field(..., min_length=1)

    @field_validator("content", mode="before")
    @classmethod
    def strip_content(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v


class MessageResponse(BaseModel):
    """Read-only message in a work-order thread."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    work_order_id: UUID
    user_id: UUID
    sender_name: Optional[str] = None
    content: str
    created_at: datetime

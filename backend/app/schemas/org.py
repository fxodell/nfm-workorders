"""Organization schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Org config sub-schema (JSONB blob stored on Organization.config)
# ---------------------------------------------------------------------------

class SLAConfig(BaseModel):
    """SLA thresholds in minutes, keyed by priority."""

    immediate_response_min: int = Field(default=30, ge=0)
    immediate_resolve_min: int = Field(default=240, ge=0)
    urgent_response_min: int = Field(default=120, ge=0)
    urgent_resolve_min: int = Field(default=480, ge=0)
    standard_response_min: int = Field(default=480, ge=0)
    standard_resolve_min: int = Field(default=2880, ge=0)
    low_response_min: int = Field(default=1440, ge=0)
    low_resolve_min: int = Field(default=10080, ge=0)


class OrgConfigUpdate(BaseModel):
    """Full organization configuration stored as JSONB.

    Every field is optional so callers can do partial patches.
    """

    sla: Optional[SLAConfig] = None
    escalation_enabled: Optional[bool] = None
    closed_wo_cache_days: Optional[int] = Field(default=None, ge=0)
    gps_clock_in_required: Optional[bool] = None
    gps_clock_in_radius_meters: Optional[int] = Field(default=None, ge=0)
    timezone: Optional[str] = Field(default=None, max_length=50)
    mfa_required_roles: Optional[list[str]] = None
    default_labor_rate_per_hour: Optional[float] = Field(default=None, ge=0)

    @field_validator("timezone", mode="before")
    @classmethod
    def strip_timezone(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v


# ---------------------------------------------------------------------------
# Org CRUD
# ---------------------------------------------------------------------------

class OrgResponse(BaseModel):
    """Read-only organization representation."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    logo_url: Optional[str] = None
    currency_code: str = "USD"
    config: Optional[dict[str, Any]] = None
    created_at: datetime


class OrgUpdate(BaseModel):
    """Fields that may be updated on an organization."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    logo_url: Optional[str] = None
    currency_code: Optional[str] = Field(
        default=None, min_length=3, max_length=3
    )

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v

    @field_validator("logo_url", mode="before")
    @classmethod
    def strip_logo_url(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v

    @field_validator("currency_code", mode="before")
    @classmethod
    def strip_and_upper_currency(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            v = v.strip().upper()
            return v or None
        return v

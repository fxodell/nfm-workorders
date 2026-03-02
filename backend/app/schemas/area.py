"""Area schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AreaCreate(BaseModel):
    """Payload for creating a new area."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    timezone: str = Field(default="America/Chicago", max_length=50)

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("description", mode="before")
    @classmethod
    def strip_description(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v

    @field_validator("timezone", mode="before")
    @classmethod
    def strip_timezone(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v


class AreaUpdate(BaseModel):
    """Fields that may be updated on an area."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    timezone: Optional[str] = Field(default=None, max_length=50)
    is_active: Optional[bool] = None

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v

    @field_validator("description", mode="before")
    @classmethod
    def strip_description(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v

    @field_validator("timezone", mode="before")
    @classmethod
    def strip_timezone(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v


class AreaResponse(BaseModel):
    """Read-only area representation."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    org_id: UUID
    name: str
    description: Optional[str] = None
    timezone: str
    is_active: bool
    created_at: datetime

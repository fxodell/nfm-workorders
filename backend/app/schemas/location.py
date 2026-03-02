"""Location schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LocationCreate(BaseModel):
    """Payload for creating a new location."""

    area_id: UUID
    name: str = Field(..., min_length=1, max_length=255)
    address: Optional[str] = Field(default=None, max_length=500)
    gps_lat: Optional[float] = Field(default=None, ge=-90, le=90)
    gps_lng: Optional[float] = Field(default=None, ge=-180, le=180)

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("address", mode="before")
    @classmethod
    def strip_address(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v


class LocationUpdate(BaseModel):
    """Fields that may be updated on a location."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    address: Optional[str] = Field(default=None, max_length=500)
    gps_lat: Optional[float] = Field(default=None, ge=-90, le=90)
    gps_lng: Optional[float] = Field(default=None, ge=-180, le=180)
    is_active: Optional[bool] = None

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v

    @field_validator("address", mode="before")
    @classmethod
    def strip_address(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v


class LocationResponse(BaseModel):
    """Read-only location representation."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    org_id: UUID
    area_id: UUID
    name: str
    address: Optional[str] = None
    gps_lat: Optional[float] = None
    gps_lng: Optional[float] = None
    qr_code_token: UUID
    is_active: bool
    created_at: datetime

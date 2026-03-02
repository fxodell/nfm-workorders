"""Site schemas."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SiteType(str, enum.Enum):
    """Mirrors the SiteType enum defined in models.site."""

    WELL_SITE = "WELL_SITE"
    PLANT = "PLANT"
    BUILDING = "BUILDING"
    APARTMENT = "APARTMENT"
    LINE = "LINE"
    SUITE = "SUITE"
    COMPRESSOR_STATION = "COMPRESSOR_STATION"
    TANK_BATTERY = "TANK_BATTERY"
    SEPARATOR = "SEPARATOR"
    OTHER = "OTHER"


class SiteCreate(BaseModel):
    """Payload for creating a new site."""

    location_id: UUID
    name: str = Field(..., min_length=1, max_length=255)
    type: SiteType
    address: Optional[str] = Field(default=None, max_length=500)
    gps_lat: Optional[float] = Field(default=None, ge=-90, le=90)
    gps_lng: Optional[float] = Field(default=None, ge=-180, le=180)
    site_timezone: str = Field(default="America/Chicago", max_length=50)

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

    @field_validator("site_timezone", mode="before")
    @classmethod
    def strip_timezone(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v


class SiteUpdate(BaseModel):
    """Fields that may be updated on a site."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    type: Optional[SiteType] = None
    address: Optional[str] = Field(default=None, max_length=500)
    gps_lat: Optional[float] = Field(default=None, ge=-90, le=90)
    gps_lng: Optional[float] = Field(default=None, ge=-180, le=180)
    site_timezone: Optional[str] = Field(default=None, max_length=50)
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

    @field_validator("site_timezone", mode="before")
    @classmethod
    def strip_timezone(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v


class SiteResponse(BaseModel):
    """Read-only site representation."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    org_id: UUID
    location_id: UUID
    name: str
    type: SiteType
    address: Optional[str] = None
    gps_lat: Optional[float] = None
    gps_lng: Optional[float] = None
    site_timezone: str
    qr_code_token: UUID
    is_active: bool
    created_at: datetime

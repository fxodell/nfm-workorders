"""Asset schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AssetCreate(BaseModel):
    """Payload for creating a new asset."""

    site_id: UUID
    name: str = Field(..., min_length=1, max_length=255)
    asset_type: Optional[str] = Field(default=None, max_length=100)
    manufacturer: Optional[str] = Field(default=None, max_length=255)
    model: Optional[str] = Field(default=None, max_length=255)
    serial_number: Optional[str] = Field(default=None, max_length=255)
    install_date: Optional[date] = None
    warranty_expiry: Optional[date] = None
    notes: Optional[str] = None

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("asset_type", mode="before")
    @classmethod
    def strip_asset_type(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v

    @field_validator("manufacturer", mode="before")
    @classmethod
    def strip_manufacturer(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v

    @field_validator("model", mode="before")
    @classmethod
    def strip_model(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v

    @field_validator("serial_number", mode="before")
    @classmethod
    def strip_serial_number(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v

    @field_validator("notes", mode="before")
    @classmethod
    def strip_notes(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v


class AssetUpdate(BaseModel):
    """Fields that may be updated on an asset.  All optional."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    asset_type: Optional[str] = Field(default=None, max_length=100)
    manufacturer: Optional[str] = Field(default=None, max_length=255)
    model: Optional[str] = Field(default=None, max_length=255)
    serial_number: Optional[str] = Field(default=None, max_length=255)
    install_date: Optional[date] = None
    warranty_expiry: Optional[date] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v

    @field_validator("asset_type", mode="before")
    @classmethod
    def strip_asset_type(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v

    @field_validator("manufacturer", mode="before")
    @classmethod
    def strip_manufacturer(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v

    @field_validator("model", mode="before")
    @classmethod
    def strip_model(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v

    @field_validator("serial_number", mode="before")
    @classmethod
    def strip_serial_number(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v

    @field_validator("notes", mode="before")
    @classmethod
    def strip_notes(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v


class AssetResponse(BaseModel):
    """Read-only asset representation."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    org_id: UUID
    site_id: UUID
    name: str
    asset_type: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    install_date: Optional[date] = None
    warranty_expiry: Optional[date] = None
    qr_code_token: UUID
    notes: Optional[str] = None
    is_active: bool
    created_at: datetime

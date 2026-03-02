"""Part and part-transaction schemas."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class PartTransactionType(str, enum.Enum):
    """Direction of a part inventory transaction."""

    RECEIPT = "RECEIPT"
    ISSUE = "ISSUE"
    ADJUSTMENT = "ADJUSTMENT"
    RETURN = "RETURN"
    SCRAP = "SCRAP"


# ---------------------------------------------------------------------------
# Part CRUD
# ---------------------------------------------------------------------------

class PartCreate(BaseModel):
    """Payload for creating a new part in the inventory."""

    part_number: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    unit_cost: Optional[float] = Field(default=None, ge=0)
    barcode_value: Optional[str] = Field(default=None, max_length=255)
    supplier_name: Optional[str] = Field(default=None, max_length=255)
    supplier_part_number: Optional[str] = Field(default=None, max_length=100)
    stock_quantity: int = Field(default=0, ge=0)
    reorder_threshold: Optional[int] = Field(default=None, ge=0)
    storage_location: Optional[str] = Field(default=None, max_length=255)

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

    @field_validator("barcode_value", mode="before")
    @classmethod
    def strip_barcode_value(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v

    @field_validator("supplier_name", mode="before")
    @classmethod
    def strip_supplier_name(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v

    @field_validator("supplier_part_number", mode="before")
    @classmethod
    def strip_supplier_part_number(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v

    @field_validator("storage_location", mode="before")
    @classmethod
    def strip_storage_location(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v


class PartUpdate(BaseModel):
    """Fields that may be updated on a part.  All optional."""

    part_number: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    unit_cost: Optional[float] = Field(default=None, ge=0)
    barcode_value: Optional[str] = Field(default=None, max_length=255)
    supplier_name: Optional[str] = Field(default=None, max_length=255)
    supplier_part_number: Optional[str] = Field(default=None, max_length=100)
    stock_quantity: Optional[int] = Field(default=None, ge=0)
    reorder_threshold: Optional[int] = Field(default=None, ge=0)
    storage_location: Optional[str] = Field(default=None, max_length=255)
    is_active: Optional[bool] = None

    @field_validator("part_number", mode="before")
    @classmethod
    def strip_part_number(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v

    @field_validator("description", mode="before")
    @classmethod
    def strip_description(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v

    @field_validator("barcode_value", mode="before")
    @classmethod
    def strip_barcode_value(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v

    @field_validator("supplier_name", mode="before")
    @classmethod
    def strip_supplier_name(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v

    @field_validator("supplier_part_number", mode="before")
    @classmethod
    def strip_supplier_part_number(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v

    @field_validator("storage_location", mode="before")
    @classmethod
    def strip_storage_location(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v


class PartResponse(BaseModel):
    """Read-only part representation."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    org_id: UUID
    part_number: str
    description: Optional[str] = None
    unit_cost: Optional[float] = None
    barcode_value: Optional[str] = None
    supplier_name: Optional[str] = None
    supplier_part_number: Optional[str] = None
    stock_quantity: int = 0
    reorder_threshold: Optional[int] = None
    storage_location: Optional[str] = None
    qr_code_token: UUID
    is_active: bool
    created_at: datetime


# ---------------------------------------------------------------------------
# Part transactions (inventory movements)
# ---------------------------------------------------------------------------

class PartTransactionCreate(BaseModel):
    """Record an inventory movement for a part."""

    transaction_type: PartTransactionType
    quantity: int = Field(..., gt=0)
    work_order_id: Optional[UUID] = None
    notes: Optional[str] = None

    @field_validator("notes", mode="before")
    @classmethod
    def strip_notes(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v


class PartTransactionResponse(BaseModel):
    """Read-only part transaction record."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    part_id: UUID
    org_id: UUID
    work_order_id: Optional[UUID] = None
    transaction_type: PartTransactionType
    quantity: int
    notes: Optional[str] = None
    created_by: Optional[UUID] = None
    created_at: datetime

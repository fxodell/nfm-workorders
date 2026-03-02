"""Shift-schedule schemas."""

from __future__ import annotations

from datetime import datetime, time
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ShiftScheduleCreate(BaseModel):
    """Payload for creating a new shift schedule."""

    area_id: UUID
    name: str = Field(..., min_length=1, max_length=255)
    start_time: time
    end_time: time
    days_of_week: list[int] = Field(
        ...,
        min_length=1,
        max_length=7,
        description="ISO weekday numbers: 1=Monday ... 7=Sunday",
    )
    timezone: str = Field(default="America/Chicago", max_length=50)

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("timezone", mode="before")
    @classmethod
    def strip_timezone(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("days_of_week")
    @classmethod
    def validate_days(cls, v: list[int]) -> list[int]:
        for day in v:
            if day < 1 or day > 7:
                raise ValueError(
                    f"Invalid day {day}; must be 1 (Monday) through 7 (Sunday)"
                )
        if len(set(v)) != len(v):
            raise ValueError("Duplicate days are not allowed")
        return sorted(v)


class ShiftScheduleUpdate(BaseModel):
    """Fields that may be updated on a shift schedule.  All optional."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    days_of_week: Optional[list[int]] = Field(
        default=None,
        min_length=1,
        max_length=7,
    )
    timezone: Optional[str] = Field(default=None, max_length=50)
    is_active: Optional[bool] = None

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v

    @field_validator("timezone", mode="before")
    @classmethod
    def strip_timezone(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v

    @field_validator("days_of_week")
    @classmethod
    def validate_days(cls, v: Optional[list[int]]) -> Optional[list[int]]:
        if v is None:
            return v
        for day in v:
            if day < 1 or day > 7:
                raise ValueError(
                    f"Invalid day {day}; must be 1 (Monday) through 7 (Sunday)"
                )
        if len(set(v)) != len(v):
            raise ValueError("Duplicate days are not allowed")
        return sorted(v)


class ShiftScheduleResponse(BaseModel):
    """Read-only shift schedule representation."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    org_id: UUID
    area_id: UUID
    name: str
    start_time: time
    end_time: time
    days_of_week: list[int]
    timezone: str
    is_active: bool = True
    created_at: datetime
    updated_at: Optional[datetime] = None


class ShiftUserAssignment(BaseModel):
    """Assign a set of users to a shift schedule."""

    user_ids: list[UUID] = Field(..., min_length=0)

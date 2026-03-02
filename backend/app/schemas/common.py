"""Common schemas shared across modules."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PaginationParams(BaseModel):
    """Query parameters for paginated list endpoints."""

    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    per_page: int = Field(
        default=20, ge=1, le=100, description="Items per page (max 100)"
    )


class SortParams(BaseModel):
    """Query parameters for sorting list endpoints."""

    sort_by: str = Field(default="created_at", description="Column to sort by")
    sort_order: str = Field(
        default="desc",
        pattern=r"^(asc|desc)$",
        description="Sort direction: asc or desc",
    )


class MessageResponse(BaseModel):
    """Generic message response."""

    model_config = ConfigDict(from_attributes=True)

    message: str

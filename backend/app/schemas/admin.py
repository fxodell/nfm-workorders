"""Admin / audit-log schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuditLogResponse(BaseModel):
    """Read-only audit-log entry."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    org_id: UUID
    actor_user_id: Optional[UUID] = None
    action: str
    entity_type: str
    entity_id: Optional[UUID] = None
    old_value: Optional[dict[str, Any]] = None
    new_value: Optional[dict[str, Any]] = None
    created_at: datetime


class AuditLogListResponse(BaseModel):
    """Paginated list of audit-log entries."""

    model_config = ConfigDict(from_attributes=True)

    items: list[AuditLogResponse]
    total: int
    page: int
    per_page: int

"""Work order labor routes: list, log hours, remove."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_active_user, verify_org_ownership
from app.models.user import User
from app.models.work_order import (
    LaborLog,
    TimelineEvent,
    TimelineEventType,
    WorkOrder,
)
from app.schemas.common import MessageResponse
from app.schemas.work_order import LaborLogCreate, LaborLogResponse

router = APIRouter(prefix="/work-orders", tags=["work-order-labor"])


# ── GET /work-orders/{id}/labor ────────────────────────────────────────

@router.get("/{wo_id}/labor", response_model=list[LaborLogResponse])
async def list_labor_logs(
    wo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all labor log entries for a work order."""
    wo = await db.get(WorkOrder, wo_id)
    if not wo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")
    await verify_org_ownership(wo, current_user)

    result = await db.execute(
        select(LaborLog)
        .where(LaborLog.work_order_id == wo_id)
        .order_by(LaborLog.logged_at.desc())
    )
    return result.scalars().all()


# ── POST /work-orders/{id}/labor ───────────────────────────────────────

@router.post(
    "/{wo_id}/labor",
    response_model=LaborLogResponse,
    status_code=status.HTTP_201_CREATED,
)
async def log_labor(
    wo_id: uuid.UUID,
    body: LaborLogCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Log labor hours against a work order."""
    wo = await db.get(WorkOrder, wo_id)
    if not wo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")
    await verify_org_ownership(wo, current_user)

    labor = LaborLog(
        work_order_id=wo_id,
        org_id=wo.org_id,
        user_id=current_user.id,
        minutes=body.minutes,
        notes=body.notes,
    )
    db.add(labor)

    # Timeline event
    event = TimelineEvent(
        work_order_id=wo_id,
        org_id=wo.org_id,
        user_id=current_user.id,
        event_type=TimelineEventType.LABOR_LOGGED,
        payload={"minutes": body.minutes, "notes": body.notes},
    )
    db.add(event)
    await db.flush()

    return labor


# ── DELETE /work-orders/{id}/labor/{labor_id} ──────────────────────────

@router.delete("/{wo_id}/labor/{labor_id}", response_model=MessageResponse)
async def delete_labor_log(
    wo_id: uuid.UUID,
    labor_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Delete a labor log entry."""
    wo = await db.get(WorkOrder, wo_id)
    if not wo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")
    await verify_org_ownership(wo, current_user)

    labor = await db.get(LaborLog, labor_id)
    if not labor or labor.work_order_id != wo_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Labor log entry not found",
        )

    # Only the author or admin can delete
    if labor.user_id != current_user.id and current_user.role.value not in {"SUPER_ADMIN", "ADMIN"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own labor entries",
        )

    await db.delete(labor)
    await db.flush()
    return MessageResponse(message="Labor log deleted")

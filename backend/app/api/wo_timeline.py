"""Work order timeline routes: list events, add manual notes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_active_user, verify_org_ownership
from app.models.user import User
from app.models.work_order import (
    TimelineEvent,
    TimelineEventType,
    WorkOrder,
)
from app.schemas.work_order import (
    TimelineEventCreate,
    TimelineEventResponse,
)

router = APIRouter(prefix="/work-orders", tags=["work-order-timeline"])


# ── GET /work-orders/{id}/timeline ─────────────────────────────────────

@router.get("/{wo_id}/timeline", response_model=list[TimelineEventResponse])
async def list_timeline_events(
    wo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all timeline events for a work order."""
    wo = await db.get(WorkOrder, wo_id)
    if not wo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")
    await verify_org_ownership(wo, current_user)

    result = await db.execute(
        select(TimelineEvent)
        .where(TimelineEvent.work_order_id == wo_id)
        .order_by(TimelineEvent.created_at.asc())
    )
    return result.scalars().all()


# ── POST /work-orders/{id}/timeline ────────────────────────────────────

@router.post(
    "/{wo_id}/timeline",
    response_model=TimelineEventResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_timeline_note(
    wo_id: uuid.UUID,
    body: TimelineEventCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Add a manual note or message to the work-order timeline."""
    wo = await db.get(WorkOrder, wo_id)
    if not wo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")
    await verify_org_ownership(wo, current_user)

    event = TimelineEvent(
        work_order_id=wo_id,
        org_id=wo.org_id,
        user_id=current_user.id,
        event_type=body.event_type,
        payload=body.payload,
    )
    db.add(event)
    await db.flush()
    return event

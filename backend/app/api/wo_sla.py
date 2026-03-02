"""Work order SLA event routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_active_user, verify_org_ownership
from app.models.sla import SLAEvent
from app.models.user import User
from app.models.work_order import WorkOrder

router = APIRouter(prefix="/work-orders", tags=["work-order-sla"])


# ── GET /work-orders/{id}/sla-events ──────────────────────────────────

@router.get("/{wo_id}/sla-events")
async def list_sla_events(
    wo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all SLA events for a work order."""
    wo = await db.get(WorkOrder, wo_id)
    if not wo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")
    await verify_org_ownership(wo, current_user)

    result = await db.execute(
        select(SLAEvent)
        .where(SLAEvent.work_order_id == wo_id)
        .order_by(SLAEvent.triggered_at.asc())
    )
    events = result.scalars().all()

    return [
        {
            "id": str(e.id),
            "work_order_id": str(e.work_order_id),
            "event_type": e.event_type.value,
            "triggered_at": e.triggered_at.isoformat(),
            "acknowledged_by": str(e.acknowledged_by) if e.acknowledged_by else None,
            "acknowledged_at": e.acknowledged_at.isoformat() if e.acknowledged_at else None,
        }
        for e in events
    ]

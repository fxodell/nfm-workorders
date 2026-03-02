"""Work order parts routes: list, add, remove part usage."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_active_user, verify_org_ownership
from app.models.part import Part, PartTransaction, TransactionType
from app.models.user import User
from app.models.work_order import (
    TimelineEvent,
    TimelineEventType,
    WorkOrder,
    WorkOrderPartUsed,
)
from app.schemas.common import MessageResponse
from app.schemas.work_order import WorkOrderPartCreate, WorkOrderPartResponse

router = APIRouter(prefix="/work-orders", tags=["work-order-parts"])


# ── GET /work-orders/{id}/parts ────────────────────────────────────────

@router.get("/{wo_id}/parts", response_model=list[WorkOrderPartResponse])
async def list_wo_parts(
    wo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all parts used on a work order."""
    wo = await db.get(WorkOrder, wo_id)
    if not wo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")
    await verify_org_ownership(wo, current_user)

    result = await db.execute(
        select(WorkOrderPartUsed).where(WorkOrderPartUsed.work_order_id == wo_id)
    )
    return result.scalars().all()


# ── POST /work-orders/{id}/parts ───────────────────────────────────────

@router.post(
    "/{wo_id}/parts",
    response_model=WorkOrderPartResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_wo_part(
    wo_id: uuid.UUID,
    body: WorkOrderPartCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Add a part usage record to a work order and create a PartTransaction."""
    wo = await db.get(WorkOrder, wo_id)
    if not wo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")
    await verify_org_ownership(wo, current_user)

    # If part_id is provided, verify it exists and belongs to org
    unit_cost = body.unit_cost
    if body.part_id:
        part = await db.get(Part, body.part_id)
        if not part or part.org_id != current_user.org_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Part not found",
            )
        # Use part's unit cost if not provided
        if unit_cost is None:
            unit_cost = float(part.unit_cost) if part.unit_cost else None

        # Decrement stock quantity
        part.stock_quantity = max(0, part.stock_quantity - body.quantity)

        # Create a PartTransaction (inventory out)
        txn = PartTransaction(
            part_id=part.id,
            org_id=current_user.org_id,
            work_order_id=wo_id,
            transaction_type=TransactionType.OUT,
            quantity=body.quantity,
            notes=f"Used on WO {wo.human_readable_number}",
            created_by=current_user.id,
        )
        db.add(txn)

    wo_part = WorkOrderPartUsed(
        work_order_id=wo_id,
        org_id=wo.org_id,
        part_id=body.part_id,
        part_number=body.part_number,
        description=body.description,
        quantity=body.quantity,
        unit_cost=unit_cost,
    )
    db.add(wo_part)

    # Timeline event
    event = TimelineEvent(
        work_order_id=wo_id,
        org_id=wo.org_id,
        user_id=current_user.id,
        event_type=TimelineEventType.PART_USED,
        payload={
            "part_number": body.part_number,
            "quantity": body.quantity,
            "unit_cost": str(unit_cost) if unit_cost else None,
        },
    )
    db.add(event)
    await db.flush()

    return wo_part


# ── DELETE /work-orders/{id}/parts/{part_id} ───────────────────────────

@router.delete("/{wo_id}/parts/{part_usage_id}", response_model=MessageResponse)
async def remove_wo_part(
    wo_id: uuid.UUID,
    part_usage_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Remove a part usage record from a work order."""
    wo = await db.get(WorkOrder, wo_id)
    if not wo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")
    await verify_org_ownership(wo, current_user)

    part_usage = await db.get(WorkOrderPartUsed, part_usage_id)
    if not part_usage or part_usage.work_order_id != wo_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Part usage record not found",
        )

    # Restore stock if linked to an inventory part
    if part_usage.part_id:
        part = await db.get(Part, part_usage.part_id)
        if part and part.org_id == current_user.org_id:
            part.stock_quantity += part_usage.quantity

            # Create reversal transaction
            txn = PartTransaction(
                part_id=part.id,
                org_id=current_user.org_id,
                work_order_id=wo_id,
                transaction_type=TransactionType.IN,
                quantity=part_usage.quantity,
                notes=f"Reversed usage from WO {wo.human_readable_number}",
                created_by=current_user.id,
            )
            db.add(txn)

    await db.delete(part_usage)
    await db.flush()
    return MessageResponse(message="Part usage removed")

"""Part / inventory service: usage tracking, stock transactions, low-stock alerts."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.part import Part, PartTransaction, TransactionType
from app.models.user import User
from app.models.work_order import (
    TimelineEvent,
    TimelineEventType,
    WorkOrder,
    WorkOrderPartUsed,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Add part to work order
# ---------------------------------------------------------------------------


async def add_part_to_wo(
    db: AsyncSession,
    wo_id: uuid.UUID,
    part_data: dict[str, Any],
    user: User,
) -> WorkOrderPartUsed:
    """Record a part used on a work order and deduct from inventory.

    ``part_data`` should contain:
        - ``part_id`` (optional UUID -- if present, stock is decremented)
        - ``part_number`` (str)
        - ``description`` (optional str)
        - ``quantity`` (int, > 0)
        - ``unit_cost`` (optional float)

    Creates a ``WorkOrderPartUsed`` row.  If ``part_id`` is provided, also
    creates a ``PartTransaction(OUT)`` and decrements the part's
    ``stock_quantity``.

    Raises 404 if the work order or part does not exist within the user's org.
    Raises 422 if requested quantity exceeds available stock.
    """
    # Verify work order ownership
    wo_result = await db.execute(
        select(WorkOrder).where(
            WorkOrder.id == wo_id,
            WorkOrder.org_id == user.org_id,
        )
    )
    wo = wo_result.scalars().first()
    if wo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Work order not found",
        )

    part_id: uuid.UUID | None = part_data.get("part_id")
    quantity: int = part_data["quantity"]
    unit_cost: float | None = part_data.get("unit_cost")

    # If a cataloged part, look it up and verify stock
    if part_id is not None:
        part_result = await db.execute(
            select(Part).where(
                Part.id == part_id,
                Part.org_id == user.org_id,
            ).with_for_update()
        )
        part = part_result.scalars().first()
        if part is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Part not found",
            )

        if part.stock_quantity < quantity:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Insufficient stock for part {part.part_number}: "
                    f"available={part.stock_quantity}, requested={quantity}"
                ),
            )

        # Decrement stock
        part.stock_quantity -= quantity

        # Use part's unit_cost if not overridden
        if unit_cost is None:
            unit_cost = float(part.unit_cost) if part.unit_cost else None

        # Create inventory transaction
        txn = PartTransaction(
            part_id=part.id,
            org_id=user.org_id,
            work_order_id=wo_id,
            transaction_type=TransactionType.OUT,
            quantity=quantity,
            notes=f"Used on work order {wo.human_readable_number}",
            created_by=user.id,
        )
        db.add(txn)

    # Create usage record
    usage = WorkOrderPartUsed(
        work_order_id=wo_id,
        org_id=user.org_id,
        part_id=part_id,
        part_number=part_data.get("part_number", ""),
        description=part_data.get("description"),
        quantity=quantity,
        unit_cost=unit_cost,
    )
    db.add(usage)

    # Timeline event
    event = TimelineEvent(
        work_order_id=wo_id,
        org_id=wo.org_id,
        user_id=user.id,
        event_type=TimelineEventType.PARTS_ADDED,
        payload={
            "part_id": str(part_id) if part_id else None,
            "part_number": part_data.get("part_number", ""),
            "quantity": quantity,
            "unit_cost": unit_cost,
        },
    )
    db.add(event)

    await db.flush()

    logger.info(
        "Added part %s (qty=%d) to WO %s by user %s",
        part_data.get("part_number", part_id),
        quantity,
        wo.human_readable_number,
        user.id,
    )
    return usage


# ---------------------------------------------------------------------------
# Generic part transaction
# ---------------------------------------------------------------------------


async def create_part_transaction(
    db: AsyncSession,
    part_id: uuid.UUID,
    transaction_data: dict[str, Any],
    user: User,
) -> PartTransaction:
    """Create an inventory transaction and update the part's stock quantity.

    ``transaction_data`` should contain:
        - ``transaction_type`` (TransactionType or str: "IN", "OUT", "ADJUSTMENT")
        - ``quantity`` (int, > 0)
        - ``work_order_id`` (optional UUID)
        - ``notes`` (optional str)

    For ``IN`` transactions the stock is increased.
    For ``OUT`` transactions the stock is decreased (raises 422 if insufficient).
    For ``ADJUSTMENT`` the quantity is set directly relative to current stock
    (positive = add, negative = remove).
    """
    part_result = await db.execute(
        select(Part).where(
            Part.id == part_id,
            Part.org_id == user.org_id,
        ).with_for_update()
    )
    part = part_result.scalars().first()
    if part is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Part not found",
        )

    txn_type = transaction_data["transaction_type"]
    if isinstance(txn_type, str):
        txn_type = TransactionType(txn_type)
    quantity: int = transaction_data["quantity"]

    if txn_type == TransactionType.IN:
        part.stock_quantity += quantity
    elif txn_type == TransactionType.OUT:
        if part.stock_quantity < quantity:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Insufficient stock for part {part.part_number}: "
                    f"available={part.stock_quantity}, requested={quantity}"
                ),
            )
        part.stock_quantity -= quantity
    elif txn_type == TransactionType.ADJUSTMENT:
        # For adjustments, quantity can be negative (removal) or positive (addition)
        new_stock = part.stock_quantity + quantity
        if new_stock < 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Adjustment would result in negative stock for {part.part_number}: "
                    f"current={part.stock_quantity}, adjustment={quantity}"
                ),
            )
        part.stock_quantity = new_stock

    txn = PartTransaction(
        part_id=part.id,
        org_id=user.org_id,
        work_order_id=transaction_data.get("work_order_id"),
        transaction_type=txn_type,
        quantity=quantity,
        notes=transaction_data.get("notes"),
        created_by=user.id,
    )
    db.add(txn)
    await db.flush()

    logger.info(
        "Part transaction %s: part=%s qty=%d by user %s (new stock=%d)",
        txn_type.value,
        part.part_number,
        quantity,
        user.id,
        part.stock_quantity,
    )
    return txn


# ---------------------------------------------------------------------------
# Low-stock check
# ---------------------------------------------------------------------------


async def check_low_stock(
    db: AsyncSession,
    org_id: uuid.UUID,
) -> list[Part]:
    """Return all active parts whose stock_quantity is at or below reorder_threshold.

    Only returns parts belonging to the given org.
    """
    stmt = (
        select(Part)
        .where(
            Part.org_id == org_id,
            Part.is_active.is_(True),
            Part.stock_quantity <= Part.reorder_threshold,
        )
        .order_by(Part.part_number)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())

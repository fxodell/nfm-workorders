"""Inventory management routes (requires CAN_MANAGE_INVENTORY permission)."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import (
    get_current_active_user,
    require_permission,
    verify_org_ownership,
)
from app.models.part import Part, PartTransaction, TransactionType
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.part import (
    PartCreate,
    PartResponse,
    PartTransactionCreate,
    PartTransactionResponse,
    PartUpdate,
)

router = APIRouter(prefix="/inventory", tags=["inventory"])


# ── GET / ──────────────────────────────────────────────────────────────

@router.get("", response_model=list[PartResponse])
async def list_inventory(
    low_stock: Optional[bool] = Query(None, description="Filter parts below reorder threshold"),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("CAN_MANAGE_INVENTORY")),
):
    """List all inventory items with optional filters."""
    query = select(Part).where(Part.org_id == current_user.org_id, Part.is_active == True)  # noqa: E712

    if low_stock:
        query = query.where(Part.stock_quantity <= Part.reorder_threshold)
    if search:
        query = query.where(
            Part.part_number.ilike(f"%{search}%")
            | Part.description.ilike(f"%{search}%")
        )

    query = query.order_by(Part.part_number)
    result = await db.execute(query)
    return result.scalars().all()


# ── POST / ─────────────────────────────────────────────────────────────

@router.post("", response_model=PartResponse, status_code=status.HTTP_201_CREATED)
async def create_inventory_item(
    body: PartCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("CAN_MANAGE_INVENTORY")),
):
    """Create a new inventory item."""
    existing = await db.execute(
        select(Part).where(
            Part.org_id == current_user.org_id,
            Part.part_number == body.part_number,
        )
    )
    if existing.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A part with this number already exists",
        )

    part = Part(
        org_id=current_user.org_id,
        part_number=body.part_number,
        description=body.description,
        unit_cost=body.unit_cost,
        barcode_value=body.barcode_value,
        supplier_name=body.supplier_name,
        supplier_part_number=body.supplier_part_number,
        stock_quantity=body.stock_quantity,
        reorder_threshold=body.reorder_threshold or 0,
        storage_location=body.storage_location,
    )
    db.add(part)
    await db.flush()
    return part


# ── GET /{id} ──────────────────────────────────────────────────────────

@router.get("/{part_id}", response_model=PartResponse)
async def get_inventory_item(
    part_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("CAN_MANAGE_INVENTORY")),
):
    """Get an inventory item by ID."""
    part = await db.get(Part, part_id)
    if not part:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Part not found")
    await verify_org_ownership(part, current_user)
    return part


# ── PATCH /{id} ────────────────────────────────────────────────────────

@router.patch("/{part_id}", response_model=PartResponse)
async def update_inventory_item(
    part_id: uuid.UUID,
    body: PartUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("CAN_MANAGE_INVENTORY")),
):
    """Update an inventory item."""
    part = await db.get(Part, part_id)
    if not part:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Part not found")
    await verify_org_ownership(part, current_user)

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(part, field, value)
    await db.flush()
    return part


# ── DELETE /{id} ───────────────────────────────────────────────────────

@router.delete("/{part_id}", response_model=MessageResponse)
async def delete_inventory_item(
    part_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("CAN_MANAGE_INVENTORY")),
):
    """Soft-delete an inventory item."""
    part = await db.get(Part, part_id)
    if not part:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Part not found")
    await verify_org_ownership(part, current_user)

    part.is_active = False
    await db.flush()
    return MessageResponse(message="Inventory item deactivated")


# ── GET /{id}/transactions ─────────────────────────────────────────────

@router.get("/{part_id}/transactions", response_model=list[PartTransactionResponse])
async def list_inventory_transactions(
    part_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("CAN_MANAGE_INVENTORY")),
):
    """List all transactions for an inventory item."""
    part = await db.get(Part, part_id)
    if not part:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Part not found")
    await verify_org_ownership(part, current_user)

    result = await db.execute(
        select(PartTransaction)
        .where(PartTransaction.part_id == part_id)
        .order_by(PartTransaction.created_at.desc())
    )
    return result.scalars().all()


# ── POST /{id}/transactions ────────────────────────────────────────────

@router.post(
    "/{part_id}/transactions",
    response_model=PartTransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_inventory_transaction(
    part_id: uuid.UUID,
    body: PartTransactionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("CAN_MANAGE_INVENTORY")),
):
    """Create a transaction for an inventory item."""
    part = await db.get(Part, part_id)
    if not part:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Part not found")
    await verify_org_ownership(part, current_user)

    type_map = {
        "RECEIPT": TransactionType.IN,
        "ISSUE": TransactionType.OUT,
        "ADJUSTMENT": TransactionType.ADJUSTMENT,
        "RETURN": TransactionType.IN,
        "SCRAP": TransactionType.OUT,
    }
    model_type = type_map.get(body.transaction_type.value, TransactionType.ADJUSTMENT)

    txn = PartTransaction(
        part_id=part_id,
        org_id=current_user.org_id,
        work_order_id=body.work_order_id,
        transaction_type=model_type,
        quantity=body.quantity,
        notes=body.notes,
        created_by=current_user.id,
    )
    db.add(txn)

    if model_type == TransactionType.IN:
        part.stock_quantity += body.quantity
    elif model_type == TransactionType.OUT:
        part.stock_quantity = max(0, part.stock_quantity - body.quantity)
    elif model_type == TransactionType.ADJUSTMENT:
        part.stock_quantity = body.quantity

    await db.flush()
    return txn

"""Parts (inventory) routes: CRUD, transactions, QR code."""

from __future__ import annotations

import io
import uuid

import qrcode
import qrcode.constants
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
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

router = APIRouter(prefix="/parts", tags=["parts"])


# ── GET / ──────────────────────────────────────────────────────────────

@router.get("", response_model=list[PartResponse])
async def list_parts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all parts in the organization."""
    result = await db.execute(
        select(Part)
        .where(Part.org_id == current_user.org_id)
        .order_by(Part.part_number)
    )
    return result.scalars().all()


# ── POST / ─────────────────────────────────────────────────────────────

@router.post("", response_model=PartResponse, status_code=status.HTTP_201_CREATED)
async def create_part(
    body: PartCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("CAN_MANAGE_INVENTORY")),
):
    """Create a new part in the inventory."""
    # Check for duplicate part number within org
    existing = await db.execute(
        select(Part).where(
            Part.org_id == current_user.org_id,
            Part.part_number == body.part_number,
        )
    )
    if existing.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A part with this number already exists in your organization",
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
async def get_part(
    part_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get a part by ID."""
    part = await db.get(Part, part_id)
    if not part:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Part not found")
    await verify_org_ownership(part, current_user)
    return part


# ── PATCH /{id} ────────────────────────────────────────────────────────

@router.patch("/{part_id}", response_model=PartResponse)
async def update_part(
    part_id: uuid.UUID,
    body: PartUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("CAN_MANAGE_INVENTORY")),
):
    """Update a part."""
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
async def delete_part(
    part_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("CAN_MANAGE_INVENTORY")),
):
    """Soft-delete a part by deactivating it."""
    part = await db.get(Part, part_id)
    if not part:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Part not found")
    await verify_org_ownership(part, current_user)

    part.is_active = False
    await db.flush()
    return MessageResponse(message="Part deactivated")


# ── GET /{id}/transactions ─────────────────────────────────────────────

@router.get("/{part_id}/transactions", response_model=list[PartTransactionResponse])
async def list_part_transactions(
    part_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all transactions for a part."""
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
async def create_part_transaction(
    part_id: uuid.UUID,
    body: PartTransactionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("CAN_MANAGE_INVENTORY")),
):
    """Create a part transaction (inventory movement)."""
    part = await db.get(Part, part_id)
    if not part:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Part not found")
    await verify_org_ownership(part, current_user)

    # Map schema transaction type to model transaction type
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

    # Update stock quantity
    if model_type == TransactionType.IN:
        part.stock_quantity += body.quantity
    elif model_type == TransactionType.OUT:
        part.stock_quantity = max(0, part.stock_quantity - body.quantity)
    elif model_type == TransactionType.ADJUSTMENT:
        part.stock_quantity = body.quantity  # Absolute adjustment

    await db.flush()
    return txn


# ── GET /{id}/qr-code ──────────────────────────────────────────────────

@router.get("/{part_id}/qr-code")
async def get_part_qr_code(
    part_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Generate a QR code PNG for a part."""
    part = await db.get(Part, part_id)
    if not part:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Part not found")
    await verify_org_ownership(part, current_user)

    scan_url = f"{settings.FRONTEND_URL}/scan/part/{part.qr_code_token}"
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=8,
        border=4,
    )
    qr.add_data(scan_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    return StreamingResponse(buffer, media_type="image/png")

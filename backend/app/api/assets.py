"""Asset management routes: CRUD, work-order history, QR code."""

from __future__ import annotations

import io
import uuid

import qrcode
import qrcode.constants
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import (
    get_current_active_user,
    require_role,
    verify_org_ownership,
)
from app.models.asset import Asset
from app.models.site import Site
from app.models.user import User
from app.models.work_order import WorkOrder
from app.schemas.asset import AssetCreate, AssetResponse, AssetUpdate
from app.schemas.common import MessageResponse
from app.schemas.work_order import WorkOrderListResponse

router = APIRouter(prefix="/assets", tags=["assets"])


# ── GET / ──────────────────────────────────────────────────────────────

@router.get("", response_model=list[AssetResponse])
async def list_assets(
    site_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all assets in the organization, optionally filtered by site."""
    query = select(Asset).where(Asset.org_id == current_user.org_id)
    if site_id:
        query = query.where(Asset.site_id == site_id)
    query = query.order_by(Asset.name)
    result = await db.execute(query)
    return result.scalars().all()


# ── POST / ─────────────────────────────────────────────────────────────

@router.post("", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
async def create_asset(
    body: AssetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["SUPER_ADMIN", "ADMIN", "SUPERVISOR"])),
):
    """Create a new asset."""
    # Verify site belongs to org
    site = await db.get(Site, body.site_id)
    if not site:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    await verify_org_ownership(site, current_user)

    asset = Asset(
        org_id=current_user.org_id,
        site_id=body.site_id,
        name=body.name,
        asset_type=body.asset_type,
        manufacturer=body.manufacturer,
        model=body.model,
        serial_number=body.serial_number,
        install_date=body.install_date,
        warranty_expiry=body.warranty_expiry,
        notes=body.notes,
    )
    db.add(asset)
    await db.flush()
    return asset


# ── GET /{id} ──────────────────────────────────────────────────────────

@router.get("/{asset_id}", response_model=AssetResponse)
async def get_asset(
    asset_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get an asset by ID."""
    asset = await db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    await verify_org_ownership(asset, current_user)
    return asset


# ── PATCH /{id} ────────────────────────────────────────────────────────

@router.patch("/{asset_id}", response_model=AssetResponse)
async def update_asset(
    asset_id: uuid.UUID,
    body: AssetUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["SUPER_ADMIN", "ADMIN", "SUPERVISOR"])),
):
    """Update an asset."""
    asset = await db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    await verify_org_ownership(asset, current_user)

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(asset, field, value)
    await db.flush()
    return asset


# ── DELETE /{id} ───────────────────────────────────────────────────────

@router.delete("/{asset_id}", response_model=MessageResponse)
async def delete_asset(
    asset_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["SUPER_ADMIN", "ADMIN"])),
):
    """Soft-delete an asset by deactivating it."""
    asset = await db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    await verify_org_ownership(asset, current_user)

    asset.is_active = False
    await db.flush()
    return MessageResponse(message="Asset deactivated")


# ── GET /{id}/work-order-history ───────────────────────────────────────

@router.get("/{asset_id}/work-order-history", response_model=WorkOrderListResponse)
async def get_asset_work_order_history(
    asset_id: uuid.UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get paginated work-order history for an asset."""
    asset = await db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    await verify_org_ownership(asset, current_user)

    base_query = select(WorkOrder).where(
        WorkOrder.asset_id == asset_id,
        WorkOrder.org_id == current_user.org_id,
    )

    count_q = select(func.count()).select_from(base_query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = base_query.order_by(WorkOrder.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    items = result.scalars().all()

    return WorkOrderListResponse(items=items, total=total, page=page, per_page=per_page)


# ── GET /{id}/qr-code ──────────────────────────────────────────────────

@router.get("/{asset_id}/qr-code")
async def get_asset_qr_code(
    asset_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Generate a QR code PNG for an asset."""
    asset = await db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    await verify_org_ownership(asset, current_user)

    scan_url = f"{settings.FRONTEND_URL}/scan/asset/{asset.qr_code_token}"
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

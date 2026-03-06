"""Site management routes: CRUD, assets, work-order history, QR code."""

from __future__ import annotations

import io
import uuid
from typing import Optional

import qrcode
import qrcode.constants
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import (
    get_current_active_user,
    require_role,
    verify_area_access,
    verify_org_ownership,
)
from app.models.asset import Asset
from app.models.location import Location
from app.models.site import Site
from app.models.user import User
from app.models.work_order import WorkOrder
from app.schemas.asset import AssetResponse
from app.schemas.common import MessageResponse
from app.schemas.site import SiteCreate, SiteResponse, SiteUpdate
from app.schemas.work_order import WorkOrderListResponse, WorkOrderResponse

router = APIRouter(prefix="/sites", tags=["sites"])


# ── helpers ────────────────────────────────────────────────────────────

async def _get_site_with_access(
    site_id: uuid.UUID,
    db: AsyncSession,
    current_user: User,
) -> Site:
    """Load site, verify org and area access."""
    site = await db.get(Site, site_id)
    if not site:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    await verify_org_ownership(site, current_user)
    # Resolve area via location
    location = await db.get(Location, site.location_id)
    if location:
        await verify_area_access(location.area_id, current_user, db)
    return site


# ── GET / ──────────────────────────────────────────────────────────────

@router.get("", response_model=list[SiteResponse])
async def list_sites(
    location_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all sites in the organization, optionally filtered by location."""
    query = select(Site).where(Site.org_id == current_user.org_id)
    if location_id:
        query = query.where(Site.location_id == location_id)
    query = query.order_by(Site.name)
    result = await db.execute(query)
    return result.scalars().all()


# ── POST / ─────────────────────────────────────────────────────────────

@router.post("", response_model=SiteResponse, status_code=status.HTTP_201_CREATED)
async def create_site(
    body: SiteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["SUPER_ADMIN", "ADMIN", "SUPERVISOR"])),
):
    """Create a new site."""
    # Verify location exists and belongs to org
    location = await db.get(Location, body.location_id)
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
    await verify_org_ownership(location, current_user)
    await verify_area_access(location.area_id, current_user, db)

    site = Site(
        org_id=current_user.org_id,
        location_id=body.location_id,
        name=body.name,
        type=body.type,
        address=body.address,
        gps_lat=body.gps_lat,
        gps_lng=body.gps_lng,
        site_timezone=body.site_timezone,
    )
    db.add(site)
    await db.flush()
    return site


# ── GET /{id} ──────────────────────────────────────────────────────────

@router.get("/{site_id}", response_model=SiteResponse)
async def get_site(
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get a site by ID."""
    site = await _get_site_with_access(site_id, db, current_user)
    return site


# ── PATCH /{id} ────────────────────────────────────────────────────────

@router.patch("/{site_id}", response_model=SiteResponse)
async def update_site(
    site_id: uuid.UUID,
    body: SiteUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["SUPER_ADMIN", "ADMIN", "SUPERVISOR"])),
):
    """Update a site."""
    site = await _get_site_with_access(site_id, db, current_user)

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(site, field, value)
    await db.flush()
    return site


# ── DELETE /{id} ───────────────────────────────────────────────────────

@router.delete("/{site_id}", response_model=MessageResponse)
async def delete_site(
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["SUPER_ADMIN", "ADMIN"])),
):
    """Soft-delete a site by deactivating it."""
    site = await _get_site_with_access(site_id, db, current_user)
    site.is_active = False
    await db.flush()
    return MessageResponse(message="Site deactivated")


# ── GET /{id}/assets ───────────────────────────────────────────────────

@router.get("/{site_id}/assets", response_model=list[AssetResponse])
async def list_site_assets(
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all assets at a site."""
    site = await _get_site_with_access(site_id, db, current_user)

    result = await db.execute(
        select(Asset)
        .where(Asset.site_id == site_id, Asset.org_id == current_user.org_id)
        .order_by(Asset.name)
    )
    return result.scalars().all()


# ── GET /{id}/work-order-history ───────────────────────────────────────

@router.get("/{site_id}/work-order-history", response_model=WorkOrderListResponse)
async def get_site_work_order_history(
    site_id: uuid.UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get paginated work-order history for a site."""
    site = await _get_site_with_access(site_id, db, current_user)

    base_query = select(WorkOrder).where(
        WorkOrder.site_id == site_id,
        WorkOrder.org_id == current_user.org_id,
    )

    count_q = select(func.count()).select_from(base_query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = base_query.order_by(WorkOrder.created_at.desc())
    query = query.options(
        selectinload(WorkOrder.area),
        selectinload(WorkOrder.site),
        selectinload(WorkOrder.asset),
        selectinload(WorkOrder.requester),
        selectinload(WorkOrder.assignee),
    )
    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    items = result.scalars().all()

    return WorkOrderListResponse(items=items, total=total, page=page, per_page=per_page)


# ── GET /{id}/qr-code ──────────────────────────────────────────────────

@router.get("/{site_id}/qr-code")
async def get_site_qr_code(
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Generate a QR code PNG for a site."""
    site = await _get_site_with_access(site_id, db, current_user)

    scan_url = f"{settings.FRONTEND_URL}/scan/site/{site.qr_code_token}"
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

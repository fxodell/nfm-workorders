"""QR code scan routes: resolve tokens to entity data."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.models.asset import Asset
from app.models.location import Location
from app.models.part import Part
from app.models.site import Site
from app.models.user import User
from app.models.work_order import WorkOrder, WorkOrderStatus
from app.schemas.scan import (
    AssetScanResponse,
    LocationScanResponse,
    PartScanResponse,
    SiteScanResponse,
)

router = APIRouter(prefix="/scan", tags=["scan"])

# Statuses considered "open" for counting purposes
_OPEN_STATUSES = {
    WorkOrderStatus.NEW,
    WorkOrderStatus.ASSIGNED,
    WorkOrderStatus.ACCEPTED,
    WorkOrderStatus.IN_PROGRESS,
    WorkOrderStatus.WAITING_ON_OPS,
    WorkOrderStatus.ESCALATED,
}


# ── GET /scan/location/{token} ─────────────────────────────────────────

@router.get("/location/{token}", response_model=LocationScanResponse)
async def scan_location(
    token: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Look up a location by its QR code token."""
    result = await db.execute(
        select(Location).where(
            Location.qr_code_token == token,
            Location.org_id == current_user.org_id,
        )
    )
    location = result.scalars().first()
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")

    # Count open work orders for this location
    count_result = await db.execute(
        select(func.count()).where(
            WorkOrder.location_id == location.id,
            WorkOrder.org_id == current_user.org_id,
            WorkOrder.status.in_(_OPEN_STATUSES),
        )
    )
    open_count = count_result.scalar() or 0

    return LocationScanResponse(
        location_id=location.id,
        name=location.name,
        area_id=location.area_id,
        open_wo_count=open_count,
    )


# ── GET /scan/site/{token} ────────────────────────────────────────────

@router.get("/site/{token}", response_model=SiteScanResponse)
async def scan_site(
    token: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Look up a site by its QR code token."""
    result = await db.execute(
        select(Site).where(
            Site.qr_code_token == token,
            Site.org_id == current_user.org_id,
        )
    )
    site = result.scalars().first()
    if not site:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")

    # Count open work orders
    count_result = await db.execute(
        select(func.count()).where(
            WorkOrder.site_id == site.id,
            WorkOrder.org_id == current_user.org_id,
            WorkOrder.status.in_(_OPEN_STATUSES),
        )
    )
    open_count = count_result.scalar() or 0

    # Count safety-flagged work orders
    safety_result = await db.execute(
        select(func.count()).where(
            WorkOrder.site_id == site.id,
            WorkOrder.org_id == current_user.org_id,
            WorkOrder.status.in_(_OPEN_STATUSES),
            WorkOrder.safety_flag == True,  # noqa: E712
        )
    )
    safety_count = safety_result.scalar() or 0

    return SiteScanResponse(
        site_id=site.id,
        name=site.name,
        location_id=site.location_id,
        open_wo_count=open_count,
        safety_flag_count=safety_count,
    )


# ── GET /scan/asset/{token} ───────────────────────────────────────────

@router.get("/asset/{token}", response_model=AssetScanResponse)
async def scan_asset(
    token: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Look up an asset by its QR code token."""
    result = await db.execute(
        select(Asset).where(
            Asset.qr_code_token == token,
            Asset.org_id == current_user.org_id,
        )
    )
    asset = result.scalars().first()
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")

    count_result = await db.execute(
        select(func.count()).where(
            WorkOrder.asset_id == asset.id,
            WorkOrder.org_id == current_user.org_id,
            WorkOrder.status.in_(_OPEN_STATUSES),
        )
    )
    open_count = count_result.scalar() or 0

    return AssetScanResponse(
        asset_id=asset.id,
        name=asset.name,
        site_id=asset.site_id,
        open_wo_count=open_count,
    )


# ── GET /scan/part/{token} ────────────────────────────────────────────

@router.get("/part/{token}", response_model=PartScanResponse)
async def scan_part(
    token: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Look up a part by its QR code token."""
    result = await db.execute(
        select(Part).where(
            Part.qr_code_token == token,
            Part.org_id == current_user.org_id,
        )
    )
    part = result.scalars().first()
    if not part:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Part not found")

    return PartScanResponse(
        part_id=part.id,
        part_number=part.part_number,
        description=part.description,
        stock_quantity=part.stock_quantity,
        unit_cost=float(part.unit_cost) if part.unit_cost else None,
    )

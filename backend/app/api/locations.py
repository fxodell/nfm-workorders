"""Location management routes: CRUD, sites listing, QR code."""

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
    require_role,
    verify_area_access,
    verify_org_ownership,
)
from app.models.location import Location
from app.models.site import Site
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.location import LocationCreate, LocationResponse, LocationUpdate
from app.schemas.site import SiteResponse

router = APIRouter(prefix="/locations", tags=["locations"])


# ── GET / ──────────────────────────────────────────────────────────────

@router.get("", response_model=list[LocationResponse])
async def list_locations(
    area_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all locations in the organization, optionally filtered by area."""
    query = select(Location).where(Location.org_id == current_user.org_id)
    if area_id:
        query = query.where(Location.area_id == area_id)
    query = query.order_by(Location.name)
    result = await db.execute(query)
    return result.scalars().all()


# ── POST / ─────────────────────────────────────────────────────────────

@router.post("", response_model=LocationResponse, status_code=status.HTTP_201_CREATED)
async def create_location(
    body: LocationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["SUPER_ADMIN", "ADMIN", "SUPERVISOR"])),
):
    """Create a new location."""
    await verify_area_access(body.area_id, current_user, db)

    location = Location(
        org_id=current_user.org_id,
        area_id=body.area_id,
        name=body.name,
        address=body.address,
        gps_lat=body.gps_lat,
        gps_lng=body.gps_lng,
    )
    db.add(location)
    await db.flush()
    return location


# ── GET /{id} ──────────────────────────────────────────────────────────

@router.get("/{location_id}", response_model=LocationResponse)
async def get_location(
    location_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get a location by ID."""
    location = await db.get(Location, location_id)
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
    await verify_org_ownership(location, current_user)
    await verify_area_access(location.area_id, current_user, db)
    return location


# ── PATCH /{id} ────────────────────────────────────────────────────────

@router.patch("/{location_id}", response_model=LocationResponse)
async def update_location(
    location_id: uuid.UUID,
    body: LocationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["SUPER_ADMIN", "ADMIN", "SUPERVISOR"])),
):
    """Update a location."""
    location = await db.get(Location, location_id)
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
    await verify_org_ownership(location, current_user)
    await verify_area_access(location.area_id, current_user, db)

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(location, field, value)
    await db.flush()
    return location


# ── DELETE /{id} ───────────────────────────────────────────────────────

@router.delete("/{location_id}", response_model=MessageResponse)
async def delete_location(
    location_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["SUPER_ADMIN", "ADMIN"])),
):
    """Soft-delete a location by deactivating it."""
    location = await db.get(Location, location_id)
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
    await verify_org_ownership(location, current_user)

    location.is_active = False
    await db.flush()
    return MessageResponse(message="Location deactivated")


# ── GET /{id}/sites ────────────────────────────────────────────────────

@router.get("/{location_id}/sites", response_model=list[SiteResponse])
async def list_location_sites(
    location_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all sites at a location."""
    location = await db.get(Location, location_id)
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
    await verify_org_ownership(location, current_user)
    await verify_area_access(location.area_id, current_user, db)

    result = await db.execute(
        select(Site)
        .where(Site.location_id == location_id, Site.org_id == current_user.org_id)
        .order_by(Site.name)
    )
    return result.scalars().all()


# ── GET /{id}/qr-code ──────────────────────────────────────────────────

@router.get("/{location_id}/qr-code")
async def get_location_qr_code(
    location_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Generate a QR code PNG for a location."""
    location = await db.get(Location, location_id)
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
    await verify_org_ownership(location, current_user)

    scan_url = f"{settings.FRONTEND_URL}/scan/location/{location.qr_code_token}"
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

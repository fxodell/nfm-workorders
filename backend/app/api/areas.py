"""Area management routes: CRUD, on-call schedule, shifts."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import (
    get_current_active_user,
    require_role,
    verify_org_ownership,
)
from app.models.area import Area
from app.models.shift import ShiftSchedule
from app.models.user import OnCallSchedule, User
from app.schemas.area import AreaCreate, AreaResponse, AreaUpdate
from app.schemas.common import MessageResponse

router = APIRouter(prefix="/areas", tags=["areas"])


# ── GET / ──────────────────────────────────────────────────────────────

@router.get("/", response_model=list[AreaResponse])
async def list_areas(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all areas in the organization."""
    result = await db.execute(
        select(Area)
        .where(Area.org_id == current_user.org_id)
        .order_by(Area.name)
    )
    return result.scalars().all()


# ── POST / ─────────────────────────────────────────────────────────────

@router.post("/", response_model=AreaResponse, status_code=status.HTTP_201_CREATED)
async def create_area(
    body: AreaCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["SUPER_ADMIN", "ADMIN"])),
):
    """Create a new area (ADMIN only)."""
    area = Area(
        org_id=current_user.org_id,
        name=body.name,
        description=body.description,
        timezone=body.timezone,
    )
    db.add(area)
    await db.flush()
    return area


# ── GET /{id} ──────────────────────────────────────────────────────────

@router.get("/{area_id}", response_model=AreaResponse)
async def get_area(
    area_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get an area by ID."""
    area = await db.get(Area, area_id)
    if not area:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Area not found")
    await verify_org_ownership(area, current_user)
    return area


# ── PATCH /{id} ────────────────────────────────────────────────────────

@router.patch("/{area_id}", response_model=AreaResponse)
async def update_area(
    area_id: uuid.UUID,
    body: AreaUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["SUPER_ADMIN", "ADMIN"])),
):
    """Update an area (ADMIN only)."""
    area = await db.get(Area, area_id)
    if not area:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Area not found")
    await verify_org_ownership(area, current_user)

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(area, field, value)
    await db.flush()
    return area


# ── DELETE /{id} ───────────────────────────────────────────────────────

@router.delete("/{area_id}", response_model=MessageResponse)
async def delete_area(
    area_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["SUPER_ADMIN", "ADMIN"])),
):
    """Soft-delete an area by deactivating it (ADMIN only)."""
    area = await db.get(Area, area_id)
    if not area:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Area not found")
    await verify_org_ownership(area, current_user)

    area.is_active = False
    await db.flush()
    return MessageResponse(message="Area deactivated")


# ── GET /{id}/on-call ──────────────────────────────────────────────────

@router.get("/{area_id}/on-call")
async def get_area_on_call(
    area_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get on-call schedule for an area."""
    area = await db.get(Area, area_id)
    if not area:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Area not found")
    await verify_org_ownership(area, current_user)

    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(OnCallSchedule)
        .where(
            OnCallSchedule.area_id == area_id,
            OnCallSchedule.org_id == current_user.org_id,
            OnCallSchedule.end_dt >= now,
        )
        .order_by(OnCallSchedule.start_dt)
    )
    schedules = result.scalars().all()
    return [
        {
            "id": str(s.id),
            "user_id": str(s.user_id),
            "start_dt": s.start_dt.isoformat(),
            "end_dt": s.end_dt.isoformat(),
            "priority": s.priority.value,
        }
        for s in schedules
    ]


# ── GET /{id}/shifts ───────────────────────────────────────────────────

@router.get("/{area_id}/shifts")
async def get_area_shifts(
    area_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get shift schedules for an area."""
    area = await db.get(Area, area_id)
    if not area:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Area not found")
    await verify_org_ownership(area, current_user)

    result = await db.execute(
        select(ShiftSchedule)
        .where(
            ShiftSchedule.area_id == area_id,
            ShiftSchedule.org_id == current_user.org_id,
        )
        .order_by(ShiftSchedule.name)
    )
    return result.scalars().all()

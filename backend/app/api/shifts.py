"""Shift schedule routes: CRUD + user assignment."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import (
    get_current_active_user,
    require_role,
    verify_org_ownership,
)
from app.models.shift import ShiftSchedule, UserShiftAssignment
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.shift import (
    ShiftScheduleCreate,
    ShiftScheduleResponse,
    ShiftScheduleUpdate,
    ShiftUserAssignment,
)

router = APIRouter(prefix="/shifts", tags=["shifts"])


# ── GET / ──────────────────────────────────────────────────────────────

@router.get("", response_model=list[ShiftScheduleResponse])
async def list_shifts(
    area_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all shift schedules in the organization."""
    query = select(ShiftSchedule).where(ShiftSchedule.org_id == current_user.org_id)
    if area_id:
        query = query.where(ShiftSchedule.area_id == area_id)
    query = query.order_by(ShiftSchedule.name)
    result = await db.execute(query)
    return result.scalars().all()


# ── POST / ─────────────────────────────────────────────────────────────

@router.post("", response_model=ShiftScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_shift(
    body: ShiftScheduleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["SUPER_ADMIN", "ADMIN"])),
):
    """Create a new shift schedule."""
    shift = ShiftSchedule(
        org_id=current_user.org_id,
        area_id=body.area_id,
        name=body.name,
        start_time=body.start_time,
        end_time=body.end_time,
        days_of_week=body.days_of_week,
        timezone=body.timezone,
    )
    db.add(shift)
    await db.flush()
    return shift


# ── GET /{id} ──────────────────────────────────────────────────────────

@router.get("/{shift_id}", response_model=ShiftScheduleResponse)
async def get_shift(
    shift_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get a shift schedule by ID."""
    shift = await db.get(ShiftSchedule, shift_id)
    if not shift:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shift not found")
    await verify_org_ownership(shift, current_user)
    return shift


# ── PATCH /{id} ────────────────────────────────────────────────────────

@router.patch("/{shift_id}", response_model=ShiftScheduleResponse)
async def update_shift(
    shift_id: uuid.UUID,
    body: ShiftScheduleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["SUPER_ADMIN", "ADMIN"])),
):
    """Update a shift schedule."""
    shift = await db.get(ShiftSchedule, shift_id)
    if not shift:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shift not found")
    await verify_org_ownership(shift, current_user)

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(shift, field, value)
    await db.flush()
    return shift


# ── DELETE /{id} ───────────────────────────────────────────────────────

@router.delete("/{shift_id}", response_model=MessageResponse)
async def delete_shift(
    shift_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["SUPER_ADMIN", "ADMIN"])),
):
    """Soft-delete a shift schedule by deactivating it."""
    shift = await db.get(ShiftSchedule, shift_id)
    if not shift:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shift not found")
    await verify_org_ownership(shift, current_user)

    shift.is_active = False
    await db.flush()
    return MessageResponse(message="Shift deactivated")


# ── PUT /{id}/users ────────────────────────────────────────────────────

@router.put("/{shift_id}/users", response_model=MessageResponse)
async def assign_users_to_shift(
    shift_id: uuid.UUID,
    body: ShiftUserAssignment,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["SUPER_ADMIN", "ADMIN"])),
):
    """Replace users assigned to a shift schedule."""
    shift = await db.get(ShiftSchedule, shift_id)
    if not shift:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shift not found")
    await verify_org_ownership(shift, current_user)

    # Delete existing assignments
    await db.execute(
        delete(UserShiftAssignment).where(
            UserShiftAssignment.shift_schedule_id == shift_id
        )
    )

    # Create new assignments
    for user_id in body.user_ids:
        # Verify user belongs to same org
        user = await db.get(User, user_id)
        if user and user.org_id == current_user.org_id:
            db.add(UserShiftAssignment(user_id=user_id, shift_schedule_id=shift_id))

    await db.flush()
    return MessageResponse(message="Shift user assignments updated")

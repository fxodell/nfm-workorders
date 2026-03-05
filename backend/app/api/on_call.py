"""On-call schedule routes: CRUD for on-call assignments."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import (
    get_current_active_user,
    require_role,
    verify_org_ownership,
)
from app.models.user import OnCallSchedule, User
from app.schemas.common import MessageResponse

router = APIRouter(prefix="/on-call", tags=["on-call"])


class OnCallCreate(BaseModel):
    """Create an on-call schedule entry."""
    area_id: uuid.UUID
    user_id: uuid.UUID
    start_dt: datetime
    end_dt: datetime
    priority: str = Field(..., pattern=r"^(PRIMARY|SECONDARY)$")


class OnCallUpdate(BaseModel):
    """Update an on-call schedule entry."""
    start_dt: Optional[datetime] = None
    end_dt: Optional[datetime] = None
    priority: Optional[str] = Field(default=None, pattern=r"^(PRIMARY|SECONDARY)$")


class OnCallResponse(BaseModel):
    """Read-only on-call schedule entry."""
    id: uuid.UUID
    org_id: uuid.UUID
    area_id: uuid.UUID
    user_id: uuid.UUID
    start_dt: datetime
    end_dt: datetime
    priority: str


# ── GET / ──────────────────────────────────────────────────────────────

@router.get("", response_model=list[OnCallResponse])
async def list_on_call(
    area_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all on-call schedules in the organization."""
    query = select(OnCallSchedule).where(OnCallSchedule.org_id == current_user.org_id)
    if area_id:
        query = query.where(OnCallSchedule.area_id == area_id)
    query = query.order_by(OnCallSchedule.start_dt.desc())
    result = await db.execute(query)
    schedules = result.scalars().all()
    return [
        OnCallResponse(
            id=s.id,
            org_id=s.org_id,
            area_id=s.area_id,
            user_id=s.user_id,
            start_dt=s.start_dt,
            end_dt=s.end_dt,
            priority=s.priority.value,
        )
        for s in schedules
    ]


# ── POST / ─────────────────────────────────────────────────────────────

@router.post("", response_model=OnCallResponse, status_code=status.HTTP_201_CREATED)
async def create_on_call(
    body: OnCallCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["SUPER_ADMIN", "ADMIN", "SUPERVISOR"])),
):
    """Create a new on-call schedule entry."""
    # Verify user belongs to same org
    user = await db.get(User, body.user_id)
    if not user or user.org_id != current_user.org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if body.end_dt <= body.start_dt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_dt must be after start_dt",
        )

    schedule = OnCallSchedule(
        org_id=current_user.org_id,
        area_id=body.area_id,
        user_id=body.user_id,
        start_dt=body.start_dt,
        end_dt=body.end_dt,
        priority=body.priority,
    )
    db.add(schedule)
    await db.flush()
    return OnCallResponse(
        id=schedule.id,
        org_id=schedule.org_id,
        area_id=schedule.area_id,
        user_id=schedule.user_id,
        start_dt=schedule.start_dt,
        end_dt=schedule.end_dt,
        priority=schedule.priority.value,
    )


# ── GET /{id} ──────────────────────────────────────────────────────────

@router.get("/{schedule_id}", response_model=OnCallResponse)
async def get_on_call(
    schedule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get an on-call schedule entry by ID."""
    schedule = await db.get(OnCallSchedule, schedule_id)
    if not schedule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="On-call schedule not found")
    await verify_org_ownership(schedule, current_user)
    return OnCallResponse(
        id=schedule.id,
        org_id=schedule.org_id,
        area_id=schedule.area_id,
        user_id=schedule.user_id,
        start_dt=schedule.start_dt,
        end_dt=schedule.end_dt,
        priority=schedule.priority.value,
    )


# ── PATCH /{id} ────────────────────────────────────────────────────────

@router.patch("/{schedule_id}", response_model=OnCallResponse)
async def update_on_call(
    schedule_id: uuid.UUID,
    body: OnCallUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["SUPER_ADMIN", "ADMIN", "SUPERVISOR"])),
):
    """Update an on-call schedule entry."""
    schedule = await db.get(OnCallSchedule, schedule_id)
    if not schedule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="On-call schedule not found")
    await verify_org_ownership(schedule, current_user)

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(schedule, field, value)
    await db.flush()

    return OnCallResponse(
        id=schedule.id,
        org_id=schedule.org_id,
        area_id=schedule.area_id,
        user_id=schedule.user_id,
        start_dt=schedule.start_dt,
        end_dt=schedule.end_dt,
        priority=schedule.priority.value,
    )


# ── DELETE /{id} ───────────────────────────────────────────────────────

@router.delete("/{schedule_id}", response_model=MessageResponse)
async def delete_on_call(
    schedule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["SUPER_ADMIN", "ADMIN", "SUPERVISOR"])),
):
    """Delete an on-call schedule entry."""
    schedule = await db.get(OnCallSchedule, schedule_id)
    if not schedule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="On-call schedule not found")
    await verify_org_ownership(schedule, current_user)

    await db.delete(schedule)
    await db.flush()
    return MessageResponse(message="On-call schedule deleted")

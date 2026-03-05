"""Incentive program routes: CRUD + scores."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import (
    get_current_active_user,
    require_role,
    verify_org_ownership,
)
from app.models.incentive import IncentiveProgram, UserIncentiveScore
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.incentive import (
    IncentiveProgramCreate,
    IncentiveProgramResponse,
    IncentiveProgramUpdate,
)

router = APIRouter(prefix="/incentives", tags=["incentives"])


# ── GET / ──────────────────────────────────────────────────────────────

@router.get("", response_model=list[IncentiveProgramResponse])
async def list_incentive_programs(
    is_active: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all incentive programs in the organization."""
    query = select(IncentiveProgram).where(
        IncentiveProgram.org_id == current_user.org_id
    )
    if is_active is not None:
        query = query.where(IncentiveProgram.is_active == is_active)
    query = query.order_by(IncentiveProgram.name)
    result = await db.execute(query)
    return result.scalars().all()


# ── POST / ─────────────────────────────────────────────────────────────

@router.post("", response_model=IncentiveProgramResponse, status_code=status.HTTP_201_CREATED)
async def create_incentive_program(
    body: IncentiveProgramCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["SUPER_ADMIN", "ADMIN"])),
):
    """Create a new incentive program (ADMIN only)."""
    program = IncentiveProgram(
        org_id=current_user.org_id,
        name=body.name,
        metric=body.metric,
        target_value=body.target_value,
        bonus_description=body.bonus_description,
        period_type=body.period_type,
    )
    db.add(program)
    await db.flush()
    return program


# ── GET /{id} ──────────────────────────────────────────────────────────

@router.get("/{program_id}", response_model=IncentiveProgramResponse)
async def get_incentive_program(
    program_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get an incentive program by ID."""
    program = await db.get(IncentiveProgram, program_id)
    if not program:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incentive program not found")
    await verify_org_ownership(program, current_user)
    return program


# ── PATCH /{id} ────────────────────────────────────────────────────────

@router.patch("/{program_id}", response_model=IncentiveProgramResponse)
async def update_incentive_program(
    program_id: uuid.UUID,
    body: IncentiveProgramUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["SUPER_ADMIN", "ADMIN"])),
):
    """Update an incentive program (ADMIN only)."""
    program = await db.get(IncentiveProgram, program_id)
    if not program:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incentive program not found")
    await verify_org_ownership(program, current_user)

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(program, field, value)
    await db.flush()
    return program


# ── DELETE /{id} ───────────────────────────────────────────────────────

@router.delete("/{program_id}", response_model=MessageResponse)
async def delete_incentive_program(
    program_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["SUPER_ADMIN", "ADMIN"])),
):
    """Soft-delete an incentive program by deactivating it (ADMIN only)."""
    program = await db.get(IncentiveProgram, program_id)
    if not program:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incentive program not found")
    await verify_org_ownership(program, current_user)

    program.is_active = False
    await db.flush()
    return MessageResponse(message="Incentive program deactivated")


# ── GET /scores ────────────────────────────────────────────────────────

@router.get("/scores")
async def get_incentive_scores(
    program_id: Optional[uuid.UUID] = Query(None),
    user_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get incentive scores, optionally filtered by program or user."""
    # First, get org-scoped program IDs
    program_query = select(IncentiveProgram.id).where(
        IncentiveProgram.org_id == current_user.org_id
    )
    if program_id:
        program_query = program_query.where(IncentiveProgram.id == program_id)

    query = select(UserIncentiveScore).where(
        UserIncentiveScore.program_id.in_(program_query)
    )
    if user_id:
        query = query.where(UserIncentiveScore.user_id == user_id)

    query = query.order_by(UserIncentiveScore.calculated_at.desc())
    result = await db.execute(query)
    scores = result.scalars().all()

    return [
        {
            "id": str(s.id),
            "user_id": str(s.user_id),
            "program_id": str(s.program_id),
            "period_label": s.period_label,
            "score": float(s.score),
            "achieved": s.achieved,
            "calculated_at": s.calculated_at.isoformat(),
        }
        for s in scores
    ]

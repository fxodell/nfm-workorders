"""Budget management routes: get, set, summary."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission, verify_org_ownership
from app.models.area import Area
from app.models.budget import AreaBudget
from app.models.user import User
from app.schemas.budget import (
    AreaBudgetCreate,
    AreaBudgetResponse,
    AreaBudgetSummaryItem,
    BudgetSummaryResponse,
)
from app.schemas.common import MessageResponse

router = APIRouter(prefix="/budget", tags=["budget"])


# ── GET / ──────────────────────────────────────────────────────────────

@router.get("/", response_model=list[AreaBudgetResponse])
async def list_budgets(
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None),
    area_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("CAN_MANAGE_BUDGET")),
):
    """List area budgets with optional filters."""
    query = select(AreaBudget).where(AreaBudget.org_id == current_user.org_id)
    if year:
        query = query.where(AreaBudget.year == year)
    if month:
        query = query.where(AreaBudget.month == month)
    if area_id:
        query = query.where(AreaBudget.area_id == area_id)
    query = query.order_by(AreaBudget.year.desc(), AreaBudget.month.desc())
    result = await db.execute(query)
    return result.scalars().all()


# ── PUT / ──────────────────────────────────────────────────────────────

@router.put("/", response_model=AreaBudgetResponse)
async def set_budget(
    body: AreaBudgetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("CAN_MANAGE_BUDGET")),
):
    """Set or update a monthly budget for an area. Upserts by area + year + month."""
    # Verify area belongs to org
    area = await db.get(Area, body.area_id)
    if not area:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Area not found")
    await verify_org_ownership(area, current_user)

    # Upsert: check if budget exists for this area/year/month
    result = await db.execute(
        select(AreaBudget).where(
            AreaBudget.org_id == current_user.org_id,
            AreaBudget.area_id == body.area_id,
            AreaBudget.year == body.year,
            AreaBudget.month == body.month,
        )
    )
    budget = result.scalars().first()

    if budget:
        budget.budget_amount = body.budget_amount
    else:
        budget = AreaBudget(
            org_id=current_user.org_id,
            area_id=body.area_id,
            year=body.year,
            month=body.month,
            budget_amount=body.budget_amount,
        )
        db.add(budget)

    await db.flush()
    return budget


# ── GET /summary ───────────────────────────────────────────────────────

@router.get("/summary", response_model=BudgetSummaryResponse)
async def budget_summary(
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("CAN_MANAGE_BUDGET")),
):
    """Get aggregated budget summary across all areas."""
    query = select(AreaBudget).where(AreaBudget.org_id == current_user.org_id)
    if year:
        query = query.where(AreaBudget.year == year)
    if month:
        query = query.where(AreaBudget.month == month)

    result = await db.execute(query)
    budgets = result.scalars().all()

    # Build per-area summaries
    area_map: dict[str, dict] = {}
    for b in budgets:
        key = str(b.area_id)
        if key not in area_map:
            area_map[key] = {
                "area_id": b.area_id,
                "area_name": None,
                "budget_amount": 0.0,
                "actual_spend": 0.0,
            }
        area_map[key]["budget_amount"] += float(b.budget_amount)
        area_map[key]["actual_spend"] += float(b.actual_spend)

    # Resolve area names
    for key, data in area_map.items():
        area = await db.get(Area, data["area_id"])
        if area:
            data["area_name"] = area.name

    by_area = [
        AreaBudgetSummaryItem(**data)
        for data in area_map.values()
    ]

    total_budget = sum(item.budget_amount for item in by_area)
    total_spend = sum(item.actual_spend for item in by_area)

    return BudgetSummaryResponse(
        total_budget=total_budget,
        total_spend=total_spend,
        by_area=by_area,
    )

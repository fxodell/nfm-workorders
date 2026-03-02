"""Budget service: area budget recalculation and summary reporting."""

from __future__ import annotations

import calendar
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.budget import AreaBudget
from app.models.work_order import (
    LaborLog,
    WorkOrder,
    WorkOrderPartUsed,
    WorkOrderStatus,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Recalculate area budget
# ---------------------------------------------------------------------------


async def recalculate_area_budget(
    db: AsyncSession,
    org_id: uuid.UUID,
    area_id: uuid.UUID,
    year: int,
    month: int,
    labor_rate: float,
) -> AreaBudget:
    """Recalculate actual spend for a specific area-month from CLOSED work orders.

    Actual spend = sum of parts cost + sum of labor cost.
    Parts cost = sum(quantity * unit_cost) for all WorkOrderPartUsed on CLOSED WOs.
    Labor cost = sum(minutes) / 60 * labor_rate for all LaborLogs on CLOSED WOs.

    The ``AreaBudget`` row is updated (or created if missing) with the
    recalculated ``actual_spend``.
    """
    # Date range for the target month
    _, last_day = calendar.monthrange(year, month)
    month_start = datetime(year, month, 1, tzinfo=timezone.utc)
    month_end = datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc)

    # Find CLOSED work orders in this area/month
    closed_wo_subq = (
        select(WorkOrder.id)
        .where(
            WorkOrder.org_id == org_id,
            WorkOrder.area_id == area_id,
            WorkOrder.status == WorkOrderStatus.CLOSED,
            WorkOrder.closed_at >= month_start,
            WorkOrder.closed_at <= month_end,
        )
        .subquery()
    )

    # Sum parts cost
    parts_cost_result = await db.execute(
        select(
            func.coalesce(
                func.sum(WorkOrderPartUsed.quantity * WorkOrderPartUsed.unit_cost),
                0,
            ).label("parts_cost")
        ).where(
            WorkOrderPartUsed.org_id == org_id,
            WorkOrderPartUsed.work_order_id.in_(select(closed_wo_subq.c.id)),
            WorkOrderPartUsed.unit_cost.isnot(None),
        )
    )
    parts_cost = float(parts_cost_result.scalar() or 0)

    # Sum labor minutes
    labor_minutes_result = await db.execute(
        select(
            func.coalesce(func.sum(LaborLog.minutes), 0).label("total_minutes")
        ).where(
            LaborLog.org_id == org_id,
            LaborLog.work_order_id.in_(select(closed_wo_subq.c.id)),
        )
    )
    total_labor_minutes = int(labor_minutes_result.scalar() or 0)
    labor_cost = (total_labor_minutes / 60.0) * labor_rate

    actual_spend = round(parts_cost + labor_cost, 2)

    # Upsert the budget row
    budget_result = await db.execute(
        select(AreaBudget).where(
            AreaBudget.org_id == org_id,
            AreaBudget.area_id == area_id,
            AreaBudget.year == year,
            AreaBudget.month == month,
        )
    )
    budget = budget_result.scalars().first()

    if budget is None:
        budget = AreaBudget(
            org_id=org_id,
            area_id=area_id,
            year=year,
            month=month,
            budget_amount=0,
            actual_spend=actual_spend,
        )
        db.add(budget)
    else:
        budget.actual_spend = actual_spend

    await db.flush()

    logger.info(
        "Recalculated budget for org=%s area=%s %d-%02d: "
        "parts=%.2f labor=%.2f total=%.2f",
        org_id,
        area_id,
        year,
        month,
        parts_cost,
        labor_cost,
        actual_spend,
    )
    return budget


# ---------------------------------------------------------------------------
# Budget summary
# ---------------------------------------------------------------------------


async def get_budget_summary(
    db: AsyncSession,
    org_id: uuid.UUID,
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return budget vs. actual spend summary by area.

    Filters may include:
        - ``year`` (int)
        - ``month`` (int, optional -- if omitted, all months in the year)
        - ``area_id`` (UUID, optional)
    """
    filters = filters or {}

    conditions = [AreaBudget.org_id == org_id]

    if "year" in filters and filters["year"] is not None:
        conditions.append(AreaBudget.year == filters["year"])
    if "month" in filters and filters["month"] is not None:
        conditions.append(AreaBudget.month == filters["month"])
    if "area_id" in filters and filters["area_id"] is not None:
        conditions.append(AreaBudget.area_id == filters["area_id"])

    stmt = (
        select(
            AreaBudget.area_id,
            AreaBudget.year,
            AreaBudget.month,
            AreaBudget.budget_amount,
            AreaBudget.actual_spend,
        )
        .where(and_(*conditions))
        .order_by(AreaBudget.year, AreaBudget.month, AreaBudget.area_id)
    )
    result = await db.execute(stmt)
    rows = result.all()

    items = []
    total_budget = 0.0
    total_actual = 0.0

    for row in rows:
        budget_amount = float(row.budget_amount) if row.budget_amount else 0.0
        actual_spend = float(row.actual_spend) if row.actual_spend else 0.0
        variance = budget_amount - actual_spend
        variance_pct = round((variance / budget_amount) * 100, 2) if budget_amount else 0.0

        items.append({
            "area_id": str(row.area_id),
            "year": row.year,
            "month": row.month,
            "budget_amount": round(budget_amount, 2),
            "actual_spend": round(actual_spend, 2),
            "variance": round(variance, 2),
            "variance_pct": variance_pct,
            "over_budget": actual_spend > budget_amount and budget_amount > 0,
        })

        total_budget += budget_amount
        total_actual += actual_spend

    total_variance = total_budget - total_actual

    return {
        "items": items,
        "summary": {
            "total_budget": round(total_budget, 2),
            "total_actual": round(total_actual, 2),
            "total_variance": round(total_variance, 2),
            "total_variance_pct": round(
                (total_variance / total_budget) * 100, 2
            ) if total_budget else 0.0,
        },
    }

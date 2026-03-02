"""Budget recalculation Celery tasks."""

import logging

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.budget_tasks.recalculate_area_budget")
def recalculate_area_budget(org_id: str, area_id: str, year: int, month: int) -> dict:
    """Recalculate actual spend for an area budget. Triggered on WO close."""
    import asyncio
    return asyncio.get_event_loop().run_until_complete(
        _recalculate_async(org_id, area_id, year, month)
    )


async def _recalculate_async(org_id_str, area_id_str, year, month):
    import uuid
    from decimal import Decimal
    from sqlalchemy import select, func, and_, extract
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from app.core.config import settings
    from app.models.work_order import WorkOrder, WorkOrderStatus, WorkOrderPartUsed, LaborLog
    from app.models.budget import AreaBudget
    from app.models.org import Organization

    engine = create_async_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    org_id = uuid.UUID(org_id_str)
    area_id = uuid.UUID(area_id_str)

    async with session_factory() as db:
        # Get org config for labor rate
        org = await db.get(Organization, org_id)
        labor_rate = Decimal("75.00")
        if org and org.config:
            labor_rate = Decimal(str(org.config.get("default_labor_rate_per_hour", 75.00)))

        # Sum parts cost for closed WOs in this area+month
        parts_result = await db.execute(
            select(func.coalesce(func.sum(WorkOrderPartUsed.unit_cost * WorkOrderPartUsed.quantity), 0))
            .join(WorkOrder, WorkOrderPartUsed.work_order_id == WorkOrder.id)
            .where(
                WorkOrder.org_id == org_id,
                WorkOrder.area_id == area_id,
                WorkOrder.status == WorkOrderStatus.CLOSED,
                extract("year", WorkOrder.closed_at) == year,
                extract("month", WorkOrder.closed_at) == month,
            )
        )
        parts_cost = Decimal(str(parts_result.scalar() or 0))

        # Sum labor cost
        labor_result = await db.execute(
            select(func.coalesce(func.sum(LaborLog.minutes), 0))
            .join(WorkOrder, LaborLog.work_order_id == WorkOrder.id)
            .where(
                WorkOrder.org_id == org_id,
                WorkOrder.area_id == area_id,
                WorkOrder.status == WorkOrderStatus.CLOSED,
                extract("year", WorkOrder.closed_at) == year,
                extract("month", WorkOrder.closed_at) == month,
            )
        )
        total_minutes = int(labor_result.scalar() or 0)
        labor_cost = (Decimal(str(total_minutes)) / Decimal("60")) * labor_rate

        actual_spend = parts_cost + labor_cost

        # Upsert AreaBudget
        existing = await db.execute(
            select(AreaBudget).where(
                AreaBudget.org_id == org_id,
                AreaBudget.area_id == area_id,
                AreaBudget.year == year,
                AreaBudget.month == month,
            )
        )
        budget = existing.scalar_one_or_none()
        if budget:
            budget.actual_spend = actual_spend
        else:
            budget = AreaBudget(
                org_id=org_id,
                area_id=area_id,
                year=year,
                month=month,
                budget_amount=Decimal("0"),
                actual_spend=actual_spend,
            )
            db.add(budget)

        await db.commit()

    await engine.dispose()
    logger.info("Budget recalculated: org=%s area=%s %d/%d spend=%s", org_id, area_id, year, month, actual_spend)
    return {"actual_spend": str(actual_spend)}

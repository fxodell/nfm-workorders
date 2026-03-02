"""Dashboard rollup precomputation Celery tasks."""

import json
import logging

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.rollup_tasks.precompute_dashboard_rollups")
def precompute_dashboard_rollups() -> dict:
    """Precompute dashboard rollups every 2 minutes. Stored in Redis."""
    import asyncio
    return asyncio.get_event_loop().run_until_complete(_precompute_async())


async def _precompute_async():
    import uuid
    from sqlalchemy import select, func, and_, case
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    import redis.asyncio as aioredis
    from app.core.config import settings
    from app.models.work_order import WorkOrder, WorkOrderStatus, WorkOrderPriority
    from app.models.area import Area
    from app.models.org import Organization

    engine = create_async_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)

    rollups_created = 0

    async with session_factory() as db:
        # Get all orgs
        orgs = (await db.execute(select(Organization))).scalars().all()

        for org in orgs:
            areas = (await db.execute(
                select(Area).where(Area.org_id == org.id, Area.is_active.is_(True))
            )).scalars().all()

            for area in areas:
                # Count open WOs by priority
                active_statuses = [
                    WorkOrderStatus.NEW, WorkOrderStatus.ASSIGNED,
                    WorkOrderStatus.ACCEPTED, WorkOrderStatus.IN_PROGRESS,
                    WorkOrderStatus.WAITING_ON_OPS, WorkOrderStatus.WAITING_ON_PARTS,
                    WorkOrderStatus.ESCALATED,
                ]

                result = await db.execute(
                    select(
                        WorkOrder.priority,
                        func.count(WorkOrder.id),
                    )
                    .where(
                        WorkOrder.org_id == org.id,
                        WorkOrder.area_id == area.id,
                        WorkOrder.status.in_(active_statuses),
                    )
                    .group_by(WorkOrder.priority)
                )
                priority_counts = {row[0].value if hasattr(row[0], 'value') else str(row[0]): row[1] for row in result.all()}

                # Count escalated
                escalated = await db.execute(
                    select(func.count(WorkOrder.id)).where(
                        WorkOrder.org_id == org.id,
                        WorkOrder.area_id == area.id,
                        WorkOrder.status == WorkOrderStatus.ESCALATED,
                    )
                )
                escalated_count = escalated.scalar() or 0

                # Count safety flags
                safety = await db.execute(
                    select(func.count(WorkOrder.id)).where(
                        WorkOrder.org_id == org.id,
                        WorkOrder.area_id == area.id,
                        WorkOrder.safety_flag.is_(True),
                        WorkOrder.status.in_(active_statuses),
                    )
                )
                safety_count = safety.scalar() or 0

                rollup = {
                    "area_id": str(area.id),
                    "area_name": area.name,
                    "priority_counts": priority_counts,
                    "escalated_count": escalated_count,
                    "safety_flag_count": safety_count,
                }

                key = f"rollup:org:{org.id}:area:{area.id}"
                await r.set(key, json.dumps(rollup, default=str), ex=300)  # 5 min TTL
                rollups_created += 1

    await r.close()
    await engine.dispose()
    logger.info("Dashboard rollups precomputed: %d", rollups_created)
    return {"rollups_created": rollups_created}

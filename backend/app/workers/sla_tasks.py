"""SLA breach detection and escalation Celery tasks."""

import logging
from datetime import datetime, timezone

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.sla_tasks.check_sla_breaches")
def check_sla_breaches() -> dict:
    """Check for SLA breaches every 5 minutes.

    Runs synchronously in Celery worker with its own DB session.
    """
    import asyncio
    return asyncio.get_event_loop().run_until_complete(_check_sla_breaches_async())


async def _check_sla_breaches_async() -> dict:
    from sqlalchemy import select, and_
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from app.core.config import settings
    from app.models.work_order import WorkOrder, WorkOrderStatus, TimelineEvent
    from app.models.sla import SLAEvent, SLAEventType

    engine = create_async_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    now = datetime.now(timezone.utc)
    breaches = {"ack": 0, "first_update": 0, "resolve": 0}

    async with session_factory() as db:
        # ACK breach: past ack_deadline, not yet accepted
        result = await db.execute(
            select(WorkOrder).where(
                WorkOrder.ack_deadline < now,
                WorkOrder.accepted_at.is_(None),
                WorkOrder.status.in_([WorkOrderStatus.NEW, WorkOrderStatus.ASSIGNED]),
            )
        )
        ack_breached = result.scalars().all()
        for wo in ack_breached:
            existing = await db.execute(
                select(SLAEvent).where(
                    SLAEvent.work_order_id == wo.id,
                    SLAEvent.event_type == SLAEventType.ACK_BREACH,
                )
            )
            if not existing.scalar_one_or_none():
                sla_event = SLAEvent(
                    work_order_id=wo.id,
                    org_id=wo.org_id,
                    event_type=SLAEventType.ACK_BREACH,
                    triggered_at=now,
                )
                db.add(sla_event)
                breaches["ack"] += 1

        # First update breach: past first_update_deadline with no user timeline events
        result = await db.execute(
            select(WorkOrder).where(
                WorkOrder.first_update_deadline < now,
                WorkOrder.status.notin_([
                    WorkOrderStatus.RESOLVED,
                    WorkOrderStatus.VERIFIED,
                    WorkOrderStatus.CLOSED,
                ]),
            )
        )
        update_candidates = result.scalars().all()
        for wo in update_candidates:
            # Check if any user-created timeline event exists
            user_events = await db.execute(
                select(TimelineEvent).where(
                    TimelineEvent.work_order_id == wo.id,
                    TimelineEvent.user_id.isnot(None),
                    TimelineEvent.created_at > wo.created_at,
                )
            )
            if not user_events.scalar_one_or_none():
                existing = await db.execute(
                    select(SLAEvent).where(
                        SLAEvent.work_order_id == wo.id,
                        SLAEvent.event_type == SLAEventType.FIRST_UPDATE_BREACH,
                    )
                )
                if not existing.scalar_one_or_none():
                    sla_event = SLAEvent(
                        work_order_id=wo.id,
                        org_id=wo.org_id,
                        event_type=SLAEventType.FIRST_UPDATE_BREACH,
                        triggered_at=now,
                    )
                    db.add(sla_event)
                    breaches["first_update"] += 1

        # Resolve breach: past due_at, not resolved/verified/closed, not already escalated
        result = await db.execute(
            select(WorkOrder).where(
                WorkOrder.due_at < now,
                WorkOrder.status.notin_([
                    WorkOrderStatus.RESOLVED,
                    WorkOrderStatus.VERIFIED,
                    WorkOrderStatus.CLOSED,
                    WorkOrderStatus.ESCALATED,
                ]),
                WorkOrder.escalated_at.is_(None),
            )
        )
        resolve_breached = result.scalars().all()
        for wo in resolve_breached:
            existing = await db.execute(
                select(SLAEvent).where(
                    SLAEvent.work_order_id == wo.id,
                    SLAEvent.event_type == SLAEventType.RESOLVE_BREACH,
                )
            )
            if not existing.scalar_one_or_none():
                wo.status = WorkOrderStatus.ESCALATED
                wo.escalated_at = now
                sla_event = SLAEvent(
                    work_order_id=wo.id,
                    org_id=wo.org_id,
                    event_type=SLAEventType.RESOLVE_BREACH,
                    triggered_at=now,
                )
                db.add(sla_event)

                # Create timeline event
                timeline = TimelineEvent(
                    work_order_id=wo.id,
                    org_id=wo.org_id,
                    user_id=None,
                    event_type="STATUS_CHANGE",
                    payload={
                        "old_status": wo.status.value if hasattr(wo.status, 'value') else str(wo.status),
                        "new_status": "ESCALATED",
                        "reason": "SLA resolve deadline breached",
                    },
                )
                db.add(timeline)
                breaches["resolve"] += 1

        await db.commit()

    await engine.dispose()
    logger.info("SLA breach check complete: %s", breaches)
    return breaches

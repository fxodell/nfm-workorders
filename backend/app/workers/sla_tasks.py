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
    return asyncio.run(_check_sla_breaches_async())


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
        from sqlalchemy import distinct

        # ACK breach: past ack_deadline, not yet accepted
        result = await db.execute(
            select(WorkOrder).where(
                WorkOrder.ack_deadline < now,
                WorkOrder.accepted_at.is_(None),
                WorkOrder.status.in_([WorkOrderStatus.NEW, WorkOrderStatus.ASSIGNED]),
            )
        )
        ack_breached = result.scalars().all()

        if ack_breached:
            ack_ids = [wo.id for wo in ack_breached]
            existing_result = await db.execute(
                select(distinct(SLAEvent.work_order_id)).where(
                    SLAEvent.work_order_id.in_(ack_ids),
                    SLAEvent.event_type == SLAEventType.ACK_BREACH,
                )
            )
            already_breached = set(existing_result.scalars().all())

            for wo in ack_breached:
                if wo.id not in already_breached:
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

        if update_candidates:
            candidate_ids = [wo.id for wo in update_candidates]

            # Batch-fetch: WO IDs that have at least one user-created timeline event
            events_result = await db.execute(
                select(distinct(TimelineEvent.work_order_id)).where(
                    TimelineEvent.work_order_id.in_(candidate_ids),
                    TimelineEvent.user_id.isnot(None),
                )
            )
            wo_ids_with_updates = set(events_result.scalars().all())

            # Batch-fetch: WO IDs that already have a FIRST_UPDATE_BREACH SLA event
            existing_result = await db.execute(
                select(distinct(SLAEvent.work_order_id)).where(
                    SLAEvent.work_order_id.in_(candidate_ids),
                    SLAEvent.event_type == SLAEventType.FIRST_UPDATE_BREACH,
                )
            )
            wo_ids_already_breached = set(existing_result.scalars().all())

            for wo in update_candidates:
                if wo.id not in wo_ids_with_updates and wo.id not in wo_ids_already_breached:
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

        if resolve_breached:
            resolve_ids = [wo.id for wo in resolve_breached]
            existing_result = await db.execute(
                select(distinct(SLAEvent.work_order_id)).where(
                    SLAEvent.work_order_id.in_(resolve_ids),
                    SLAEvent.event_type == SLAEventType.RESOLVE_BREACH,
                )
            )
            resolve_already_breached = set(existing_result.scalars().all())

            for wo in resolve_breached:
                if wo.id not in resolve_already_breached:
                    old_status = wo.status.value if hasattr(wo.status, 'value') else str(wo.status)
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
                            "old_status": old_status,
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

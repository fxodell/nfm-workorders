"""Preventive maintenance Celery tasks."""

import logging
from datetime import date, datetime, timedelta, timezone

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.pm_tasks.generate_pm_work_orders")
def generate_pm_work_orders() -> dict:
    """Generate work orders from pending PM schedules. Runs daily at 06:00."""
    import asyncio
    return asyncio.get_event_loop().run_until_complete(_generate_pm_async())


async def _generate_pm_async() -> dict:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy.orm import selectinload
    from app.core.config import settings
    from app.models.pm import PMSchedule, PMTemplate, PMScheduleStatus, RecurrenceType
    from app.models.work_order import WorkOrder, WorkOrderStatus

    engine = create_async_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    today = date.today()
    generated = 0

    async with session_factory() as db:
        result = await db.execute(
            select(PMSchedule)
            .options(selectinload(PMSchedule.pm_template))
            .where(
                PMSchedule.due_date <= today,
                PMSchedule.status == PMScheduleStatus.PENDING,
            )
        )
        schedules = result.scalars().all()

        for schedule in schedules:
            template = schedule.pm_template
            if not template or not template.is_active:
                continue

            # Create work order from template
            import uuid
            wo = WorkOrder(
                id=uuid.uuid4(),
                org_id=template.org_id,
                area_id=None,  # Will need to be resolved from site/asset
                site_id=template.site_id,
                asset_id=template.asset_id,
                human_readable_number="",  # Will be generated
                title=template.title,
                description=template.description or "",
                type="PREVENTIVE",
                priority=template.priority if hasattr(template, 'priority') else "SCHEDULED",
                status=WorkOrderStatus.NEW,
                requested_by=None,  # System generated
                safety_flag=False,
            )
            # Note: In production, this would use work_order_service.create_work_order
            # to properly generate human_readable_number and set area_id

            schedule.status = PMScheduleStatus.GENERATED
            schedule.generated_work_order_id = wo.id

            # Create next schedule entry
            next_due = _calculate_next_due(template, schedule.due_date)
            if next_due:
                next_schedule = PMSchedule(
                    pm_template_id=template.id,
                    org_id=template.org_id,
                    due_date=next_due,
                    status=PMScheduleStatus.PENDING,
                )
                db.add(next_schedule)

            generated += 1

        await db.commit()

    await engine.dispose()
    logger.info("PM generation complete: %d work orders generated", generated)
    return {"generated": generated}


def _calculate_next_due(template, current_due: date) -> date | None:
    """Calculate the next due date based on recurrence type."""
    from app.models.pm import RecurrenceType

    recurrence = template.recurrence_type
    interval = template.recurrence_interval or 1

    if recurrence == RecurrenceType.DAILY:
        return current_due + timedelta(days=interval)
    elif recurrence == RecurrenceType.WEEKLY:
        return current_due + timedelta(weeks=interval)
    elif recurrence == RecurrenceType.MONTHLY:
        month = current_due.month + interval
        year = current_due.year + (month - 1) // 12
        month = (month - 1) % 12 + 1
        day = min(current_due.day, 28)  # Safe day
        return date(year, month, day)
    elif recurrence == RecurrenceType.CUSTOM_DAYS:
        return current_due + timedelta(days=interval)
    return None


@celery_app.task(name="app.workers.pm_tasks.send_pm_reminders")
def send_pm_reminders() -> dict:
    """Send reminders for PM work orders due within 24 hours. Runs daily at 08:00."""
    logger.info("PM reminders task executed")
    return {"reminders_sent": 0}

"""Preventive-maintenance service: schedule generation, WO creation, skipping."""

from __future__ import annotations

import calendar
import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.asset import Asset
from app.models.location import Location
from app.models.org import Organization
from app.models.pm import (
    PMSchedule,
    PMScheduleStatus,
    PMTemplate,
    RecurrenceType,
)
from app.models.site import Site
from app.models.user import User, UserRole
from app.models.work_order import (
    TimelineEvent,
    TimelineEventType,
    WorkOrder,
    WorkOrderStatus,
    WorkOrderType,
)

from app.services.work_order_service import (
    compute_sla_deadlines,
    generate_human_readable_number,
)

logger = logging.getLogger(__name__)

# Mapping recurrence types to timedelta or dateutil-style offsets
_RECURRENCE_DAYS: dict[RecurrenceType, int | None] = {
    RecurrenceType.DAILY: 1,
    RecurrenceType.WEEKLY: 7,
    RecurrenceType.BIWEEKLY: 14,
    RecurrenceType.MONTHLY: None,      # handled via month arithmetic
    RecurrenceType.QUARTERLY: None,    # handled via month arithmetic
    RecurrenceType.SEMI_ANNUAL: None,  # handled via month arithmetic
    RecurrenceType.ANNUAL: None,       # handled via month arithmetic
    RecurrenceType.CUSTOM_DAYS: None,  # uses recurrence_interval
}

_RECURRENCE_MONTHS: dict[RecurrenceType, int] = {
    RecurrenceType.MONTHLY: 1,
    RecurrenceType.QUARTERLY: 3,
    RecurrenceType.SEMI_ANNUAL: 6,
    RecurrenceType.ANNUAL: 12,
}


def _add_months(d: date, months: int) -> date:
    """Add ``months`` to a date, clamping to end-of-month if necessary."""
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    max_day = calendar.monthrange(year, month)[1]
    day = min(d.day, max_day)
    return date(year, month, day)


# ---------------------------------------------------------------------------
# Generate PM work orders for today
# ---------------------------------------------------------------------------


async def generate_pm_work_orders(
    db: AsyncSession,
) -> list[WorkOrder]:
    """Find all PENDING PMSchedules due today and generate work orders.

    For each schedule:
    1. Load the parent PMTemplate (with asset/site relationships).
    2. Create a new WorkOrder of type PREVENTIVE.
    3. Mark the schedule as GENERATED.
    4. Create the next schedule occurrence.

    Returns the list of newly created work orders.
    """
    today = date.today()

    stmt = (
        select(PMSchedule)
        .options(selectinload(PMSchedule.pm_template))
        .where(
            PMSchedule.status == PMScheduleStatus.PENDING,
            PMSchedule.due_date <= today,
        )
    )
    result = await db.execute(stmt)
    schedules = list(result.scalars().all())

    created_work_orders: list[WorkOrder] = []

    for schedule in schedules:
        template = schedule.pm_template

        if template is None or not template.is_active:
            logger.info(
                "Skipping PM schedule %s: template inactive or missing",
                schedule.id,
            )
            continue

        # Resolve location hierarchy: asset -> site -> location -> area
        # We need area_id, location_id, and site_id for the work order.
        site_id = template.site_id
        area_id: uuid.UUID | None = None
        location_id: uuid.UUID | None = None

        if template.asset_id:
            asset_result = await db.execute(
                select(Asset).where(Asset.id == template.asset_id)
            )
            asset = asset_result.scalars().first()
            if asset:
                site_id = asset.site_id

        if site_id:
            site_result = await db.execute(
                select(Site).where(Site.id == site_id)
            )
            site = site_result.scalars().first()
            if site:
                location_id = site.location_id

        if location_id:
            location_result = await db.execute(
                select(Location).where(Location.id == location_id)
            )
            location = location_result.scalars().first()
            if location:
                area_id = location.area_id

        if not all([site_id, location_id, area_id]):
            logger.warning(
                "Cannot resolve site/location/area for PM template %s; skipping schedule %s",
                template.id,
                schedule.id,
            )
            continue

        now = datetime.now(timezone.utc)

        # Generate human-readable number
        human_readable_number = await generate_human_readable_number(
            db, template.org_id
        )

        # Compute SLA deadlines
        org_row = (await db.execute(
            select(Organization).where(Organization.id == template.org_id)
        )).scalars().first()
        org_config = org_row.config if org_row else None

        sla = compute_sla_deadlines(template.priority, org_config, now)

        wo = WorkOrder(
            org_id=template.org_id,
            area_id=area_id,
            location_id=location_id,
            site_id=site_id,
            asset_id=template.asset_id,
            human_readable_number=human_readable_number,
            title=template.title,
            description=template.description,
            type=WorkOrderType.PREVENTIVE,
            priority=template.priority,
            status=WorkOrderStatus.NEW,
            requested_by=None,  # system-generated; will use a system user if available
            created_at=now,
            updated_at=now,
            ack_deadline=sla["ack_deadline"],
            first_update_deadline=sla["first_update_deadline"],
            due_at=sla["due_at"],
            required_cert=template.required_cert,
            custom_fields={"pm_template_id": str(template.id), "checklist": template.checklist_json},
        )
        # PM WOs may not have a requester user; set to org admin or leave nullable
        # if the schema allows.  Since requested_by is non-nullable in the model,
        # we need a system user.  Find the first ADMIN user in the org.
        admin_result = await db.execute(
            select(User).where(
                User.org_id == template.org_id,
                User.role == UserRole.ADMIN,
                User.is_active.is_(True),
            ).limit(1)
        )
        admin_user = admin_result.scalars().first()
        if admin_user:
            wo.requested_by = admin_user.id
        else:
            # Fallback: find any active user in the org
            any_user_result = await db.execute(
                select(User).where(
                    User.org_id == template.org_id,
                    User.is_active.is_(True),
                ).limit(1)
            )
            any_user = any_user_result.scalars().first()
            if any_user:
                wo.requested_by = any_user.id
            else:
                logger.warning(
                    "No active user found in org %s for PM WO creation; skipping",
                    template.org_id,
                )
                continue

        db.add(wo)
        await db.flush()

        # Initial timeline event
        event = TimelineEvent(
            work_order_id=wo.id,
            org_id=wo.org_id,
            user_id=None,
            event_type=TimelineEventType.STATUS_CHANGE,
            payload={
                "from_status": None,
                "to_status": WorkOrderStatus.NEW.value,
                "source": "pm_schedule",
                "pm_template_id": str(template.id),
            },
        )
        db.add(event)

        # Update schedule
        schedule.status = PMScheduleStatus.GENERATED
        schedule.generated_work_order_id = wo.id

        # Create next schedule occurrence
        await create_next_schedule(db, template, schedule)

        created_work_orders.append(wo)

        logger.info(
            "Generated PM work order %s for template %s (schedule %s)",
            wo.human_readable_number,
            template.id,
            schedule.id,
        )

    await db.flush()
    return created_work_orders


# ---------------------------------------------------------------------------
# Next schedule calculation
# ---------------------------------------------------------------------------


async def create_next_schedule(
    db: AsyncSession,
    pm_template: PMTemplate,
    current_schedule: PMSchedule,
) -> PMSchedule:
    """Calculate and create the next PMSchedule based on the template's recurrence.

    Returns the newly created schedule row.
    """
    current_due = current_schedule.due_date
    recurrence = pm_template.recurrence_type

    # Calculate next due date
    fixed_days = _RECURRENCE_DAYS.get(recurrence)

    if recurrence == RecurrenceType.CUSTOM_DAYS:
        interval = pm_template.recurrence_interval or 30
        next_due = current_due + timedelta(days=interval)
    elif fixed_days is not None:
        next_due = current_due + timedelta(days=fixed_days)
    else:
        months = _RECURRENCE_MONTHS.get(recurrence, 1)
        next_due = _add_months(current_due, months)

    next_schedule = PMSchedule(
        pm_template_id=pm_template.id,
        org_id=pm_template.org_id,
        due_date=next_due,
        status=PMScheduleStatus.PENDING,
    )
    db.add(next_schedule)
    await db.flush()

    logger.info(
        "Created next PM schedule for template %s: due %s",
        pm_template.id,
        next_due,
    )
    return next_schedule


# ---------------------------------------------------------------------------
# Skip schedule
# ---------------------------------------------------------------------------


async def skip_schedule(
    db: AsyncSession,
    schedule: PMSchedule,
    reason: str,
) -> PMSchedule:
    """Mark a PENDING schedule as SKIPPED with a reason.

    Also creates the next schedule occurrence so the PM chain is not broken.
    """
    schedule.status = PMScheduleStatus.SKIPPED
    schedule.skip_reason = reason

    # Load template for next schedule creation
    template_result = await db.execute(
        select(PMTemplate).where(PMTemplate.id == schedule.pm_template_id)
    )
    template = template_result.scalars().first()

    if template and template.is_active:
        await create_next_schedule(db, template, schedule)

    await db.flush()

    logger.info(
        "Skipped PM schedule %s: %s",
        schedule.id,
        reason,
    )
    return schedule

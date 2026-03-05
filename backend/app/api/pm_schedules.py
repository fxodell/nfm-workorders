"""Preventive maintenance schedule routes: list, skip, generate-now."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import (
    get_current_active_user,
    require_permission,
    verify_org_ownership,
)
from app.models.org import Organization, WOCounter
from app.models.pm import PMSchedule, PMScheduleStatus, PMTemplate
from app.models.user import User
from app.models.work_order import (
    TimelineEvent,
    TimelineEventType,
    WorkOrder,
    WorkOrderStatus,
)
from app.schemas.common import MessageResponse
from app.schemas.pm import PMScheduleResponse, PMScheduleSkip

router = APIRouter(prefix="/pm-schedules", tags=["pm-schedules"])


# ── GET / ──────────────────────────────────────────────────────────────

@router.get("", response_model=list[PMScheduleResponse])
async def list_pm_schedules(
    template_id: Optional[uuid.UUID] = Query(None),
    pm_status: Optional[str] = Query(None, alias="status"),
    due_from: Optional[date] = Query(None),
    due_to: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List PM schedule instances with optional filters."""
    query = select(PMSchedule).where(PMSchedule.org_id == current_user.org_id)

    if template_id:
        query = query.where(PMSchedule.pm_template_id == template_id)
    if pm_status:
        query = query.where(PMSchedule.status == pm_status)
    if due_from:
        query = query.where(PMSchedule.due_date >= due_from)
    if due_to:
        query = query.where(PMSchedule.due_date <= due_to)

    query = query.order_by(PMSchedule.due_date.desc())
    result = await db.execute(query)
    return result.scalars().all()


# ── POST /{id}/skip ────────────────────────────────────────────────────

@router.post("/{schedule_id}/skip", response_model=PMScheduleResponse)
async def skip_pm_schedule(
    schedule_id: uuid.UUID,
    body: PMScheduleSkip,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("CAN_MANAGE_PM_TEMPLATES")),
):
    """Skip a pending PM schedule instance."""
    schedule = await db.get(PMSchedule, schedule_id)
    if not schedule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PM schedule not found")
    await verify_org_ownership(schedule, current_user)

    if schedule.status != PMScheduleStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only PENDING schedules can be skipped",
        )

    schedule.status = PMScheduleStatus.SKIPPED
    schedule.skip_reason = body.skip_reason
    await db.flush()
    return schedule


# ── POST /{id}/generate-now ────────────────────────────────────────────

@router.post("/{schedule_id}/generate-now", response_model=PMScheduleResponse)
async def generate_pm_now(
    schedule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("CAN_MANAGE_PM_TEMPLATES")),
):
    """Generate a work order from a PM schedule immediately."""
    schedule = await db.get(PMSchedule, schedule_id)
    if not schedule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PM schedule not found")
    await verify_org_ownership(schedule, current_user)

    if schedule.status != PMScheduleStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only PENDING schedules can generate work orders",
        )

    # Load the PM template
    template = await db.get(PMTemplate, schedule.pm_template_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associated PM template not found",
        )

    # We need site and location to create the WO
    if not template.site_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="PM template must have a site_id to generate a work order",
        )

    from app.models.site import Site
    site = await db.get(Site, template.site_id)
    if not site:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")

    from app.models.location import Location
    location = await db.get(Location, site.location_id)
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")

    # Generate human-readable number
    year = datetime.now(timezone.utc).year
    result = await db.execute(
        select(WOCounter).where(WOCounter.org_id == current_user.org_id, WOCounter.year == year)
    )
    counter = result.scalars().first()
    if not counter:
        counter = WOCounter(org_id=current_user.org_id, year=year, counter=0)
        db.add(counter)
        await db.flush()
    counter.counter += 1
    human_readable = f"WO-{year}-{counter.counter:06d}"

    # Create work order
    wo = WorkOrder(
        org_id=current_user.org_id,
        area_id=location.area_id,
        location_id=site.location_id,
        site_id=site.id,
        asset_id=template.asset_id,
        human_readable_number=human_readable,
        title=f"[PM] {template.title}",
        description=template.description or f"Preventive maintenance: {template.title}",
        type="PREVENTIVE",
        priority=template.priority,
        status=WorkOrderStatus.NEW,
        requested_by=current_user.id,
        required_cert=template.required_cert,
    )
    db.add(wo)
    await db.flush()

    # Create timeline event
    event = TimelineEvent(
        work_order_id=wo.id,
        org_id=wo.org_id,
        user_id=current_user.id,
        event_type=TimelineEventType.CREATED,
        payload={"source": "PM_SCHEDULE", "pm_template_id": str(template.id)},
    )
    db.add(event)

    # Update schedule
    schedule.status = PMScheduleStatus.GENERATED
    schedule.generated_work_order_id = wo.id
    await db.flush()

    return schedule

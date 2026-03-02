"""Reporting service: aggregated work-order metrics, SLA compliance, costs."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import and_, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole
from app.models.work_order import (
    LaborLog,
    WorkOrder,
    WorkOrderPartUsed,
    WorkOrderStatus,
)
from app.models.pm import PMSchedule, PMScheduleStatus
from app.models.sla import SLAEvent, SLAEventType

logger = logging.getLogger(__name__)

# Statuses considered "completed"
_COMPLETED_STATUSES = {
    WorkOrderStatus.RESOLVED,
    WorkOrderStatus.VERIFIED,
    WorkOrderStatus.CLOSED,
}


def _apply_date_filters(
    stmt: Any,
    model: Any,
    filters: dict[str, Any],
) -> Any:
    """Apply common date-range and area filters to a query."""
    if "date_from" in filters and filters["date_from"] is not None:
        stmt = stmt.where(model.created_at >= filters["date_from"])
    if "date_to" in filters and filters["date_to"] is not None:
        stmt = stmt.where(model.created_at <= filters["date_to"])
    if "area_id" in filters and filters["area_id"] is not None:
        stmt = stmt.where(model.area_id == filters["area_id"])
    if "site_id" in filters and filters["site_id"] is not None:
        stmt = stmt.where(model.site_id == filters["site_id"])
    return stmt


# ---------------------------------------------------------------------------
# Work-order report
# ---------------------------------------------------------------------------


async def get_work_order_report(
    db: AsyncSession,
    org_id: uuid.UUID,
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return aggregated work-order counts by status, priority, and type.

    Filters may include ``date_from``, ``date_to``, ``area_id``, ``site_id``.
    """
    filters = filters or {}

    # Status breakdown
    status_stmt = (
        select(
            WorkOrder.status,
            func.count().label("count"),
        )
        .where(WorkOrder.org_id == org_id)
        .group_by(WorkOrder.status)
    )
    status_stmt = _apply_date_filters(status_stmt, WorkOrder, filters)
    status_result = await db.execute(status_stmt)
    by_status = {row.status.value: row.count for row in status_result.all()}

    # Priority breakdown
    priority_stmt = (
        select(
            WorkOrder.priority,
            func.count().label("count"),
        )
        .where(WorkOrder.org_id == org_id)
        .group_by(WorkOrder.priority)
    )
    priority_stmt = _apply_date_filters(priority_stmt, WorkOrder, filters)
    priority_result = await db.execute(priority_stmt)
    by_priority = {row.priority.value: row.count for row in priority_result.all()}

    # Type breakdown
    type_stmt = (
        select(
            WorkOrder.type,
            func.count().label("count"),
        )
        .where(WorkOrder.org_id == org_id)
        .group_by(WorkOrder.type)
    )
    type_stmt = _apply_date_filters(type_stmt, WorkOrder, filters)
    type_result = await db.execute(type_stmt)
    by_type = {row.type.value: row.count for row in type_result.all()}

    # Total count
    total_stmt = select(func.count()).select_from(WorkOrder).where(WorkOrder.org_id == org_id)
    total_stmt = _apply_date_filters(total_stmt, WorkOrder, filters)
    total = (await db.execute(total_stmt)).scalar() or 0

    # Safety-flagged count
    safety_stmt = (
        select(func.count())
        .select_from(WorkOrder)
        .where(WorkOrder.org_id == org_id, WorkOrder.safety_flag.is_(True))
    )
    safety_stmt = _apply_date_filters(safety_stmt, WorkOrder, filters)
    safety_count = (await db.execute(safety_stmt)).scalar() or 0

    return {
        "total": total,
        "by_status": by_status,
        "by_priority": by_priority,
        "by_type": by_type,
        "safety_flagged": safety_count,
    }


# ---------------------------------------------------------------------------
# Response times
# ---------------------------------------------------------------------------


async def get_response_times(
    db: AsyncSession,
    org_id: uuid.UUID,
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Calculate average response and resolution times in minutes.

    - Response time: ``created_at`` to ``accepted_at``
    - Resolution time: ``created_at`` to ``resolved_at``

    Only considers work orders that have the relevant timestamps set.
    """
    filters = filters or {}

    # Avg response time (in seconds, converted to minutes)
    response_stmt = (
        select(
            func.avg(
                extract("epoch", WorkOrder.accepted_at) - extract("epoch", WorkOrder.created_at)
            ).label("avg_response_seconds"),
            func.count().label("count"),
        )
        .where(
            WorkOrder.org_id == org_id,
            WorkOrder.accepted_at.isnot(None),
        )
    )
    response_stmt = _apply_date_filters(response_stmt, WorkOrder, filters)
    response_result = (await db.execute(response_stmt)).first()

    avg_response_minutes = None
    if response_result and response_result.avg_response_seconds:
        avg_response_minutes = round(float(response_result.avg_response_seconds) / 60.0, 2)

    # Avg resolution time
    resolution_stmt = (
        select(
            func.avg(
                extract("epoch", WorkOrder.resolved_at) - extract("epoch", WorkOrder.created_at)
            ).label("avg_resolve_seconds"),
            func.count().label("count"),
        )
        .where(
            WorkOrder.org_id == org_id,
            WorkOrder.resolved_at.isnot(None),
        )
    )
    resolution_stmt = _apply_date_filters(resolution_stmt, WorkOrder, filters)
    resolution_result = (await db.execute(resolution_stmt)).first()

    avg_resolution_minutes = None
    if resolution_result and resolution_result.avg_resolve_seconds:
        avg_resolution_minutes = round(float(resolution_result.avg_resolve_seconds) / 60.0, 2)

    return {
        "avg_response_minutes": avg_response_minutes,
        "response_count": response_result.count if response_result else 0,
        "avg_resolution_minutes": avg_resolution_minutes,
        "resolution_count": resolution_result.count if resolution_result else 0,
    }


# ---------------------------------------------------------------------------
# SLA compliance
# ---------------------------------------------------------------------------


async def get_sla_compliance(
    db: AsyncSession,
    org_id: uuid.UUID,
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Calculate SLA compliance percentages.

    Compliance is measured as:
    - Ack compliance: % of WOs acknowledged before ``ack_deadline``
    - Resolution compliance: % of WOs resolved before ``due_at``
    - Overall compliance: % of WOs with no SLA breach events
    """
    filters = filters or {}

    # Total WOs with SLA deadlines
    total_stmt = (
        select(func.count())
        .select_from(WorkOrder)
        .where(
            WorkOrder.org_id == org_id,
            WorkOrder.ack_deadline.isnot(None),
        )
    )
    total_stmt = _apply_date_filters(total_stmt, WorkOrder, filters)
    total_with_sla = (await db.execute(total_stmt)).scalar() or 0

    if total_with_sla == 0:
        return {
            "total_with_sla": 0,
            "ack_compliance_pct": 100.0,
            "resolve_compliance_pct": 100.0,
            "overall_compliance_pct": 100.0,
        }

    # Ack compliance: accepted_at <= ack_deadline OR accepted_at IS NOT NULL
    ack_met_stmt = (
        select(func.count())
        .select_from(WorkOrder)
        .where(
            WorkOrder.org_id == org_id,
            WorkOrder.ack_deadline.isnot(None),
            WorkOrder.accepted_at.isnot(None),
            WorkOrder.accepted_at <= WorkOrder.ack_deadline,
        )
    )
    ack_met_stmt = _apply_date_filters(ack_met_stmt, WorkOrder, filters)
    ack_met = (await db.execute(ack_met_stmt)).scalar() or 0

    # Resolve compliance: resolved_at <= due_at
    resolve_total_stmt = (
        select(func.count())
        .select_from(WorkOrder)
        .where(
            WorkOrder.org_id == org_id,
            WorkOrder.due_at.isnot(None),
            WorkOrder.resolved_at.isnot(None),
        )
    )
    resolve_total_stmt = _apply_date_filters(resolve_total_stmt, WorkOrder, filters)
    resolve_total = (await db.execute(resolve_total_stmt)).scalar() or 0

    resolve_met_stmt = (
        select(func.count())
        .select_from(WorkOrder)
        .where(
            WorkOrder.org_id == org_id,
            WorkOrder.due_at.isnot(None),
            WorkOrder.resolved_at.isnot(None),
            WorkOrder.resolved_at <= WorkOrder.due_at,
        )
    )
    resolve_met_stmt = _apply_date_filters(resolve_met_stmt, WorkOrder, filters)
    resolve_met = (await db.execute(resolve_met_stmt)).scalar() or 0

    # Overall: WOs with zero breach events
    breached_subq = (
        select(SLAEvent.work_order_id)
        .where(
            SLAEvent.org_id == org_id,
            SLAEvent.event_type.in_([
                SLAEventType.ACK_BREACH,
                SLAEventType.FIRST_UPDATE_BREACH,
                SLAEventType.RESOLVE_BREACH,
            ]),
        )
        .distinct()
        .subquery()
    )
    no_breach_stmt = (
        select(func.count())
        .select_from(WorkOrder)
        .where(
            WorkOrder.org_id == org_id,
            WorkOrder.ack_deadline.isnot(None),
            WorkOrder.id.notin_(select(breached_subq.c.work_order_id)),
        )
    )
    no_breach_stmt = _apply_date_filters(no_breach_stmt, WorkOrder, filters)
    no_breach = (await db.execute(no_breach_stmt)).scalar() or 0

    ack_pct = round((ack_met / total_with_sla) * 100, 2) if total_with_sla else 100.0
    resolve_pct = round((resolve_met / resolve_total) * 100, 2) if resolve_total else 100.0
    overall_pct = round((no_breach / total_with_sla) * 100, 2) if total_with_sla else 100.0

    return {
        "total_with_sla": total_with_sla,
        "ack_compliance_pct": ack_pct,
        "resolve_compliance_pct": resolve_pct,
        "overall_compliance_pct": overall_pct,
    }


# ---------------------------------------------------------------------------
# Parts spend
# ---------------------------------------------------------------------------


async def get_parts_spend(
    db: AsyncSession,
    org_id: uuid.UUID,
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return total parts cost aggregated by area.

    Joins ``WorkOrderPartUsed`` through ``WorkOrder`` to get area grouping.
    """
    filters = filters or {}

    stmt = (
        select(
            WorkOrder.area_id,
            func.sum(WorkOrderPartUsed.quantity * WorkOrderPartUsed.unit_cost).label("total_cost"),
            func.sum(WorkOrderPartUsed.quantity).label("total_quantity"),
            func.count(func.distinct(WorkOrderPartUsed.id)).label("usage_count"),
        )
        .join(WorkOrder, WorkOrder.id == WorkOrderPartUsed.work_order_id)
        .where(
            WorkOrder.org_id == org_id,
            WorkOrderPartUsed.unit_cost.isnot(None),
        )
        .group_by(WorkOrder.area_id)
    )

    if "date_from" in filters and filters["date_from"] is not None:
        stmt = stmt.where(WorkOrder.created_at >= filters["date_from"])
    if "date_to" in filters and filters["date_to"] is not None:
        stmt = stmt.where(WorkOrder.created_at <= filters["date_to"])
    if "area_id" in filters and filters["area_id"] is not None:
        stmt = stmt.where(WorkOrder.area_id == filters["area_id"])

    result = await db.execute(stmt)
    rows = result.all()

    by_area = [
        {
            "area_id": str(row.area_id),
            "total_cost": float(row.total_cost) if row.total_cost else 0.0,
            "total_quantity": int(row.total_quantity) if row.total_quantity else 0,
            "usage_count": row.usage_count,
        }
        for row in rows
    ]

    grand_total = sum(item["total_cost"] for item in by_area)

    return {
        "grand_total": round(grand_total, 2),
        "by_area": by_area,
    }


# ---------------------------------------------------------------------------
# Labor cost
# ---------------------------------------------------------------------------


async def get_labor_cost(
    db: AsyncSession,
    org_id: uuid.UUID,
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return labor hours and estimated cost by area.

    Uses the ``labor_rate`` from filters (defaults to 0 if not provided)
    multiplied by total labor hours.
    """
    filters = filters or {}
    labor_rate = filters.get("labor_rate", 0)

    stmt = (
        select(
            WorkOrder.area_id,
            func.sum(LaborLog.minutes).label("total_minutes"),
            func.count(func.distinct(LaborLog.id)).label("log_count"),
        )
        .join(WorkOrder, WorkOrder.id == LaborLog.work_order_id)
        .where(LaborLog.org_id == org_id)
        .group_by(WorkOrder.area_id)
    )

    if "date_from" in filters and filters["date_from"] is not None:
        stmt = stmt.where(LaborLog.logged_at >= filters["date_from"])
    if "date_to" in filters and filters["date_to"] is not None:
        stmt = stmt.where(LaborLog.logged_at <= filters["date_to"])
    if "area_id" in filters and filters["area_id"] is not None:
        stmt = stmt.where(WorkOrder.area_id == filters["area_id"])

    result = await db.execute(stmt)
    rows = result.all()

    by_area = []
    for row in rows:
        total_minutes = int(row.total_minutes) if row.total_minutes else 0
        total_hours = total_minutes / 60.0
        estimated_cost = total_hours * labor_rate
        by_area.append({
            "area_id": str(row.area_id),
            "total_minutes": total_minutes,
            "total_hours": round(total_hours, 2),
            "estimated_cost": round(estimated_cost, 2),
            "log_count": row.log_count,
        })

    grand_total_minutes = sum(item["total_minutes"] for item in by_area)
    grand_total_cost = sum(item["estimated_cost"] for item in by_area)

    return {
        "labor_rate": labor_rate,
        "grand_total_minutes": grand_total_minutes,
        "grand_total_hours": round(grand_total_minutes / 60.0, 2) if grand_total_minutes else 0,
        "grand_total_cost": round(grand_total_cost, 2),
        "by_area": by_area,
    }


# ---------------------------------------------------------------------------
# PM completion rates
# ---------------------------------------------------------------------------


async def get_pm_completion(
    db: AsyncSession,
    org_id: uuid.UUID,
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return PM schedule completion rates.

    Calculates the percentage of GENERATED (completed) vs. total (GENERATED +
    SKIPPED + PENDING past due).
    """
    filters = filters or {}

    base_conditions = [PMSchedule.org_id == org_id]
    if "date_from" in filters and filters["date_from"] is not None:
        base_conditions.append(PMSchedule.due_date >= filters["date_from"])
    if "date_to" in filters and filters["date_to"] is not None:
        base_conditions.append(PMSchedule.due_date <= filters["date_to"])

    # Total schedules
    total_stmt = (
        select(func.count())
        .select_from(PMSchedule)
        .where(and_(*base_conditions))
    )
    total = (await db.execute(total_stmt)).scalar() or 0

    # Generated (completed)
    generated_stmt = (
        select(func.count())
        .select_from(PMSchedule)
        .where(
            and_(*base_conditions),
            PMSchedule.status == PMScheduleStatus.GENERATED,
        )
    )
    generated = (await db.execute(generated_stmt)).scalar() or 0

    # Skipped
    skipped_stmt = (
        select(func.count())
        .select_from(PMSchedule)
        .where(
            and_(*base_conditions),
            PMSchedule.status == PMScheduleStatus.SKIPPED,
        )
    )
    skipped = (await db.execute(skipped_stmt)).scalar() or 0

    # Pending
    pending = total - generated - skipped

    completion_pct = round((generated / total) * 100, 2) if total else 100.0

    return {
        "total": total,
        "generated": generated,
        "skipped": skipped,
        "pending": pending,
        "completion_pct": completion_pct,
    }


# ---------------------------------------------------------------------------
# Technician performance
# ---------------------------------------------------------------------------


async def get_technician_performance(
    db: AsyncSession,
    org_id: uuid.UUID,
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return per-technician performance metrics.

    Metrics per technician:
    - Total assigned work orders
    - Completed work orders (RESOLVED/VERIFIED/CLOSED)
    - Avg resolution time (minutes)
    - Total labor hours
    """
    filters = filters or {}

    # Technicians in org
    tech_stmt = (
        select(User)
        .where(
            User.org_id == org_id,
            User.role == UserRole.TECHNICIAN,
            User.is_active.is_(True),
        )
    )
    tech_result = await db.execute(tech_stmt)
    technicians = tech_result.scalars().all()

    results = []
    for tech in technicians:
        # Total assigned
        assigned_conditions = [
            WorkOrder.org_id == org_id,
            WorkOrder.assigned_to == tech.id,
        ]
        if "date_from" in filters and filters["date_from"]:
            assigned_conditions.append(WorkOrder.created_at >= filters["date_from"])
        if "date_to" in filters and filters["date_to"]:
            assigned_conditions.append(WorkOrder.created_at <= filters["date_to"])

        total_assigned = (await db.execute(
            select(func.count()).select_from(WorkOrder).where(and_(*assigned_conditions))
        )).scalar() or 0

        # Completed
        completed_conditions = assigned_conditions + [
            WorkOrder.status.in_(list(_COMPLETED_STATUSES))
        ]
        total_completed = (await db.execute(
            select(func.count()).select_from(WorkOrder).where(and_(*completed_conditions))
        )).scalar() or 0

        # Avg resolution time
        avg_resolve = (await db.execute(
            select(
                func.avg(
                    extract("epoch", WorkOrder.resolved_at) - extract("epoch", WorkOrder.created_at)
                )
            ).where(
                and_(
                    *assigned_conditions,
                    WorkOrder.resolved_at.isnot(None),
                )
            )
        )).scalar()
        avg_resolution_minutes = round(float(avg_resolve) / 60.0, 2) if avg_resolve else None

        # Total labor hours
        labor_conditions = [
            LaborLog.org_id == org_id,
            LaborLog.user_id == tech.id,
        ]
        if "date_from" in filters and filters["date_from"]:
            labor_conditions.append(LaborLog.logged_at >= filters["date_from"])
        if "date_to" in filters and filters["date_to"]:
            labor_conditions.append(LaborLog.logged_at <= filters["date_to"])

        total_labor_minutes = (await db.execute(
            select(func.sum(LaborLog.minutes)).where(and_(*labor_conditions))
        )).scalar() or 0

        results.append({
            "user_id": str(tech.id),
            "name": tech.name,
            "email": tech.email,
            "total_assigned": total_assigned,
            "total_completed": total_completed,
            "completion_rate_pct": round((total_completed / total_assigned) * 100, 2) if total_assigned else 0.0,
            "avg_resolution_minutes": avg_resolution_minutes,
            "total_labor_minutes": int(total_labor_minutes),
            "total_labor_hours": round(int(total_labor_minutes) / 60.0, 2),
        })

    return {"technicians": results}


# ---------------------------------------------------------------------------
# Safety flags report
# ---------------------------------------------------------------------------


async def get_safety_flags_report(
    db: AsyncSession,
    org_id: uuid.UUID,
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return all safety-flagged work orders with key details.

    Filters may include ``date_from``, ``date_to``, ``area_id``, ``status``.
    """
    filters = filters or {}

    conditions = [
        WorkOrder.org_id == org_id,
        WorkOrder.safety_flag.is_(True),
    ]

    if "date_from" in filters and filters["date_from"] is not None:
        conditions.append(WorkOrder.created_at >= filters["date_from"])
    if "date_to" in filters and filters["date_to"] is not None:
        conditions.append(WorkOrder.created_at <= filters["date_to"])
    if "area_id" in filters and filters["area_id"] is not None:
        conditions.append(WorkOrder.area_id == filters["area_id"])
    if "status" in filters and filters["status"] is not None:
        conditions.append(WorkOrder.status == filters["status"])

    stmt = (
        select(WorkOrder)
        .where(and_(*conditions))
        .order_by(WorkOrder.created_at.desc())
    )
    result = await db.execute(stmt)
    work_orders = result.scalars().all()

    items = [
        {
            "id": str(wo.id),
            "human_readable_number": wo.human_readable_number,
            "title": wo.title,
            "status": wo.status.value,
            "priority": wo.priority.value,
            "area_id": str(wo.area_id),
            "safety_notes": wo.safety_notes,
            "required_cert": wo.required_cert,
            "created_at": wo.created_at.isoformat() if wo.created_at else None,
            "resolved_at": wo.resolved_at.isoformat() if wo.resolved_at else None,
        }
        for wo in work_orders
    ]

    # Status breakdown of safety-flagged WOs
    status_stmt = (
        select(
            WorkOrder.status,
            func.count().label("count"),
        )
        .where(and_(*conditions))
        .group_by(WorkOrder.status)
    )
    status_result = await db.execute(status_stmt)
    by_status = {row.status.value: row.count for row in status_result.all()}

    return {
        "total": len(items),
        "by_status": by_status,
        "items": items,
    }

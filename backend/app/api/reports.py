"""Reports routes: all support ?format=csv for CSV download."""

from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_active_user, require_permission
from app.models.budget import AreaBudget
from app.models.incentive import IncentiveProgram, UserIncentiveScore
from app.models.part import Part
from app.models.pm import PMSchedule, PMScheduleStatus
from app.models.sla import SLAEvent
from app.models.user import User
from app.models.work_order import LaborLog, WorkOrder, WorkOrderPartUsed, WorkOrderStatus

router = APIRouter(prefix="/reports", tags=["reports"])

_OPEN_STATUSES = {
    WorkOrderStatus.NEW,
    WorkOrderStatus.ASSIGNED,
    WorkOrderStatus.ACCEPTED,
    WorkOrderStatus.IN_PROGRESS,
    WorkOrderStatus.WAITING_ON_OPS,
    WorkOrderStatus.ESCALATED,
}


def _csv_response(rows: list[dict], filename: str) -> StreamingResponse:
    """Create a streaming CSV response from a list of dicts."""
    if not rows:
        return StreamingResponse(
            io.StringIO("No data"),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    output.seek(0)

    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── GET /work-orders ──────────────────────────────────────────────────

@router.get("/work-orders")
async def report_work_orders(
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    format: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Work order summary report."""
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="date_from must be before date_to",
        )
    query = select(WorkOrder).where(WorkOrder.org_id == current_user.org_id)
    if date_from:
        query = query.where(WorkOrder.created_at >= date_from)
    if date_to:
        query = query.where(WorkOrder.created_at <= date_to)
    query = query.order_by(WorkOrder.created_at.desc())
    result = await db.execute(query)
    wos = result.scalars().all()

    rows = [
        {
            "id": str(wo.id),
            "human_readable_number": wo.human_readable_number,
            "title": wo.title,
            "type": wo.type.value,
            "priority": wo.priority.value,
            "status": wo.status.value,
            "safety_flag": wo.safety_flag,
            "created_at": wo.created_at.isoformat() if wo.created_at else "",
            "resolved_at": wo.resolved_at.isoformat() if wo.resolved_at else "",
            "closed_at": wo.closed_at.isoformat() if wo.closed_at else "",
        }
        for wo in wos
    ]

    if format == "csv":
        return _csv_response(rows, "work_orders.csv")
    return rows


# ── GET /response-times ───────────────────────────────────────────────

@router.get("/response-times")
async def report_response_times(
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    format: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Report on work order response times (created -> accepted)."""
    query = select(WorkOrder).where(
        WorkOrder.org_id == current_user.org_id,
        WorkOrder.accepted_at.isnot(None),
    )
    if date_from:
        query = query.where(WorkOrder.created_at >= date_from)
    if date_to:
        query = query.where(WorkOrder.created_at <= date_to)
    result = await db.execute(query)
    wos = result.scalars().all()

    rows = []
    for wo in wos:
        response_minutes = None
        if wo.accepted_at and wo.created_at:
            delta = wo.accepted_at - wo.created_at
            response_minutes = int(delta.total_seconds() / 60)
        rows.append({
            "id": str(wo.id),
            "human_readable_number": wo.human_readable_number,
            "priority": wo.priority.value,
            "created_at": wo.created_at.isoformat() if wo.created_at else "",
            "accepted_at": wo.accepted_at.isoformat() if wo.accepted_at else "",
            "response_minutes": response_minutes,
        })

    if format == "csv":
        return _csv_response(rows, "response_times.csv")
    return rows


# ── GET /sla-compliance ───────────────────────────────────────────────

@router.get("/sla-compliance")
async def report_sla_compliance(
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    format: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """SLA compliance report."""
    query = select(SLAEvent).where(SLAEvent.org_id == current_user.org_id)
    if date_from:
        query = query.where(SLAEvent.triggered_at >= date_from)
    if date_to:
        query = query.where(SLAEvent.triggered_at <= date_to)
    result = await db.execute(query)
    events = result.scalars().all()

    rows = [
        {
            "id": str(e.id),
            "work_order_id": str(e.work_order_id),
            "event_type": e.event_type.value,
            "triggered_at": e.triggered_at.isoformat(),
            "acknowledged_by": str(e.acknowledged_by) if e.acknowledged_by else "",
            "acknowledged_at": e.acknowledged_at.isoformat() if e.acknowledged_at else "",
        }
        for e in events
    ]

    if format == "csv":
        return _csv_response(rows, "sla_compliance.csv")
    return rows


# ── GET /parts-spend ──────────────────────────────────────────────────

@router.get("/parts-spend")
async def report_parts_spend(
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    format: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("CAN_VIEW_COSTS")),
):
    """Parts spend report across all work orders."""
    query = (
        select(WorkOrderPartUsed)
        .where(WorkOrderPartUsed.org_id == current_user.org_id)
    )
    result = await db.execute(query)
    parts = result.scalars().all()

    rows = [
        {
            "work_order_id": str(p.work_order_id),
            "part_number": p.part_number or "",
            "description": p.description or "",
            "quantity": p.quantity,
            "unit_cost": float(p.unit_cost) if p.unit_cost else 0,
            "total_cost": float(p.unit_cost or 0) * p.quantity,
        }
        for p in parts
    ]

    if format == "csv":
        return _csv_response(rows, "parts_spend.csv")
    return rows


# ── GET /labor-cost ───────────────────────────────────────────────────

@router.get("/labor-cost")
async def report_labor_cost(
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    format: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("CAN_VIEW_COSTS")),
):
    """Labor cost report."""
    query = select(LaborLog).where(LaborLog.org_id == current_user.org_id)
    if date_from:
        query = query.where(LaborLog.logged_at >= date_from)
    if date_to:
        query = query.where(LaborLog.logged_at <= date_to)
    result = await db.execute(query)
    logs = result.scalars().all()

    rows = [
        {
            "work_order_id": str(ll.work_order_id),
            "user_id": str(ll.user_id),
            "minutes": ll.minutes,
            "hours": round(ll.minutes / 60.0, 2),
            "notes": ll.notes or "",
            "logged_at": ll.logged_at.isoformat() if ll.logged_at else "",
        }
        for ll in logs
    ]

    if format == "csv":
        return _csv_response(rows, "labor_cost.csv")
    return rows


# ── GET /budget ───────────────────────────────────────────────────────

@router.get("/budget")
async def report_budget(
    year: Optional[int] = Query(None),
    format: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("CAN_MANAGE_BUDGET")),
):
    """Budget vs. actual report."""
    query = select(AreaBudget).where(AreaBudget.org_id == current_user.org_id)
    if year:
        query = query.where(AreaBudget.year == year)
    result = await db.execute(query)
    budgets = result.scalars().all()

    rows = [
        {
            "area_id": str(b.area_id),
            "year": b.year,
            "month": b.month,
            "budget_amount": float(b.budget_amount),
            "actual_spend": float(b.actual_spend),
            "variance": float(b.budget_amount) - float(b.actual_spend),
        }
        for b in budgets
    ]

    if format == "csv":
        return _csv_response(rows, "budget.csv")
    return rows


# ── GET /pm-completion ────────────────────────────────────────────────

@router.get("/pm-completion")
async def report_pm_completion(
    format: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """PM schedule completion report."""
    query = select(PMSchedule).where(PMSchedule.org_id == current_user.org_id)
    result = await db.execute(query)
    schedules = result.scalars().all()

    total = len(schedules)
    generated = sum(1 for s in schedules if s.status == PMScheduleStatus.GENERATED)
    skipped = sum(1 for s in schedules if s.status == PMScheduleStatus.SKIPPED)
    pending = sum(1 for s in schedules if s.status == PMScheduleStatus.PENDING)

    rows = [{
        "total_schedules": total,
        "generated": generated,
        "skipped": skipped,
        "pending": pending,
        "completion_rate": round(generated / total * 100, 2) if total > 0 else 0,
    }]

    if format == "csv":
        return _csv_response(rows, "pm_completion.csv")
    return rows[0]


# ── GET /technician-performance ───────────────────────────────────────

@router.get("/technician-performance")
async def report_technician_performance(
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    format: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Technician performance report (WOs completed, avg resolution time)."""
    query = select(WorkOrder).where(
        WorkOrder.org_id == current_user.org_id,
        WorkOrder.assigned_to.isnot(None),
        WorkOrder.status.in_({WorkOrderStatus.RESOLVED, WorkOrderStatus.VERIFIED, WorkOrderStatus.CLOSED}),
    )
    if date_from:
        query = query.where(WorkOrder.created_at >= date_from)
    if date_to:
        query = query.where(WorkOrder.created_at <= date_to)
    result = await db.execute(query)
    wos = result.scalars().all()

    # Aggregate by technician
    tech_stats: dict[str, dict] = {}
    for wo in wos:
        tech_id = str(wo.assigned_to)
        if tech_id not in tech_stats:
            tech_stats[tech_id] = {
                "user_id": tech_id,
                "completed_count": 0,
                "total_resolution_minutes": 0,
                "resolution_count": 0,
            }
        tech_stats[tech_id]["completed_count"] += 1

        if wo.resolved_at and wo.created_at:
            delta = wo.resolved_at - wo.created_at
            minutes = int(delta.total_seconds() / 60)
            tech_stats[tech_id]["total_resolution_minutes"] += minutes
            tech_stats[tech_id]["resolution_count"] += 1

    rows = []
    for tech_id, stats in tech_stats.items():
        avg_minutes = (
            round(stats["total_resolution_minutes"] / stats["resolution_count"], 1)
            if stats["resolution_count"] > 0
            else None
        )
        # Look up name
        user = await db.get(User, tech_id)
        rows.append({
            "user_id": tech_id,
            "name": user.name if user else "Unknown",
            "completed_count": stats["completed_count"],
            "avg_resolution_minutes": avg_minutes,
        })

    if format == "csv":
        return _csv_response(rows, "technician_performance.csv")
    return rows


# ── GET /safety-flags ─────────────────────────────────────────────────

@router.get("/safety-flags")
async def report_safety_flags(
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    format: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Report on safety-flagged work orders."""
    query = select(WorkOrder).where(
        WorkOrder.org_id == current_user.org_id,
        WorkOrder.safety_flag == True,  # noqa: E712
    )
    if date_from:
        query = query.where(WorkOrder.created_at >= date_from)
    if date_to:
        query = query.where(WorkOrder.created_at <= date_to)
    query = query.order_by(WorkOrder.created_at.desc())
    result = await db.execute(query)
    wos = result.scalars().all()

    rows = [
        {
            "id": str(wo.id),
            "human_readable_number": wo.human_readable_number,
            "title": wo.title,
            "priority": wo.priority.value,
            "status": wo.status.value,
            "safety_notes": wo.safety_notes or "",
            "created_at": wo.created_at.isoformat() if wo.created_at else "",
        }
        for wo in wos
    ]

    if format == "csv":
        return _csv_response(rows, "safety_flags.csv")
    return rows


# ── GET /incentives ───────────────────────────────────────────────────

@router.get("/incentives")
async def report_incentives(
    format: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Incentive program scores report."""
    programs_result = await db.execute(
        select(IncentiveProgram).where(
            IncentiveProgram.org_id == current_user.org_id
        )
    )
    programs = programs_result.scalars().all()
    program_ids = [p.id for p in programs]

    if not program_ids:
        if format == "csv":
            return _csv_response([], "incentives.csv")
        return []

    scores_result = await db.execute(
        select(UserIncentiveScore).where(
            UserIncentiveScore.program_id.in_(program_ids)
        )
    )
    scores = scores_result.scalars().all()

    rows = []
    for s in scores:
        user = await db.get(User, s.user_id)
        program = next((p for p in programs if p.id == s.program_id), None)
        rows.append({
            "user_id": str(s.user_id),
            "user_name": user.name if user else "Unknown",
            "program_name": program.name if program else "Unknown",
            "period_label": s.period_label,
            "score": float(s.score),
            "achieved": s.achieved,
            "calculated_at": s.calculated_at.isoformat(),
        })

    if format == "csv":
        return _csv_response(rows, "incentives.csv")
    return rows

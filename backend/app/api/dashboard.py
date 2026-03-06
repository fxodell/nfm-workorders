"""Dashboard routes: overview, area detail, site detail."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_active_user, verify_area_access, verify_org_ownership
from app.models.area import Area
from app.models.location import Location
from app.models.site import Site
from app.models.user import User, UserAreaAssignment
from app.models.work_order import WorkOrder, WorkOrderStatus
from app.schemas.dashboard import AreaDashboard, AssignedTech, DashboardOverview, SiteDashboard

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_OPEN_STATUSES = {
    WorkOrderStatus.NEW,
    WorkOrderStatus.ASSIGNED,
    WorkOrderStatus.ACCEPTED,
    WorkOrderStatus.IN_PROGRESS,
    WorkOrderStatus.WAITING_ON_OPS,
    WorkOrderStatus.ESCALATED,
}


# ── GET /overview ──────────────────────────────────────────────────────

@router.get("/overview", response_model=DashboardOverview)
async def dashboard_overview(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get dashboard overview with area rollups."""
    # Determine accessible areas
    bypass_roles = {"SUPER_ADMIN", "ADMIN"}
    if current_user.role.value in bypass_roles:
        areas_result = await db.execute(
            select(Area).where(Area.org_id == current_user.org_id, Area.is_active == True)  # noqa: E712
        )
    else:
        areas_result = await db.execute(
            select(Area)
            .join(UserAreaAssignment, UserAreaAssignment.area_id == Area.id)
            .where(
                Area.org_id == current_user.org_id,
                Area.is_active == True,  # noqa: E712
                UserAreaAssignment.user_id == current_user.id,
            )
        )
    areas = areas_result.scalars().all()

    area_dashboards = []
    for area in areas:
        # Count WOs by priority for open statuses
        priority_result = await db.execute(
            select(
                WorkOrder.priority,
                func.count(WorkOrder.id),
            )
            .where(
                WorkOrder.area_id == area.id,
                WorkOrder.org_id == current_user.org_id,
                WorkOrder.status.in_(_OPEN_STATUSES),
            )
            .group_by(WorkOrder.priority)
        )
        priority_counts = {row[0].value: row[1] for row in priority_result}

        # Count escalated
        escalated_result = await db.execute(
            select(func.count()).where(
                WorkOrder.area_id == area.id,
                WorkOrder.org_id == current_user.org_id,
                WorkOrder.status == WorkOrderStatus.ESCALATED,
            )
        )
        escalated_count = escalated_result.scalar() or 0

        # Count safety flagged
        safety_result = await db.execute(
            select(func.count()).where(
                WorkOrder.area_id == area.id,
                WorkOrder.org_id == current_user.org_id,
                WorkOrder.status.in_(_OPEN_STATUSES),
                WorkOrder.safety_flag == True,  # noqa: E712
            )
        )
        safety_count = safety_result.scalar() or 0

        # Per-site summaries
        sites_result = await db.execute(
            select(Site)
            .join(Location, Location.id == Site.location_id)
            .where(
                Location.area_id == area.id,
                Site.org_id == current_user.org_id,
                Site.is_active == True,  # noqa: E712
            )
        )
        sites = sites_result.scalars().all()

        site_dashboards = []
        for site in sites:
            wo_count_result = await db.execute(
                select(func.count()).where(
                    WorkOrder.site_id == site.id,
                    WorkOrder.org_id == current_user.org_id,
                    WorkOrder.status.in_(_OPEN_STATUSES),
                )
            )
            wo_count = wo_count_result.scalar() or 0

            site_esc_result = await db.execute(
                select(func.count()).where(
                    WorkOrder.site_id == site.id,
                    WorkOrder.org_id == current_user.org_id,
                    WorkOrder.status == WorkOrderStatus.ESCALATED,
                )
            )
            site_esc = (site_esc_result.scalar() or 0) > 0

            site_sf_result = await db.execute(
                select(func.count()).where(
                    WorkOrder.site_id == site.id,
                    WorkOrder.org_id == current_user.org_id,
                    WorkOrder.status.in_(_OPEN_STATUSES),
                    WorkOrder.safety_flag == True,  # noqa: E712
                )
            )
            site_sf = (site_sf_result.scalar() or 0) > 0

            highest_result = await db.execute(
                select(WorkOrder.priority)
                .where(
                    WorkOrder.site_id == site.id,
                    WorkOrder.org_id == current_user.org_id,
                    WorkOrder.status.in_(_OPEN_STATUSES),
                )
                .order_by(
                    case(
                        (WorkOrder.priority == "IMMEDIATE", 1),
                        (WorkOrder.priority == "URGENT", 2),
                        (WorkOrder.priority == "SCHEDULED", 3),
                        (WorkOrder.priority == "DEFERRED", 4),
                        else_=5,
                    )
                )
                .limit(1)
            )
            highest_priority_row = highest_result.scalars().first()

            # Assigned technicians
            tech_result = await db.execute(
                select(User.id, User.name)
                .join(WorkOrder, WorkOrder.assigned_to == User.id)
                .where(
                    WorkOrder.site_id == site.id,
                    WorkOrder.org_id == current_user.org_id,
                    WorkOrder.status.in_(_OPEN_STATUSES),
                    WorkOrder.assigned_to.isnot(None),
                )
                .distinct()
            )
            assigned_techs = [AssignedTech(id=row[0], name=row[1]) for row in tech_result]

            site_dashboards.append(
                SiteDashboard(
                    site_id=site.id,
                    site_name=site.name,
                    site_type=site.type,
                    highest_priority=highest_priority_row,
                    wo_count=wo_count,
                    escalated=site_esc,
                    safety_flag=site_sf,
                    assigned_techs=assigned_techs,
                )
            )

        area_dashboards.append(
            AreaDashboard(
                area_id=area.id,
                area_name=area.name,
                priority_counts=priority_counts,
                escalated_count=escalated_count,
                safety_flag_count=safety_count,
                sites=site_dashboards,
            )
        )

    return DashboardOverview(areas=area_dashboards)


# ── GET /area/{area_id} ───────────────────────────────────────────────

@router.get("/area/{area_id}", response_model=AreaDashboard)
async def area_dashboard(
    area_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get detailed dashboard for a specific area including site-level summaries."""
    area = await db.get(Area, area_id)
    if not area:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Area not found")
    await verify_org_ownership(area, current_user)
    await verify_area_access(area_id, current_user, db)

    # Priority counts
    priority_result = await db.execute(
        select(WorkOrder.priority, func.count(WorkOrder.id))
        .where(
            WorkOrder.area_id == area_id,
            WorkOrder.org_id == current_user.org_id,
            WorkOrder.status.in_(_OPEN_STATUSES),
        )
        .group_by(WorkOrder.priority)
    )
    priority_counts = {row[0].value: row[1] for row in priority_result}

    escalated_result = await db.execute(
        select(func.count()).where(
            WorkOrder.area_id == area_id,
            WorkOrder.org_id == current_user.org_id,
            WorkOrder.status == WorkOrderStatus.ESCALATED,
        )
    )
    escalated_count = escalated_result.scalar() or 0

    safety_result = await db.execute(
        select(func.count()).where(
            WorkOrder.area_id == area_id,
            WorkOrder.org_id == current_user.org_id,
            WorkOrder.status.in_(_OPEN_STATUSES),
            WorkOrder.safety_flag == True,  # noqa: E712
        )
    )
    safety_count = safety_result.scalar() or 0

    # Per-site summaries
    sites_result = await db.execute(
        select(Site)
        .join(Location, Location.id == Site.location_id)
        .where(
            Location.area_id == area_id,
            Site.org_id == current_user.org_id,
            Site.is_active == True,  # noqa: E712
        )
    )
    sites = sites_result.scalars().all()

    site_dashboards = []
    for site in sites:
        wo_count_result = await db.execute(
            select(func.count()).where(
                WorkOrder.site_id == site.id,
                WorkOrder.org_id == current_user.org_id,
                WorkOrder.status.in_(_OPEN_STATUSES),
            )
        )
        wo_count = wo_count_result.scalar() or 0

        site_escalated = await db.execute(
            select(func.count()).where(
                WorkOrder.site_id == site.id,
                WorkOrder.org_id == current_user.org_id,
                WorkOrder.status == WorkOrderStatus.ESCALATED,
            )
        )
        site_esc = (site_escalated.scalar() or 0) > 0

        site_safety = await db.execute(
            select(func.count()).where(
                WorkOrder.site_id == site.id,
                WorkOrder.org_id == current_user.org_id,
                WorkOrder.status.in_(_OPEN_STATUSES),
                WorkOrder.safety_flag == True,  # noqa: E712
            )
        )
        site_sf = (site_safety.scalar() or 0) > 0

        # Get highest priority
        highest_result = await db.execute(
            select(WorkOrder.priority)
            .where(
                WorkOrder.site_id == site.id,
                WorkOrder.org_id == current_user.org_id,
                WorkOrder.status.in_(_OPEN_STATUSES),
            )
            .order_by(
                case(
                    (WorkOrder.priority == "CRITICAL", 1),
                    (WorkOrder.priority == "HIGH", 2),
                    (WorkOrder.priority == "MEDIUM", 3),
                    (WorkOrder.priority == "LOW", 4),
                    else_=5,
                )
            )
            .limit(1)
        )
        highest_priority_row = highest_result.scalars().first()

        # Assigned technicians
        tech_result = await db.execute(
            select(User.id, User.name)
            .join(WorkOrder, WorkOrder.assigned_to == User.id)
            .where(
                WorkOrder.site_id == site.id,
                WorkOrder.org_id == current_user.org_id,
                WorkOrder.status.in_(_OPEN_STATUSES),
                WorkOrder.assigned_to.isnot(None),
            )
            .distinct()
        )
        assigned_techs = [AssignedTech(id=row[0], name=row[1]) for row in tech_result]

        site_dashboards.append(
            SiteDashboard(
                site_id=site.id,
                site_name=site.name,
                site_type=site.type,
                highest_priority=highest_priority_row,
                wo_count=wo_count,
                escalated=site_esc,
                safety_flag=site_sf,
                assigned_techs=assigned_techs,
            )
        )

    return AreaDashboard(
        area_id=area.id,
        area_name=area.name,
        priority_counts=priority_counts,
        escalated_count=escalated_count,
        safety_flag_count=safety_count,
        sites=site_dashboards,
    )


# ── GET /site/{site_id} ───────────────────────────────────────────────

@router.get("/site/{site_id}", response_model=SiteDashboard)
async def site_dashboard(
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get detailed dashboard for a specific site."""
    site = await db.get(Site, site_id)
    if not site:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    await verify_org_ownership(site, current_user)

    wo_count_result = await db.execute(
        select(func.count()).where(
            WorkOrder.site_id == site_id,
            WorkOrder.org_id == current_user.org_id,
            WorkOrder.status.in_(_OPEN_STATUSES),
        )
    )
    wo_count = wo_count_result.scalar() or 0

    escalated_result = await db.execute(
        select(func.count()).where(
            WorkOrder.site_id == site_id,
            WorkOrder.org_id == current_user.org_id,
            WorkOrder.status == WorkOrderStatus.ESCALATED,
        )
    )
    escalated = (escalated_result.scalar() or 0) > 0

    safety_result = await db.execute(
        select(func.count()).where(
            WorkOrder.site_id == site_id,
            WorkOrder.org_id == current_user.org_id,
            WorkOrder.status.in_(_OPEN_STATUSES),
            WorkOrder.safety_flag == True,  # noqa: E712
        )
    )
    safety_flag = (safety_result.scalar() or 0) > 0

    # Waiting counts
    waiting_ops_result = await db.execute(
        select(func.count()).where(
            WorkOrder.site_id == site_id,
            WorkOrder.org_id == current_user.org_id,
            WorkOrder.status == WorkOrderStatus.WAITING_ON_OPS,
        )
    )
    waiting_ops = waiting_ops_result.scalar() or 0

    # Assigned technicians
    tech_result = await db.execute(
        select(User.id, User.name)
        .join(WorkOrder, WorkOrder.assigned_to == User.id)
        .where(
            WorkOrder.site_id == site_id,
            WorkOrder.org_id == current_user.org_id,
            WorkOrder.status.in_(_OPEN_STATUSES),
            WorkOrder.assigned_to.isnot(None),
        )
        .distinct()
    )
    assigned_techs = [AssignedTech(id=row[0], name=row[1]) for row in tech_result]

    return SiteDashboard(
        site_id=site.id,
        site_name=site.name,
        site_type=site.type,
        wo_count=wo_count,
        escalated=escalated,
        safety_flag=safety_flag,
        waiting_on_ops=waiting_ops,
        assigned_techs=assigned_techs,
    )

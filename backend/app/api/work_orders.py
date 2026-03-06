"""Work order routes: CRUD, FSM state transitions, filtering."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import (
    get_current_active_user,
    require_role,
    verify_area_access,
    verify_org_ownership,
)
from app.core.idempotency import IdempotencyResult, idempotency_check
from app.models.org import Organization, WOCounter
from app.models.user import TechnicianCertification, User, UserAreaAssignment
from app.models.work_order import (
    TimelineEvent,
    TimelineEventType,
    WorkOrder,
    WorkOrderStatus,
)
from app.schemas.common import MessageResponse
from app.schemas.work_order import (
    WorkOrderAccept,
    WorkOrderAssign,
    WorkOrderCreate,
    WorkOrderEscalate,
    WorkOrderListResponse,
    WorkOrderReopen,
    WorkOrderResolve,
    WorkOrderResponse,
    WorkOrderUpdate,
)
from app.services.work_order_service import (
    generate_human_readable_number,
    validate_fsm_transition,
)

router = APIRouter(prefix="/work-orders", tags=["work-orders"])


def _validate_transition(current: WorkOrderStatus, target: WorkOrderStatus, user_role: str = "SUPER_ADMIN") -> None:
    """Validate FSM transition using the canonical service function."""
    validate_fsm_transition(current, target, user_role)


async def _create_timeline_event(
    db: AsyncSession,
    wo: WorkOrder,
    user: User,
    event_type: TimelineEventType,
    payload: dict | None = None,
) -> TimelineEvent:
    """Create and persist a timeline event for a work order."""
    event = TimelineEvent(
        work_order_id=wo.id,
        org_id=wo.org_id,
        user_id=user.id,
        event_type=event_type,
        payload=payload or {},
    )
    db.add(event)
    return event


def _compute_sla_deadlines(
    wo: WorkOrder, org: Organization,
) -> None:
    """Compute SLA deadlines based on org config and priority."""
    config = org.config or {}
    sla = config.get("sla", {})
    now = datetime.now(timezone.utc)

    priority_key = wo.priority.value.lower()
    response_key = f"{priority_key}_response_min"
    resolve_key = f"{priority_key}_resolve_min"

    response_min = sla.get(response_key)
    resolve_min = sla.get(resolve_key)

    if response_min:
        wo.ack_deadline = now + timedelta(minutes=int(response_min))
    if resolve_min:
        wo.due_at = now + timedelta(minutes=int(resolve_min))


def _escape_like(value: str) -> str:
    """Escape special LIKE characters to prevent wildcard injection."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _wo_query_with_joins(base_query=None):
    """Return a select() with eager-loaded relationships for name resolution."""
    q = base_query if base_query is not None else select(WorkOrder)
    return q.options(
        selectinload(WorkOrder.area),
        selectinload(WorkOrder.site),
        selectinload(WorkOrder.asset),
        selectinload(WorkOrder.requester),
        selectinload(WorkOrder.assignee),
    )


async def _get_wo_with_joins(db: AsyncSession, wo_id: uuid.UUID) -> WorkOrder | None:
    """Fetch a single WorkOrder with eager-loaded relationships."""
    result = await db.execute(
        _wo_query_with_joins().where(WorkOrder.id == wo_id)
    )
    return result.scalars().first()


# ── GET / (list with filters) ─────────────────────────────────────────

@router.get("", response_model=WorkOrderListResponse)
async def list_work_orders(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    area_id: Optional[uuid.UUID] = Query(None),
    site_id: Optional[uuid.UUID] = Query(None),
    asset_id: Optional[uuid.UUID] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    priority: Optional[str] = Query(None),
    type_filter: Optional[str] = Query(None, alias="type"),
    assigned_to: Optional[uuid.UUID] = Query(None),
    requested_by: Optional[uuid.UUID] = Query(None),
    safety_flag: Optional[bool] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List work orders with filters, scoped to user's org and assigned areas."""
    query = _wo_query_with_joins().where(WorkOrder.org_id == current_user.org_id)

    # Scope to user's assigned areas unless admin
    bypass_roles = {"SUPER_ADMIN", "ADMIN"}
    if current_user.role.value not in bypass_roles:
        area_subq = select(UserAreaAssignment.area_id).where(
            UserAreaAssignment.user_id == current_user.id
        )
        query = query.where(WorkOrder.area_id.in_(area_subq))

    if area_id:
        query = query.where(WorkOrder.area_id == area_id)
    if site_id:
        query = query.where(WorkOrder.site_id == site_id)
    if asset_id:
        query = query.where(WorkOrder.asset_id == asset_id)
    if status_filter:
        query = query.where(WorkOrder.status == status_filter)
    if priority:
        query = query.where(WorkOrder.priority == priority)
    if type_filter:
        query = query.where(WorkOrder.type == type_filter)
    if assigned_to:
        query = query.where(WorkOrder.assigned_to == assigned_to)
    if requested_by:
        query = query.where(WorkOrder.requested_by == requested_by)
    if safety_flag is not None:
        query = query.where(WorkOrder.safety_flag == safety_flag)
    if date_from:
        query = query.where(WorkOrder.created_at >= date_from)
    if date_to:
        query = query.where(WorkOrder.created_at <= date_to)
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="date_from must be before date_to",
        )
    if search:
        if len(search) > 500:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Search query too long (max 500 characters)",
            )
        escaped = _escape_like(search)
        query = query.where(
            or_(
                WorkOrder.title.ilike(f"%{escaped}%", escape="\\"),
                WorkOrder.human_readable_number.ilike(f"%{escaped}%", escape="\\"),
                WorkOrder.description.ilike(f"%{escaped}%", escape="\\"),
            )
        )

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = query.order_by(WorkOrder.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    items = result.scalars().all()

    return WorkOrderListResponse(items=items, total=total, page=page, per_page=per_page)


# ── POST / (create) ───────────────────────────────────────────────────

@router.post("", response_model=WorkOrderResponse, status_code=status.HTTP_201_CREATED)
async def create_work_order(
    request: Request,
    body: WorkOrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    idempotency: IdempotencyResult = Depends(idempotency_check),
):
    """Create a new work order. Requires X-Idempotency-Key header."""
    if idempotency.cached_response is not None:
        return idempotency.cached_response

    await verify_area_access(body.area_id, current_user, db)

    # Resolve location_id from site
    from app.models.site import Site
    site = await db.get(Site, body.site_id)
    if not site:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    await verify_org_ownership(site, current_user)

    human_readable = await generate_human_readable_number(db, current_user.org_id)

    # Load org for SLA config
    org = await db.get(Organization, current_user.org_id)

    idempotency_key_header = request.headers.get("Idempotency-Key")

    wo = WorkOrder(
        org_id=current_user.org_id,
        area_id=body.area_id,
        location_id=site.location_id,
        site_id=body.site_id,
        asset_id=body.asset_id,
        human_readable_number=human_readable,
        title=body.title,
        description=body.description,
        type=body.type,
        priority=body.priority,
        status=WorkOrderStatus.NEW,
        requested_by=current_user.id,
        safety_flag=body.safety_flag,
        safety_notes=body.safety_notes,
        required_cert=body.required_cert,
        tags=body.tags,
        custom_fields=body.custom_fields,
        idempotency_key=idempotency_key_header,
    )

    if org:
        _compute_sla_deadlines(wo, org)

    db.add(wo)
    await db.flush()

    # Timeline event
    await _create_timeline_event(
        db, wo, current_user, TimelineEventType.STATUS_CHANGE,
        {"title": wo.title, "priority": wo.priority.value},
    )

    # Handle optional assignment during creation
    if body.assigned_to is not None:
        assign_roles = {"SUPER_ADMIN", "ADMIN", "SUPERVISOR"}
        if current_user.role.value not in assign_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only supervisors and admins can assign work orders",
            )
        assignee = await db.get(User, body.assigned_to)
        if not assignee or assignee.org_id != current_user.org_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Assignee not found",
            )
        area_check = await db.execute(
            select(UserAreaAssignment).where(
                UserAreaAssignment.user_id == body.assigned_to,
                UserAreaAssignment.area_id == body.area_id,
            )
        )
        if area_check.scalars().first() is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Assignee is not assigned to this work order's area",
            )
        wo.assigned_to = body.assigned_to
        wo.assigned_at = datetime.now(timezone.utc)
        wo.status = WorkOrderStatus.ASSIGNED
        wo.updated_at = datetime.now(timezone.utc)
        await _create_timeline_event(
            db, wo, current_user, TimelineEventType.STATUS_CHANGE,
            {"assigned_to": str(body.assigned_to), "assigned_by": str(current_user.id)},
        )

    await db.flush()

    # Re-fetch with eager-loaded relationships for name resolution
    wo = await _get_wo_with_joins(db, wo.id)
    response_data = WorkOrderResponse.model_validate(wo).model_dump(mode="json")
    await idempotency.store(response_data)
    return wo


# ── GET /{id} ──────────────────────────────────────────────────────────

@router.get("/{wo_id}", response_model=WorkOrderResponse)
async def get_work_order(
    wo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get a work order by ID."""
    wo = await _get_wo_with_joins(db, wo_id)
    if not wo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")
    await verify_org_ownership(wo, current_user)
    return wo


# ── PATCH /{id} ────────────────────────────────────────────────────────

@router.patch("/{wo_id}", response_model=WorkOrderResponse)
async def update_work_order(
    wo_id: uuid.UUID,
    body: WorkOrderUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    idempotency: IdempotencyResult = Depends(idempotency_check),
):
    """Update a work order's editable fields."""
    if idempotency.cached_response is not None:
        return idempotency.cached_response

    wo = await _get_wo_with_joins(db, wo_id)
    if not wo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")
    await verify_org_ownership(wo, current_user)

    update_data = body.model_dump(exclude_unset=True)
    old_priority = wo.priority.value if wo.priority else None

    for field, value in update_data.items():
        setattr(wo, field, value)
    wo.updated_at = datetime.now(timezone.utc)
    await db.flush()

    # Log priority change if applicable
    if "priority" in update_data and update_data["priority"] != old_priority:
        await _create_timeline_event(
            db, wo, current_user, TimelineEventType.STATUS_CHANGE,
            {"old_priority": old_priority, "new_priority": wo.priority.value},
        )
        await db.flush()

    response_data = WorkOrderResponse.model_validate(wo).model_dump(mode="json")
    await idempotency.store(response_data)
    return wo


# ── DELETE /{id} (soft delete, ADMIN only) ─────────────────────────────

@router.delete("/{wo_id}", response_model=MessageResponse)
async def delete_work_order(
    wo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["SUPER_ADMIN", "ADMIN"])),
):
    """Soft-delete a work order (ADMIN only). Cancels the WO."""
    wo = await _get_wo_with_joins(db, wo_id)
    if not wo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")
    await verify_org_ownership(wo, current_user)

    wo.status = WorkOrderStatus.CANCELLED
    wo.updated_at = datetime.now(timezone.utc)

    await _create_timeline_event(
        db, wo, current_user, TimelineEventType.CANCELLED,
        {"reason": "Deleted by admin"},
    )
    await db.flush()
    return MessageResponse(message="Work order cancelled")


# ── POST /{id}/assign ─────────────────────────────────────────────────

@router.post("/{wo_id}/assign", response_model=WorkOrderResponse)
async def assign_work_order(
    wo_id: uuid.UUID,
    body: WorkOrderAssign,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["SUPER_ADMIN", "ADMIN", "SUPERVISOR"])),
):
    """Assign a technician to a work order. FSM: OPEN -> ASSIGNED."""
    wo = await _get_wo_with_joins(db, wo_id)
    if not wo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")
    await verify_org_ownership(wo, current_user)
    _validate_transition(wo.status, WorkOrderStatus.ASSIGNED, current_user.role.value)

    # Verify assignee exists and belongs to same org
    assignee = await db.get(User, body.assigned_to)
    if not assignee or assignee.org_id != current_user.org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignee not found")

    # Verify assignee is assigned to the work order's area
    area_check = await db.execute(
        select(UserAreaAssignment).where(
            UserAreaAssignment.user_id == body.assigned_to,
            UserAreaAssignment.area_id == wo.area_id,
        )
    )
    if area_check.scalars().first() is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assignee is not assigned to this work order's area",
        )

    wo.assigned_to = body.assigned_to
    wo.assigned_at = datetime.now(timezone.utc)
    wo.status = WorkOrderStatus.ASSIGNED
    wo.updated_at = datetime.now(timezone.utc)

    await _create_timeline_event(
        db, wo, current_user, TimelineEventType.STATUS_CHANGE,
        {"assigned_to": str(body.assigned_to), "assigned_by": str(current_user.id)},
    )
    await db.flush()
    return wo


# ── POST /{id}/accept ─────────────────────────────────────────────────

@router.post("/{wo_id}/accept", response_model=WorkOrderResponse)
async def accept_work_order(
    wo_id: uuid.UUID,
    body: WorkOrderAccept = WorkOrderAccept(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Accept a work order and optionally set ETA. FSM: ASSIGNED/OPEN -> ACCEPTED."""
    wo = await _get_wo_with_joins(db, wo_id)
    if not wo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")
    await verify_org_ownership(wo, current_user)
    _validate_transition(wo.status, WorkOrderStatus.ACCEPTED, current_user.role.value)

    # Check required certification
    if wo.required_cert:
        cert_result = await db.execute(
            select(TechnicianCertification).where(
                TechnicianCertification.user_id == current_user.id,
                TechnicianCertification.cert_name == wo.required_cert,
            )
        )
        if cert_result.scalars().first() is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required certification '{wo.required_cert}' not found for this user",
            )

    wo.accepted_by = current_user.id
    wo.accepted_at = datetime.now(timezone.utc)
    wo.status = WorkOrderStatus.ACCEPTED
    wo.updated_at = datetime.now(timezone.utc)

    if body.eta_minutes is not None:
        wo.eta_minutes = body.eta_minutes

    # Auto-assign if not already assigned
    if wo.assigned_to is None:
        wo.assigned_to = current_user.id
        wo.assigned_at = datetime.now(timezone.utc)

    await _create_timeline_event(
        db, wo, current_user, TimelineEventType.STATUS_CHANGE,
        {"eta_minutes": body.eta_minutes},
    )
    await db.flush()
    return wo


# ── POST /{id}/start ──────────────────────────────────────────────────

@router.post("/{wo_id}/start", response_model=WorkOrderResponse)
async def start_work_order(
    wo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Start work on a work order. FSM: ACCEPTED -> IN_PROGRESS."""
    wo = await _get_wo_with_joins(db, wo_id)
    if not wo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")
    await verify_org_ownership(wo, current_user)
    _validate_transition(wo.status, WorkOrderStatus.IN_PROGRESS, current_user.role.value)

    wo.status = WorkOrderStatus.IN_PROGRESS
    wo.in_progress_at = datetime.now(timezone.utc)
    wo.updated_at = datetime.now(timezone.utc)

    await _create_timeline_event(
        db, wo, current_user, TimelineEventType.STATUS_CHANGE,
    )
    await db.flush()
    return wo


# ── POST /{id}/wait-ops ───────────────────────────────────────────────

@router.post("/{wo_id}/wait-ops", response_model=WorkOrderResponse)
async def wait_ops(
    wo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Mark work order as waiting on operations. FSM: IN_PROGRESS -> WAITING_ON_OPS."""
    wo = await _get_wo_with_joins(db, wo_id)
    if not wo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")
    await verify_org_ownership(wo, current_user)
    _validate_transition(wo.status, WorkOrderStatus.WAITING_ON_OPS, current_user.role.value)

    wo.status = WorkOrderStatus.WAITING_ON_OPS
    wo.updated_at = datetime.now(timezone.utc)

    await _create_timeline_event(
        db, wo, current_user, TimelineEventType.STATUS_CHANGE,
        {"reason": "WAITING_ON_OPS"},
    )
    await db.flush()
    return wo


# ── POST /{id}/wait-parts ─────────────────────────────────────────────

@router.post("/{wo_id}/wait-parts", response_model=WorkOrderResponse)
async def wait_parts(
    wo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Mark work order as waiting on parts. FSM: IN_PROGRESS -> WAITING_ON_PARTS."""
    wo = await _get_wo_with_joins(db, wo_id)
    if not wo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")
    await verify_org_ownership(wo, current_user)
    _validate_transition(wo.status, WorkOrderStatus.WAITING_ON_PARTS, current_user.role.value)

    wo.status = WorkOrderStatus.WAITING_ON_PARTS
    wo.updated_at = datetime.now(timezone.utc)

    await _create_timeline_event(
        db, wo, current_user, TimelineEventType.STATUS_CHANGE,
        {"reason": "WAITING_ON_PARTS"},
    )
    await db.flush()
    return wo


# ── POST /{id}/resume ─────────────────────────────────────────────────

@router.post("/{wo_id}/resume", response_model=WorkOrderResponse)
async def resume_work_order(
    wo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Resume a work order from waiting state. FSM: ON_HOLD -> IN_PROGRESS."""
    wo = await _get_wo_with_joins(db, wo_id)
    if not wo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")
    await verify_org_ownership(wo, current_user)
    _validate_transition(wo.status, WorkOrderStatus.IN_PROGRESS, current_user.role.value)

    wo.status = WorkOrderStatus.IN_PROGRESS
    wo.updated_at = datetime.now(timezone.utc)

    await _create_timeline_event(
        db, wo, current_user, TimelineEventType.STATUS_CHANGE,
        {"resumed_from": "ON_HOLD"},
    )
    await db.flush()
    return wo


# ── POST /{id}/resolve ────────────────────────────────────────────────

@router.post("/{wo_id}/resolve", response_model=WorkOrderResponse)
async def resolve_work_order(
    wo_id: uuid.UUID,
    body: WorkOrderResolve,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Resolve a work order. FSM: IN_PROGRESS -> RESOLVED."""
    wo = await _get_wo_with_joins(db, wo_id)
    if not wo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")
    await verify_org_ownership(wo, current_user)
    _validate_transition(wo.status, WorkOrderStatus.RESOLVED, current_user.role.value)

    wo.status = WorkOrderStatus.RESOLVED
    wo.resolution_summary = body.resolution_summary
    wo.resolution_details = body.resolution_details
    wo.resolved_at = datetime.now(timezone.utc)
    wo.updated_at = datetime.now(timezone.utc)

    await _create_timeline_event(
        db, wo, current_user, TimelineEventType.STATUS_CHANGE,
        {"resolution_summary": body.resolution_summary},
    )
    await db.flush()
    return wo


# ── POST /{id}/verify ─────────────────────────────────────────────────

@router.post("/{wo_id}/verify", response_model=WorkOrderResponse)
async def verify_work_order(
    wo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["SUPER_ADMIN", "ADMIN", "SUPERVISOR", "OPERATOR"])),
):
    """Verify a resolved work order. FSM: RESOLVED -> VERIFIED."""
    wo = await _get_wo_with_joins(db, wo_id)
    if not wo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")
    await verify_org_ownership(wo, current_user)
    _validate_transition(wo.status, WorkOrderStatus.VERIFIED, current_user.role.value)

    wo.status = WorkOrderStatus.VERIFIED
    wo.verified_by = current_user.id
    wo.verified_at = datetime.now(timezone.utc)
    wo.updated_at = datetime.now(timezone.utc)

    await _create_timeline_event(
        db, wo, current_user, TimelineEventType.STATUS_CHANGE,
        {"verified_by": str(current_user.id)},
    )
    await db.flush()
    return wo


# ── POST /{id}/close ──────────────────────────────────────────────────

@router.post("/{wo_id}/close", response_model=WorkOrderResponse)
async def close_work_order(
    wo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["SUPER_ADMIN", "ADMIN", "SUPERVISOR"])),
):
    """Close a verified work order. FSM: VERIFIED -> CLOSED."""
    wo = await _get_wo_with_joins(db, wo_id)
    if not wo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")
    await verify_org_ownership(wo, current_user)
    _validate_transition(wo.status, WorkOrderStatus.CLOSED, current_user.role.value)

    wo.status = WorkOrderStatus.CLOSED
    wo.closed_by = current_user.id
    wo.closed_at = datetime.now(timezone.utc)
    wo.updated_at = datetime.now(timezone.utc)

    await _create_timeline_event(
        db, wo, current_user, TimelineEventType.STATUS_CHANGE,
        {"closed_by": str(current_user.id)},
    )
    await db.flush()
    return wo


# ── POST /{id}/reopen ─────────────────────────────────────────────────

@router.post("/{wo_id}/reopen", response_model=WorkOrderResponse)
async def reopen_work_order(
    wo_id: uuid.UUID,
    body: WorkOrderReopen,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["SUPER_ADMIN", "ADMIN"])),
):
    """Reopen a closed work order. FSM: CLOSED -> RESOLVED. Requires reason."""
    wo = await _get_wo_with_joins(db, wo_id)
    if not wo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")
    await verify_org_ownership(wo, current_user)
    _validate_transition(wo.status, WorkOrderStatus.RESOLVED, current_user.role.value)

    wo.status = WorkOrderStatus.RESOLVED
    wo.closed_at = None
    wo.closed_by = None
    wo.updated_at = datetime.now(timezone.utc)

    await _create_timeline_event(
        db, wo, current_user, TimelineEventType.MESSAGE,
        {"action": "REOPENED", "reason": body.reason},
    )
    await db.flush()
    return wo


# ── POST /{id}/escalate ───────────────────────────────────────────────

@router.post("/{wo_id}/escalate", response_model=WorkOrderResponse)
async def escalate_work_order(
    wo_id: uuid.UUID,
    body: WorkOrderEscalate = WorkOrderEscalate(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Manually escalate a work order."""
    wo = await _get_wo_with_joins(db, wo_id)
    if not wo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")
    await verify_org_ownership(wo, current_user)
    _validate_transition(wo.status, WorkOrderStatus.ESCALATED, current_user.role.value)

    wo.status = WorkOrderStatus.ESCALATED
    wo.escalated_at = datetime.now(timezone.utc)
    wo.updated_at = datetime.now(timezone.utc)

    await _create_timeline_event(
        db, wo, current_user, TimelineEventType.ESCALATED,
        {"reason": body.reason, "escalated_by": str(current_user.id)},
    )
    await db.flush()
    return wo


# ── POST /{id}/acknowledge-escalation ──────────────────────────────────

@router.post("/{wo_id}/acknowledge-escalation", response_model=WorkOrderResponse)
async def acknowledge_escalation(
    wo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["SUPER_ADMIN", "ADMIN", "SUPERVISOR"])),
):
    """Acknowledge an escalation and move back to ASSIGNED."""
    wo = await _get_wo_with_joins(db, wo_id)
    if not wo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")
    await verify_org_ownership(wo, current_user)

    if wo.status != WorkOrderStatus.ESCALATED:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Work order is not in ESCALATED state",
        )

    wo.status = WorkOrderStatus.ASSIGNED
    wo.updated_at = datetime.now(timezone.utc)

    await _create_timeline_event(
        db, wo, current_user, TimelineEventType.MESSAGE,
        {"action": "ESCALATION_ACKNOWLEDGED", "acknowledged_by": str(current_user.id)},
    )
    await db.flush()
    return wo

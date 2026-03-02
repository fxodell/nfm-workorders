"""Work-order service: creation, FSM transitions, SLA computation, querying."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.org import WOCounter
from app.models.user import User, UserRole
from app.models.work_order import (
    TimelineEvent,
    TimelineEventType,
    WorkOrder,
    WorkOrderPriority,
    WorkOrderStatus,
    WorkOrderType,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FSM transition table
# Each entry: (from_status, to_status) -> set of allowed roles
# ---------------------------------------------------------------------------

_ACTIVE_STATUSES = {
    WorkOrderStatus.NEW,
    WorkOrderStatus.ASSIGNED,
    WorkOrderStatus.ACCEPTED,
    WorkOrderStatus.IN_PROGRESS,
    WorkOrderStatus.WAITING_ON_OPS,
    WorkOrderStatus.WAITING_ON_PARTS,
}

_FSM_TRANSITIONS: dict[tuple[WorkOrderStatus, WorkOrderStatus], set[str]] = {
    (WorkOrderStatus.NEW, WorkOrderStatus.ASSIGNED): {
        UserRole.SUPERVISOR.value,
        UserRole.ADMIN.value,
    },
    (WorkOrderStatus.NEW, WorkOrderStatus.ACCEPTED): {
        UserRole.TECHNICIAN.value,
    },
    (WorkOrderStatus.ASSIGNED, WorkOrderStatus.ACCEPTED): {
        UserRole.TECHNICIAN.value,
        UserRole.SUPERVISOR.value,
    },
    (WorkOrderStatus.ACCEPTED, WorkOrderStatus.IN_PROGRESS): {
        UserRole.TECHNICIAN.value,
        UserRole.SUPERVISOR.value,
    },
    (WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.WAITING_ON_OPS): {
        UserRole.TECHNICIAN.value,
    },
    (WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.WAITING_ON_PARTS): {
        UserRole.TECHNICIAN.value,
    },
    (WorkOrderStatus.WAITING_ON_OPS, WorkOrderStatus.IN_PROGRESS): {
        UserRole.TECHNICIAN.value,
        UserRole.SUPERVISOR.value,
    },
    (WorkOrderStatus.WAITING_ON_PARTS, WorkOrderStatus.IN_PROGRESS): {
        UserRole.TECHNICIAN.value,
        UserRole.SUPERVISOR.value,
    },
    (WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.RESOLVED): {
        UserRole.TECHNICIAN.value,
    },
    (WorkOrderStatus.RESOLVED, WorkOrderStatus.VERIFIED): {
        UserRole.OPERATOR.value,
        UserRole.SUPERVISOR.value,
        UserRole.ADMIN.value,
    },
    (WorkOrderStatus.VERIFIED, WorkOrderStatus.CLOSED): {
        UserRole.SUPERVISOR.value,
        UserRole.ADMIN.value,
    },
    (WorkOrderStatus.CLOSED, WorkOrderStatus.RESOLVED): {
        UserRole.ADMIN.value,
    },
}

# Roles allowed to escalate (system escalation bypasses role check)
_ESCALATION_ROLES = {UserRole.SUPERVISOR.value, UserRole.ADMIN.value}

# Roles allowed to de-escalate
_DE_ESCALATION_ROLES = {UserRole.SUPERVISOR.value, UserRole.ADMIN.value}

# Default SLA deadlines in minutes per priority
_DEFAULT_SLA: dict[str, dict[str, int]] = {
    WorkOrderPriority.IMMEDIATE.value: {
        "ack_minutes": 15,
        "first_update_minutes": 30,
        "resolve_minutes": 240,
    },
    WorkOrderPriority.URGENT.value: {
        "ack_minutes": 30,
        "first_update_minutes": 60,
        "resolve_minutes": 480,
    },
    WorkOrderPriority.SCHEDULED.value: {
        "ack_minutes": 120,
        "first_update_minutes": 240,
        "resolve_minutes": 2880,
    },
    WorkOrderPriority.DEFERRED.value: {
        "ack_minutes": 1440,
        "first_update_minutes": 2880,
        "resolve_minutes": 10080,
    },
}


# ---------------------------------------------------------------------------
# Human-readable number generation
# ---------------------------------------------------------------------------


async def generate_human_readable_number(
    db: AsyncSession,
    org_id: uuid.UUID,
) -> str:
    """Atomically generate the next human-readable work-order number.

    Uses SELECT FOR UPDATE on the WOCounter row for the current year to
    guarantee uniqueness even under concurrent requests.  If no counter row
    exists for the current year, one is created with counter=1.

    Returns a string like ``"WO-2026-000001"``.
    """
    now = datetime.now(timezone.utc)
    year = now.year

    # Try to fetch the counter with a row-level lock
    stmt = (
        select(WOCounter)
        .where(
            WOCounter.org_id == org_id,
            WOCounter.year == year,
        )
        .with_for_update()
    )
    result = await db.execute(stmt)
    counter_row = result.scalars().first()

    if counter_row is None:
        counter_row = WOCounter(
            org_id=org_id,
            year=year,
            counter=1,
        )
        db.add(counter_row)
    else:
        counter_row.counter += 1

    await db.flush()
    return f"WO-{year}-{counter_row.counter:06d}"


# ---------------------------------------------------------------------------
# SLA deadline computation
# ---------------------------------------------------------------------------


def compute_sla_deadlines(
    priority: WorkOrderPriority,
    org_config: dict | None,
    created_at: datetime,
) -> dict[str, datetime]:
    """Compute SLA deadlines for a work order based on priority.

    ``org_config`` may contain an ``"sla"`` key whose value is a dict
    keyed by priority name with ``ack_minutes``, ``first_update_minutes``,
    and ``resolve_minutes``.  Falls back to built-in defaults if missing.

    Returns a dict with keys ``ack_deadline``, ``first_update_deadline``,
    and ``due_at``.
    """
    sla_cfg = (org_config or {}).get("sla", {}).get(priority.value, {})
    defaults = _DEFAULT_SLA.get(priority.value, _DEFAULT_SLA[WorkOrderPriority.SCHEDULED.value])

    ack_min = sla_cfg.get("ack_minutes", defaults["ack_minutes"])
    update_min = sla_cfg.get("first_update_minutes", defaults["first_update_minutes"])
    resolve_min = sla_cfg.get("resolve_minutes", defaults["resolve_minutes"])

    return {
        "ack_deadline": created_at + timedelta(minutes=ack_min),
        "first_update_deadline": created_at + timedelta(minutes=update_min),
        "due_at": created_at + timedelta(minutes=resolve_min),
    }


# ---------------------------------------------------------------------------
# FSM validation
# ---------------------------------------------------------------------------


def validate_fsm_transition(
    current_status: WorkOrderStatus,
    new_status: WorkOrderStatus,
    user_role: str,
) -> None:
    """Validate that a status transition is allowed for the given role.

    Raises ``HTTPException(422)`` if the transition is invalid.
    """
    # Handle escalation from any active status
    if new_status == WorkOrderStatus.ESCALATED:
        if current_status not in _ACTIVE_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Cannot escalate from status {current_status.value}; "
                    f"only active statuses may be escalated."
                ),
            )
        if user_role not in _ESCALATION_ROLES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Role '{user_role}' is not allowed to escalate work orders."
                ),
            )
        return

    # Handle de-escalation (ESCALATED -> previous status)
    if current_status == WorkOrderStatus.ESCALATED:
        if user_role not in _DE_ESCALATION_ROLES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Role '{user_role}' is not allowed to de-escalate work orders."
                ),
            )
        # The target status will be stored in ``previous_status`` on the WO;
        # the caller is responsible for selecting a valid previous status.
        return

    key = (current_status, new_status)
    allowed_roles = _FSM_TRANSITIONS.get(key)

    if allowed_roles is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Status transition from {current_status.value} to "
                f"{new_status.value} is not allowed."
            ),
        )

    if user_role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Role '{user_role}' cannot transition from "
                f"{current_status.value} to {new_status.value}."
            ),
        )

    # Extra validations
    if new_status == WorkOrderStatus.RESOLVED:
        # Resolution summary requirement is enforced in transition_status
        pass

    if current_status == WorkOrderStatus.CLOSED and new_status == WorkOrderStatus.RESOLVED:
        # Reopen reason is enforced in transition_status
        pass


# ---------------------------------------------------------------------------
# Status transition
# ---------------------------------------------------------------------------


async def transition_status(
    db: AsyncSession,
    wo: WorkOrder,
    new_status: WorkOrderStatus,
    user: User,
    *,
    assigned_to: uuid.UUID | None = None,
    resolution_summary: str | None = None,
    resolution_details: str | None = None,
    reason: str | None = None,
    eta_minutes: int | None = None,
    gps_lat: float | None = None,
    gps_lng: float | None = None,
    previous_status: WorkOrderStatus | None = None,
) -> WorkOrder:
    """Perform a validated status transition on a work order.

    Updates relevant timestamps, records a ``TimelineEvent``, and flushes
    the session so the caller can inspect the updated state before commit.
    """
    now = datetime.now(timezone.utc)
    old_status = wo.status

    # Build timeline payload
    payload: dict[str, Any] = {
        "from_status": old_status.value,
        "to_status": new_status.value,
    }

    # ----- per-transition side-effects -----

    if new_status == WorkOrderStatus.ASSIGNED:
        if assigned_to is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="assigned_to is required when transitioning to ASSIGNED.",
            )
        wo.assigned_to = assigned_to
        wo.assigned_at = now
        payload["assigned_to"] = str(assigned_to)

    elif new_status == WorkOrderStatus.ACCEPTED:
        wo.accepted_by = user.id
        wo.accepted_at = now
        if eta_minutes is not None:
            wo.eta_minutes = eta_minutes
            payload["eta_minutes"] = eta_minutes
        if gps_lat is not None and gps_lng is not None:
            wo.gps_lat_accept = gps_lat
            wo.gps_lng_accept = gps_lng

    elif new_status == WorkOrderStatus.IN_PROGRESS:
        if wo.in_progress_at is None:
            wo.in_progress_at = now
        if gps_lat is not None and gps_lng is not None:
            wo.gps_lat_start = gps_lat
            wo.gps_lng_start = gps_lng

    elif new_status == WorkOrderStatus.RESOLVED:
        if old_status == WorkOrderStatus.CLOSED:
            # Reopen flow: CLOSED -> RESOLVED requires reason
            if not reason:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="reason is required to reopen a closed work order.",
                )
            payload["reopen_reason"] = reason
        else:
            # Normal resolve flow
            if not resolution_summary:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="resolution_summary is required to resolve a work order.",
                )
            wo.resolution_summary = resolution_summary
            wo.resolution_details = resolution_details
            payload["resolution_summary"] = resolution_summary
        wo.resolved_at = now
        if gps_lat is not None and gps_lng is not None:
            wo.gps_lat_resolve = gps_lat
            wo.gps_lng_resolve = gps_lng

    elif new_status == WorkOrderStatus.VERIFIED:
        wo.verified_by = user.id
        wo.verified_at = now

    elif new_status == WorkOrderStatus.CLOSED:
        wo.closed_by = user.id
        wo.closed_at = now

    elif new_status == WorkOrderStatus.ESCALATED:
        wo.escalated_at = now
        # Store the pre-escalation status in custom_fields for de-escalation
        if wo.custom_fields is None:
            wo.custom_fields = {}
        wo.custom_fields["pre_escalation_status"] = old_status.value
        if reason:
            payload["escalation_reason"] = reason

    elif new_status in (WorkOrderStatus.WAITING_ON_OPS, WorkOrderStatus.WAITING_ON_PARTS):
        if reason:
            payload["wait_reason"] = reason

    # De-escalation: restore previous status
    if old_status == WorkOrderStatus.ESCALATED and new_status != WorkOrderStatus.ESCALATED:
        wo.escalated_at = None

    wo.status = new_status
    wo.updated_at = now

    # Record timeline event
    event = TimelineEvent(
        work_order_id=wo.id,
        org_id=wo.org_id,
        user_id=user.id,
        event_type=TimelineEventType.STATUS_CHANGE,
        payload=payload,
    )
    db.add(event)

    await db.flush()
    return wo


# ---------------------------------------------------------------------------
# Work-order creation
# ---------------------------------------------------------------------------


async def create_work_order(
    db: AsyncSession,
    data: dict[str, Any],
    user: User,
    org_config: dict | None,
) -> WorkOrder:
    """Create a new work order with human-readable number and SLA deadlines.

    ``data`` should contain the validated fields from the request schema.
    The caller is responsible for verifying area access and org ownership.
    """
    now = datetime.now(timezone.utc)

    human_readable_number = await generate_human_readable_number(db, user.org_id)

    # Map priority for SLA
    priority = data.get("priority", WorkOrderPriority.SCHEDULED)
    if isinstance(priority, str):
        priority = WorkOrderPriority(priority)

    sla = compute_sla_deadlines(priority, org_config, now)

    wo = WorkOrder(
        org_id=user.org_id,
        area_id=data["area_id"],
        location_id=data["location_id"],
        site_id=data["site_id"],
        asset_id=data.get("asset_id"),
        human_readable_number=human_readable_number,
        title=data["title"],
        description=data.get("description"),
        type=data.get("type", WorkOrderType.REACTIVE),
        priority=priority,
        status=WorkOrderStatus.NEW,
        requested_by=user.id,
        assigned_to=data.get("assigned_to"),
        created_at=now,
        updated_at=now,
        ack_deadline=sla["ack_deadline"],
        first_update_deadline=sla["first_update_deadline"],
        due_at=sla["due_at"],
        safety_flag=data.get("safety_flag", False),
        safety_notes=data.get("safety_notes"),
        required_cert=data.get("required_cert"),
        tags=data.get("tags"),
        custom_fields=data.get("custom_fields"),
        idempotency_key=data.get("idempotency_key"),
    )
    db.add(wo)
    await db.flush()

    # Initial timeline event
    event = TimelineEvent(
        work_order_id=wo.id,
        org_id=wo.org_id,
        user_id=user.id,
        event_type=TimelineEventType.STATUS_CHANGE,
        payload={
            "from_status": None,
            "to_status": WorkOrderStatus.NEW.value,
        },
    )
    db.add(event)
    await db.flush()

    logger.info(
        "Created work order %s (%s) for org %s",
        wo.human_readable_number,
        wo.id,
        wo.org_id,
    )
    return wo


# ---------------------------------------------------------------------------
# Work-order listing
# ---------------------------------------------------------------------------


async def get_work_orders(
    db: AsyncSession,
    org_id: uuid.UUID,
    area_ids: list[uuid.UUID] | None = None,
    filters: dict[str, Any] | None = None,
    pagination: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Return a paginated, filtered list of work orders for an org.

    ``filters`` may include:
        - ``status`` (str or list[str])
        - ``priority`` (str or list[str])
        - ``type`` (str or list[str])
        - ``assigned_to`` (UUID)
        - ``requested_by`` (UUID)
        - ``asset_id`` (UUID)
        - ``site_id`` (UUID)
        - ``location_id`` (UUID)
        - ``safety_flag`` (bool)
        - ``search`` (str) -- searches title and human_readable_number
        - ``created_after`` (datetime)
        - ``created_before`` (datetime)
        - ``sort_by`` (str, default "created_at")
        - ``sort_order`` ("asc" | "desc", default "desc")

    ``pagination`` dict with ``page`` (1-indexed) and ``per_page``.
    """
    filters = filters or {}
    pagination = pagination or {}
    page = max(pagination.get("page", 1), 1)
    per_page = min(max(pagination.get("per_page", 20), 1), 100)

    conditions = [WorkOrder.org_id == org_id]

    if area_ids is not None:
        conditions.append(WorkOrder.area_id.in_(area_ids))

    # Status filter
    if "status" in filters:
        status_val = filters["status"]
        if isinstance(status_val, list):
            conditions.append(WorkOrder.status.in_(status_val))
        else:
            conditions.append(WorkOrder.status == status_val)

    # Priority filter
    if "priority" in filters:
        priority_val = filters["priority"]
        if isinstance(priority_val, list):
            conditions.append(WorkOrder.priority.in_(priority_val))
        else:
            conditions.append(WorkOrder.priority == priority_val)

    # Type filter
    if "type" in filters:
        type_val = filters["type"]
        if isinstance(type_val, list):
            conditions.append(WorkOrder.type.in_(type_val))
        else:
            conditions.append(WorkOrder.type == type_val)

    # Specific FK filters
    if "assigned_to" in filters and filters["assigned_to"] is not None:
        conditions.append(WorkOrder.assigned_to == filters["assigned_to"])
    if "requested_by" in filters and filters["requested_by"] is not None:
        conditions.append(WorkOrder.requested_by == filters["requested_by"])
    if "asset_id" in filters and filters["asset_id"] is not None:
        conditions.append(WorkOrder.asset_id == filters["asset_id"])
    if "site_id" in filters and filters["site_id"] is not None:
        conditions.append(WorkOrder.site_id == filters["site_id"])
    if "location_id" in filters and filters["location_id"] is not None:
        conditions.append(WorkOrder.location_id == filters["location_id"])

    # Boolean filters
    if "safety_flag" in filters:
        conditions.append(WorkOrder.safety_flag == filters["safety_flag"])

    # Text search
    if "search" in filters and filters["search"]:
        search_term = f"%{filters['search']}%"
        conditions.append(
            WorkOrder.title.ilike(search_term)
            | WorkOrder.human_readable_number.ilike(search_term)
        )

    # Date range
    if "created_after" in filters and filters["created_after"] is not None:
        conditions.append(WorkOrder.created_at >= filters["created_after"])
    if "created_before" in filters and filters["created_before"] is not None:
        conditions.append(WorkOrder.created_at <= filters["created_before"])

    # Sorting
    sort_by = filters.get("sort_by", "created_at")
    sort_order = filters.get("sort_order", "desc")
    sort_column = getattr(WorkOrder, sort_by, WorkOrder.created_at)
    if sort_order == "asc":
        order_clause = sort_column.asc()
    else:
        order_clause = sort_column.desc()

    # Count total
    count_stmt = select(func.count()).select_from(WorkOrder).where(and_(*conditions))
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # Fetch page
    offset = (page - 1) * per_page
    query = (
        select(WorkOrder)
        .where(and_(*conditions))
        .order_by(order_clause)
        .offset(offset)
        .limit(per_page)
    )
    result = await db.execute(query)
    items = list(result.scalars().all())

    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
    }

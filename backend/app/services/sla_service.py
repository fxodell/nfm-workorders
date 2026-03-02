"""SLA monitoring service: breach detection, escalation, acknowledgment."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sla import SLAEvent, SLAEventType
from app.models.user import User
from app.models.work_order import (
    TimelineEvent,
    TimelineEventType,
    WorkOrder,
    WorkOrderStatus,
)

logger = logging.getLogger(__name__)

# Statuses considered "resolved" or beyond -- not subject to breach
_CLOSED_STATUSES = {
    WorkOrderStatus.RESOLVED,
    WorkOrderStatus.VERIFIED,
    WorkOrderStatus.CLOSED,
}


# ---------------------------------------------------------------------------
# Breach detection queries
# ---------------------------------------------------------------------------


async def check_ack_breaches(
    db: AsyncSession,
) -> list[WorkOrder]:
    """Find work orders that have exceeded their acknowledgment deadline.

    A work order is considered breached when:
    - ``ack_deadline`` is in the past
    - ``accepted_at`` is NULL (technician has not accepted)
    - Status is not yet resolved/verified/closed
    - No existing ``ACK_BREACH`` SLA event has been recorded for this WO
    """
    now = datetime.now(timezone.utc)

    already_breached_subq = (
        select(SLAEvent.work_order_id)
        .where(SLAEvent.event_type == SLAEventType.ACK_BREACH)
        .subquery()
    )

    stmt = (
        select(WorkOrder)
        .where(
            WorkOrder.ack_deadline.isnot(None),
            WorkOrder.ack_deadline < now,
            WorkOrder.accepted_at.is_(None),
            WorkOrder.status.notin_(_CLOSED_STATUSES),
            WorkOrder.id.notin_(select(already_breached_subq.c.work_order_id)),
        )
    )

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def check_first_update_breaches(
    db: AsyncSession,
) -> list[WorkOrder]:
    """Find work orders past their first-update deadline with no user timeline events.

    A breach occurs when:
    - ``first_update_deadline`` is in the past
    - No ``TimelineEvent`` with a non-null ``user_id`` exists (aside from the
      initial creation event)
    - Status is not resolved/verified/closed
    - No ``FIRST_UPDATE_BREACH`` SLA event already recorded
    """
    now = datetime.now(timezone.utc)

    already_breached_subq = (
        select(SLAEvent.work_order_id)
        .where(SLAEvent.event_type == SLAEventType.FIRST_UPDATE_BREACH)
        .subquery()
    )

    # Sub-query for WOs that have at least one user-generated timeline event
    # beyond the initial status change to NEW.
    has_user_update_subq = (
        select(TimelineEvent.work_order_id)
        .where(
            TimelineEvent.user_id.isnot(None),
            TimelineEvent.event_type != TimelineEventType.STATUS_CHANGE,
        )
        .group_by(TimelineEvent.work_order_id)
        .subquery()
    )

    stmt = (
        select(WorkOrder)
        .where(
            WorkOrder.first_update_deadline.isnot(None),
            WorkOrder.first_update_deadline < now,
            WorkOrder.status.notin_(_CLOSED_STATUSES),
            WorkOrder.id.notin_(select(already_breached_subq.c.work_order_id)),
            WorkOrder.id.notin_(select(has_user_update_subq.c.work_order_id)),
        )
    )

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def check_resolve_breaches(
    db: AsyncSession,
) -> list[WorkOrder]:
    """Find work orders past their resolution deadline.

    A breach occurs when:
    - ``due_at`` is in the past
    - Status is not resolved/verified/closed
    - No ``RESOLVE_BREACH`` SLA event already recorded
    """
    now = datetime.now(timezone.utc)

    already_breached_subq = (
        select(SLAEvent.work_order_id)
        .where(SLAEvent.event_type == SLAEventType.RESOLVE_BREACH)
        .subquery()
    )

    stmt = (
        select(WorkOrder)
        .where(
            WorkOrder.due_at.isnot(None),
            WorkOrder.due_at < now,
            WorkOrder.status.notin_(_CLOSED_STATUSES),
            WorkOrder.id.notin_(select(already_breached_subq.c.work_order_id)),
        )
    )

    result = await db.execute(stmt)
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Escalation
# ---------------------------------------------------------------------------


async def escalate_work_order(
    db: AsyncSession,
    wo: WorkOrder,
    redis: Any,
    *,
    breach_type: SLAEventType | None = None,
    reason: str | None = None,
) -> SLAEvent:
    """Set a work order to ESCALATED status, create an SLAEvent, and publish via WS.

    This is called either by the SLA check background job or by a manual
    supervisor escalation.  The ``breach_type`` should be provided when
    called from an automated check; it defaults to ``MANUAL_ESCALATION``.
    """
    now = datetime.now(timezone.utc)
    event_type = breach_type or SLAEventType.MANUAL_ESCALATION

    # Store pre-escalation status for de-escalation
    pre_escalation_status = wo.status.value
    if wo.custom_fields is None:
        wo.custom_fields = {}
    wo.custom_fields["pre_escalation_status"] = pre_escalation_status

    wo.status = WorkOrderStatus.ESCALATED
    wo.escalated_at = now
    wo.updated_at = now

    sla_event = SLAEvent(
        work_order_id=wo.id,
        org_id=wo.org_id,
        event_type=event_type,
        triggered_at=now,
    )
    db.add(sla_event)

    # Timeline entry
    payload: dict[str, Any] = {
        "from_status": pre_escalation_status,
        "to_status": WorkOrderStatus.ESCALATED.value,
        "breach_type": event_type.value,
    }
    if reason:
        payload["reason"] = reason

    event = TimelineEvent(
        work_order_id=wo.id,
        org_id=wo.org_id,
        user_id=None,  # system-generated
        event_type=TimelineEventType.ESCALATION,
        payload=payload,
    )
    db.add(event)

    await db.flush()

    # Publish WS event
    channel = f"org:{wo.org_id}:area:{wo.area_id}"
    ws_payload = json.dumps({
        "event": "work_order.escalated",
        "work_order_id": str(wo.id),
        "human_readable_number": wo.human_readable_number,
        "breach_type": event_type.value,
        "reason": reason,
    })
    await redis.publish(channel, ws_payload)

    logger.warning(
        "Escalated work order %s (%s) due to %s",
        wo.human_readable_number,
        wo.id,
        event_type.value,
    )
    return sla_event


# ---------------------------------------------------------------------------
# Acknowledge escalation
# ---------------------------------------------------------------------------


async def acknowledge_escalation(
    db: AsyncSession,
    wo: WorkOrder,
    user: User,
) -> SLAEvent:
    """Clear escalation status and record an acknowledgment SLAEvent.

    Restores the work order to its pre-escalation status (stored in
    ``custom_fields["pre_escalation_status"]``).
    """
    now = datetime.now(timezone.utc)

    # Determine restore status
    pre_status_value = (wo.custom_fields or {}).get("pre_escalation_status")
    if pre_status_value:
        restore_status = WorkOrderStatus(pre_status_value)
    else:
        # Fallback if pre-escalation status was not stored
        restore_status = WorkOrderStatus.IN_PROGRESS

    wo.status = restore_status
    wo.escalated_at = None
    wo.updated_at = now

    # Clean up custom fields
    if wo.custom_fields and "pre_escalation_status" in wo.custom_fields:
        del wo.custom_fields["pre_escalation_status"]

    sla_event = SLAEvent(
        work_order_id=wo.id,
        org_id=wo.org_id,
        event_type=SLAEventType.ACKNOWLEDGED,
        triggered_at=now,
        acknowledged_by=user.id,
        acknowledged_at=now,
    )
    db.add(sla_event)

    # Timeline entry
    event = TimelineEvent(
        work_order_id=wo.id,
        org_id=wo.org_id,
        user_id=user.id,
        event_type=TimelineEventType.STATUS_CHANGE,
        payload={
            "from_status": WorkOrderStatus.ESCALATED.value,
            "to_status": restore_status.value,
            "action": "escalation_acknowledged",
        },
    )
    db.add(event)

    await db.flush()

    logger.info(
        "Escalation acknowledged on %s by user %s, restored to %s",
        wo.human_readable_number,
        user.id,
        restore_status.value,
    )
    return sla_event

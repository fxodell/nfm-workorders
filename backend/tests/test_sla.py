"""
SLA breach detection and escalation tests.

Validates that:
- Acknowledgment (ACK) breaches are detected when the deadline passes without
  technician acceptance
- First-update breaches are detected when no user activity occurs before
  the deadline
- Resolution breaches are detected when due_at passes without resolution
- SLA breaches create SLAEvent records
- Breaches trigger automatic escalation
- Acknowledging an escalation restores the pre-escalation status
- Duplicate breaches are not created (idempotent breach detection)
- Non-breached work orders are correctly excluded
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models.sla import SLAEvent, SLAEventType
from app.models.work_order import (
    TimelineEvent,
    TimelineEventType,
    WorkOrder,
    WorkOrderStatus,
)
from app.services.sla_service import (
    acknowledge_escalation,
    check_ack_breaches,
    check_first_update_breaches,
    check_resolve_breaches,
    escalate_work_order,
)
from tests.conftest import FakeRedis

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# ACK breach detection
# ---------------------------------------------------------------------------


async def test_ack_breach_detected_when_past_deadline(
    db_session, org_a_hierarchy, create_work_order,
):
    """A work order with ack_deadline in the past and no accepted_at should
    be returned by check_ack_breaches."""
    h = org_a_hierarchy
    past_deadline = datetime.now(timezone.utc) - timedelta(minutes=30)

    wo = await create_work_order(
        org_id=h["org"].id,
        area_id=h["area"].id,
        location_id=h["location"].id,
        site_id=h["site"].id,
        requested_by=h["admin"].id,
        status=WorkOrderStatus.NEW,
        ack_deadline=past_deadline,
    )

    breached = await check_ack_breaches(db_session)
    breached_ids = [w.id for w in breached]
    assert wo.id in breached_ids, "WO past ack deadline should be detected"


async def test_ack_breach_not_detected_when_accepted(
    db_session, org_a_hierarchy, create_work_order,
):
    """A work order that has been accepted (accepted_at is set) should not
    trigger an ACK breach even if the deadline has passed."""
    h = org_a_hierarchy
    past_deadline = datetime.now(timezone.utc) - timedelta(minutes=30)

    wo = await create_work_order(
        org_id=h["org"].id,
        area_id=h["area"].id,
        location_id=h["location"].id,
        site_id=h["site"].id,
        requested_by=h["admin"].id,
        status=WorkOrderStatus.ACCEPTED,
        ack_deadline=past_deadline,
    )
    # Simulate that the WO was accepted
    wo.accepted_at = datetime.now(timezone.utc) - timedelta(minutes=45)
    await db_session.flush()

    breached = await check_ack_breaches(db_session)
    breached_ids = [w.id for w in breached]
    assert wo.id not in breached_ids, "Accepted WO should not be flagged as breached"


async def test_ack_breach_not_detected_for_resolved(
    db_session, org_a_hierarchy, create_work_order,
):
    """Resolved/verified/closed work orders should not trigger ACK breaches."""
    h = org_a_hierarchy
    past_deadline = datetime.now(timezone.utc) - timedelta(minutes=30)

    wo = await create_work_order(
        org_id=h["org"].id,
        area_id=h["area"].id,
        location_id=h["location"].id,
        site_id=h["site"].id,
        requested_by=h["admin"].id,
        status=WorkOrderStatus.RESOLVED,
        ack_deadline=past_deadline,
    )

    breached = await check_ack_breaches(db_session)
    breached_ids = [w.id for w in breached]
    assert wo.id not in breached_ids


# ---------------------------------------------------------------------------
# First-update breach detection
# ---------------------------------------------------------------------------


async def test_first_update_breach_detected(
    db_session, org_a_hierarchy, create_work_order,
):
    """A work order past its first_update_deadline with no user updates
    should be detected by check_first_update_breaches."""
    h = org_a_hierarchy
    past_deadline = datetime.now(timezone.utc) - timedelta(hours=2)

    wo = await create_work_order(
        org_id=h["org"].id,
        area_id=h["area"].id,
        location_id=h["location"].id,
        site_id=h["site"].id,
        requested_by=h["admin"].id,
        status=WorkOrderStatus.ASSIGNED,
        first_update_deadline=past_deadline,
    )

    breached = await check_first_update_breaches(db_session)
    breached_ids = [w.id for w in breached]
    assert wo.id in breached_ids


async def test_first_update_breach_not_detected_with_user_update(
    db_session, org_a_hierarchy, create_work_order,
):
    """A work order that has received a user-generated timeline event
    should not trigger a first-update breach."""
    h = org_a_hierarchy
    past_deadline = datetime.now(timezone.utc) - timedelta(hours=2)

    wo = await create_work_order(
        org_id=h["org"].id,
        area_id=h["area"].id,
        location_id=h["location"].id,
        site_id=h["site"].id,
        requested_by=h["admin"].id,
        status=WorkOrderStatus.ASSIGNED,
        first_update_deadline=past_deadline,
    )

    # Simulate a user-generated note event (not a STATUS_CHANGE)
    note_event = TimelineEvent(
        work_order_id=wo.id,
        org_id=h["org"].id,
        user_id=h["tech"].id,
        event_type=TimelineEventType.NOTE,
        payload={"message": "Investigating the issue"},
    )
    db_session.add(note_event)
    await db_session.flush()

    breached = await check_first_update_breaches(db_session)
    breached_ids = [w.id for w in breached]
    assert wo.id not in breached_ids


# ---------------------------------------------------------------------------
# Resolve breach detection
# ---------------------------------------------------------------------------


async def test_resolve_breach_detected(
    db_session, org_a_hierarchy, create_work_order,
):
    """A work order past due_at that is not resolved should be detected."""
    h = org_a_hierarchy
    past_deadline = datetime.now(timezone.utc) - timedelta(hours=8)

    wo = await create_work_order(
        org_id=h["org"].id,
        area_id=h["area"].id,
        location_id=h["location"].id,
        site_id=h["site"].id,
        requested_by=h["admin"].id,
        status=WorkOrderStatus.IN_PROGRESS,
        due_at=past_deadline,
    )

    breached = await check_resolve_breaches(db_session)
    breached_ids = [w.id for w in breached]
    assert wo.id in breached_ids


async def test_resolve_breach_not_detected_when_resolved(
    db_session, org_a_hierarchy, create_work_order,
):
    """A resolved work order should not trigger a resolve breach."""
    h = org_a_hierarchy
    past_deadline = datetime.now(timezone.utc) - timedelta(hours=8)

    wo = await create_work_order(
        org_id=h["org"].id,
        area_id=h["area"].id,
        location_id=h["location"].id,
        site_id=h["site"].id,
        requested_by=h["admin"].id,
        status=WorkOrderStatus.RESOLVED,
        due_at=past_deadline,
    )

    breached = await check_resolve_breaches(db_session)
    breached_ids = [w.id for w in breached]
    assert wo.id not in breached_ids


# ---------------------------------------------------------------------------
# SLA breach event creation
# ---------------------------------------------------------------------------


async def test_sla_breach_creates_event(
    db_session, org_a_hierarchy, create_work_order, fake_redis,
):
    """Escalating a work order should create an SLAEvent record."""
    h = org_a_hierarchy
    wo = await create_work_order(
        org_id=h["org"].id,
        area_id=h["area"].id,
        location_id=h["location"].id,
        site_id=h["site"].id,
        requested_by=h["admin"].id,
        status=WorkOrderStatus.NEW,
    )

    sla_event = await escalate_work_order(
        db_session, wo, fake_redis,
        breach_type=SLAEventType.ACK_BREACH,
        reason="Acknowledgment deadline exceeded",
    )

    assert sla_event.event_type == SLAEventType.ACK_BREACH
    assert sla_event.work_order_id == wo.id
    assert sla_event.org_id == h["org"].id
    assert sla_event.triggered_at is not None

    # Verify the event was persisted
    result = await db_session.execute(
        select(SLAEvent).where(SLAEvent.work_order_id == wo.id)
    )
    events = result.scalars().all()
    assert len(events) >= 1


# ---------------------------------------------------------------------------
# SLA breach escalation
# ---------------------------------------------------------------------------


async def test_sla_breach_escalates_work_order(
    db_session, org_a_hierarchy, create_work_order, fake_redis,
):
    """An SLA breach should change the work order status to ESCALATED."""
    h = org_a_hierarchy
    wo = await create_work_order(
        org_id=h["org"].id,
        area_id=h["area"].id,
        location_id=h["location"].id,
        site_id=h["site"].id,
        requested_by=h["admin"].id,
        status=WorkOrderStatus.IN_PROGRESS,
    )

    await escalate_work_order(
        db_session, wo, fake_redis,
        breach_type=SLAEventType.RESOLVE_BREACH,
    )

    assert wo.status == WorkOrderStatus.ESCALATED
    assert wo.escalated_at is not None
    # Pre-escalation status should be stored
    assert wo.custom_fields is not None
    assert wo.custom_fields.get("pre_escalation_status") == "IN_PROGRESS"


async def test_escalation_publishes_ws_event(
    db_session, org_a_hierarchy, create_work_order, fake_redis,
):
    """Escalation should publish a WebSocket event via Redis pub/sub."""
    h = org_a_hierarchy
    wo = await create_work_order(
        org_id=h["org"].id,
        area_id=h["area"].id,
        location_id=h["location"].id,
        site_id=h["site"].id,
        requested_by=h["admin"].id,
        status=WorkOrderStatus.ASSIGNED,
    )

    await escalate_work_order(
        db_session, wo, fake_redis,
        breach_type=SLAEventType.ACK_BREACH,
    )

    # Verify WS event was published
    assert len(fake_redis._published) >= 1
    channel, message = fake_redis._published[-1]
    assert str(wo.org_id) in channel
    assert "work_order.escalated" in message


# ---------------------------------------------------------------------------
# Acknowledge escalation
# ---------------------------------------------------------------------------


async def test_acknowledge_escalation_restores_status(
    db_session, org_a_hierarchy, create_work_order, fake_redis,
):
    """Acknowledging an escalation should restore the pre-escalation status."""
    h = org_a_hierarchy
    wo = await create_work_order(
        org_id=h["org"].id,
        area_id=h["area"].id,
        location_id=h["location"].id,
        site_id=h["site"].id,
        requested_by=h["admin"].id,
        status=WorkOrderStatus.IN_PROGRESS,
    )

    # First escalate
    await escalate_work_order(
        db_session, wo, fake_redis,
        breach_type=SLAEventType.RESOLVE_BREACH,
    )
    assert wo.status == WorkOrderStatus.ESCALATED

    # Then acknowledge
    sla_event = await acknowledge_escalation(db_session, wo, h["supervisor"])

    assert wo.status == WorkOrderStatus.IN_PROGRESS, (
        "Status should be restored to the pre-escalation state"
    )
    assert wo.escalated_at is None
    assert sla_event.event_type == SLAEventType.ACKNOWLEDGED
    assert sla_event.acknowledged_by == h["supervisor"].id
    assert sla_event.acknowledged_at is not None


async def test_acknowledge_creates_timeline_event(
    db_session, org_a_hierarchy, create_work_order, fake_redis,
):
    """Acknowledging an escalation should create a STATUS_CHANGE timeline event."""
    h = org_a_hierarchy
    wo = await create_work_order(
        org_id=h["org"].id,
        area_id=h["area"].id,
        location_id=h["location"].id,
        site_id=h["site"].id,
        requested_by=h["admin"].id,
        status=WorkOrderStatus.ASSIGNED,
    )

    await escalate_work_order(
        db_session, wo, fake_redis,
        breach_type=SLAEventType.ACK_BREACH,
    )
    await acknowledge_escalation(db_session, wo, h["supervisor"])

    result = await db_session.execute(
        select(TimelineEvent).where(
            TimelineEvent.work_order_id == wo.id,
            TimelineEvent.event_type == TimelineEventType.STATUS_CHANGE,
        )
    )
    events = result.scalars().all()

    # Find the acknowledgment event
    ack_events = [
        e for e in events
        if e.payload and e.payload.get("action") == "escalation_acknowledged"
    ]
    assert len(ack_events) >= 1, "Should have an acknowledgment timeline event"
    assert ack_events[0].payload["from_status"] == "ESCALATED"


# ---------------------------------------------------------------------------
# Idempotent breach detection
# ---------------------------------------------------------------------------


async def test_double_breach_not_created(
    db_session, org_a_hierarchy, create_work_order, fake_redis,
):
    """Running breach detection twice should not create duplicate SLAEvents
    for the same work order and breach type (idempotent)."""
    h = org_a_hierarchy
    past_deadline = datetime.now(timezone.utc) - timedelta(minutes=30)

    wo = await create_work_order(
        org_id=h["org"].id,
        area_id=h["area"].id,
        location_id=h["location"].id,
        site_id=h["site"].id,
        requested_by=h["admin"].id,
        status=WorkOrderStatus.NEW,
        ack_deadline=past_deadline,
    )

    # First check -- should detect the breach
    breached_first = await check_ack_breaches(db_session)
    assert wo.id in [w.id for w in breached_first]

    # Simulate creating the SLA event (as the background job would)
    sla_event = SLAEvent(
        work_order_id=wo.id,
        org_id=h["org"].id,
        event_type=SLAEventType.ACK_BREACH,
        triggered_at=datetime.now(timezone.utc),
    )
    db_session.add(sla_event)
    await db_session.flush()

    # Second check -- the same WO should NOT appear again
    breached_second = await check_ack_breaches(db_session)
    assert wo.id not in [w.id for w in breached_second], (
        "WO should not be detected as breached again after SLAEvent was created"
    )

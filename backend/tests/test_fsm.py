"""
Finite State Machine (FSM) transition tests for work order status lifecycle.

Validates that:
- All valid status transitions succeed when performed by authorized roles
- Invalid/illegal transitions are rejected with HTTP 422
- Role restrictions are enforced for privileged transitions
- Required fields (resolution_summary, reason) are enforced
- GPS coordinates are captured on accept/start/resolve
- TimelineEvents are created for each transition

The FSM graph tested here matches the transition table defined in
app.services.work_order_service._FSM_TRANSITIONS and the route-layer
VALID_TRANSITIONS dict in app.api.work_orders.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from fastapi import HTTPException

from app.models.user import User, UserRole
from app.models.work_order import (
    WorkOrder,
    WorkOrderPriority,
    WorkOrderStatus,
    WorkOrderType,
)
from app.services.work_order_service import (
    transition_status,
    validate_fsm_transition,
)
from tests.conftest import make_auth_headers

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_in_memory_user(
    org_id: uuid.UUID,
    role: UserRole = UserRole.TECHNICIAN,
) -> User:
    """Create a minimal in-memory User object (no DB flush) for service-layer
    tests that only need role and ID."""
    user = User.__new__(User)
    user.id = uuid.uuid4()
    user.org_id = org_id
    user.role = role
    user.name = "Test User"
    user.email = f"{uuid.uuid4().hex[:8]}@test.com"
    user.is_active = True
    return user


# ---------------------------------------------------------------------------
# A. Valid transition tests (service layer)
# ---------------------------------------------------------------------------


async def test_transition_new_to_assigned(db_session, org_a_hierarchy, create_work_order):
    """NEW -> ASSIGNED is valid for SUPERVISOR and ADMIN roles."""
    h = org_a_hierarchy
    wo = await create_work_order(
        org_id=h["org"].id,
        area_id=h["area"].id,
        location_id=h["location"].id,
        site_id=h["site"].id,
        requested_by=h["admin"].id,
        status=WorkOrderStatus.NEW,
    )
    result = await transition_status(
        db_session, wo, WorkOrderStatus.ASSIGNED, h["supervisor"],
        assigned_to=h["tech"].id,
    )
    assert result.status == WorkOrderStatus.ASSIGNED
    assert result.assigned_to == h["tech"].id
    assert result.assigned_at is not None


async def test_transition_new_to_accepted(db_session, org_a_hierarchy, create_work_order):
    """NEW -> ACCEPTED is valid (auto-assigns to accepting technician)."""
    h = org_a_hierarchy
    wo = await create_work_order(
        org_id=h["org"].id,
        area_id=h["area"].id,
        location_id=h["location"].id,
        site_id=h["site"].id,
        requested_by=h["admin"].id,
        status=WorkOrderStatus.NEW,
    )
    result = await transition_status(
        db_session, wo, WorkOrderStatus.ACCEPTED, h["tech"],
    )
    assert result.status == WorkOrderStatus.ACCEPTED
    assert result.accepted_by == h["tech"].id
    assert result.accepted_at is not None


async def test_transition_assigned_to_accepted(db_session, org_a_hierarchy, create_work_order):
    """ASSIGNED -> ACCEPTED is valid for technicians."""
    h = org_a_hierarchy
    wo = await create_work_order(
        org_id=h["org"].id,
        area_id=h["area"].id,
        location_id=h["location"].id,
        site_id=h["site"].id,
        requested_by=h["admin"].id,
        status=WorkOrderStatus.ASSIGNED,
        assigned_to=h["tech"].id,
    )
    result = await transition_status(
        db_session, wo, WorkOrderStatus.ACCEPTED, h["tech"],
    )
    assert result.status == WorkOrderStatus.ACCEPTED


async def test_transition_accepted_to_in_progress(db_session, org_a_hierarchy, create_work_order):
    """ACCEPTED -> IN_PROGRESS is valid."""
    h = org_a_hierarchy
    wo = await create_work_order(
        org_id=h["org"].id,
        area_id=h["area"].id,
        location_id=h["location"].id,
        site_id=h["site"].id,
        requested_by=h["admin"].id,
        status=WorkOrderStatus.ACCEPTED,
    )
    result = await transition_status(
        db_session, wo, WorkOrderStatus.IN_PROGRESS, h["tech"],
    )
    assert result.status == WorkOrderStatus.IN_PROGRESS
    assert result.in_progress_at is not None


async def test_transition_in_progress_to_waiting_on_ops(
    db_session, org_a_hierarchy, create_work_order,
):
    """IN_PROGRESS -> WAITING_ON_OPS is valid for technicians."""
    h = org_a_hierarchy
    wo = await create_work_order(
        org_id=h["org"].id,
        area_id=h["area"].id,
        location_id=h["location"].id,
        site_id=h["site"].id,
        requested_by=h["admin"].id,
        status=WorkOrderStatus.IN_PROGRESS,
    )
    result = await transition_status(
        db_session, wo, WorkOrderStatus.WAITING_ON_OPS, h["tech"],
    )
    assert result.status == WorkOrderStatus.WAITING_ON_OPS


async def test_transition_in_progress_to_waiting_on_parts(
    db_session, org_a_hierarchy, create_work_order,
):
    """IN_PROGRESS -> WAITING_ON_PARTS is valid for technicians."""
    h = org_a_hierarchy
    wo = await create_work_order(
        org_id=h["org"].id,
        area_id=h["area"].id,
        location_id=h["location"].id,
        site_id=h["site"].id,
        requested_by=h["admin"].id,
        status=WorkOrderStatus.IN_PROGRESS,
    )
    result = await transition_status(
        db_session, wo, WorkOrderStatus.WAITING_ON_PARTS, h["tech"],
    )
    assert result.status == WorkOrderStatus.WAITING_ON_PARTS


async def test_transition_in_progress_to_resolved(
    db_session, org_a_hierarchy, create_work_order,
):
    """IN_PROGRESS -> RESOLVED requires resolution_summary."""
    h = org_a_hierarchy
    wo = await create_work_order(
        org_id=h["org"].id,
        area_id=h["area"].id,
        location_id=h["location"].id,
        site_id=h["site"].id,
        requested_by=h["admin"].id,
        status=WorkOrderStatus.IN_PROGRESS,
    )
    result = await transition_status(
        db_session, wo, WorkOrderStatus.RESOLVED, h["tech"],
        resolution_summary="Replaced faulty bearing",
    )
    assert result.status == WorkOrderStatus.RESOLVED
    assert result.resolution_summary == "Replaced faulty bearing"
    assert result.resolved_at is not None


async def test_transition_waiting_on_ops_to_in_progress(
    db_session, org_a_hierarchy, create_work_order,
):
    """WAITING_ON_OPS -> IN_PROGRESS is valid."""
    h = org_a_hierarchy
    wo = await create_work_order(
        org_id=h["org"].id,
        area_id=h["area"].id,
        location_id=h["location"].id,
        site_id=h["site"].id,
        requested_by=h["admin"].id,
        status=WorkOrderStatus.WAITING_ON_OPS,
    )
    result = await transition_status(
        db_session, wo, WorkOrderStatus.IN_PROGRESS, h["tech"],
    )
    assert result.status == WorkOrderStatus.IN_PROGRESS


async def test_transition_waiting_on_parts_to_in_progress(
    db_session, org_a_hierarchy, create_work_order,
):
    """WAITING_ON_PARTS -> IN_PROGRESS is valid."""
    h = org_a_hierarchy
    wo = await create_work_order(
        org_id=h["org"].id,
        area_id=h["area"].id,
        location_id=h["location"].id,
        site_id=h["site"].id,
        requested_by=h["admin"].id,
        status=WorkOrderStatus.WAITING_ON_PARTS,
    )
    result = await transition_status(
        db_session, wo, WorkOrderStatus.IN_PROGRESS, h["tech"],
    )
    assert result.status == WorkOrderStatus.IN_PROGRESS


async def test_transition_resolved_to_verified(
    db_session, org_a_hierarchy, create_work_order,
):
    """RESOLVED -> VERIFIED is valid for OPERATOR, SUPERVISOR, ADMIN."""
    h = org_a_hierarchy
    wo = await create_work_order(
        org_id=h["org"].id,
        area_id=h["area"].id,
        location_id=h["location"].id,
        site_id=h["site"].id,
        requested_by=h["admin"].id,
        status=WorkOrderStatus.RESOLVED,
    )
    result = await transition_status(
        db_session, wo, WorkOrderStatus.VERIFIED, h["operator"],
    )
    assert result.status == WorkOrderStatus.VERIFIED
    assert result.verified_by == h["operator"].id
    assert result.verified_at is not None


async def test_transition_verified_to_closed(
    db_session, org_a_hierarchy, create_work_order,
):
    """VERIFIED -> CLOSED is valid for SUPERVISOR and ADMIN."""
    h = org_a_hierarchy
    wo = await create_work_order(
        org_id=h["org"].id,
        area_id=h["area"].id,
        location_id=h["location"].id,
        site_id=h["site"].id,
        requested_by=h["admin"].id,
        status=WorkOrderStatus.VERIFIED,
    )
    result = await transition_status(
        db_session, wo, WorkOrderStatus.CLOSED, h["supervisor"],
    )
    assert result.status == WorkOrderStatus.CLOSED
    assert result.closed_by == h["supervisor"].id
    assert result.closed_at is not None


async def test_transition_closed_to_resolved_reopen(
    db_session, org_a_hierarchy, create_work_order,
):
    """CLOSED -> RESOLVED (reopen) is valid for ADMIN only and requires reason."""
    h = org_a_hierarchy
    wo = await create_work_order(
        org_id=h["org"].id,
        area_id=h["area"].id,
        location_id=h["location"].id,
        site_id=h["site"].id,
        requested_by=h["admin"].id,
        status=WorkOrderStatus.CLOSED,
    )
    result = await transition_status(
        db_session, wo, WorkOrderStatus.RESOLVED, h["admin"],
        reason="Issue recurred after initial fix",
    )
    assert result.status == WorkOrderStatus.RESOLVED


async def test_transition_any_active_to_escalated(
    db_session, org_a_hierarchy, create_work_order,
):
    """Any active status can be escalated to ESCALATED by SUPERVISOR/ADMIN."""
    h = org_a_hierarchy
    active_statuses = [
        WorkOrderStatus.NEW,
        WorkOrderStatus.ASSIGNED,
        WorkOrderStatus.ACCEPTED,
        WorkOrderStatus.IN_PROGRESS,
        WorkOrderStatus.WAITING_ON_OPS,
        WorkOrderStatus.WAITING_ON_PARTS,
    ]
    for st in active_statuses:
        wo = await create_work_order(
            org_id=h["org"].id,
            area_id=h["area"].id,
            location_id=h["location"].id,
            site_id=h["site"].id,
            requested_by=h["admin"].id,
            status=st,
        )
        result = await transition_status(
            db_session, wo, WorkOrderStatus.ESCALATED, h["supervisor"],
        )
        assert result.status == WorkOrderStatus.ESCALATED, (
            f"Escalation from {st.value} should succeed"
        )


async def test_transition_escalated_to_assigned(
    db_session, org_a_hierarchy, create_work_order,
):
    """ESCALATED -> ASSIGNED (acknowledge) is valid for SUPERVISOR/ADMIN."""
    h = org_a_hierarchy
    wo = await create_work_order(
        org_id=h["org"].id,
        area_id=h["area"].id,
        location_id=h["location"].id,
        site_id=h["site"].id,
        requested_by=h["admin"].id,
        status=WorkOrderStatus.ESCALATED,
    )
    # De-escalation: ESCALATED -> ASSIGNED
    result = await transition_status(
        db_session, wo, WorkOrderStatus.ASSIGNED, h["supervisor"],
        assigned_to=h["tech"].id,
    )
    assert result.status == WorkOrderStatus.ASSIGNED


# ---------------------------------------------------------------------------
# B. Invalid transition tests
# ---------------------------------------------------------------------------


async def test_invalid_transition_new_to_closed():
    """NEW -> CLOSED is not a valid transition and should be rejected."""
    with pytest.raises(HTTPException) as exc_info:
        validate_fsm_transition(
            WorkOrderStatus.NEW,
            WorkOrderStatus.CLOSED,
            UserRole.ADMIN.value,
        )
    assert exc_info.value.status_code == 422


async def test_invalid_transition_closed_to_in_progress():
    """CLOSED -> IN_PROGRESS is not a valid transition."""
    with pytest.raises(HTTPException) as exc_info:
        validate_fsm_transition(
            WorkOrderStatus.CLOSED,
            WorkOrderStatus.IN_PROGRESS,
            UserRole.ADMIN.value,
        )
    assert exc_info.value.status_code == 422


async def test_invalid_transition_resolved_to_new():
    """RESOLVED -> NEW is not a valid transition."""
    with pytest.raises(HTTPException) as exc_info:
        validate_fsm_transition(
            WorkOrderStatus.RESOLVED,
            WorkOrderStatus.NEW,
            UserRole.ADMIN.value,
        )
    assert exc_info.value.status_code == 422


async def test_invalid_transition_new_to_in_progress():
    """NEW -> IN_PROGRESS (skipping ASSIGNED/ACCEPTED) is not valid."""
    with pytest.raises(HTTPException) as exc_info:
        validate_fsm_transition(
            WorkOrderStatus.NEW,
            WorkOrderStatus.IN_PROGRESS,
            UserRole.TECHNICIAN.value,
        )
    assert exc_info.value.status_code == 422


async def test_invalid_transition_new_to_resolved():
    """NEW -> RESOLVED is not valid (must go through work flow)."""
    with pytest.raises(HTTPException) as exc_info:
        validate_fsm_transition(
            WorkOrderStatus.NEW,
            WorkOrderStatus.RESOLVED,
            UserRole.TECHNICIAN.value,
        )
    assert exc_info.value.status_code == 422


async def test_invalid_transition_verified_to_in_progress():
    """VERIFIED -> IN_PROGRESS is not valid."""
    with pytest.raises(HTTPException) as exc_info:
        validate_fsm_transition(
            WorkOrderStatus.VERIFIED,
            WorkOrderStatus.IN_PROGRESS,
            UserRole.ADMIN.value,
        )
    assert exc_info.value.status_code == 422


async def test_invalid_transition_accepted_to_closed():
    """ACCEPTED -> CLOSED (skipping resolution) is not valid."""
    with pytest.raises(HTTPException) as exc_info:
        validate_fsm_transition(
            WorkOrderStatus.ACCEPTED,
            WorkOrderStatus.CLOSED,
            UserRole.ADMIN.value,
        )
    assert exc_info.value.status_code == 422


# ---------------------------------------------------------------------------
# C. Role restriction tests
# ---------------------------------------------------------------------------


async def test_only_supervisor_admin_can_assign():
    """TECHNICIAN cannot perform NEW -> ASSIGNED."""
    with pytest.raises(HTTPException) as exc_info:
        validate_fsm_transition(
            WorkOrderStatus.NEW,
            WorkOrderStatus.ASSIGNED,
            UserRole.TECHNICIAN.value,
        )
    assert exc_info.value.status_code == 422

    # SUPERVISOR should succeed
    validate_fsm_transition(
        WorkOrderStatus.NEW,
        WorkOrderStatus.ASSIGNED,
        UserRole.SUPERVISOR.value,
    )

    # ADMIN should succeed
    validate_fsm_transition(
        WorkOrderStatus.NEW,
        WorkOrderStatus.ASSIGNED,
        UserRole.ADMIN.value,
    )


async def test_only_operator_supervisor_admin_can_verify():
    """TECHNICIAN cannot perform RESOLVED -> VERIFIED."""
    with pytest.raises(HTTPException) as exc_info:
        validate_fsm_transition(
            WorkOrderStatus.RESOLVED,
            WorkOrderStatus.VERIFIED,
            UserRole.TECHNICIAN.value,
        )
    assert exc_info.value.status_code == 422

    # OPERATOR should succeed
    validate_fsm_transition(
        WorkOrderStatus.RESOLVED,
        WorkOrderStatus.VERIFIED,
        UserRole.OPERATOR.value,
    )

    # SUPERVISOR should succeed
    validate_fsm_transition(
        WorkOrderStatus.RESOLVED,
        WorkOrderStatus.VERIFIED,
        UserRole.SUPERVISOR.value,
    )


async def test_only_admin_can_reopen():
    """Only ADMIN can perform CLOSED -> RESOLVED (reopen)."""
    with pytest.raises(HTTPException) as exc_info:
        validate_fsm_transition(
            WorkOrderStatus.CLOSED,
            WorkOrderStatus.RESOLVED,
            UserRole.SUPERVISOR.value,
        )
    assert exc_info.value.status_code == 422

    with pytest.raises(HTTPException) as exc_info:
        validate_fsm_transition(
            WorkOrderStatus.CLOSED,
            WorkOrderStatus.RESOLVED,
            UserRole.TECHNICIAN.value,
        )
    assert exc_info.value.status_code == 422

    # ADMIN should succeed
    validate_fsm_transition(
        WorkOrderStatus.CLOSED,
        WorkOrderStatus.RESOLVED,
        UserRole.ADMIN.value,
    )


async def test_escalation_requires_supervisor_or_admin():
    """Only SUPERVISOR and ADMIN can escalate work orders."""
    with pytest.raises(HTTPException) as exc_info:
        validate_fsm_transition(
            WorkOrderStatus.IN_PROGRESS,
            WorkOrderStatus.ESCALATED,
            UserRole.TECHNICIAN.value,
        )
    assert exc_info.value.status_code == 422

    # SUPERVISOR should succeed
    validate_fsm_transition(
        WorkOrderStatus.IN_PROGRESS,
        WorkOrderStatus.ESCALATED,
        UserRole.SUPERVISOR.value,
    )


# ---------------------------------------------------------------------------
# D. Resolution summary requirement
# ---------------------------------------------------------------------------


async def test_resolution_summary_required_for_resolve(
    db_session, org_a_hierarchy, create_work_order,
):
    """Resolving without a resolution_summary must raise 422."""
    h = org_a_hierarchy
    wo = await create_work_order(
        org_id=h["org"].id,
        area_id=h["area"].id,
        location_id=h["location"].id,
        site_id=h["site"].id,
        requested_by=h["admin"].id,
        status=WorkOrderStatus.IN_PROGRESS,
    )
    with pytest.raises(HTTPException) as exc_info:
        await transition_status(
            db_session, wo, WorkOrderStatus.RESOLVED, h["tech"],
            resolution_summary=None,
        )
    assert exc_info.value.status_code == 422
    assert "resolution_summary" in exc_info.value.detail


async def test_reopen_reason_required(
    db_session, org_a_hierarchy, create_work_order,
):
    """Reopening (CLOSED -> RESOLVED) without a reason must raise 422."""
    h = org_a_hierarchy
    wo = await create_work_order(
        org_id=h["org"].id,
        area_id=h["area"].id,
        location_id=h["location"].id,
        site_id=h["site"].id,
        requested_by=h["admin"].id,
        status=WorkOrderStatus.CLOSED,
    )
    with pytest.raises(HTTPException) as exc_info:
        await transition_status(
            db_session, wo, WorkOrderStatus.RESOLVED, h["admin"],
            reason=None,
        )
    assert exc_info.value.status_code == 422
    assert "reason" in exc_info.value.detail


# ---------------------------------------------------------------------------
# E. GPS capture on transitions
# ---------------------------------------------------------------------------


async def test_gps_captured_on_accept(
    db_session, org_a_hierarchy, create_work_order,
):
    """GPS coordinates should be stored on the work order when accepted."""
    h = org_a_hierarchy
    wo = await create_work_order(
        org_id=h["org"].id,
        area_id=h["area"].id,
        location_id=h["location"].id,
        site_id=h["site"].id,
        requested_by=h["admin"].id,
        status=WorkOrderStatus.ASSIGNED,
    )
    result = await transition_status(
        db_session, wo, WorkOrderStatus.ACCEPTED, h["tech"],
        gps_lat=31.9686,
        gps_lng=-99.9018,
    )
    assert float(result.gps_lat_accept) == pytest.approx(31.9686, abs=0.001)
    assert float(result.gps_lng_accept) == pytest.approx(-99.9018, abs=0.001)


async def test_gps_captured_on_start(
    db_session, org_a_hierarchy, create_work_order,
):
    """GPS coordinates should be stored when work is started."""
    h = org_a_hierarchy
    wo = await create_work_order(
        org_id=h["org"].id,
        area_id=h["area"].id,
        location_id=h["location"].id,
        site_id=h["site"].id,
        requested_by=h["admin"].id,
        status=WorkOrderStatus.ACCEPTED,
    )
    result = await transition_status(
        db_session, wo, WorkOrderStatus.IN_PROGRESS, h["tech"],
        gps_lat=31.9700,
        gps_lng=-99.9100,
    )
    assert float(result.gps_lat_start) == pytest.approx(31.9700, abs=0.001)
    assert float(result.gps_lng_start) == pytest.approx(-99.9100, abs=0.001)


async def test_gps_captured_on_resolve(
    db_session, org_a_hierarchy, create_work_order,
):
    """GPS coordinates should be stored when work order is resolved."""
    h = org_a_hierarchy
    wo = await create_work_order(
        org_id=h["org"].id,
        area_id=h["area"].id,
        location_id=h["location"].id,
        site_id=h["site"].id,
        requested_by=h["admin"].id,
        status=WorkOrderStatus.IN_PROGRESS,
    )
    result = await transition_status(
        db_session, wo, WorkOrderStatus.RESOLVED, h["tech"],
        resolution_summary="Fixed the pump",
        gps_lat=31.9750,
        gps_lng=-99.9200,
    )
    assert float(result.gps_lat_resolve) == pytest.approx(31.9750, abs=0.001)
    assert float(result.gps_lng_resolve) == pytest.approx(-99.9200, abs=0.001)


# ---------------------------------------------------------------------------
# F. Timeline event creation on transitions
# ---------------------------------------------------------------------------


async def test_timeline_event_created_on_transition(
    db_session, org_a_hierarchy, create_work_order,
):
    """Each status transition should create a TimelineEvent with status change payload."""
    from sqlalchemy import select
    from app.models.work_order import TimelineEvent, TimelineEventType

    h = org_a_hierarchy
    wo = await create_work_order(
        org_id=h["org"].id,
        area_id=h["area"].id,
        location_id=h["location"].id,
        site_id=h["site"].id,
        requested_by=h["admin"].id,
        status=WorkOrderStatus.NEW,
    )

    # Transition NEW -> ASSIGNED
    await transition_status(
        db_session, wo, WorkOrderStatus.ASSIGNED, h["supervisor"],
        assigned_to=h["tech"].id,
    )

    result = await db_session.execute(
        select(TimelineEvent).where(
            TimelineEvent.work_order_id == wo.id,
            TimelineEvent.event_type == TimelineEventType.STATUS_CHANGE,
        )
    )
    events = result.scalars().all()
    assert len(events) >= 1

    latest_event = events[-1]
    assert latest_event.payload["from_status"] == "NEW"
    assert latest_event.payload["to_status"] == "ASSIGNED"
    assert latest_event.user_id == h["supervisor"].id


async def test_timeline_events_accumulate_through_lifecycle(
    db_session, org_a_hierarchy, create_work_order,
):
    """Multiple transitions should create multiple timeline events."""
    from sqlalchemy import select
    from app.models.work_order import TimelineEvent, TimelineEventType

    h = org_a_hierarchy
    wo = await create_work_order(
        org_id=h["org"].id,
        area_id=h["area"].id,
        location_id=h["location"].id,
        site_id=h["site"].id,
        requested_by=h["admin"].id,
        status=WorkOrderStatus.NEW,
    )

    # Walk through several transitions
    await transition_status(
        db_session, wo, WorkOrderStatus.ASSIGNED, h["supervisor"],
        assigned_to=h["tech"].id,
    )
    await transition_status(
        db_session, wo, WorkOrderStatus.ACCEPTED, h["tech"],
    )
    await transition_status(
        db_session, wo, WorkOrderStatus.IN_PROGRESS, h["tech"],
    )

    result = await db_session.execute(
        select(TimelineEvent).where(
            TimelineEvent.work_order_id == wo.id,
            TimelineEvent.event_type == TimelineEventType.STATUS_CHANGE,
        )
    )
    events = result.scalars().all()
    # At least 3 events for the 3 transitions above
    assert len(events) >= 3


async def test_assign_requires_assigned_to(
    db_session, org_a_hierarchy, create_work_order,
):
    """Transitioning to ASSIGNED without assigned_to must raise 422."""
    h = org_a_hierarchy
    wo = await create_work_order(
        org_id=h["org"].id,
        area_id=h["area"].id,
        location_id=h["location"].id,
        site_id=h["site"].id,
        requested_by=h["admin"].id,
        status=WorkOrderStatus.NEW,
    )
    with pytest.raises(HTTPException) as exc_info:
        await transition_status(
            db_session, wo, WorkOrderStatus.ASSIGNED, h["supervisor"],
            assigned_to=None,
        )
    assert exc_info.value.status_code == 422
    assert "assigned_to" in exc_info.value.detail


# ---------------------------------------------------------------------------
# G. API-level FSM tests via HTTP
# ---------------------------------------------------------------------------


async def test_api_assign_endpoint(
    async_client, org_a_hierarchy, create_work_order,
):
    """POST /work-orders/{id}/assign should transition OPEN/NEW -> ASSIGNED."""
    h = org_a_hierarchy
    wo = await create_work_order(
        org_id=h["org"].id,
        area_id=h["area"].id,
        location_id=h["location"].id,
        site_id=h["site"].id,
        requested_by=h["admin"].id,
    )

    headers = make_auth_headers(h["supervisor"])
    resp = await async_client.post(
        f"/api/v1/work-orders/{wo.id}/assign",
        headers=headers,
        json={"assigned_to": str(h["tech"].id)},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] in ("ASSIGNED", "OPEN")


async def test_api_resolve_without_summary_rejected(
    async_client, org_a_hierarchy, create_work_order,
):
    """POST /work-orders/{id}/resolve without resolution_summary should fail."""
    h = org_a_hierarchy
    wo = await create_work_order(
        org_id=h["org"].id,
        area_id=h["area"].id,
        location_id=h["location"].id,
        site_id=h["site"].id,
        requested_by=h["admin"].id,
        status=WorkOrderStatus.IN_PROGRESS,
    )

    headers = make_auth_headers(h["tech"])
    resp = await async_client.post(
        f"/api/v1/work-orders/{wo.id}/resolve",
        headers=headers,
        json={},  # Missing resolution_summary
    )
    assert resp.status_code == 422


async def test_api_reopen_requires_reason(
    async_client, org_a_hierarchy, create_work_order,
):
    """POST /work-orders/{id}/reopen without reason should fail."""
    h = org_a_hierarchy
    wo = await create_work_order(
        org_id=h["org"].id,
        area_id=h["area"].id,
        location_id=h["location"].id,
        site_id=h["site"].id,
        requested_by=h["admin"].id,
        status=WorkOrderStatus.CLOSED,
    )

    headers = make_auth_headers(h["admin"])
    resp = await async_client.post(
        f"/api/v1/work-orders/{wo.id}/reopen",
        headers=headers,
        json={},  # Missing reason
    )
    assert resp.status_code == 422

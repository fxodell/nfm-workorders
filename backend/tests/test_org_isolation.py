"""
Multi-tenancy isolation tests.

Verifies that resources belonging to one organization are never visible to
users from a different organization. The API must return 404 (not 403) when
a user attempts to access a resource from another org, to prevent
information leakage about the existence of cross-tenant resources.
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio

from tests.conftest import make_auth_headers

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Work order isolation
# ---------------------------------------------------------------------------


async def test_user_cannot_see_other_org_work_orders(
    async_client,
    org_a_hierarchy,
    org_b_hierarchy,
    create_work_order,
):
    """A user from Org A must not be able to view a work order owned by Org B."""
    h_a = org_a_hierarchy
    h_b = org_b_hierarchy

    # Create a work order in Org B
    wo_b = await create_work_order(
        org_id=h_b["org"].id,
        area_id=h_b["area"].id,
        location_id=h_b["location"].id,
        site_id=h_b["site"].id,
        requested_by=h_b["admin"].id,
        title="Org B Work Order",
    )

    # Org A admin tries to fetch Org B's work order
    headers = make_auth_headers(h_a["admin"])
    resp = await async_client.get(
        f"/api/v1/work-orders/{wo_b.id}",
        headers=headers,
    )
    assert resp.status_code == 404


async def test_user_cannot_see_other_org_sites(
    async_client,
    org_a_hierarchy,
    org_b_hierarchy,
):
    """A user from Org A must not be able to view a site owned by Org B."""
    headers = make_auth_headers(org_a_hierarchy["admin"])
    resp = await async_client.get(
        f"/api/v1/sites/{org_b_hierarchy['site'].id}",
        headers=headers,
    )
    assert resp.status_code == 404


async def test_user_cannot_see_other_org_assets(
    async_client,
    org_a_hierarchy,
    org_b_hierarchy,
):
    """A user from Org A must not be able to view an asset owned by Org B."""
    headers = make_auth_headers(org_a_hierarchy["admin"])
    resp = await async_client.get(
        f"/api/v1/assets/{org_b_hierarchy['asset'].id}",
        headers=headers,
    )
    assert resp.status_code == 404


async def test_user_cannot_see_other_org_parts(
    async_client,
    org_a_hierarchy,
    org_b_hierarchy,
    create_part,
):
    """A user from Org A must not be able to view a part owned by Org B."""
    part_b = await create_part(org_b_hierarchy["org"].id, part_number="PN-B-001")

    headers = make_auth_headers(org_a_hierarchy["admin"])
    resp = await async_client.get(
        f"/api/v1/parts/{part_b.id}",
        headers=headers,
    )
    assert resp.status_code == 404


async def test_user_cannot_update_other_org_work_order(
    async_client,
    org_a_hierarchy,
    org_b_hierarchy,
    create_work_order,
):
    """Updating a work order from another org must return 404 (not 403)
    to prevent info leakage about resource existence."""
    h_b = org_b_hierarchy
    wo_b = await create_work_order(
        org_id=h_b["org"].id,
        area_id=h_b["area"].id,
        location_id=h_b["location"].id,
        site_id=h_b["site"].id,
        requested_by=h_b["admin"].id,
        title="Org B Private WO",
    )

    headers = make_auth_headers(org_a_hierarchy["admin"])
    resp = await async_client.patch(
        f"/api/v1/work-orders/{wo_b.id}",
        headers=headers,
        json={"title": "Hacked Title"},
    )
    # Must be 404 not 403
    assert resp.status_code == 404


async def test_user_cannot_see_other_org_users(
    async_client,
    org_a_hierarchy,
    org_b_hierarchy,
):
    """An admin from Org A must not be able to view a user from Org B."""
    headers = make_auth_headers(org_a_hierarchy["admin"])
    resp = await async_client.get(
        f"/api/v1/users/{org_b_hierarchy['admin'].id}",
        headers=headers,
    )
    assert resp.status_code == 404


async def test_api_returns_404_not_403_for_wrong_org(
    async_client,
    org_a_hierarchy,
    org_b_hierarchy,
):
    """Cross-org access must consistently return 404, not 403, to prevent
    leaking information about whether a resource exists in another tenant."""
    headers = make_auth_headers(org_a_hierarchy["admin"])

    # Try multiple resource types -- all must return 404
    endpoints = [
        f"/api/v1/work-orders/{uuid.uuid4()}",
        f"/api/v1/sites/{org_b_hierarchy['site'].id}",
        f"/api/v1/assets/{org_b_hierarchy['asset'].id}",
        f"/api/v1/users/{org_b_hierarchy['admin'].id}",
    ]
    for endpoint in endpoints:
        resp = await async_client.get(endpoint, headers=headers)
        assert resp.status_code == 404, (
            f"Expected 404 for {endpoint}, got {resp.status_code}"
        )


async def test_work_order_list_only_shows_own_org(
    async_client,
    org_a_hierarchy,
    org_b_hierarchy,
    create_work_order,
):
    """The work order list endpoint must only return WOs from the caller's org."""
    h_a = org_a_hierarchy
    h_b = org_b_hierarchy

    # Create WOs in both orgs
    await create_work_order(
        org_id=h_a["org"].id,
        area_id=h_a["area"].id,
        location_id=h_a["location"].id,
        site_id=h_a["site"].id,
        requested_by=h_a["admin"].id,
        title="Org A WO 1",
    )
    await create_work_order(
        org_id=h_b["org"].id,
        area_id=h_b["area"].id,
        location_id=h_b["location"].id,
        site_id=h_b["site"].id,
        requested_by=h_b["admin"].id,
        title="Org B WO 1",
    )

    # Org A admin lists work orders
    headers = make_auth_headers(h_a["admin"])
    resp = await async_client.get("/api/v1/work-orders/", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    # All returned WOs must belong to Org A
    for item in data.get("items", []):
        assert item["org_id"] == str(h_a["org"].id), (
            "Work order list returned a WO from a different org"
        )


async def test_dashboard_only_shows_own_org_data(
    async_client,
    org_a_hierarchy,
    org_b_hierarchy,
    create_work_order,
):
    """The dashboard overview must only include data from the caller's org."""
    h_a = org_a_hierarchy
    h_b = org_b_hierarchy

    # Create WOs in both orgs
    await create_work_order(
        org_id=h_a["org"].id,
        area_id=h_a["area"].id,
        location_id=h_a["location"].id,
        site_id=h_a["site"].id,
        requested_by=h_a["admin"].id,
        title="Org A Dashboard WO",
    )
    await create_work_order(
        org_id=h_b["org"].id,
        area_id=h_b["area"].id,
        location_id=h_b["location"].id,
        site_id=h_b["site"].id,
        requested_by=h_b["admin"].id,
        title="Org B Dashboard WO",
    )

    headers = make_auth_headers(h_a["admin"])
    resp = await async_client.get("/api/v1/dashboard/overview", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    # Dashboard area IDs must only contain Org A areas
    area_ids_in_dashboard = [a["area_id"] for a in data.get("areas", [])]
    assert str(h_b["area"].id) not in area_ids_in_dashboard, (
        "Dashboard overview leaked area data from another org"
    )

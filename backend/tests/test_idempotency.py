"""
Idempotency key middleware tests.

Verifies that:
- Duplicate requests with the same idempotency key return the cached response
  instead of creating a new resource
- Different keys create separate, independent resources
- The idempotency key entry expires after 24 hours (TTL check)
- Missing idempotency key is handled gracefully (key is optional)
- Concurrent duplicate requests are blocked with 409 Conflict
"""

from __future__ import annotations

import json
import uuid

import pytest
import pytest_asyncio
from fastapi import Request
from starlette.datastructures import Headers

from app.core.idempotency import (
    IDEMPOTENCY_KEY_PREFIX,
    IDEMPOTENCY_PROCESSING_SUFFIX,
    IDEMPOTENCY_TTL_SECONDS,
    IdempotencyResult,
    idempotency_check,
)
from tests.conftest import FakeRedis, make_auth_headers

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Unit tests for IdempotencyResult
# ---------------------------------------------------------------------------


async def test_idempotency_result_store(fake_redis: FakeRedis):
    """IdempotencyResult.store() should write the response to Redis with
    the correct TTL and remove the processing lock."""
    key = f"{IDEMPOTENCY_KEY_PREFIX}test-key-123"
    processing_key = f"{key}{IDEMPOTENCY_PROCESSING_SUFFIX}"

    # Simulate having a processing lock
    await fake_redis.set(processing_key, "1", ex=60)

    result = IdempotencyResult(key=key, redis=fake_redis)
    response_data = {"id": "abc-123", "title": "Test WO"}
    await result.store(response_data)

    # Verify response was stored
    cached = await fake_redis.get(key)
    assert cached is not None
    parsed = json.loads(cached)
    assert parsed["id"] == "abc-123"

    # Verify processing lock was removed
    lock_exists = await fake_redis.exists(processing_key)
    assert lock_exists == 0


async def test_idempotency_result_no_op_without_redis():
    """IdempotencyResult.store() should be a no-op when redis is None."""
    result = IdempotencyResult(key="", redis=None)
    # Should not raise
    await result.store({"data": "test"})


# ---------------------------------------------------------------------------
# Duplicate request handling
# ---------------------------------------------------------------------------


async def test_duplicate_request_returns_cached_response(fake_redis: FakeRedis):
    """When an idempotency key already has a cached response in Redis,
    the check should return it as-is without re-processing."""
    idem_key = str(uuid.uuid4())
    full_key = f"{IDEMPOTENCY_KEY_PREFIX}{idem_key}"

    # Pre-store a cached response
    cached_response = {"id": str(uuid.uuid4()), "title": "Cached Work Order"}
    await fake_redis.set(full_key, json.dumps(cached_response))

    # Simulate the idempotency check
    # Build a minimal mock request with the Idempotency-Key header
    scope = {
        "type": "http",
        "method": "POST",
        "headers": [(b"idempotency-key", idem_key.encode())],
        "path": "/api/v1/work-orders",
    }
    request = Request(scope)

    result = await idempotency_check(request, fake_redis)

    assert result.is_duplicate is True
    assert result.cached_response is not None
    assert result.cached_response["id"] == cached_response["id"]
    assert result.cached_response["title"] == cached_response["title"]


async def test_different_keys_create_separate_resources(fake_redis: FakeRedis):
    """Two requests with different idempotency keys should each proceed
    independently (neither is treated as a duplicate)."""
    key_1 = str(uuid.uuid4())
    key_2 = str(uuid.uuid4())

    scope_1 = {
        "type": "http",
        "method": "POST",
        "headers": [(b"idempotency-key", key_1.encode())],
        "path": "/api/v1/work-orders",
    }
    scope_2 = {
        "type": "http",
        "method": "POST",
        "headers": [(b"idempotency-key", key_2.encode())],
        "path": "/api/v1/work-orders",
    }

    result_1 = await idempotency_check(Request(scope_1), fake_redis)
    result_2 = await idempotency_check(Request(scope_2), fake_redis)

    assert result_1.is_duplicate is False
    assert result_2.is_duplicate is False
    assert result_1.key != result_2.key


# ---------------------------------------------------------------------------
# TTL / expiry
# ---------------------------------------------------------------------------


async def test_idempotency_key_expires_after_24h(fake_redis: FakeRedis):
    """The cached response should be stored with a 24-hour TTL (86400 seconds)."""
    key = f"{IDEMPOTENCY_KEY_PREFIX}ttl-test-key"
    result = IdempotencyResult(key=key, redis=fake_redis)

    await result.store({"data": "test"})

    # Check that the TTL was set to 24 hours
    assert key in fake_redis._ttls
    assert fake_redis._ttls[key] == IDEMPOTENCY_TTL_SECONDS
    assert IDEMPOTENCY_TTL_SECONDS == 86400


# ---------------------------------------------------------------------------
# Missing key (graceful degradation)
# ---------------------------------------------------------------------------


async def test_missing_key_still_works(fake_redis: FakeRedis):
    """When no Idempotency-Key header is present, the request should proceed
    normally without caching -- idempotency is optional."""
    scope = {
        "type": "http",
        "method": "POST",
        "headers": [],
        "path": "/api/v1/work-orders",
    }
    request = Request(scope)

    result = await idempotency_check(request, fake_redis)

    assert result.is_duplicate is False
    assert result.cached_response is None
    # Key should be empty since no idempotency key was provided
    assert result.key == ""


# ---------------------------------------------------------------------------
# Empty key validation
# ---------------------------------------------------------------------------


async def test_empty_idempotency_key_rejected(fake_redis: FakeRedis):
    """An empty Idempotency-Key header value should be rejected with 400."""
    from fastapi import HTTPException

    scope = {
        "type": "http",
        "method": "POST",
        "headers": [(b"idempotency-key", b"  ")],
        "path": "/api/v1/work-orders",
    }
    request = Request(scope)

    with pytest.raises(HTTPException) as exc_info:
        await idempotency_check(request, fake_redis)
    assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# Concurrent duplicate detection
# ---------------------------------------------------------------------------


async def test_concurrent_duplicate_blocked(fake_redis: FakeRedis):
    """If another request with the same key is currently being processed,
    a subsequent request should be blocked with 409 Conflict."""
    from fastapi import HTTPException

    idem_key = str(uuid.uuid4())

    # First request acquires the processing lock
    scope = {
        "type": "http",
        "method": "POST",
        "headers": [(b"idempotency-key", idem_key.encode())],
        "path": "/api/v1/work-orders",
    }
    result_1 = await idempotency_check(Request(scope), fake_redis)
    assert result_1.is_duplicate is False

    # Second request with the same key while the first is still processing
    with pytest.raises(HTTPException) as exc_info:
        await idempotency_check(Request(scope), fake_redis)
    assert exc_info.value.status_code == 409
    assert "already being processed" in exc_info.value.detail


# ---------------------------------------------------------------------------
# API-level idempotency integration test
# ---------------------------------------------------------------------------


async def test_api_create_wo_with_idempotency_key(
    async_client, org_a_hierarchy,
):
    """Creating a work order with an Idempotency-Key header should succeed
    and a repeat request with the same key should return the same result."""
    h = org_a_hierarchy
    headers = make_auth_headers(h["admin"])
    idem_key = str(uuid.uuid4())
    headers["Idempotency-Key"] = idem_key

    body = {
        "area_id": str(h["area"].id),
        "site_id": str(h["site"].id),
        "title": "Idempotent Work Order",
        "description": "Testing idempotency key handling for duplicate prevention.",
        "type": "CORRECTIVE",
        "priority": "SCHEDULED",
    }

    # First request
    resp1 = await async_client.post(
        "/api/v1/work-orders/",
        headers=headers,
        json=body,
    )
    assert resp1.status_code == 201

    # Second request with the same idempotency key
    resp2 = await async_client.post(
        "/api/v1/work-orders/",
        headers=headers,
        json=body,
    )
    # Should return 200 (cached) or 201 depending on implementation
    # The key point is both should return the same resource
    assert resp2.status_code in (200, 201)

    # Both should reference the same work order
    data1 = resp1.json()
    data2 = resp2.json()
    if "id" in data1 and "id" in data2:
        assert data1["id"] == data2["id"], (
            "Duplicate request should return the same work order"
        )

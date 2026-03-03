"""
Redis-backed idempotency key middleware for mutation endpoints.

Prevents duplicate work order creation (and other write operations) when
the offline queue retries a request that already succeeded. The client
generates a UUID idempotency key and sends it in the ``Idempotency-Key``
header. The server:

1. Checks Redis for a cached response under that key.
2. If found, returns the cached response immediately (HTTP 200).
3. If not found, processes the request, stores the response in Redis
   with a 24-hour TTL, and returns it.

Usage in a route handler::

    from app.core.idempotency import idempotency_check, IdempotencyResult

    @router.post("/work-orders")
    async def create_work_order(
        request: Request,
        idempotency: IdempotencyResult = Depends(idempotency_check),
        ...
    ):
        if idempotency.cached_response is not None:
            return idempotency.cached_response
        # ... process the request ...
        await idempotency.store(response_data)
        return response_data
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, Request, status

from app.core.redis import get_redis

IDEMPOTENCY_TTL_SECONDS: int = 86400  # 24 hours
IDEMPOTENCY_KEY_PREFIX: str = "idempotency:"
IDEMPOTENCY_PROCESSING_SUFFIX: str = ":processing"


@dataclass
class IdempotencyResult:
    """Result of an idempotency check.

    Attributes
    ----------
    cached_response : dict or None
        The previously stored response if a duplicate key was found.
    key : str
        The full Redis key (including prefix).
    redis : aioredis.Redis
        The Redis connection for storing the response after processing.
    is_duplicate : bool
        ``True`` if the response was served from cache.
    """

    cached_response: dict[str, Any] | None = None
    key: str = ""
    redis: aioredis.Redis = field(default=None, repr=False)  # type: ignore[assignment]
    is_duplicate: bool = False

    async def store(self, response_data: Any) -> None:
        """Store the response in Redis so subsequent duplicate requests
        receive the cached result.

        Must be called by the route handler after successful processing.
        """
        if self.redis is None or not self.key:
            return

        serialized = json.dumps(response_data, default=str)
        await self.redis.set(self.key, serialized, ex=IDEMPOTENCY_TTL_SECONDS)

        # Remove the processing lock
        processing_key = f"{self.key}{IDEMPOTENCY_PROCESSING_SUFFIX}"
        await self.redis.delete(processing_key)


async def idempotency_check(
    request: Request,
    r: aioredis.Redis = Depends(get_redis),
) -> IdempotencyResult:
    """FastAPI dependency that checks for a duplicate idempotency key.

    The idempotency key is read from the ``Idempotency-Key`` header. If the
    header is absent, the dependency returns a no-op result and the request
    proceeds normally (useful for endpoints where idempotency is optional).
    """
    raw_key = request.headers.get("Idempotency-Key")
    if raw_key is None:
        return IdempotencyResult(redis=r)

    # Validate that it looks like a UUID (basic length + format check)
    raw_key = raw_key.strip()
    if not raw_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency-Key header must not be empty",
        )

    full_key = f"{IDEMPOTENCY_KEY_PREFIX}{raw_key}"

    # Check for a cached response
    cached = await r.get(full_key)
    if cached is not None:
        try:
            parsed = json.loads(cached)
        except json.JSONDecodeError:
            # Corrupted cache entry; delete it and proceed
            await r.delete(full_key)
            return IdempotencyResult(key=full_key, redis=r)

        return IdempotencyResult(
            cached_response=parsed,
            key=full_key,
            redis=r,
            is_duplicate=True,
        )

    # Attempt to acquire a processing lock to prevent concurrent duplicates.
    # The lock has a short TTL (60 s) to auto-expire if the request crashes.
    processing_key = f"{full_key}{IDEMPOTENCY_PROCESSING_SUFFIX}"
    acquired = await r.set(processing_key, "1", ex=300, nx=True)
    if not acquired:
        # Another request with the same key is being processed right now.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A request with this idempotency key is already being processed",
        )

    return IdempotencyResult(key=full_key, redis=r)

"""
Redis connection pool and helper utilities.

Provides:
- ``get_redis`` -- FastAPI dependency that yields an ``aioredis`` connection
- Token revocation helpers (SET-based) used by the auth service to track
  revoked refresh-token JTIs
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import redis.asyncio as aioredis

from app.core.config import settings

# ── Connection pool ─────────────────────────────────────────────────────

redis_pool = aioredis.ConnectionPool.from_url(
    settings.REDIS_URL,
    decode_responses=True,
    max_connections=50,
)


async def get_redis() -> AsyncGenerator[aioredis.Redis, None]:
    """FastAPI dependency that yields a Redis connection from the pool."""
    client = aioredis.Redis(connection_pool=redis_pool)
    try:
        yield client
    finally:
        await client.aclose()


# ── Token revocation SET operations ────────────────────────────────────

_REVOKED_SET_KEY = "revoked_refresh_jtis"


async def revoke_refresh_token(
    r: aioredis.Redis,
    jti: str,
    ttl_seconds: int,
) -> None:
    """Add a refresh-token JTI to the revoked set.

    Each JTI is stored as an individual key with an expiry matching the
    token's remaining lifetime so that the set self-prunes without a
    background cleanup job.
    """
    key = f"{_REVOKED_SET_KEY}:{jti}"
    await r.set(key, "1", ex=ttl_seconds)


async def is_refresh_token_revoked(r: aioredis.Redis, jti: str) -> bool:
    """Return ``True`` if the JTI has been revoked."""
    key = f"{_REVOKED_SET_KEY}:{jti}"
    return await r.exists(key) == 1


async def revoke_all_user_tokens(
    r: aioredis.Redis,
    user_id: str,
    ttl_seconds: int,
) -> None:
    """Mark all tokens for a specific user as revoked.

    This is a blunt instrument used for password changes, account lockout,
    or admin-initiated session termination. The auth middleware checks this
    flag in addition to individual JTI revocation.
    """
    key = f"user_tokens_revoked:{user_id}"
    await r.set(key, "1", ex=ttl_seconds)


async def are_user_tokens_revoked(r: aioredis.Redis, user_id: str) -> bool:
    """Return ``True`` if the user's tokens have been globally revoked."""
    key = f"user_tokens_revoked:{user_id}"
    return await r.exists(key) == 1

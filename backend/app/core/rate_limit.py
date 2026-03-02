"""
Rate limiting configuration using slowapi with a Redis backend.

Provides pre-configured rate limit strings and a ``limiter`` instance that
can be applied to FastAPI route handlers via the ``@limiter.limit()``
decorator.

Usage in a router::

    from app.core.rate_limit import limiter, RATE_AUTH, RATE_GENERAL

    @router.post("/login")
    @limiter.limit(RATE_AUTH)
    async def login(request: Request, ...):
        ...

    @router.get("/work-orders")
    @limiter.limit(RATE_GENERAL)
    async def list_work_orders(request: Request, ...):
        ...

The limiter must be registered on the FastAPI ``app`` instance at startup::

    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from app.core.rate_limit import limiter

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

# Rate limit strings (slowapi format).
RATE_AUTH: str = "10/minute"
RATE_GENERAL: str = "120/minute"
RATE_WRITE: str = "60/minute"

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.REDIS_URL,
    strategy="fixed-window",
    default_limits=[RATE_GENERAL],
)

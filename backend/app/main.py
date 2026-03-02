"""FastAPI application entry point.

Configures the app with lifespan events, middleware, routers, and
observability. All API routes are mounted under /api/v1.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.responses import Response

from app.core.config import settings
from app.core.firebase import get_firebase_app
from app.core.observability import setup_observability
from app.core.rate_limit import limiter

logger = logging.getLogger(__name__)


# ── Lifespan ───────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown lifecycle events."""
    # Startup
    logger.info("Starting up OFMaint CMMS API (%s)", settings.ENVIRONMENT)

    # Initialize Firebase for push notifications
    get_firebase_app()

    # Initialize Redis subscriber for WebSocket relay
    try:
        import redis.asyncio as aioredis
        redis_client = aioredis.from_url(settings.REDIS_URL)
        app.state.redis = redis_client
        logger.info("Redis connection established")
    except Exception:
        logger.warning("Redis subscriber initialization failed; WS relay disabled")

    yield

    # Shutdown
    logger.info("Shutting down OFMaint CMMS API")
    if hasattr(app.state, "redis") and app.state.redis:
        await app.state.redis.aclose()
        logger.info("Redis connection closed")


# ── App factory ────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="OFMaint CMMS API",
        version="1.0.0",
        description="Computerized Maintenance Management System API",
        docs_url="/api/docs" if settings.is_development else None,
        redoc_url="/api/redoc" if settings.is_development else None,
        openapi_url="/api/openapi.json" if settings.is_development else None,
        lifespan=lifespan,
    )

    # ── Rate limiter ───────────────────────────────────────────────────
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # ── CORS ───────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.FRONTEND_URL],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    # ── Observability (request ID, Prometheus, Sentry, OTel) ──────────
    setup_observability(app)

    # ── Include routers ───────────────────────────────────────────────
    _include_routers(app)

    # ── Health & metrics endpoints ────────────────────────────────────
    _include_health_endpoints(app)

    return app


def _include_routers(app: FastAPI) -> None:
    """Register all API routers under /api/v1."""
    from app.api.admin import router as admin_router
    from app.api.areas import router as areas_router
    from app.api.assets import router as assets_router
    from app.api.auth import router as auth_router
    from app.api.budget import router as budget_router
    from app.api.dashboard import router as dashboard_router
    from app.api.incentives import router as incentives_router
    from app.api.inventory import router as inventory_router
    from app.api.locations import router as locations_router
    from app.api.on_call import router as on_call_router
    from app.api.parts import router as parts_router
    from app.api.pm_schedules import router as pm_schedules_router
    from app.api.pm_templates import router as pm_templates_router
    from app.api.reports import router as reports_router
    from app.api.scan import router as scan_router
    from app.api.shifts import router as shifts_router
    from app.api.sites import router as sites_router
    from app.api.users import router as users_router
    from app.api.websocket import router as ws_router
    from app.api.wo_attachments import router as wo_attachments_router
    from app.api.wo_labor import router as wo_labor_router
    from app.api.wo_messages import router as wo_messages_router
    from app.api.wo_parts import router as wo_parts_router
    from app.api.wo_sla import router as wo_sla_router
    from app.api.wo_timeline import router as wo_timeline_router
    from app.api.work_orders import router as work_orders_router

    prefix = "/api/v1"

    # Auth (no extra prefix needed - router has /auth)
    app.include_router(auth_router, prefix=prefix)

    # Users
    app.include_router(users_router, prefix=prefix)

    # Org hierarchy
    app.include_router(areas_router, prefix=prefix)
    app.include_router(locations_router, prefix=prefix)
    app.include_router(sites_router, prefix=prefix)
    app.include_router(assets_router, prefix=prefix)

    # Work orders & sub-resources
    app.include_router(work_orders_router, prefix=prefix)
    app.include_router(wo_timeline_router, prefix=prefix)
    app.include_router(wo_attachments_router, prefix=prefix)
    app.include_router(wo_parts_router, prefix=prefix)
    app.include_router(wo_labor_router, prefix=prefix)
    app.include_router(wo_messages_router, prefix=prefix)
    app.include_router(wo_sla_router, prefix=prefix)

    # Parts / inventory
    app.include_router(parts_router, prefix=prefix)
    app.include_router(inventory_router, prefix=prefix)

    # QR scan
    app.include_router(scan_router, prefix=prefix)

    # PM
    app.include_router(pm_templates_router, prefix=prefix)
    app.include_router(pm_schedules_router, prefix=prefix)

    # Shifts & on-call
    app.include_router(shifts_router, prefix=prefix)
    app.include_router(on_call_router, prefix=prefix)

    # Dashboard
    app.include_router(dashboard_router, prefix=prefix)

    # Budget
    app.include_router(budget_router, prefix=prefix)

    # Incentives
    app.include_router(incentives_router, prefix=prefix)

    # Reports
    app.include_router(reports_router, prefix=prefix)

    # Admin
    app.include_router(admin_router, prefix=prefix)

    # WebSocket (mounted at root /ws so frontend can connect without API prefix)
    app.include_router(ws_router)


def _include_health_endpoints(app: FastAPI) -> None:
    """Add /health and /metrics endpoints (public, no auth)."""

    @app.get("/health", tags=["health"])
    async def health_check() -> dict:
        """Basic health check -- returns 200 if the server is running."""
        return {
            "status": "healthy",
            "environment": settings.ENVIRONMENT,
            "version": "1.0.0",
        }

    @app.get("/metrics", tags=["metrics"])
    async def metrics() -> Response:
        """Prometheus metrics endpoint."""
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST,
        )


# ── Create the application instance ───────────────────────────────────

app = create_app()

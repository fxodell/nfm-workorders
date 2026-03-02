"""
Observability stack: OpenTelemetry tracing, Prometheus metrics, Sentry
error monitoring, structured logging, and request-ID middleware.

Call ``setup_observability(app)`` once during FastAPI startup to wire
everything in.
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

import sentry_sdk
import structlog
from prometheus_client import Counter, Gauge, Histogram, Summary
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings

if TYPE_CHECKING:
    from fastapi import FastAPI

# ── Prometheus metrics ──────────────────────────────────────────────────

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

WS_CONNECTIONS = Gauge(
    "ws_active_connections",
    "Number of active WebSocket connections",
)

CELERY_TASKS = Summary(
    "celery_task_duration_seconds",
    "Celery task execution duration in seconds",
    ["task_name", "status"],
)

SLA_BREACHES = Counter(
    "sla_breaches_total",
    "Total SLA breaches detected",
    ["org_id", "breach_type", "priority"],
)


# ── Structured logging ─────────────────────────────────────────────────

def setup_logging() -> None:
    """Configure ``structlog`` for JSON-formatted structured logging."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Set root logger level from settings
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    )


# ── Request ID middleware ───────────────────────────────────────────────

class RequestIDMiddleware(BaseHTTPMiddleware):
    """Inject a unique ``X-Request-ID`` header into every request/response.

    If the client sends an ``X-Request-ID`` header, it is reused; otherwise
    a new UUIDv4 is generated. The ID is bound to structlog's context vars
    so that every log line emitted during the request includes it.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


# ── Prometheus middleware ───────────────────────────────────────────────

class PrometheusMiddleware(BaseHTTPMiddleware):
    """Record request count and latency for Prometheus scraping."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        import time

        method = request.method
        path = request.url.path

        start = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - start

        REQUEST_COUNT.labels(
            method=method,
            endpoint=path,
            status_code=response.status_code,
        ).inc()

        REQUEST_LATENCY.labels(
            method=method,
            endpoint=path,
        ).observe(elapsed)

        return response


# ── Sentry ──────────────────────────────────────────────────────────────

def setup_sentry() -> None:
    """Initialize Sentry error tracking if a DSN is configured."""
    if not settings.SENTRY_DSN:
        logging.getLogger(__name__).info(
            "SENTRY_DSN not set; Sentry error tracking disabled"
        )
        return

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        traces_sample_rate=0.1 if settings.is_production else 1.0,
        profiles_sample_rate=0.1 if settings.is_production else 0.0,
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            SqlalchemyIntegration(),
        ],
        send_default_pii=False,
    )


# ── OpenTelemetry ───────────────────────────────────────────────────────

def setup_opentelemetry(app: FastAPI) -> None:
    """Configure OpenTelemetry tracing with OTLP export if an endpoint is set."""
    if not settings.OTEL_EXPORTER_OTLP_ENDPOINT:
        logging.getLogger(__name__).info(
            "OTEL_EXPORTER_OTLP_ENDPOINT not set; OpenTelemetry tracing disabled"
        )
        return

    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
        OTLPSpanExporter,
    )
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    resource = Resource.create(
        {
            "service.name": "ofmaint-api",
            "service.version": "1.0.0",
            "deployment.environment": settings.ENVIRONMENT,
        }
    )

    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(
        endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT,
        insecure=not settings.is_production,
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(
        app,
        excluded_urls="health,metrics",
    )


# ── Unified setup ───────────────────────────────────────────────────────

def setup_observability(app: FastAPI) -> None:
    """Wire all observability components into the FastAPI application.

    Call this once during startup (e.g., in ``main.py`` or a lifespan
    handler).
    """
    setup_logging()
    setup_sentry()
    setup_opentelemetry(app)

    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(PrometheusMiddleware)

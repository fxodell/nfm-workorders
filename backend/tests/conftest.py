"""
Shared pytest fixtures for the OFMaint CMMS backend test suite.

Provides:
- Async test database session with SQLite (aiosqlite) for local testing
- httpx.AsyncClient wired to FastAPI app with dependency overrides
- Factory fixtures for org hierarchy entities (org, area, location, site, asset)
- Factory fixtures for users and work orders
- Auth header helpers for JWT-authenticated requests
- Dual org fixtures (org_a, org_b) for cross-tenant isolation testing
- FakeRedis mock for idempotency and token revocation
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock

# Force settings before any app imports
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("SECRET_KEY", "test-secret-key-min-32-characters-long")
os.environ.setdefault("WS_SECRET_KEY", "test-ws-secret-key-min-32-characters")
os.environ.setdefault("MFA_SECRET_KEY", "test-mfa-secret-key-min-32-characters")
os.environ.setdefault("ENVIRONMENT", "test")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.database import Base, get_db
from app.core.redis import get_redis
from app.core.security import create_access_token, hash_password
from app.models.area import Area
from app.models.asset import Asset
from app.models.location import Location
from app.models.org import Organization
from app.models.part import Part
from app.models.site import Site, SiteType
from app.models.user import User, UserAreaAssignment, UserRole
from app.models.work_order import (
    WorkOrder,
    WorkOrderPriority,
    WorkOrderStatus,
    WorkOrderType,
)

# ---------------------------------------------------------------------------
# pytest-asyncio configuration
# ---------------------------------------------------------------------------

pytest_plugins = []


def pytest_configure(config: Any) -> None:
    """Register custom markers and set asyncio mode."""
    config.addinivalue_line("markers", "asyncio: mark test as async")


# ---------------------------------------------------------------------------
# Database engine for tests — uses SQLite + aiosqlite for local testing
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


def _sqlite_now():
    """SQLite-compatible now() function."""
    return datetime.now(timezone.utc).isoformat()


test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)


@event.listens_for(test_engine.sync_engine, "connect")
def _register_sqlite_functions(dbapi_conn, connection_record):
    """Register the now() function in SQLite so server_default=text('now()') works."""
    dbapi_conn.create_function("now", 0, _sqlite_now)

TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ---------------------------------------------------------------------------
# FakeRedis -- in-memory dict-based Redis mock
# ---------------------------------------------------------------------------


class FakeRedis:
    """Minimal async Redis mock backed by an in-memory dict.

    Supports get, set, delete, exists, publish, and expiry tracking
    sufficient for idempotency and token revocation tests.
    """

    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self._ttls: dict[str, int] = {}
        self._published: list[tuple[str, str]] = []

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(
        self,
        key: str,
        value: str,
        ex: int | None = None,
        nx: bool = False,
    ) -> bool:
        if nx and key in self._store:
            return False
        self._store[key] = value
        if ex is not None:
            self._ttls[key] = ex
        return True

    async def delete(self, *keys: str) -> int:
        count = 0
        for key in keys:
            if key in self._store:
                del self._store[key]
                self._ttls.pop(key, None)
                count += 1
        return count

    async def exists(self, key: str) -> int:
        return 1 if key in self._store else 0

    async def publish(self, channel: str, message: str) -> int:
        self._published.append((channel, message))
        return 1

    async def aclose(self) -> None:
        pass

    def clear(self) -> None:
        """Reset all stored data between tests."""
        self._store.clear()
        self._ttls.clear()
        self._published.clear()


# ---------------------------------------------------------------------------
# Core fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def fake_redis() -> FakeRedis:
    """Provide a fresh FakeRedis instance per test."""
    r = FakeRedis()
    yield r
    r.clear()


@pytest_asyncio.fixture(autouse=True)
async def _create_tables():
    """Create all tables before each test and drop after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session for test use."""
    async with TestSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@pytest_asyncio.fixture
async def async_client(
    db_session: AsyncSession,
    fake_redis: FakeRedis,
) -> AsyncGenerator[AsyncClient, None]:
    """Provide an httpx.AsyncClient connected to the FastAPI app with
    dependency overrides for the database session and Redis."""
    from app.main import create_app

    app = create_app()

    # Override dependencies
    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    async def _override_get_redis() -> AsyncGenerator[FakeRedis, None]:
        yield fake_redis

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis] = _override_get_redis

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        yield client

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Factory fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
def create_org(db_session: AsyncSession):
    """Factory fixture that creates an Organization with a unique slug."""

    async def _create(
        name: str = "Test Org",
        slug: str | None = None,
        config: dict | None = None,
    ) -> Organization:
        org = Organization(
            id=uuid.uuid4(),
            name=name,
            slug=slug or f"test-org-{uuid.uuid4().hex[:8]}",
            config=config,
        )
        db_session.add(org)
        await db_session.flush()
        return org

    return _create


@pytest_asyncio.fixture
def create_user(db_session: AsyncSession):
    """Factory fixture that creates a User within a specified org."""

    async def _create(
        org_id: uuid.UUID,
        email: str | None = None,
        name: str = "Test User",
        role: UserRole = UserRole.ADMIN,
        password: str = "testpassword123",
        is_active: bool = True,
        mfa_enabled: bool = False,
        totp_secret: str | None = None,
    ) -> User:
        user = User(
            id=uuid.uuid4(),
            org_id=org_id,
            name=name,
            email=email or f"user-{uuid.uuid4().hex[:8]}@test.com",
            password_hash=hash_password(password),
            role=role,
            is_active=is_active,
            mfa_enabled=mfa_enabled,
            totp_secret=totp_secret,
        )
        db_session.add(user)
        await db_session.flush()
        return user

    return _create


@pytest_asyncio.fixture
def create_area(db_session: AsyncSession):
    """Factory fixture that creates an Area within a specified org."""

    async def _create(
        org_id: uuid.UUID,
        name: str = "Test Area",
    ) -> Area:
        area = Area(
            id=uuid.uuid4(),
            org_id=org_id,
            name=name,
        )
        db_session.add(area)
        await db_session.flush()
        return area

    return _create


@pytest_asyncio.fixture
def create_location(db_session: AsyncSession):
    """Factory fixture that creates a Location within a specified area/org."""

    async def _create(
        org_id: uuid.UUID,
        area_id: uuid.UUID,
        name: str = "Test Location",
    ) -> Location:
        location = Location(
            id=uuid.uuid4(),
            org_id=org_id,
            area_id=area_id,
            name=name,
        )
        db_session.add(location)
        await db_session.flush()
        return location

    return _create


@pytest_asyncio.fixture
def create_site(db_session: AsyncSession):
    """Factory fixture that creates a Site within a specified location/org."""

    async def _create(
        org_id: uuid.UUID,
        location_id: uuid.UUID,
        name: str = "Test Site",
        site_type: SiteType = SiteType.WELL_SITE,
    ) -> Site:
        site = Site(
            id=uuid.uuid4(),
            org_id=org_id,
            location_id=location_id,
            name=name,
            type=site_type,
        )
        db_session.add(site)
        await db_session.flush()
        return site

    return _create


@pytest_asyncio.fixture
def create_asset(db_session: AsyncSession):
    """Factory fixture that creates an Asset within a specified site/org."""

    async def _create(
        org_id: uuid.UUID,
        site_id: uuid.UUID,
        name: str = "Test Asset",
    ) -> Asset:
        asset = Asset(
            id=uuid.uuid4(),
            org_id=org_id,
            site_id=site_id,
            name=name,
        )
        db_session.add(asset)
        await db_session.flush()
        return asset

    return _create


@pytest_asyncio.fixture
def create_part(db_session: AsyncSession):
    """Factory fixture that creates a Part within a specified org."""

    async def _create(
        org_id: uuid.UUID,
        part_number: str | None = None,
        description: str = "Test Part",
        stock_quantity: int = 100,
    ) -> Part:
        part = Part(
            id=uuid.uuid4(),
            org_id=org_id,
            part_number=part_number or f"PN-{uuid.uuid4().hex[:8]}",
            description=description,
            stock_quantity=stock_quantity,
        )
        db_session.add(part)
        await db_session.flush()
        return part

    return _create


@pytest_asyncio.fixture
def create_work_order(db_session: AsyncSession):
    """Factory fixture that creates a WorkOrder with all required FK hierarchy."""

    async def _create(
        org_id: uuid.UUID,
        area_id: uuid.UUID,
        location_id: uuid.UUID,
        site_id: uuid.UUID,
        requested_by: uuid.UUID,
        title: str = "Test Work Order",
        status: WorkOrderStatus = WorkOrderStatus.NEW,
        priority: WorkOrderPriority = WorkOrderPriority.SCHEDULED,
        wo_type: WorkOrderType = WorkOrderType.REACTIVE,
        safety_flag: bool = False,
        safety_notes: str | None = None,
        assigned_to: uuid.UUID | None = None,
        asset_id: uuid.UUID | None = None,
        ack_deadline: datetime | None = None,
        first_update_deadline: datetime | None = None,
        due_at: datetime | None = None,
        custom_fields: dict | None = None,
    ) -> WorkOrder:
        now = datetime.now(timezone.utc)
        wo = WorkOrder(
            id=uuid.uuid4(),
            org_id=org_id,
            area_id=area_id,
            location_id=location_id,
            site_id=site_id,
            asset_id=asset_id,
            human_readable_number=f"WO-{now.year}-{uuid.uuid4().hex[:6]}",
            title=title,
            description="Test description for work order with enough length.",
            type=wo_type,
            priority=priority,
            status=status,
            requested_by=requested_by,
            assigned_to=assigned_to,
            safety_flag=safety_flag,
            safety_notes=safety_notes,
            ack_deadline=ack_deadline,
            first_update_deadline=first_update_deadline,
            due_at=due_at,
            custom_fields=custom_fields,
            created_at=now,
            updated_at=now,
        )
        db_session.add(wo)
        await db_session.flush()
        return wo

    return _create


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------


def make_auth_headers(user: User) -> dict[str, str]:
    """Generate an Authorization header with a valid access JWT for the user."""
    token = create_access_token(
        user_id=str(user.id),
        org_id=str(user.org_id),
        role=user.role.value,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
def auth_headers():
    """Fixture that returns a callable producing JWT auth headers for a user."""
    return make_auth_headers


# ---------------------------------------------------------------------------
# Area assignment helper
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
def assign_user_to_area(db_session: AsyncSession):
    """Factory fixture that assigns a user to an area."""

    async def _assign(user_id: uuid.UUID, area_id: uuid.UUID) -> None:
        assignment = UserAreaAssignment(user_id=user_id, area_id=area_id)
        db_session.add(assignment)
        await db_session.flush()

    return _assign


# ---------------------------------------------------------------------------
# Full org hierarchy fixtures for convenience
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def org_a(create_org) -> Organization:
    """Create Organization A for cross-tenant isolation tests."""
    return await create_org(name="Acme Oil & Gas", slug="acme-oil")


@pytest_asyncio.fixture
async def org_b(create_org) -> Organization:
    """Create Organization B for cross-tenant isolation tests."""
    return await create_org(name="Baker Drilling Co", slug="baker-drilling")


@pytest_asyncio.fixture
async def org_a_hierarchy(
    org_a,
    create_user,
    create_area,
    create_location,
    create_site,
    create_asset,
    assign_user_to_area,
) -> dict[str, Any]:
    """Create a complete entity hierarchy for Organization A.

    Returns a dict with keys: org, admin, tech, supervisor, area, location,
    site, asset.
    """
    org = org_a
    admin = await create_user(org.id, name="Org A Admin", role=UserRole.ADMIN)
    tech = await create_user(org.id, name="Org A Tech", role=UserRole.TECHNICIAN)
    supervisor = await create_user(org.id, name="Org A Supervisor", role=UserRole.SUPERVISOR)
    operator = await create_user(org.id, name="Org A Operator", role=UserRole.OPERATOR)
    area = await create_area(org.id, name="Permian Basin")
    location = await create_location(org.id, area.id, name="West Texas Field")
    site = await create_site(org.id, location.id, name="Well Site Alpha")
    asset = await create_asset(org.id, site.id, name="Pump Jack A-1")

    # Assign users to area
    await assign_user_to_area(admin.id, area.id)
    await assign_user_to_area(tech.id, area.id)
    await assign_user_to_area(supervisor.id, area.id)
    await assign_user_to_area(operator.id, area.id)

    return {
        "org": org,
        "admin": admin,
        "tech": tech,
        "supervisor": supervisor,
        "operator": operator,
        "area": area,
        "location": location,
        "site": site,
        "asset": asset,
    }


@pytest_asyncio.fixture
async def org_b_hierarchy(
    org_b,
    create_user,
    create_area,
    create_location,
    create_site,
    create_asset,
    assign_user_to_area,
) -> dict[str, Any]:
    """Create a complete entity hierarchy for Organization B.

    Returns a dict with keys: org, admin, tech, area, location, site, asset.
    """
    org = org_b
    admin = await create_user(org.id, name="Org B Admin", role=UserRole.ADMIN)
    tech = await create_user(org.id, name="Org B Tech", role=UserRole.TECHNICIAN)
    area = await create_area(org.id, name="Eagle Ford Shale")
    location = await create_location(org.id, area.id, name="South Texas Field")
    site = await create_site(org.id, location.id, name="Well Site Beta")
    asset = await create_asset(org.id, site.id, name="Compressor B-1")

    await assign_user_to_area(admin.id, area.id)
    await assign_user_to_area(tech.id, area.id)

    return {
        "org": org,
        "admin": admin,
        "tech": tech,
        "area": area,
        "location": location,
        "site": site,
        "asset": asset,
    }

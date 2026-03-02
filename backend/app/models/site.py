"""Site model."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.asset import Asset
    from app.models.location import Location
    from app.models.org import Organization
    from app.models.pm import PMTemplate
    from app.models.work_order import WorkOrder


class SiteType(str, enum.Enum):
    WELL_SITE = "WELL_SITE"
    PLANT = "PLANT"
    BUILDING = "BUILDING"
    APARTMENT = "APARTMENT"
    LINE = "LINE"
    SUITE = "SUITE"
    COMPRESSOR_STATION = "COMPRESSOR_STATION"
    TANK_BATTERY = "TANK_BATTERY"
    SEPARATOR = "SEPARATOR"
    OTHER = "OTHER"


class Site(Base):
    __tablename__ = "sites"
    __table_args__ = (
        Index("ix_sites_org_id", "org_id"),
        Index("ix_sites_location_id", "location_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[SiteType] = mapped_column(
        Enum(SiteType, name="site_type", native_enum=False, length=30),
        nullable=False,
    )
    address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    gps_lat: Mapped[Optional[float]] = mapped_column(
        Numeric(precision=10, scale=7), nullable=True
    )
    gps_lng: Mapped[Optional[float]] = mapped_column(
        Numeric(precision=10, scale=7), nullable=True
    )
    site_timezone: Mapped[str] = mapped_column(
        String(50), nullable=False, default="America/Chicago"
    )
    qr_code_token: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    # Relationships
    organization: Mapped[Organization] = relationship(back_populates="sites")
    location: Mapped[Location] = relationship(back_populates="sites")
    assets: Mapped[list[Asset]] = relationship(
        back_populates="site", cascade="all, delete-orphan"
    )
    work_orders: Mapped[list[WorkOrder]] = relationship(
        back_populates="site", cascade="all, delete-orphan"
    )
    pm_templates: Mapped[list[PMTemplate]] = relationship(
        back_populates="site", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Site {self.name!r} ({self.type.value})>"

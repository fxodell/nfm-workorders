"""User and related models."""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime, time, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.area import Area
    from app.models.incentive import UserIncentiveScore
    from app.models.org import Organization
    from app.models.shift import UserShiftAssignment
    from app.models.work_order import (
        LaborLog,
        TimelineEvent,
        WorkOrder,
    )


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class UserRole(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN = "ADMIN"
    SUPERVISOR = "SUPERVISOR"
    OPERATOR = "OPERATOR"
    TECHNICIAN = "TECHNICIAN"
    READ_ONLY = "READ_ONLY"
    COST_ANALYST = "COST_ANALYST"


class PermissionType(str, enum.Enum):
    CAN_VIEW_COSTS = "CAN_VIEW_COSTS"
    CAN_MANAGE_BUDGET = "CAN_MANAGE_BUDGET"
    CAN_VIEW_INCENTIVES = "CAN_VIEW_INCENTIVES"
    CAN_MANAGE_INVENTORY = "CAN_MANAGE_INVENTORY"
    CAN_MANAGE_USERS = "CAN_MANAGE_USERS"
    CAN_VIEW_AUDIT_LOG = "CAN_VIEW_AUDIT_LOG"
    CAN_MANAGE_PM_TEMPLATES = "CAN_MANAGE_PM_TEMPLATES"


class OnCallPriority(str, enum.Enum):
    PRIMARY = "PRIMARY"
    SECONDARY = "SECONDARY"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_org_id", "org_id"),
        Index("ix_users_email", "email", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", native_enum=False, length=20),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    totp_secret: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    fcm_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    email_notifications_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    organization: Mapped[Organization] = relationship(back_populates="users")
    area_assignments: Mapped[list[UserAreaAssignment]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    permissions: Mapped[list[UserPermission]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    certifications: Mapped[list[TechnicianCertification]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    notification_prefs: Mapped[list[UserNotificationPref]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    on_call_schedules: Mapped[list[OnCallSchedule]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    shift_assignments: Mapped[list[UserShiftAssignment]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    incentive_scores: Mapped[list[UserIncentiveScore]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    timeline_events: Mapped[list[TimelineEvent]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    labor_logs: Mapped[list[LaborLog]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    # Work-order role relationships (no cascade - WOs should not be deleted
    # when a user is removed; foreign_keys disambiguates the multiple FKs)
    requested_work_orders: Mapped[list[WorkOrder]] = relationship(
        back_populates="requester",
        foreign_keys="WorkOrder.requested_by",
    )
    assigned_work_orders: Mapped[list[WorkOrder]] = relationship(
        back_populates="assignee",
        foreign_keys="WorkOrder.assigned_to",
    )

    def __repr__(self) -> str:
        return f"<User {self.email!r}>"


class UserAreaAssignment(Base):
    __tablename__ = "user_area_assignments"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    area_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("areas.id", ondelete="CASCADE"),
        primary_key=True,
    )

    # Relationships
    user: Mapped[User] = relationship(back_populates="area_assignments")
    area: Mapped[Area] = relationship(back_populates="user_area_assignments")

    def __repr__(self) -> str:
        return f"<UserAreaAssignment user={self.user_id} area={self.area_id}>"


class UserPermission(Base):
    __tablename__ = "user_permissions"
    __table_args__ = (Index("ix_user_permissions_user_id", "user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    permission: Mapped[PermissionType] = mapped_column(
        Enum(PermissionType, name="permission_type", native_enum=False, length=30),
        nullable=False,
    )

    # Relationships
    user: Mapped[User] = relationship(back_populates="permissions")

    def __repr__(self) -> str:
        return f"<UserPermission user={self.user_id} {self.permission.value}>"


class TechnicianCertification(Base):
    __tablename__ = "technician_certifications"
    __table_args__ = (Index("ix_technician_certifications_user_id", "user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    cert_name: Mapped[str] = mapped_column(String(255), nullable=False)
    cert_number: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    issued_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    issued_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    user: Mapped[User] = relationship(back_populates="certifications")

    def __repr__(self) -> str:
        return f"<TechnicianCertification {self.cert_name!r}>"


class UserNotificationPref(Base):
    __tablename__ = "user_notification_prefs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    area_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("areas.id", ondelete="CASCADE"),
        primary_key=True,
    )
    push_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    email_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    on_shift: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Relationships
    user: Mapped[User] = relationship(back_populates="notification_prefs")
    area: Mapped[Area] = relationship(back_populates="user_notification_prefs")

    def __repr__(self) -> str:
        return f"<UserNotificationPref user={self.user_id} area={self.area_id}>"


class OnCallSchedule(Base):
    __tablename__ = "on_call_schedules"
    __table_args__ = (
        Index("ix_on_call_schedules_org_id", "org_id"),
        Index("ix_on_call_schedules_area_id", "area_id"),
        Index("ix_on_call_schedules_user_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    area_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("areas.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    start_dt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    end_dt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    priority: Mapped[OnCallPriority] = mapped_column(
        Enum(OnCallPriority, name="on_call_priority", native_enum=False, length=15),
        nullable=False,
    )

    # Relationships
    organization: Mapped[Organization] = relationship(
        back_populates="on_call_schedules"
    )
    area: Mapped[Area] = relationship(back_populates="on_call_schedules")
    user: Mapped[User] = relationship(back_populates="on_call_schedules")

    def __repr__(self) -> str:
        return (
            f"<OnCallSchedule user={self.user_id} "
            f"{self.start_dt} - {self.end_dt} ({self.priority.value})>"
        )

"""User, certification, and notification-preference schemas."""

from __future__ import annotations

import enum
from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class UserRole(str, enum.Enum):
    """Roles that can be assigned to a user within an organization."""

    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN = "ADMIN"
    SUPERVISOR = "SUPERVISOR"
    OPERATOR = "OPERATOR"
    TECHNICIAN = "TECHNICIAN"
    READ_ONLY = "READ_ONLY"
    COST_ANALYST = "COST_ANALYST"


class Permission(str, enum.Enum):
    """Granular permissions that can be granted to a user."""

    CAN_VIEW_COSTS = "CAN_VIEW_COSTS"
    CAN_MANAGE_BUDGET = "CAN_MANAGE_BUDGET"
    CAN_VIEW_INCENTIVES = "CAN_VIEW_INCENTIVES"
    CAN_MANAGE_INVENTORY = "CAN_MANAGE_INVENTORY"
    CAN_MANAGE_USERS = "CAN_MANAGE_USERS"
    CAN_VIEW_AUDIT_LOG = "CAN_VIEW_AUDIT_LOG"
    CAN_MANAGE_PM_TEMPLATES = "CAN_MANAGE_PM_TEMPLATES"


# ---------------------------------------------------------------------------
# User CRUD
# ---------------------------------------------------------------------------

class UserCreate(BaseModel):
    """Payload for creating a new user."""

    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    phone: Optional[str] = Field(default=None, max_length=30)
    password: str = Field(..., min_length=8)
    role: UserRole
    area_ids: list[UUID] = Field(default_factory=list)

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("email", mode="before")
    @classmethod
    def strip_email(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("phone", mode="before")
    @classmethod
    def strip_phone(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v

    @field_validator("password", mode="before")
    @classmethod
    def strip_password(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v


class UserUpdate(BaseModel):
    """Fields a user (or admin) may update on a user profile."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=30)
    avatar_url: Optional[str] = None
    email_notifications_enabled: Optional[bool] = None

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v

    @field_validator("phone", mode="before")
    @classmethod
    def strip_phone(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v

    @field_validator("avatar_url", mode="before")
    @classmethod
    def strip_avatar_url(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v


class UserResponse(BaseModel):
    """Read-only user representation returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    org_id: UUID
    name: str
    email: str
    phone: Optional[str] = None
    role: UserRole
    is_active: bool
    avatar_url: Optional[str] = None
    mfa_enabled: bool = False
    email_notifications_enabled: bool = True
    last_login_at: Optional[datetime] = None
    created_at: datetime


class UserListResponse(BaseModel):
    """Paginated list of users."""

    model_config = ConfigDict(from_attributes=True)

    items: list[UserResponse]
    total: int
    page: int
    per_page: int


# ---------------------------------------------------------------------------
# Area assignment
# ---------------------------------------------------------------------------

class UserAreaUpdate(BaseModel):
    """Replace the set of areas assigned to a user."""

    area_ids: list[UUID] = Field(..., min_length=0)


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------

class UserPermissionUpdate(BaseModel):
    """Replace the set of explicit permissions for a user."""

    permissions: list[Permission]


# ---------------------------------------------------------------------------
# Notification preferences
# ---------------------------------------------------------------------------

class NotificationPrefUpdate(BaseModel):
    """Per-area notification preferences for a user."""

    area_id: UUID
    push_enabled: bool = True
    email_enabled: bool = True
    on_shift: bool = True


# ---------------------------------------------------------------------------
# Certifications
# ---------------------------------------------------------------------------

class CertificationCreate(BaseModel):
    """Add a certification to a user's profile."""

    cert_name: str = Field(..., min_length=1, max_length=255)
    cert_number: Optional[str] = Field(default=None, max_length=100)
    issued_by: Optional[str] = Field(default=None, max_length=255)
    issued_date: Optional[date] = None
    expires_at: Optional[date] = None
    notes: Optional[str] = None

    @field_validator("cert_name", mode="before")
    @classmethod
    def strip_cert_name(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("cert_number", mode="before")
    @classmethod
    def strip_cert_number(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v

    @field_validator("issued_by", mode="before")
    @classmethod
    def strip_issued_by(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v

    @field_validator("notes", mode="before")
    @classmethod
    def strip_notes(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v


class CertificationResponse(BaseModel):
    """Read-only certification attached to a user."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    cert_name: str
    cert_number: Optional[str] = None
    issued_by: Optional[str] = None
    issued_date: Optional[date] = None
    expires_at: Optional[date] = None
    notes: Optional[str] = None

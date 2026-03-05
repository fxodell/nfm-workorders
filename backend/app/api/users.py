"""User management routes: profile, CRUD, certifications, permissions, shifts."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

import redis.asyncio as aioredis

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import (
    get_current_active_user,
    require_role,
    verify_org_ownership,
)
from app.core.redis import get_redis, revoke_all_user_tokens
from app.core.security import hash_password
from app.models.shift import ShiftSchedule, UserShiftAssignment
from app.models.user import (
    OnCallSchedule,
    TechnicianCertification,
    User,
    UserAreaAssignment,
    UserNotificationPref,
    UserPermission,
)
from app.schemas.common import MessageResponse
from app.schemas.user import (
    CertificationCreate,
    CertificationResponse,
    NotificationPrefUpdate,
    UserAreaUpdate,
    UserCreate,
    UserListResponse,
    UserPermissionUpdate,
    UserResponse,
    UserUpdate,
)

router = APIRouter(prefix="/users", tags=["users"])


# ── GET /me ────────────────────────────────────────────────────────────

@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_active_user),
):
    """Return the authenticated user's profile."""
    return current_user


# ── PATCH /me ──────────────────────────────────────────────────────────

@router.patch("/me", response_model=UserResponse)
async def update_me(
    body: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update the authenticated user's own profile."""
    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(current_user, field, value)
    current_user.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return current_user


# ── POST /me/fcm-token ────────────────────────────────────────────────

@router.post("/me/fcm-token", response_model=MessageResponse)
async def store_fcm_token(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Store or update the user's FCM push-notification token."""
    fcm_token = body.get("fcm_token")
    if not fcm_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="fcm_token is required",
        )
    current_user.fcm_token = fcm_token
    await db.flush()
    return MessageResponse(message="FCM token stored")


# ── DELETE /me/fcm-token ──────────────────────────────────────────────

@router.delete("/me/fcm-token", response_model=MessageResponse)
async def clear_fcm_token(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Clear the user's FCM push-notification token."""
    current_user.fcm_token = None
    await db.flush()
    return MessageResponse(message="FCM token cleared")


# ── GET /me/notification-prefs ─────────────────────────────────────────

@router.get("/me/notification-prefs", response_model=list[NotificationPrefUpdate])
async def get_notification_prefs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Return the authenticated user's per-area notification preferences."""
    result = await db.execute(
        select(UserNotificationPref).where(
            UserNotificationPref.user_id == current_user.id
        )
    )
    prefs = result.scalars().all()
    return [
        NotificationPrefUpdate(
            area_id=p.area_id,
            push_enabled=p.push_enabled,
            email_enabled=p.email_enabled,
            on_shift=p.on_shift,
        )
        for p in prefs
    ]


# ── PATCH /me/notification-prefs ───────────────────────────────────────

@router.patch("/me/notification-prefs", response_model=MessageResponse)
async def update_notification_prefs(
    body: NotificationPrefUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create or update per-area notification preferences."""
    result = await db.execute(
        select(UserNotificationPref).where(
            UserNotificationPref.user_id == current_user.id,
            UserNotificationPref.area_id == body.area_id,
        )
    )
    pref = result.scalars().first()
    if pref:
        pref.push_enabled = body.push_enabled
        pref.email_enabled = body.email_enabled
        pref.on_shift = body.on_shift
    else:
        pref = UserNotificationPref(
            user_id=current_user.id,
            area_id=body.area_id,
            push_enabled=body.push_enabled,
            email_enabled=body.email_enabled,
            on_shift=body.on_shift,
        )
        db.add(pref)
    await db.flush()
    return MessageResponse(message="Notification preferences updated")


# ── GET /me/certifications ─────────────────────────────────────────────

@router.get("/me/certifications", response_model=list[CertificationResponse])
async def get_my_certifications(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List the authenticated user's certifications."""
    result = await db.execute(
        select(TechnicianCertification).where(
            TechnicianCertification.user_id == current_user.id
        )
    )
    return result.scalars().all()


# ── GET /me/shifts ─────────────────────────────────────────────────────

@router.get("/me/shifts")
async def get_my_shifts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List shift schedules assigned to the authenticated user."""
    result = await db.execute(
        select(ShiftSchedule)
        .join(UserShiftAssignment,
              UserShiftAssignment.shift_schedule_id == ShiftSchedule.id)
        .where(UserShiftAssignment.user_id == current_user.id)
    )
    return result.scalars().all()


# ── GET / (list users, ADMIN only) ─────────────────────────────────────

@router.get("", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["SUPER_ADMIN", "ADMIN"])),
):
    """List all users in the organization (ADMIN only, paginated)."""
    query = select(User).where(User.org_id == current_user.org_id)

    if search:
        query = query.where(
            User.name.ilike(f"%{search}%") | User.email.ilike(f"%{search}%")
        )
    if role:
        query = query.where(User.role == role)
    if is_active is not None:
        query = query.where(User.is_active == is_active)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginate
    query = query.order_by(User.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    users = result.scalars().all()

    return UserListResponse(items=users, total=total, page=page, per_page=per_page)


# ── POST / (create user, ADMIN only) ──────────────────────────────────

@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["SUPER_ADMIN", "ADMIN"])),
):
    """Create a new user in the organization (ADMIN only)."""
    # Check for duplicate email
    existing = await db.execute(
        select(User).where(User.email == body.email.lower())
    )
    if existing.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    user = User(
        org_id=current_user.org_id,
        name=body.name,
        email=body.email.lower(),
        phone=body.phone,
        password_hash=hash_password(body.password),
        role=body.role,
    )
    db.add(user)
    await db.flush()

    # Assign areas
    for area_id in body.area_ids:
        assignment = UserAreaAssignment(user_id=user.id, area_id=area_id)
        db.add(assignment)
    await db.flush()

    return user


# ── GET /{id} ──────────────────────────────────────────────────────────

@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["SUPER_ADMIN", "ADMIN"])),
):
    """Get a user by ID (ADMIN only, org_id check)."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    await verify_org_ownership(user, current_user)
    return user


# ── PATCH /{id} ────────────────────────────────────────────────────────

@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["SUPER_ADMIN", "ADMIN"])),
):
    """Update a user's profile (ADMIN only)."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    await verify_org_ownership(user, current_user)

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)
    user.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return user


# ── DELETE /{id} (soft delete) ─────────────────────────────────────────

@router.delete("/{user_id}", response_model=MessageResponse)
async def delete_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    r: aioredis.Redis = Depends(get_redis),
    current_user: User = Depends(require_role(["SUPER_ADMIN", "ADMIN"])),
):
    """Soft-delete a user (ADMIN only). Sets is_active to False."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    await verify_org_ownership(user, current_user)

    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account",
        )

    user.is_active = False
    user.updated_at = datetime.now(timezone.utc)
    await db.flush()

    # Revoke all tokens so the disabled user is immediately logged out
    await revoke_all_user_tokens(r, str(user_id), settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400)

    return MessageResponse(message="User deactivated")


# ── PUT /{id}/areas ────────────────────────────────────────────────────

@router.put("/{user_id}/areas", response_model=MessageResponse)
async def replace_area_assignments(
    user_id: uuid.UUID,
    body: UserAreaUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["SUPER_ADMIN", "ADMIN"])),
):
    """Replace a user's area assignments (ADMIN only)."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    await verify_org_ownership(user, current_user)

    # Delete existing assignments
    await db.execute(
        delete(UserAreaAssignment).where(UserAreaAssignment.user_id == user_id)
    )

    # Create new assignments
    for area_id in body.area_ids:
        db.add(UserAreaAssignment(user_id=user_id, area_id=area_id))
    await db.flush()

    return MessageResponse(message="Area assignments updated")


# ── GET /{id}/permissions ──────────────────────────────────────────────

@router.get("/{user_id}/permissions")
async def get_user_permissions(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get a user's explicit permissions."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    await verify_org_ownership(user, current_user)

    result = await db.execute(
        select(UserPermission).where(UserPermission.user_id == user_id)
    )
    perms = result.scalars().all()
    return [{"permission": p.permission.value} for p in perms]


# ── PUT /{id}/permissions ──────────────────────────────────────────────

@router.put("/{user_id}/permissions", response_model=MessageResponse)
async def update_user_permissions(
    user_id: uuid.UUID,
    body: UserPermissionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["SUPER_ADMIN", "ADMIN"])),
):
    """Replace a user's explicit permissions (ADMIN only)."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    await verify_org_ownership(user, current_user)

    # Delete existing permissions
    await db.execute(
        delete(UserPermission).where(UserPermission.user_id == user_id)
    )

    # Create new permissions
    for perm in body.permissions:
        db.add(UserPermission(user_id=user_id, permission=perm))
    await db.flush()

    return MessageResponse(message="Permissions updated")


# ── GET /{id}/certifications ───────────────────────────────────────────

@router.get("/{user_id}/certifications", response_model=list[CertificationResponse])
async def list_user_certifications(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List certifications for a specific user."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    await verify_org_ownership(user, current_user)

    result = await db.execute(
        select(TechnicianCertification).where(
            TechnicianCertification.user_id == user_id
        )
    )
    return result.scalars().all()


# ── POST /{id}/certifications ──────────────────────────────────────────

@router.post(
    "/{user_id}/certifications",
    response_model=CertificationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_certification(
    user_id: uuid.UUID,
    body: CertificationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Add a certification to a user."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    await verify_org_ownership(user, current_user)

    cert = TechnicianCertification(
        user_id=user_id,
        cert_name=body.cert_name,
        cert_number=body.cert_number,
        issued_by=body.issued_by,
        issued_date=body.issued_date,
        expires_at=body.expires_at,
        notes=body.notes,
    )
    db.add(cert)
    await db.flush()
    return cert


# ── DELETE /{id}/certifications/{cert_id} ──────────────────────────────

@router.delete("/{user_id}/certifications/{cert_id}", response_model=MessageResponse)
async def remove_certification(
    user_id: uuid.UUID,
    cert_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Remove a certification from a user."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    await verify_org_ownership(user, current_user)

    cert = await db.get(TechnicianCertification, cert_id)
    if not cert or cert.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certification not found",
        )

    await db.delete(cert)
    await db.flush()
    return MessageResponse(message="Certification removed")

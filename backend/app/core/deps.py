"""
FastAPI dependency functions for authentication and authorization.

Provides:
- ``get_current_user``         -- validates JWT and loads the user from DB
- ``get_current_active_user``  -- additionally checks ``is_active``
- ``require_role``             -- dependency factory restricting by role(s)
- ``require_permission``       -- dependency factory restricting by permission
- ``verify_org_ownership``     -- confirms entity belongs to caller's org
- ``verify_area_access``       -- confirms user is assigned to the area
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


# ── Get current user ───────────────────────────────────────────────────

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Decode the access JWT and return the corresponding ``User`` row.

    Raises 401 if the token is invalid or the user does not exist.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        user_id_str: str | None = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
        user_id = uuid.UUID(user_id_str)
    except (JWTError, ValueError):
        raise credentials_exception

    # Deferred import to avoid circular dependency between core and models.
    from app.models.user import User  # noqa: WPS433

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if user is None:
        raise credentials_exception
    return user


# ── Active user gate ────────────────────────────────────────────────────

async def get_current_active_user(
    current_user: Any = Depends(get_current_user),
) -> Any:
    """Ensure the authenticated user has ``is_active=True``."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account",
        )
    return current_user


# ── Role restriction ───────────────────────────────────────────────────

def require_role(allowed_roles: Sequence[str]) -> Callable:
    """Return a FastAPI dependency that restricts access to specific roles.

    Usage::

        @router.get("/admin-only", dependencies=[Depends(require_role(["ADMIN"]))])
        async def admin_only():
            ...
    """

    async def _role_checker(
        current_user: Any = Depends(get_current_active_user),
    ) -> Any:
        if current_user.role.value not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role.value}' is not permitted for this operation",
            )
        return current_user

    return _role_checker


# ── Permission restriction ─────────────────────────────────────────────

def require_permission(permission_name: str) -> Callable:
    """Return a FastAPI dependency that checks for a specific permission.

    Looks up the ``UserPermission`` table for a matching row. Admins and
    super-admins bypass the check.

    Usage::

        @router.get(
            "/costs",
            dependencies=[Depends(require_permission("CAN_VIEW_COSTS"))],
        )
        async def view_costs():
            ...
    """

    async def _permission_checker(
        current_user: Any = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db),
    ) -> Any:
        # Super-admins and admins have all permissions implicitly.
        bypass_roles = {"SUPER_ADMIN", "ADMIN"}
        if current_user.role.value in bypass_roles:
            return current_user

        from app.models.user import UserPermission  # noqa: WPS433

        result = await db.execute(
            select(UserPermission).where(
                UserPermission.user_id == current_user.id,
                UserPermission.permission == permission_name,
            )
        )
        if result.scalars().first() is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission: {permission_name}",
            )
        return current_user

    return _permission_checker


# ── Org ownership verification ──────────────────────────────────────────

async def verify_org_ownership(
    entity: Any,
    current_user: Any,
) -> None:
    """Verify that *entity.org_id* matches the current user's org.

    Raises 404 (not 403) to avoid leaking information about resources
    belonging to other organizations.
    """
    if entity.org_id != current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource not found",
        )


# ── Area access verification ───────────────────────────────────────────

async def verify_area_access(
    area_id: uuid.UUID,
    current_user: Any,
    db: AsyncSession,
) -> None:
    """Verify the user is assigned to the given area.

    Admins and super-admins bypass the check; they have access to all
    areas within their organization.
    """
    bypass_roles = {"SUPER_ADMIN", "ADMIN"}
    if current_user.role.value in bypass_roles:
        return

    from app.models.user import UserAreaAssignment  # noqa: WPS433

    result = await db.execute(
        select(UserAreaAssignment).where(
            UserAreaAssignment.user_id == current_user.id,
            UserAreaAssignment.area_id == area_id,
        )
    )
    if result.scalars().first() is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this area",
        )

"""Admin routes: org management, config, audit log."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import (
    get_current_active_user,
    require_permission,
    require_role,
    verify_org_ownership,
)
from app.models.audit_log import AuditLog
from app.models.org import Organization
from app.models.user import User
from app.schemas.admin import AuditLogListResponse, AuditLogResponse
from app.schemas.org import OrgConfigUpdate, OrgResponse, OrgUpdate

router = APIRouter(prefix="/admin", tags=["admin"])


# ── GET /org ───────────────────────────────────────────────────────────

@router.get("/org", response_model=OrgResponse)
async def get_org(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["SUPER_ADMIN", "ADMIN"])),
):
    """Get the current user's organization."""
    org = await db.get(Organization, current_user.org_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return org


# ── PATCH /org ─────────────────────────────────────────────────────────

@router.patch("/org", response_model=OrgResponse)
async def update_org(
    body: OrgUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["SUPER_ADMIN", "ADMIN"])),
):
    """Update organization details."""
    org = await db.get(Organization, current_user.org_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(org, field, value)
    await db.flush()

    # Audit log
    audit = AuditLog(
        org_id=current_user.org_id,
        actor_user_id=current_user.id,
        action="UPDATE",
        entity_type="Organization",
        entity_id=str(org.id),
        new_value=update_data,
    )
    db.add(audit)
    await db.flush()

    return org


# ── GET /org/config ────────────────────────────────────────────────────

@router.get("/org/config")
async def get_org_config(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["SUPER_ADMIN", "ADMIN"])),
):
    """Get the organization's configuration (SLA thresholds, etc.)."""
    org = await db.get(Organization, current_user.org_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return org.config or {}


# ── PUT /org/config ────────────────────────────────────────────────────

@router.put("/org/config")
async def update_org_config(
    body: OrgConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["SUPER_ADMIN", "ADMIN"])),
):
    """Update the organization's configuration."""
    org = await db.get(Organization, current_user.org_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    config = org.config or {}
    update_data = body.model_dump(exclude_unset=True)

    # Handle nested SLA config
    if "sla" in update_data and update_data["sla"] is not None:
        sla_data = update_data.pop("sla")
        if isinstance(sla_data, dict):
            config["sla"] = {**config.get("sla", {}), **sla_data}
        else:
            config["sla"] = sla_data.model_dump() if hasattr(sla_data, "model_dump") else sla_data

    # Merge remaining top-level keys
    for key, value in update_data.items():
        if value is not None:
            config[key] = value

    org.config = config
    await db.flush()

    # Audit log
    audit = AuditLog(
        org_id=current_user.org_id,
        actor_user_id=current_user.id,
        action="UPDATE_CONFIG",
        entity_type="Organization",
        entity_id=str(org.id),
        new_value=config,
    )
    db.add(audit)
    await db.flush()

    return config


# ── GET /audit-log ────────────────────────────────────────────────────

@router.get("/audit-log", response_model=AuditLogListResponse)
async def list_audit_log(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    entity_type: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    actor_user_id: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("CAN_VIEW_AUDIT_LOG")),
):
    """List audit log entries (paginated, filterable)."""
    query = select(AuditLog).where(AuditLog.org_id == current_user.org_id)

    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
    if action:
        query = query.where(AuditLog.action == action)
    if actor_user_id:
        query = query.where(AuditLog.actor_user_id == actor_user_id)
    if date_from:
        query = query.where(AuditLog.created_at >= date_from)
    if date_to:
        query = query.where(AuditLog.created_at <= date_to)

    # Count total
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # Paginate
    query = query.order_by(AuditLog.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    items = result.scalars().all()

    return AuditLogListResponse(
        items=items, total=total, page=page, per_page=per_page
    )

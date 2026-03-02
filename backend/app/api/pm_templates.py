"""Preventive maintenance template routes: CRUD with filtering."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import (
    get_current_active_user,
    require_permission,
    verify_org_ownership,
)
from app.models.pm import PMTemplate
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.pm import PMTemplateCreate, PMTemplateResponse, PMTemplateUpdate

router = APIRouter(prefix="/pm-templates", tags=["pm-templates"])


# ── GET / ──────────────────────────────────────────────────────────────

@router.get("/", response_model=list[PMTemplateResponse])
async def list_pm_templates(
    site_id: Optional[uuid.UUID] = Query(None),
    asset_id: Optional[uuid.UUID] = Query(None),
    is_active: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List PM templates with optional filters."""
    query = select(PMTemplate).where(PMTemplate.org_id == current_user.org_id)

    if site_id:
        query = query.where(PMTemplate.site_id == site_id)
    if asset_id:
        query = query.where(PMTemplate.asset_id == asset_id)
    if is_active is not None:
        query = query.where(PMTemplate.is_active == is_active)

    query = query.order_by(PMTemplate.title)
    result = await db.execute(query)
    return result.scalars().all()


# ── POST / ─────────────────────────────────────────────────────────────

@router.post("/", response_model=PMTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_pm_template(
    body: PMTemplateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("CAN_MANAGE_PM_TEMPLATES")),
):
    """Create a new PM template."""
    template = PMTemplate(
        org_id=current_user.org_id,
        asset_id=body.asset_id,
        site_id=body.site_id,
        title=body.title,
        description=body.description,
        priority=body.priority,
        checklist_json=body.checklist_json,
        recurrence_type=body.recurrence_type,
        recurrence_interval=body.recurrence_interval,
        required_cert=body.required_cert,
        assigned_to_role=body.assigned_to_role,
    )
    db.add(template)
    await db.flush()
    return template


# ── GET /{id} ──────────────────────────────────────────────────────────

@router.get("/{template_id}", response_model=PMTemplateResponse)
async def get_pm_template(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get a PM template by ID."""
    template = await db.get(PMTemplate, template_id)
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PM template not found")
    await verify_org_ownership(template, current_user)
    return template


# ── PATCH /{id} ────────────────────────────────────────────────────────

@router.patch("/{template_id}", response_model=PMTemplateResponse)
async def update_pm_template(
    template_id: uuid.UUID,
    body: PMTemplateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("CAN_MANAGE_PM_TEMPLATES")),
):
    """Update a PM template."""
    template = await db.get(PMTemplate, template_id)
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PM template not found")
    await verify_org_ownership(template, current_user)

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(template, field, value)
    await db.flush()
    return template


# ── DELETE /{id} ───────────────────────────────────────────────────────

@router.delete("/{template_id}", response_model=MessageResponse)
async def delete_pm_template(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("CAN_MANAGE_PM_TEMPLATES")),
):
    """Soft-delete a PM template by deactivating it."""
    template = await db.get(PMTemplate, template_id)
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PM template not found")
    await verify_org_ownership(template, current_user)

    template.is_active = False
    await db.flush()
    return MessageResponse(message="PM template deactivated")

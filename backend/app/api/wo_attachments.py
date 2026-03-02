"""Work order attachment routes: list, create (presigned upload), delete."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_active_user, verify_org_ownership
from app.core.s3 import (
    delete_object,
    generate_presigned_download_url,
    generate_presigned_upload_url,
)
from app.models.user import User
from app.models.work_order import Attachment, TimelineEvent, TimelineEventType, WorkOrder
from app.schemas.common import MessageResponse
from app.schemas.work_order import AttachmentResponse

router = APIRouter(prefix="/work-orders", tags=["work-order-attachments"])


class AttachmentCreateRequest(BaseModel):
    """Request to create an attachment record and get a presigned upload URL."""
    filename: str = Field(..., min_length=1, max_length=500)
    mime_type: str = Field(..., min_length=1, max_length=255)
    size_bytes: Optional[int] = Field(default=None, ge=0)
    caption: Optional[str] = None


class AttachmentCreateResponse(BaseModel):
    """Response with the attachment record and presigned upload URL."""
    attachment: AttachmentResponse
    upload_url: str
    s3_key: str


# ── GET /work-orders/{id}/attachments ──────────────────────────────────

@router.get("/{wo_id}/attachments", response_model=list[AttachmentResponse])
async def list_attachments(
    wo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all attachments for a work order with presigned download URLs."""
    wo = await db.get(WorkOrder, wo_id)
    if not wo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")
    await verify_org_ownership(wo, current_user)

    result = await db.execute(
        select(Attachment)
        .where(Attachment.work_order_id == wo_id)
        .order_by(Attachment.created_at.asc())
    )
    attachments = result.scalars().all()

    response = []
    for att in attachments:
        download_url = generate_presigned_download_url(att.s3_key, att.filename)
        resp = AttachmentResponse.model_validate(att)
        resp.download_url = download_url
        response.append(resp)

    return response


# ── POST /work-orders/{id}/attachments ─────────────────────────────────

@router.post(
    "/{wo_id}/attachments",
    response_model=AttachmentCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_attachment(
    wo_id: uuid.UUID,
    body: AttachmentCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create an attachment record and return a presigned upload URL."""
    wo = await db.get(WorkOrder, wo_id)
    if not wo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")
    await verify_org_ownership(wo, current_user)

    # Generate presigned upload URL
    upload_info = generate_presigned_upload_url(
        filename=body.filename,
        content_type=body.mime_type,
        org_id=str(current_user.org_id),
        prefix=f"attachments/{wo_id}",
    )

    attachment = Attachment(
        work_order_id=wo_id,
        org_id=wo.org_id,
        uploaded_by=current_user.id,
        s3_key=upload_info["s3_key"],
        s3_bucket=upload_info["s3_bucket"],
        filename=body.filename,
        mime_type=body.mime_type,
        size_bytes=body.size_bytes,
        caption=body.caption,
    )
    db.add(attachment)

    # Timeline event
    event = TimelineEvent(
        work_order_id=wo_id,
        org_id=wo.org_id,
        user_id=current_user.id,
        event_type=TimelineEventType.ATTACHMENT_ADDED,
        payload={"filename": body.filename, "mime_type": body.mime_type},
    )
    db.add(event)
    await db.flush()

    att_response = AttachmentResponse.model_validate(attachment)
    return AttachmentCreateResponse(
        attachment=att_response,
        upload_url=upload_info["url"],
        s3_key=upload_info["s3_key"],
    )


# ── DELETE /work-orders/{id}/attachments/{attachment_id} ───────────────

@router.delete("/{wo_id}/attachments/{attachment_id}", response_model=MessageResponse)
async def delete_attachment(
    wo_id: uuid.UUID,
    attachment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Delete an attachment from a work order."""
    wo = await db.get(WorkOrder, wo_id)
    if not wo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")
    await verify_org_ownership(wo, current_user)

    attachment = await db.get(Attachment, attachment_id)
    if not attachment or attachment.work_order_id != wo_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment not found",
        )
    await verify_org_ownership(attachment, current_user)

    # Delete from S3
    delete_object(attachment.s3_key)

    await db.delete(attachment)
    await db.flush()
    return MessageResponse(message="Attachment deleted")

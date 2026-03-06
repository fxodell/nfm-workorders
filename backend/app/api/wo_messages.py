"""Work order message routes: list and send messages."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_active_user, verify_org_ownership
from app.models.user import User
from app.models.work_order import (
    TimelineEvent,
    TimelineEventType,
    WorkOrder,
)
from app.schemas.work_order import (
    MessageCreate,
    MessageResponse as WOMessageResponse,
    TimelineEventResponse,
)

router = APIRouter(prefix="/work-orders", tags=["work-order-messages"])


# ── GET /work-orders/{id}/messages ─────────────────────────────────────

@router.get("/{wo_id}/messages", response_model=list[WOMessageResponse])
async def list_messages(
    wo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all messages on a work order thread."""
    wo = await db.get(WorkOrder, wo_id)
    if not wo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")
    await verify_org_ownership(wo, current_user)

    result = await db.execute(
        select(TimelineEvent)
        .where(
            TimelineEvent.work_order_id == wo_id,
            TimelineEvent.event_type == TimelineEventType.MESSAGE,
        )
        .order_by(TimelineEvent.created_at.asc())
    )
    events = result.scalars().all()

    messages = []
    for e in events:
        payload = e.payload or {}
        # Look up sender name
        sender_name = None
        if e.user_id:
            sender = await db.get(User, e.user_id)
            if sender:
                sender_name = sender.name

        messages.append(
            WOMessageResponse(
                id=e.id,
                work_order_id=e.work_order_id,
                user_id=e.user_id,
                sender_name=sender_name,
                content=payload.get("content", ""),
                created_at=e.created_at,
            )
        )

    return messages


# ── POST /work-orders/{id}/messages ────────────────────────────────────

@router.post(
    "/{wo_id}/messages",
    response_model=WOMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def send_message(
    wo_id: uuid.UUID,
    body: MessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Send a message on a work-order thread. Publishes WS event."""
    wo = await db.get(WorkOrder, wo_id)
    if not wo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")
    await verify_org_ownership(wo, current_user)

    event = TimelineEvent(
        work_order_id=wo_id,
        org_id=wo.org_id,
        user_id=current_user.id,
        event_type=TimelineEventType.MESSAGE,
        payload={"content": body.content, "type": "message"},
    )
    db.add(event)
    await db.flush()

    # Publish WebSocket event for real-time delivery
    try:
        import json
        import logging
        import redis.asyncio as aioredis
        from app.core.redis import redis_pool

        r = aioredis.Redis(connection_pool=redis_pool)
        try:
            ws_payload = json.dumps({
                "type": "wo_message",
                "work_order_id": str(wo_id),
                "message": {
                    "id": str(event.id),
                    "user_id": str(current_user.id),
                    "sender_name": current_user.name,
                    "content": body.content,
                    "created_at": event.created_at.isoformat() if event.created_at else None,
                },
            }, default=str)
            await r.publish(f"wo:{wo_id}", ws_payload)
        finally:
            await r.aclose()
    except Exception:
        logging.getLogger(__name__).warning(
            "Failed to publish WS event for wo=%s", wo_id, exc_info=True
        )

    return WOMessageResponse(
        id=event.id,
        work_order_id=wo_id,
        user_id=current_user.id,
        sender_name=current_user.name,
        content=body.content,
        created_at=event.created_at,
    )

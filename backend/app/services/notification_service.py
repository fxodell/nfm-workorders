"""Notification service: WebSocket publishing, push notifications, email."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.firebase import send_push_notification, send_multicast_notification
from app.models.user import (
    OnCallSchedule,
    OnCallPriority,
    User,
    UserAreaAssignment,
    UserNotificationPref,
    UserRole,
)
from app.models.work_order import WorkOrder, WorkOrderStatus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _get_area_users_with_push(
    db: AsyncSession,
    org_id: uuid.UUID,
    area_id: uuid.UUID,
    roles: set[str] | None = None,
) -> list[User]:
    """Return active users assigned to the given area who have push enabled.

    Optionally filters by role.
    """
    stmt = (
        select(User)
        .join(UserAreaAssignment, UserAreaAssignment.user_id == User.id)
        .outerjoin(
            UserNotificationPref,
            and_(
                UserNotificationPref.user_id == User.id,
                UserNotificationPref.area_id == area_id,
            ),
        )
        .where(
            User.org_id == org_id,
            User.is_active.is_(True),
            UserAreaAssignment.area_id == area_id,
            User.fcm_token.isnot(None),
        )
    )

    if roles:
        stmt = stmt.where(User.role.in_([UserRole(r) for r in roles]))

    result = await db.execute(stmt)
    return list(result.scalars().unique().all())


async def _get_on_call_users(
    db: AsyncSession,
    org_id: uuid.UUID,
    area_id: uuid.UUID,
    priority: OnCallPriority,
) -> list[User]:
    """Return on-call users for the area at the given priority level."""
    now = datetime.now(timezone.utc)
    stmt = (
        select(User)
        .join(OnCallSchedule, OnCallSchedule.user_id == User.id)
        .where(
            OnCallSchedule.org_id == org_id,
            OnCallSchedule.area_id == area_id,
            OnCallSchedule.priority == priority,
            OnCallSchedule.start_dt <= now,
            OnCallSchedule.end_dt >= now,
            User.is_active.is_(True),
        )
    )
    result = await db.execute(stmt)
    return list(result.scalars().unique().all())


async def _get_supervisors(
    db: AsyncSession,
    org_id: uuid.UUID,
    area_id: uuid.UUID,
) -> list[User]:
    """Return active supervisors assigned to the area."""
    stmt = (
        select(User)
        .join(UserAreaAssignment, UserAreaAssignment.user_id == User.id)
        .where(
            User.org_id == org_id,
            User.is_active.is_(True),
            UserAreaAssignment.area_id == area_id,
            User.role == UserRole.SUPERVISOR,
        )
    )
    result = await db.execute(stmt)
    return list(result.scalars().unique().all())


async def _publish_ws(
    redis: Any,
    org_id: uuid.UUID,
    area_id: uuid.UUID,
    event_data: dict[str, Any],
) -> None:
    """Publish a JSON event to the Redis pub/sub channel for the area."""
    channel = f"org:{org_id}:area:{area_id}"
    await redis.publish(channel, json.dumps(event_data, default=str))


async def _send_push_to_users(
    users: list[User],
    title: str,
    body: str,
    data: dict[str, str] | None = None,
) -> None:
    """Send push notifications to a list of users that have FCM tokens."""
    tokens = [u.fcm_token for u in users if u.fcm_token]
    if not tokens:
        return

    if len(tokens) == 1:
        await send_push_notification(tokens[0], title, body, data)
    else:
        await send_multicast_notification(tokens, title, body, data)


async def _send_email_to_users(
    users: list[User],
    subject: str,
    body_text: str,
) -> None:
    """Send an email notification to users who have email notifications enabled.

    Uses SendGrid if configured; otherwise logs a warning.
    """
    if not settings.SENDGRID_API_KEY:
        logger.debug(
            "SendGrid not configured; skipping email to %d users", len(users)
        )
        return

    recipients = [
        u.email
        for u in users
        if u.email and u.email_notifications_enabled
    ]
    if not recipients:
        return

    try:
        import sendgrid
        from sendgrid.helpers.mail import Mail

        sg = sendgrid.SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)
        for email_addr in recipients:
            message = Mail(
                from_email=settings.EMAIL_FROM,
                to_emails=email_addr,
                subject=subject,
                plain_text_content=body_text,
            )
            sg.send(message)
    except Exception:
        logger.exception("Failed to send email notifications")


# ---------------------------------------------------------------------------
# Public notification methods
# ---------------------------------------------------------------------------


async def notify_new_work_order(
    wo: WorkOrder,
    redis: Any,
    db: AsyncSession | None = None,
) -> None:
    """Notify users about a newly created work order.

    Publishes a WebSocket event to the area channel and sends push
    notifications to all users assigned to the work order's area.
    """
    event_data = {
        "event": "work_order.created",
        "work_order_id": str(wo.id),
        "human_readable_number": wo.human_readable_number,
        "title": wo.title,
        "priority": wo.priority.value if wo.priority else None,
        "area_id": str(wo.area_id),
        "safety_flag": wo.safety_flag,
    }
    await _publish_ws(redis, wo.org_id, wo.area_id, event_data)

    if db is not None:
        users = await _get_area_users_with_push(db, wo.org_id, wo.area_id)
        await _send_push_to_users(
            users,
            title=f"New Work Order: {wo.human_readable_number}",
            body=wo.title,
            data={
                "type": "new_work_order",
                "work_order_id": str(wo.id),
            },
        )


async def notify_status_change(
    wo: WorkOrder,
    old_status: WorkOrderStatus,
    new_status: WorkOrderStatus,
    user: User,
    redis: Any,
    db: AsyncSession | None = None,
) -> None:
    """Notify users about a work-order status change.

    Publishes a WebSocket event and sends push notifications to relevant
    area users.
    """
    event_data = {
        "event": "work_order.status_changed",
        "work_order_id": str(wo.id),
        "human_readable_number": wo.human_readable_number,
        "from_status": old_status.value,
        "to_status": new_status.value,
        "changed_by": str(user.id),
        "changed_by_name": user.name,
    }
    await _publish_ws(redis, wo.org_id, wo.area_id, event_data)

    if db is not None:
        users = await _get_area_users_with_push(db, wo.org_id, wo.area_id)
        await _send_push_to_users(
            users,
            title=f"{wo.human_readable_number} Status Update",
            body=f"{old_status.value} -> {new_status.value} by {user.name}",
            data={
                "type": "status_change",
                "work_order_id": str(wo.id),
                "new_status": new_status.value,
            },
        )


async def notify_escalation(
    wo: WorkOrder,
    redis: Any,
    db: AsyncSession | None = None,
) -> None:
    """Notify on-call personnel about a work-order escalation.

    Push notification order:
    1. On-call PRIMARY for the area
    2. If no PRIMARY, on-call SECONDARY
    3. Email is always sent to on-call users

    Publishes a WebSocket event to the area channel.
    """
    event_data = {
        "event": "work_order.escalated",
        "work_order_id": str(wo.id),
        "human_readable_number": wo.human_readable_number,
        "priority": wo.priority.value if wo.priority else None,
        "area_id": str(wo.area_id),
    }
    await _publish_ws(redis, wo.org_id, wo.area_id, event_data)

    if db is None:
        return

    # Try PRIMARY on-call first
    primary_users = await _get_on_call_users(
        db, wo.org_id, wo.area_id, OnCallPriority.PRIMARY
    )
    target_users = primary_users

    if not target_users:
        # Fall back to SECONDARY
        target_users = await _get_on_call_users(
            db, wo.org_id, wo.area_id, OnCallPriority.SECONDARY
        )

    push_title = f"ESCALATION: {wo.human_readable_number}"
    push_body = f"{wo.title} - Priority: {wo.priority.value if wo.priority else 'N/A'}"

    await _send_push_to_users(
        target_users,
        title=push_title,
        body=push_body,
        data={
            "type": "escalation",
            "work_order_id": str(wo.id),
        },
    )

    # Email is always sent for escalations
    all_on_call = primary_users + await _get_on_call_users(
        db, wo.org_id, wo.area_id, OnCallPriority.SECONDARY
    )
    # Deduplicate
    seen_ids: set[uuid.UUID] = set()
    unique_users: list[User] = []
    for u in all_on_call:
        if u.id not in seen_ids:
            seen_ids.add(u.id)
            unique_users.append(u)

    await _send_email_to_users(
        unique_users,
        subject=f"[ESCALATION] Work Order {wo.human_readable_number}",
        body_text=(
            f"Work Order {wo.human_readable_number} has been escalated.\n\n"
            f"Title: {wo.title}\n"
            f"Priority: {wo.priority.value if wo.priority else 'N/A'}\n\n"
            f"Please respond immediately.\n\n"
            f"View: {settings.FRONTEND_URL}/work-orders/{wo.id}"
        ),
    )


async def notify_sla_breach(
    wo: WorkOrder,
    breach_type: str,
    redis: Any,
    db: AsyncSession | None = None,
) -> None:
    """Notify supervisors and on-call PRIMARY about an SLA breach.

    Publishes a WebSocket event and sends push notifications.
    """
    event_data = {
        "event": "work_order.sla_breach",
        "work_order_id": str(wo.id),
        "human_readable_number": wo.human_readable_number,
        "breach_type": breach_type,
        "area_id": str(wo.area_id),
    }
    await _publish_ws(redis, wo.org_id, wo.area_id, event_data)

    if db is None:
        return

    supervisors = await _get_supervisors(db, wo.org_id, wo.area_id)
    primary_on_call = await _get_on_call_users(
        db, wo.org_id, wo.area_id, OnCallPriority.PRIMARY
    )

    # Merge and deduplicate
    seen_ids: set[uuid.UUID] = set()
    all_users: list[User] = []
    for u in supervisors + primary_on_call:
        if u.id not in seen_ids:
            seen_ids.add(u.id)
            all_users.append(u)

    await _send_push_to_users(
        all_users,
        title=f"SLA Breach: {wo.human_readable_number}",
        body=f"{breach_type} - {wo.title}",
        data={
            "type": "sla_breach",
            "work_order_id": str(wo.id),
            "breach_type": breach_type,
        },
    )


async def notify_message(
    wo: WorkOrder,
    sender: User,
    message: str,
    redis: Any,
    db: AsyncSession | None = None,
    recipient_id: uuid.UUID | None = None,
) -> None:
    """Notify about a new message on a work-order thread.

    Publishes a WebSocket event.  If a specific ``recipient_id`` is provided,
    push notification is sent to that user; otherwise to all area users.
    """
    event_data = {
        "event": "work_order.message",
        "work_order_id": str(wo.id),
        "human_readable_number": wo.human_readable_number,
        "sender_id": str(sender.id),
        "sender_name": sender.name,
        "message_preview": message[:200],
    }
    await _publish_ws(redis, wo.org_id, wo.area_id, event_data)

    if db is None:
        return

    if recipient_id is not None:
        # Send to specific recipient
        user_result = await db.execute(
            select(User).where(
                User.id == recipient_id,
                User.org_id == wo.org_id,
                User.is_active.is_(True),
            )
        )
        recipient = user_result.scalars().first()
        if recipient and recipient.fcm_token:
            await send_push_notification(
                recipient.fcm_token,
                title=f"Message on {wo.human_readable_number}",
                body=f"{sender.name}: {message[:100]}",
                data={
                    "type": "message",
                    "work_order_id": str(wo.id),
                },
            )
    else:
        # Notify all area users except the sender
        users = await _get_area_users_with_push(db, wo.org_id, wo.area_id)
        users = [u for u in users if u.id != sender.id]
        await _send_push_to_users(
            users,
            title=f"Message on {wo.human_readable_number}",
            body=f"{sender.name}: {message[:100]}",
            data={
                "type": "message",
                "work_order_id": str(wo.id),
            },
        )

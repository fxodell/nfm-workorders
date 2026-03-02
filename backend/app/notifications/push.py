"""Firebase Cloud Messaging push notification sender."""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


async def send_push(
    user_ids: list,
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
    db=None,
) -> dict:
    """Send push notifications to users via Firebase Cloud Messaging.

    Args:
        user_ids: List of user UUIDs to notify
        title: Notification title (include WO# and safety flag if applicable)
        body: Notification body text
        data: Optional data payload for the notification
        db: Database session to look up FCM tokens

    Returns:
        Dict with success_count, failure_count, failed_user_ids
    """
    from sqlalchemy import select
    from app.models.user import User

    if not db:
        return {"success_count": 0, "failure_count": 0, "failed_user_ids": list(user_ids)}

    result = await db.execute(
        select(User).where(
            User.id.in_(user_ids),
            User.fcm_token.isnot(None),
            User.is_active.is_(True),
        )
    )
    users = result.scalars().all()

    if not users:
        logger.info("No users with FCM tokens found for push notification")
        return {"success_count": 0, "failure_count": 0, "failed_user_ids": list(user_ids)}

    tokens = [u.fcm_token for u in users if u.fcm_token]
    if not tokens:
        return {"success_count": 0, "failure_count": 0, "failed_user_ids": list(user_ids)}

    success_count = 0
    failure_count = 0
    failed_user_ids = []
    stale_tokens = []

    try:
        from app.core.firebase import send_multicast_notification
        result = await send_multicast_notification(
            tokens=tokens,
            title=title,
            body=body,
            data=data or {},
        )
        if result:
            success_count = result.get("success_count", 0)
            failure_count = result.get("failure_count", 0)
            stale_tokens = result.get("failed_tokens", [])
    except Exception:
        logger.exception("FCM push failed, will fall back to email")
        failure_count = len(tokens)
        failed_user_ids = [u.id for u in users]

    # Clear stale tokens
    if stale_tokens:
        for user in users:
            if user.fcm_token in stale_tokens:
                user.fcm_token = None
                failed_user_ids.append(user.id)
        await db.flush()

    # Email fallback for failed pushes
    if failed_user_ids:
        from app.notifications.email import send_email_fallback
        await send_email_fallback(
            user_ids=failed_user_ids,
            title=title,
            body=body,
            db=db,
        )

    return {
        "success_count": success_count,
        "failure_count": failure_count,
        "failed_user_ids": failed_user_ids,
    }

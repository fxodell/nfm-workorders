"""
Firebase Admin SDK initialization for push notifications via FCM.

The SDK is initialized lazily from the ``FIREBASE_SERVICE_ACCOUNT_JSON``
environment variable. If the variable is empty or contains invalid JSON,
initialization is skipped and ``send_push_notification`` logs a warning
instead of raising.

This allows the application to run without Firebase in development while
requiring it in production via deployment checks.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import firebase_admin
from firebase_admin import credentials, messaging

from app.core.config import settings

logger = logging.getLogger(__name__)

_firebase_app: firebase_admin.App | None = None
_initialized = False


def _init_firebase() -> firebase_admin.App | None:
    """Initialize the Firebase Admin SDK from environment configuration.

    Returns the ``App`` instance or ``None`` if configuration is missing.
    This function is idempotent; subsequent calls return the cached result.
    """
    global _firebase_app, _initialized  # noqa: WPS420
    if _initialized:
        return _firebase_app

    _initialized = True
    raw = settings.FIREBASE_SERVICE_ACCOUNT_JSON
    if not raw or raw.strip() == "":
        logger.warning(
            "FIREBASE_SERVICE_ACCOUNT_JSON is not set; push notifications disabled"
        )
        return None

    try:
        service_account_info = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning(
            "FIREBASE_SERVICE_ACCOUNT_JSON contains invalid JSON; "
            "push notifications disabled"
        )
        return None

    # Guard against placeholder/example values
    if service_account_info.get("project_id", "").startswith("your-"):
        logger.warning(
            "FIREBASE_SERVICE_ACCOUNT_JSON contains placeholder values; "
            "push notifications disabled"
        )
        return None

    try:
        cred = credentials.Certificate(service_account_info)
        _firebase_app = firebase_admin.initialize_app(cred)
        logger.info("Firebase Admin SDK initialized successfully")
    except Exception:
        logger.exception("Failed to initialize Firebase Admin SDK")
        _firebase_app = None

    return _firebase_app


def get_firebase_app() -> firebase_admin.App | None:
    """Return the Firebase App instance, initializing on first call."""
    return _init_firebase()


async def send_push_notification(
    token: str,
    title: str,
    body: str,
    data: dict[str, str] | None = None,
) -> str | None:
    """Send a push notification via FCM.

    Parameters
    ----------
    token : str
        The device's FCM registration token.
    title : str
        Notification title (shown in the OS notification tray).
    body : str
        Notification body text.
    data : dict, optional
        Key-value pairs delivered as the notification's data payload.
        The frontend uses these for deep-linking and badge updates.

    Returns
    -------
    str or None
        The FCM message ID on success, or ``None`` if Firebase is not
        configured or the send fails.
    """
    app = get_firebase_app()
    if app is None:
        logger.warning(
            "Firebase not configured; skipping push notification to token=%s",
            token[:8] + "...",
        )
        return None

    message = messaging.Message(
        notification=messaging.Notification(title=title, body=body),
        data=data or {},
        token=token,
        android=messaging.AndroidConfig(
            priority="high",
            notification=messaging.AndroidNotification(
                channel_id="work_orders",
                priority="max",
            ),
        ),
        apns=messaging.APNSConfig(
            payload=messaging.APNSPayload(
                aps=messaging.Aps(
                    alert=messaging.ApsAlert(title=title, body=body),
                    sound="default",
                    badge=1,
                ),
            ),
        ),
    )

    try:
        response = messaging.send(message, app=app)
        logger.info("Push notification sent: message_id=%s", response)
        return response
    except messaging.UnregisteredError:
        logger.warning(
            "FCM token is unregistered (device uninstalled?): token=%s",
            token[:8] + "...",
        )
        return None
    except Exception:
        logger.exception("Failed to send push notification")
        return None


async def send_multicast_notification(
    tokens: list[str],
    title: str,
    body: str,
    data: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Send a push notification to multiple devices.

    Returns a summary dict with ``success_count``, ``failure_count``, and
    ``failed_tokens`` (tokens that should be removed from the database).
    """
    app = get_firebase_app()
    if app is None:
        logger.warning("Firebase not configured; skipping multicast notification")
        return {"success_count": 0, "failure_count": len(tokens), "failed_tokens": []}

    message = messaging.MulticastMessage(
        notification=messaging.Notification(title=title, body=body),
        data=data or {},
        tokens=tokens,
        android=messaging.AndroidConfig(priority="high"),
        apns=messaging.APNSConfig(
            payload=messaging.APNSPayload(
                aps=messaging.Aps(sound="default", badge=1),
            ),
        ),
    )

    try:
        response = messaging.send_each_for_multicast(message, app=app)
        failed_tokens = []
        for idx, send_response in enumerate(response.responses):
            if send_response.exception is not None:
                if isinstance(send_response.exception, messaging.UnregisteredError):
                    failed_tokens.append(tokens[idx])
        return {
            "success_count": response.success_count,
            "failure_count": response.failure_count,
            "failed_tokens": failed_tokens,
        }
    except Exception:
        logger.exception("Failed to send multicast notification")
        return {
            "success_count": 0,
            "failure_count": len(tokens),
            "failed_tokens": [],
        }

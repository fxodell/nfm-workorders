"""Email notification Celery tasks."""

import logging

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.email_tasks.send_push_notification")
def send_push_notification_task(
    user_ids: list[str],
    title: str,
    body: str,
    data: dict | None = None,
) -> dict:
    """Generic async push notification task."""
    import asyncio
    return asyncio.get_event_loop().run_until_complete(
        _send_push_async(user_ids, title, body, data)
    )


async def _send_push_async(user_ids, title, body, data):
    import uuid
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from app.core.config import settings
    from app.notifications.push import send_push

    engine = create_async_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        result = await send_push(
            user_ids=[uuid.UUID(uid) for uid in user_ids],
            title=title,
            body=body,
            data=data,
            db=db,
        )
        await db.commit()

    await engine.dispose()
    return result


@celery_app.task(name="app.workers.email_tasks.send_email_notification")
def send_email_notification_task(
    to_email: str,
    subject: str,
    body_html: str,
    action_url: str = "",
) -> bool:
    """Generic async email notification task."""
    import asyncio
    return asyncio.get_event_loop().run_until_complete(
        _send_email_async(to_email, subject, body_html, action_url)
    )


async def _send_email_async(to_email, subject, body_html, action_url):
    from app.notifications.email import send_email
    return await send_email(to_email, subject, body_html, action_url)

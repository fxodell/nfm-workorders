"""Email notification sender with SendGrid and stdout fallback."""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

EMAIL_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><style>
  body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
  .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; overflow: hidden; }}
  .header {{ background: #1e3a5f; color: white; padding: 20px; }}
  .body {{ padding: 20px; }}
  .safety {{ background: #fee2e2; border-left: 4px solid #dc2626; padding: 12px; margin: 12px 0; }}
  .btn {{ display: inline-block; background: #1e3a5f; color: white; padding: 12px 24px;
          text-decoration: none; border-radius: 4px; margin-top: 16px; }}
  .footer {{ padding: 12px 20px; background: #f5f5f5; font-size: 12px; color: #666; }}
</style></head>
<body>
<div class="container">
  <div class="header"><h2>{title}</h2></div>
  <div class="body">
    {body_html}
    <a href="{action_url}" class="btn">View Details</a>
  </div>
  <div class="footer">This is an automated notification from OilfieldMaint CMMS.</div>
</div>
</body>
</html>
"""


async def send_email(
    to_email: str,
    subject: str,
    body_html: str,
    action_url: str = "",
) -> bool:
    """Send an email via SendGrid or log to stdout in dev."""
    title = subject
    html_content = EMAIL_TEMPLATE.format(
        title=title,
        body_html=body_html,
        action_url=action_url or settings.FRONTEND_URL,
    )

    if settings.SENDGRID_API_KEY:
        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail

            message = Mail(
                from_email=settings.EMAIL_FROM,
                to_emails=to_email,
                subject=subject,
                html_content=html_content,
            )
            sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
            response = sg.send(message)
            logger.info("Email sent to %s, status=%s", to_email, response.status_code)
            return response.status_code in (200, 201, 202)
        except Exception:
            logger.exception("SendGrid email failed to %s", to_email)
            return False
    else:
        # Dev fallback: log to stdout
        logger.info(
            "EMAIL (dev stdout fallback):\n"
            "  To: %s\n  Subject: %s\n  Body: %s",
            to_email, subject, body_html[:200],
        )
        return True


async def send_email_fallback(
    user_ids: list,
    title: str,
    body: str,
    db=None,
) -> None:
    """Send email notifications as fallback when push fails."""
    if not db:
        return

    from sqlalchemy import select
    from app.models.user import User

    result = await db.execute(
        select(User).where(
            User.id.in_(user_ids),
            User.email_notifications_enabled.is_(True),
            User.is_active.is_(True),
        )
    )
    users = result.scalars().all()

    for user in users:
        await send_email(
            to_email=user.email,
            subject=title,
            body_html=f"<p>{body}</p>",
        )


async def send_escalation_email(
    user_ids: list,
    wo_number: str,
    site_name: str,
    priority: str,
    safety_flag: bool,
    safety_notes: str | None,
    db=None,
) -> None:
    """Send escalation email - ALWAYS fires for escalated events."""
    if not db:
        return

    from sqlalchemy import select
    from app.models.user import User

    result = await db.execute(
        select(User).where(
            User.id.in_(user_ids),
            User.is_active.is_(True),
        )
    )
    users = result.scalars().all()

    safety_prefix = "⚠ SAFETY - " if safety_flag else ""
    subject = f"{safety_prefix}ESCALATED: {wo_number} at {site_name} [{priority}]"

    safety_html = ""
    if safety_flag and safety_notes:
        safety_html = f'<div class="safety"><strong>⚠ Safety Hazard:</strong> {safety_notes}</div>'

    body_html = f"""
    <p>Work order <strong>{wo_number}</strong> has been <strong>ESCALATED</strong>.</p>
    <p><strong>Site:</strong> {site_name}<br>
    <strong>Priority:</strong> {priority}</p>
    {safety_html}
    <p>This work order has breached its SLA deadline and requires immediate attention.</p>
    """

    for user in users:
        await send_email(
            to_email=user.email,
            subject=subject,
            body_html=body_html,
            action_url=f"{settings.FRONTEND_URL}/work-orders",
        )

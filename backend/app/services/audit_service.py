"""Audit-log service: structured action logging and retrieval."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Log an action
# ---------------------------------------------------------------------------


async def log_action(
    db: AsyncSession,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    action: str,
    entity_type: str,
    entity_id: str,
    old_value: dict[str, Any] | None = None,
    new_value: dict[str, Any] | None = None,
) -> AuditLog:
    """Create an audit-log entry.

    Parameters
    ----------
    db : AsyncSession
        Active database session.
    org_id : UUID
        Organization scope.
    user_id : UUID
        The user performing the action.
    action : str
        Verb describing the action (e.g. ``"CREATE"``, ``"UPDATE"``,
        ``"DELETE"``, ``"STATUS_CHANGE"``, ``"LOGIN"``).
    entity_type : str
        The type of entity affected (e.g. ``"WorkOrder"``, ``"Part"``,
        ``"User"``).
    entity_id : str
        Identifier of the affected entity (typically the UUID as a string).
    old_value : dict, optional
        Snapshot of the entity before the change.
    new_value : dict, optional
        Snapshot of the entity after the change.

    Returns
    -------
    AuditLog
        The newly created audit-log row.
    """
    entry = AuditLog(
        org_id=org_id,
        actor_user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_value=old_value,
        new_value=new_value,
    )
    db.add(entry)
    await db.flush()

    logger.info(
        "Audit: user=%s action=%s entity=%s:%s org=%s",
        user_id,
        action,
        entity_type,
        entity_id,
        org_id,
    )
    return entry


# ---------------------------------------------------------------------------
# Query audit logs
# ---------------------------------------------------------------------------


async def get_audit_logs(
    db: AsyncSession,
    org_id: uuid.UUID,
    filters: dict[str, Any] | None = None,
    pagination: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Return a paginated, filtered list of audit-log entries.

    Filters may include:
        - ``user_id`` (UUID) -- filter by acting user
        - ``action`` (str) -- exact match on action verb
        - ``entity_type`` (str) -- exact match on entity type
        - ``entity_id`` (str) -- exact match on entity identifier
        - ``date_from`` (datetime) -- lower bound for ``created_at``
        - ``date_to`` (datetime) -- upper bound for ``created_at``
        - ``search`` (str) -- substring search across action and entity_type
        - ``sort_by`` (str, default "created_at")
        - ``sort_order`` ("asc" | "desc", default "desc")

    Pagination dict with ``page`` (1-indexed) and ``per_page``.
    """
    filters = filters or {}
    pagination = pagination or {}
    page = max(pagination.get("page", 1), 1)
    per_page = min(max(pagination.get("per_page", 20), 1), 100)

    conditions = [AuditLog.org_id == org_id]

    if "user_id" in filters and filters["user_id"] is not None:
        conditions.append(AuditLog.actor_user_id == filters["user_id"])

    if "action" in filters and filters["action"]:
        conditions.append(AuditLog.action == filters["action"])

    if "entity_type" in filters and filters["entity_type"]:
        conditions.append(AuditLog.entity_type == filters["entity_type"])

    if "entity_id" in filters and filters["entity_id"]:
        conditions.append(AuditLog.entity_id == filters["entity_id"])

    if "date_from" in filters and filters["date_from"] is not None:
        conditions.append(AuditLog.created_at >= filters["date_from"])

    if "date_to" in filters and filters["date_to"] is not None:
        conditions.append(AuditLog.created_at <= filters["date_to"])

    if "search" in filters and filters["search"]:
        search_term = f"%{filters['search']}%"
        conditions.append(
            AuditLog.action.ilike(search_term)
            | AuditLog.entity_type.ilike(search_term)
        )

    # Sorting
    sort_by = filters.get("sort_by", "created_at")
    sort_order = filters.get("sort_order", "desc")
    sort_column = getattr(AuditLog, sort_by, AuditLog.created_at)
    if sort_order == "asc":
        order_clause = sort_column.asc()
    else:
        order_clause = sort_column.desc()

    # Total count
    count_stmt = (
        select(func.count())
        .select_from(AuditLog)
        .where(and_(*conditions))
    )
    total = (await db.execute(count_stmt)).scalar() or 0

    # Fetch page
    offset = (page - 1) * per_page
    query = (
        select(AuditLog)
        .where(and_(*conditions))
        .order_by(order_clause)
        .offset(offset)
        .limit(per_page)
    )
    result = await db.execute(query)
    items = list(result.scalars().all())

    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
    }

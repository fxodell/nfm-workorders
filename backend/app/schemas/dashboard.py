"""Dashboard schemas."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.site import SiteType
from app.schemas.work_order import WOPriority


class SiteDashboard(BaseModel):
    """Per-site summary in the dashboard view."""

    model_config = ConfigDict(from_attributes=True)

    site_id: UUID
    site_name: str
    site_type: SiteType
    highest_priority: Optional[WOPriority] = None
    wo_count: int = 0
    escalated: bool = False
    safety_flag: bool = False
    waiting_on_ops: int = 0
    waiting_on_parts: int = 0
    assigned_techs: list[str] = []


class AreaDashboard(BaseModel):
    """Per-area summary in the dashboard view."""

    model_config = ConfigDict(from_attributes=True)

    area_id: UUID
    area_name: str
    priority_counts: dict[str, int] = {}
    escalated_count: int = 0
    safety_flag_count: int = 0
    sites: list[SiteDashboard] = []


class DashboardOverview(BaseModel):
    """Top-level dashboard overview aggregating all areas."""

    model_config = ConfigDict(from_attributes=True)

    areas: list[AreaDashboard] = []

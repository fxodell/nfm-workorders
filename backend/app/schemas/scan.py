"""QR-code scan response schemas."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class LocationScanResponse(BaseModel):
    """Response when a location QR code is scanned."""

    model_config = ConfigDict(from_attributes=True)

    location_id: UUID
    name: str
    area_id: UUID
    open_wo_count: int = 0


class SiteScanResponse(BaseModel):
    """Response when a site QR code is scanned."""

    model_config = ConfigDict(from_attributes=True)

    site_id: UUID
    name: str
    location_id: UUID
    open_wo_count: int = 0
    safety_flag_count: int = 0


class AssetScanResponse(BaseModel):
    """Response when an asset QR code is scanned."""

    model_config = ConfigDict(from_attributes=True)

    asset_id: UUID
    name: str
    site_id: UUID
    open_wo_count: int = 0


class PartScanResponse(BaseModel):
    """Response when a part barcode / QR code is scanned."""

    model_config = ConfigDict(from_attributes=True)

    part_id: UUID
    part_number: str
    description: Optional[str] = None
    stock_quantity: int = 0
    unit_cost: Optional[float] = None

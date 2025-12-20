"""BISHOP Module - Pydantic Schemas"""
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.bishop.models import BishopLocationType, BishopScanStatus, ShrinkageType


# ============ Location Schemas ============

class BishopLocationBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    location_type: BishopLocationType = BishopLocationType.RESTAURANT
    address: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    vendor_config: dict[str, Any] | None = None
    daily_order_limit: float | None = None
    auto_order_enabled: bool = False


class BishopLocationCreate(BishopLocationBase):
    pass


class BishopLocationUpdate(BaseModel):
    name: str | None = None
    location_type: BishopLocationType | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    vendor_config: dict[str, Any] | None = None
    daily_order_limit: float | None = None
    auto_order_enabled: bool | None = None


class BishopLocationResponse(BishopLocationBase):
    id: UUID
    owner_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============ Shelf Schemas ============

class BishopShelfBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    shelf_code: str | None = None
    zone: str | None = None
    expected_inventory: dict[str, Any] | None = None


class BishopShelfCreate(BishopShelfBase):
    location_id: UUID


class BishopShelfResponse(BishopShelfBase):
    id: UUID
    location_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


# ============ Item Schemas ============

class BishopItemBase(BaseModel):
    sku: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    quantity_on_hand: int = 0
    quantity_unit: str | None = None
    par_level: int | None = None
    reorder_point: int | None = None
    vendor_sku: str | None = None
    vendor_name: str | None = None
    unit_cost: float | None = None
    is_perishable: bool = False
    shelf_life_days: int | None = None


class BishopItemCreate(BishopItemBase):
    shelf_id: UUID


class BishopItemUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    quantity_on_hand: int | None = None
    quantity_unit: str | None = None
    par_level: int | None = None
    reorder_point: int | None = None
    vendor_sku: str | None = None
    vendor_name: str | None = None
    unit_cost: float | None = None
    is_perishable: bool | None = None
    shelf_life_days: int | None = None


class BishopItemResponse(BishopItemBase):
    id: UUID
    shelf_id: UUID
    last_scanned_at: datetime | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============ Scan Schemas ============

class BishopScanCreate(BaseModel):
    location_id: UUID
    shelf_id: UUID | None = None
    image_url: str | None = None


class BishopScanResponse(BaseModel):
    id: UUID
    location_id: UUID
    shelf_id: UUID | None
    scanned_by_id: UUID | None
    status: BishopScanStatus
    image_url: str | None
    image_hash: str | None
    ai_detected_items: dict[str, Any] | None
    discrepancies: dict[str, Any] | None
    risk_score: float | None
    suggested_order: dict[str, Any] | None
    order_total: float | None
    order_approved: bool | None
    started_at: datetime
    completed_at: datetime | None

    class Config:
        from_attributes = True


# ============ Shrinkage Schemas ============

class ShrinkageEventCreate(BaseModel):
    location_id: UUID
    item_id: UUID | None = None
    scan_id: UUID | None = None
    shrinkage_type: ShrinkageType = ShrinkageType.UNKNOWN
    sku: str | None = None
    item_name: str | None = None
    quantity_lost: int
    unit_cost: float | None = None
    notes: str | None = None
    evidence_url: str | None = None


class ShrinkageEventResponse(BaseModel):
    id: UUID
    location_id: UUID
    item_id: UUID | None
    scan_id: UUID | None
    shrinkage_type: ShrinkageType
    sku: str | None
    item_name: str | None
    quantity_lost: int
    unit_cost: float | None
    total_loss_value: float | None
    notes: str | None
    evidence_url: str | None
    detected_at: datetime
    resolved: bool
    resolved_at: datetime | None

    class Config:
        from_attributes = True


class ShrinkageReport(BaseModel):
    """Aggregated shrinkage report for a location."""
    location_id: UUID
    period_start: datetime
    period_end: datetime
    total_events: int
    total_loss_value: float
    by_type: dict[str, float]  # ShrinkageType -> total value
    top_items: list[dict[str, Any]]  # Top shrinkage items

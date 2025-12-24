"""
PROVENIQ Ops - Predictive Stockout Schemas
Bishop foresight engine data contracts

RULE: No floats for money/quantities. Use MoneyMicros/Quantity/Rate.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from app.core.types import MoneyMicros, Quantity, IntQuantity, Rate


class AlertType(str, Enum):
    """Stockout alert classification."""
    PREDICTIVE_STOCKOUT = "PREDICTIVE_STOCKOUT"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class AlertSeverity(str, Enum):
    """Alert urgency levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ReorderRecommendation(BaseModel):
    """Pre-built reorder action from Bishop."""
    vendor_id: uuid.UUID
    vendor_name: str
    reorder_qty: IntQuantity = Field(..., gt=0)
    estimated_cost_micros: MoneyMicros = Field(..., gt=0)
    lead_time_hours: int
    requires_approval: bool = True


class StockoutAlert(BaseModel):
    """
    Bishop predictive stockout alert.
    Deterministic output schema - no free-form text.
    """
    alert_type: AlertType
    severity: AlertSeverity
    product_id: uuid.UUID
    product_name: str
    current_on_hand: IntQuantity
    safety_stock: IntQuantity
    projected_hours_to_stockout: Quantity  # Decimal, not float
    confidence: Rate = Field(..., ge=0, le=1)
    recommended_action: Optional[ReorderRecommendation] = None
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "alert_type": "PREDICTIVE_STOCKOUT",
                "severity": "high",
                "product_id": "550e8400-e29b-41d4-a716-446655440000",
                "product_name": "Chicken Breast 5lb",
                "current_on_hand": 12,
                "safety_stock": 20,
                "projected_hours_to_stockout": 36,
                "confidence": 0.87,
                "recommended_action": {
                    "vendor_id": "550e8400-e29b-41d4-a716-446655440001",
                    "vendor_name": "Sysco",
                    "reorder_qty": 50,
                    "estimated_cost": "127.50",
                    "lead_time_hours": 24,
                    "requires_approval": True
                }
            }
        }


class InventoryLevel(BaseModel):
    """Current inventory state for a product."""
    product_id: uuid.UUID
    on_hand_qty: IntQuantity = Field(..., ge=0)
    safety_stock: IntQuantity = Field(0, ge=0)
    location_id: Optional[str] = None


class ScanEvent(BaseModel):
    """Individual scan event for burn rate calculation."""
    product_id: uuid.UUID
    qty_delta: int  # negative = consumption, positive = receiving (int OK for delta)
    timestamp: datetime
    location_id: Optional[str] = None
    scan_type: str = "consumption"  # consumption, receiving, adjustment


class HistoricalUsage(BaseModel):
    """Aggregated usage statistics for a product."""
    product_id: uuid.UUID
    avg_daily_burn_7d: Quantity = Field(..., ge=0)  # Decimal, not float
    avg_daily_burn_30d: Quantity = Field(..., ge=0)
    avg_daily_burn_90d: Quantity = Field(..., ge=0)
    variance_coefficient: Quantity = Field(default=Decimal("0"), ge=0)  # demand volatility
    last_calculated: datetime = Field(default_factory=datetime.utcnow)


class VendorLeadTime(BaseModel):
    """Vendor-specific lead time for a product."""
    product_id: uuid.UUID
    vendor_id: uuid.UUID
    vendor_name: str
    avg_lead_time_hours: int = Field(..., ge=0)
    reliability_score: Rate = Field(default=Decimal("1"), ge=0, le=1)  # historical on-time %


class OpenPurchaseOrder(BaseModel):
    """Pending PO that affects projected inventory."""
    order_id: uuid.UUID
    product_id: uuid.UUID
    vendor_id: uuid.UUID
    qty_ordered: IntQuantity = Field(..., gt=0)
    expected_delivery: datetime
    status: str = "pending"  # pending, shipped, delayed


class StockoutPredictionRequest(BaseModel):
    """Request to analyze stockout risk for products."""
    product_ids: Optional[list[uuid.UUID]] = None  # None = all products
    include_open_pos: bool = True
    safety_buffer_hours: int = Field(24, ge=0)  # extra buffer beyond lead time


class StockoutPredictionResponse(BaseModel):
    """Response containing all stockout predictions."""
    alerts: list[StockoutAlert]
    products_analyzed: int
    alerts_generated: int
    analysis_timestamp: datetime = Field(default_factory=datetime.utcnow)

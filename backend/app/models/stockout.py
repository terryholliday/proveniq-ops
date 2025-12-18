"""
PROVENIQ Ops - Predictive Stockout Schemas
Bishop foresight engine data contracts
"""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


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
    reorder_qty: int = Field(..., gt=0)
    estimated_cost: Decimal = Field(..., gt=0)
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
    current_on_hand: int
    safety_stock: int
    projected_hours_to_stockout: float
    confidence: float = Field(..., ge=0.0, le=1.0)
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
    on_hand_qty: int = Field(..., ge=0)
    safety_stock: int = Field(0, ge=0)
    location_id: Optional[str] = None


class ScanEvent(BaseModel):
    """Individual scan event for burn rate calculation."""
    product_id: uuid.UUID
    qty_delta: int  # negative = consumption, positive = receiving
    timestamp: datetime
    location_id: Optional[str] = None
    scan_type: str = "consumption"  # consumption, receiving, adjustment


class HistoricalUsage(BaseModel):
    """Aggregated usage statistics for a product."""
    product_id: uuid.UUID
    avg_daily_burn_7d: float = Field(..., ge=0)
    avg_daily_burn_30d: float = Field(..., ge=0)
    avg_daily_burn_90d: float = Field(..., ge=0)
    variance_coefficient: float = Field(0.0, ge=0)  # demand volatility
    last_calculated: datetime = Field(default_factory=datetime.utcnow)


class VendorLeadTime(BaseModel):
    """Vendor-specific lead time for a product."""
    product_id: uuid.UUID
    vendor_id: uuid.UUID
    vendor_name: str
    avg_lead_time_hours: int = Field(..., ge=0)
    reliability_score: float = Field(1.0, ge=0, le=1)  # historical on-time %


class OpenPurchaseOrder(BaseModel):
    """Pending PO that affects projected inventory."""
    order_id: uuid.UUID
    product_id: uuid.UUID
    vendor_id: uuid.UUID
    qty_ordered: int = Field(..., gt=0)
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

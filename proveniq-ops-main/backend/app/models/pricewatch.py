"""
PROVENIQ Ops - Vendor Price Watch Schemas
Bishop price arbitrage detection data contracts

RULE: No floats for money. Use MoneyMicros.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from app.core.types import MoneyMicros, Quantity, Rate


class PriceAlertType(str, Enum):
    """Price alert classifications."""
    VENDOR_PRICE_VARIANCE = "VENDOR_PRICE_VARIANCE"
    PRICE_SPIKE = "PRICE_SPIKE"
    PRICE_DROP = "PRICE_DROP"
    CONTRACT_DEVIATION = "CONTRACT_DEVIATION"


class ActionPrompt(str, Enum):
    """Suggested actions for price alerts."""
    SWITCH_VENDOR = "SWITCH_VENDOR?"
    RENEGOTIATE = "RENEGOTIATE?"
    LOCK_PRICE = "LOCK_PRICE?"
    MONITOR = "MONITOR"
    NO_ACTION = "NO_ACTION"


class ContractStatus(str, Enum):
    """Vendor contract status."""
    ACTIVE = "active"
    EXPIRED = "expired"
    LOCKED = "locked"  # Cannot switch
    NEGOTIATING = "negotiating"


# =============================================================================
# PRICE DATA MODELS
# =============================================================================

class VendorPriceFeed(BaseModel):
    """Price feed from a vendor."""
    vendor_id: uuid.UUID
    vendor_name: str
    vendor_sku: str
    canonical_sku: str
    price_micros: MoneyMicros
    currency: str = "USD"
    unit_of_measure: str  # each, lb, case, etc.
    min_order_qty: int = 1
    stock_available: Optional[int] = None
    lead_time_hours: Optional[int] = None
    effective_date: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None


class ActiveContract(BaseModel):
    """Active vendor contract."""
    contract_id: uuid.UUID
    vendor_id: uuid.UUID
    vendor_name: str
    product_id: uuid.UUID
    canonical_sku: str
    contracted_price_micros: MoneyMicros
    volume_commitment: Optional[int] = None
    start_date: datetime
    end_date: datetime
    status: ContractStatus = ContractStatus.ACTIVE
    is_locked: bool = False  # Cannot switch even if cheaper
    lock_reason: Optional[str] = None
    rebate_percent: Optional[Quantity] = None


class SKUMapping(BaseModel):
    """SKU normalization mapping."""
    canonical_sku: str
    product_id: uuid.UUID
    product_name: str
    category: str
    vendor_mappings: list[dict] = Field(default_factory=list)
    # Each mapping: {vendor_id, vendor_sku, vendor_name}


class HistoricalPrice(BaseModel):
    """Historical price point for trend analysis."""
    canonical_sku: str
    vendor_id: uuid.UUID
    price_micros: MoneyMicros
    recorded_at: datetime
    source: str = "feed"  # feed, invoice, manual


# =============================================================================
# ALERT MODELS
# =============================================================================

class CheaperAlternative(BaseModel):
    """Cheaper vendor alternative."""
    vendor_id: uuid.UUID
    vendor_name: str
    vendor_sku: str
    price_micros: MoneyMicros
    savings_micros: MoneyMicros
    savings_percent: Quantity
    lead_time_hours: Optional[int] = None
    stock_available: Optional[int] = None
    reliability_score: Optional[Quantity] = None


class VendorPriceAlert(BaseModel):
    """
    Bishop vendor price variance alert.
    Deterministic output schema.
    """
    alert_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    alert_type: PriceAlertType
    
    # SKU info
    canonical_sku: str
    product_id: uuid.UUID
    product_name: str
    
    # Current vendor
    current_vendor_id: uuid.UUID
    current_vendor_name: str
    current_price_micros: MoneyMicros
    
    # Price delta
    price_delta_micros: MoneyMicros  # Can be negative
    price_delta_percent: Quantity
    
    # Alternative
    cheaper_alternative: Optional[CheaperAlternative] = None
    
    # Contract context
    contract_id: Optional[uuid.UUID] = None
    contract_locked: bool = False
    contract_end_date: Optional[datetime] = None
    
    # Recommendation
    action_prompt: ActionPrompt
    confidence: Rate
    reason_codes: list[str] = []
    
    # Estimated impact
    annual_volume: Optional[int] = None
    annual_savings_micros: Optional[MoneyMicros] = None
    
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "alert_type": "VENDOR_PRICE_VARIANCE",
                "canonical_sku": "CHK-BRST-5LB",
                "product_name": "Chicken Breast 5lb",
                "current_vendor_name": "Sysco",
                "current_price_micros": 12500000,
                "price_delta_percent": "15.2",
                "cheaper_alternative": {
                    "vendor_name": "US Foods",
                    "price_micros": 10850000,
                    "savings_percent": "13.2"
                },
                "action_prompt": "SWITCH_VENDOR?",
                "confidence": "0.85"
            }
        }


class PriceWatchConfig(BaseModel):
    """Configuration for price watch engine."""
    alert_threshold_percent: Quantity = Field(default=Decimal("5.0"))  # Alert if >5% variance
    spike_threshold_percent: Quantity = Field(default=Decimal("10.0"))  # Price spike alert
    rolling_window_days: int = Field(default=30)
    min_samples_for_trend: int = Field(default=5)
    ignore_locked_contracts: bool = Field(default=True)
    auto_switch_enabled: bool = Field(default=False)  # GUARDRAIL: Default false


class PriceWatchSummary(BaseModel):
    """Summary of price watch analysis."""
    analysis_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Counts
    skus_analyzed: int
    vendors_compared: int
    alerts_generated: int
    
    # Opportunities
    total_savings_available_micros: MoneyMicros
    switch_opportunities: int
    locked_opportunities: int  # Savings blocked by locked contracts
    
    # Alerts by type
    alerts_by_type: dict[str, int] = Field(default_factory=dict)
    
    # Top opportunities
    top_savings: list[VendorPriceAlert] = []

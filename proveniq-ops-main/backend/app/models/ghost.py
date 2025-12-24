"""
PROVENIQ Ops - Ghost Inventory Schemas
Bishop shrinkage detection data contracts

DAG Node: N12

GUARDRAILS:
- Do not accuse users
- This is a loss-signal, not a disciplinary tool
"""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from app.core.types import MoneyMicros, IntQuantity, Quantity, Rate


class GhostAlertType(str, Enum):
    """Ghost inventory alert classifications."""
    GHOST_INVENTORY = "GHOST_INVENTORY"
    UNSCANNED_WINDOW = "UNSCANNED_WINDOW"
    VARIANCE_DETECTED = "VARIANCE_DETECTED"
    LOCATION_DISCREPANCY = "LOCATION_DISCREPANCY"


class RecommendedAction(str, Enum):
    """Recommended actions for ghost alerts."""
    PHYSICAL_AUDIT = "PHYSICAL_AUDIT"
    LOCATION_CHECK = "LOCATION_CHECK"
    CYCLE_COUNT = "CYCLE_COUNT"
    INVESTIGATE = "INVESTIGATE"
    MONITOR = "MONITOR"
    NO_ACTION = "NO_ACTION"


class RiskLevel(str, Enum):
    """Risk level for ghost inventory."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# =============================================================================
# INVENTORY DATA MODELS
# =============================================================================

class InventoryRecord(BaseModel):
    """System inventory record."""
    product_id: uuid.UUID
    product_name: str
    canonical_sku: str
    location_id: uuid.UUID
    location_name: str
    system_qty: IntQuantity  # What system says we have
    unit_cost_micros: MoneyMicros
    category: str = "general"
    is_high_value: bool = False
    is_controlled: bool = False


class ScanRecord(BaseModel):
    """Individual scan event."""
    scan_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    product_id: uuid.UUID
    location_id: uuid.UUID
    scanned_qty: IntQuantity
    scanned_at: datetime
    scanned_by: str
    scan_type: str = "cycle_count"  # cycle_count, receiving, consumption


class ProductScanHistory(BaseModel):
    """Scan history for a product at a location."""
    product_id: uuid.UUID
    location_id: uuid.UUID
    last_scanned_at: Optional[datetime] = None
    last_scanned_qty: Optional[IntQuantity] = None
    scan_count_30d: int = 0
    avg_days_between_scans: Optional[Quantity] = None


# =============================================================================
# GHOST DETECTION MODELS
# =============================================================================

class GhostItem(BaseModel):
    """Individual item flagged as potential ghost inventory."""
    product_id: uuid.UUID
    product_name: str
    canonical_sku: str
    location_id: uuid.UUID
    location_name: str
    
    # System vs Reality
    system_qty: IntQuantity
    last_scanned_qty: Optional[IntQuantity] = None
    variance_qty: Optional[int] = None  # Positive = system has more than scanned
    
    # Time since last scan
    last_scanned_at: Optional[datetime] = None
    days_since_scan: int
    
    # Financial exposure
    unit_cost_micros: MoneyMicros
    exposure_value_micros: MoneyMicros  # system_qty * unit_cost
    variance_value_micros: Optional[MoneyMicros] = None
    
    # Risk factors
    risk_level: RiskLevel
    risk_factors: list[str] = []
    
    # Context (not accusations)
    possible_causes: list[str] = []


class GhostInventoryAlert(BaseModel):
    """
    Bishop ghost inventory alert.
    Deterministic output - no accusations.
    """
    alert_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    alert_type: GhostAlertType = GhostAlertType.GHOST_INVENTORY
    
    # Summary
    items_flagged: int
    days_unscanned_threshold: int
    
    # Financial
    total_system_value_micros: MoneyMicros
    total_variance_value_micros: MoneyMicros
    total_exposure_value_micros: MoneyMicros
    
    # Breakdown by risk
    critical_items: int = 0
    high_risk_items: int = 0
    medium_risk_items: int = 0
    low_risk_items: int = 0
    
    # Flagged items (sorted by exposure)
    flagged_items: list[GhostItem] = []
    
    # Recommendation
    recommended_action: RecommendedAction
    confidence: Rate
    
    # Context
    analysis_scope: str  # all, location, category
    locations_analyzed: int
    products_analyzed: int
    
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "alert_type": "GHOST_INVENTORY",
                "items_flagged": 12,
                "days_unscanned_threshold": 14,
                "total_variance_value_micros": 4523000000,
                "recommended_action": "PHYSICAL_AUDIT",
                "confidence": "0.82"
            }
        }


# =============================================================================
# CONFIGURATION
# =============================================================================

class GhostDetectorConfig(BaseModel):
    """Configuration for ghost inventory detection."""
    unscanned_threshold_days: int = Field(default=14, ge=1)
    high_value_threshold_micros: MoneyMicros = Field(default=50_000_000)  # $50
    critical_exposure_threshold_micros: MoneyMicros = Field(default=500_000_000)  # $500
    
    # Risk weights
    weight_days_unscanned: Quantity = Field(default=Decimal("0.3"))
    weight_value: Quantity = Field(default=Decimal("0.3"))
    weight_variance: Quantity = Field(default=Decimal("0.4"))
    
    # Filters
    include_controlled_items: bool = True
    include_low_value_items: bool = True
    min_system_qty: int = 1


class GhostDetectorSummary(BaseModel):
    """Summary of ghost detection analysis."""
    analysis_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Scope
    config: GhostDetectorConfig
    locations_analyzed: int
    products_analyzed: int
    
    # Results
    total_flagged: int
    total_exposure_micros: MoneyMicros
    total_variance_micros: MoneyMicros
    
    # By category
    flagged_by_category: dict[str, int] = Field(default_factory=dict)
    exposure_by_category: dict[str, int] = Field(default_factory=dict)
    
    # By location
    flagged_by_location: dict[str, int] = Field(default_factory=dict)
    
    # Top exposures
    top_exposures: list[GhostItem] = []
    
    # Possible causes (system-level, not accusations)
    common_patterns: list[str] = []

"""
PROVENIQ Ops - Salvage Bridge Schemas
Bishop asset disposition data contracts

Identify assets suitable for transfer, donation, or liquidation.
"""

import uuid
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from app.core.types import MoneyMicros, Quantity, Rate


class DispositionPath(str, Enum):
    """Recommended disposition paths."""
    TRANSFER = "transfer"       # Move to another location
    DONATE = "donate"           # Food bank / charity
    LIQUIDATE = "liquidate"     # Sell at discount
    REPURPOSE = "repurpose"     # Use in different menu item
    HOLD = "hold"               # Keep - still viable
    DISPOSE = "dispose"         # Waste - no recovery


class OverstockReason(str, Enum):
    """Reasons for overstock."""
    DEMAND_DROP = "demand_drop"
    OVER_ORDER = "over_order"
    MENU_CHANGE = "menu_change"
    SEASONAL_END = "seasonal_end"
    VENDOR_ERROR = "vendor_error"
    FORECAST_MISS = "forecast_miss"


class AssetCondition(str, Enum):
    """Condition of salvageable asset."""
    EXCELLENT = "excellent"     # Full shelf life remaining
    GOOD = "good"               # >50% shelf life
    FAIR = "fair"               # 25-50% shelf life
    POOR = "poor"               # <25% shelf life, still usable
    CRITICAL = "critical"       # Must act immediately


class RecoveryConfidence(str, Enum):
    """Confidence in recovery estimate."""
    HIGH = "high"               # 80%+ likely
    MEDIUM = "medium"           # 50-80% likely
    LOW = "low"                 # <50% likely
    SPECULATIVE = "speculative" # Best effort estimate


# =============================================================================
# INPUT MODELS
# =============================================================================

class OverstockFlag(BaseModel):
    """Flag indicating overstock situation."""
    flag_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    
    # Item
    item_id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    
    # Overstock details
    current_qty: Quantity
    par_qty: Quantity
    excess_qty: Quantity
    unit: str
    
    # Reason
    reason: OverstockReason
    
    # Value
    unit_cost_micros: MoneyMicros
    total_value_micros: MoneyMicros
    
    # Location
    location_id: uuid.UUID
    location_name: str
    
    # Timing
    flagged_at: datetime = Field(default_factory=datetime.utcnow)
    days_overstocked: int = 0


class ExpirationWindow(BaseModel):
    """Expiration window for an item."""
    item_id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    
    # Quantity
    quantity: Quantity
    unit: str
    
    # Expiration
    expiration_date: date
    days_until_expiry: int
    
    # Condition
    condition: AssetCondition
    
    # Value
    current_value_micros: MoneyMicros
    
    # Location
    location_id: uuid.UUID
    location_name: str


class NetworkLocation(BaseModel):
    """A location in the network that might accept transfers."""
    location_id: uuid.UUID
    location_name: str
    
    # Demand
    needs_product: bool = False
    current_inventory: Quantity = Decimal("0")
    daily_demand: Quantity = Decimal("0")
    days_of_supply: Decimal = Decimal("0")
    
    # Capacity
    can_accept: bool = True
    max_accept_qty: Optional[Quantity] = None
    
    # Distance/cost
    transfer_cost_micros: MoneyMicros = 0
    transfer_hours: int = 0


class NetworkInventory(BaseModel):
    """Network-wide inventory view for a product."""
    product_id: uuid.UUID
    product_name: str
    
    # Network totals
    total_network_qty: Quantity
    total_network_demand: Quantity
    
    # Locations
    locations: list[NetworkLocation] = []
    
    # Transfer opportunities
    surplus_locations: list[uuid.UUID] = []
    deficit_locations: list[uuid.UUID] = []


# =============================================================================
# DISPOSITION OPTIONS
# =============================================================================

class TransferOption(BaseModel):
    """Transfer to another location."""
    target_location_id: uuid.UUID
    target_location_name: str
    
    # Quantity
    transfer_qty: Quantity
    unit: str
    
    # Economics
    transfer_cost_micros: MoneyMicros
    value_retained_micros: MoneyMicros
    net_recovery_micros: MoneyMicros
    
    # Logistics
    transfer_hours: int
    feasible: bool = True
    
    # Why this location
    reason: str


class DonationOption(BaseModel):
    """Donation to food bank or charity."""
    recipient_type: str  # "food_bank", "shelter", "school", etc.
    recipient_name: Optional[str] = None
    
    # Quantity
    donate_qty: Quantity
    unit: str
    
    # Value
    fair_market_value_micros: MoneyMicros
    tax_deduction_estimate_micros: MoneyMicros
    net_recovery_micros: MoneyMicros  # Tax benefit
    
    # Logistics
    pickup_available: bool = True
    donation_hours: int = 0
    
    # Eligibility
    eligible: bool = True
    ineligibility_reason: Optional[str] = None


class LiquidationOption(BaseModel):
    """Sell at discount."""
    channel: str  # "employee_sale", "discount_shelf", "liquidator", etc.
    
    # Quantity
    liquidate_qty: Quantity
    unit: str
    
    # Pricing
    original_value_micros: MoneyMicros
    liquidation_price_micros: MoneyMicros
    discount_pct: Rate
    
    # Recovery
    net_recovery_micros: MoneyMicros
    recovery_rate_pct: Rate
    
    # Timing
    sale_window_hours: int = 24


class RepurposeOption(BaseModel):
    """Repurpose for different use."""
    new_use: str  # "staff_meal", "special_menu", "prep_ingredient", etc.
    
    # Quantity
    repurpose_qty: Quantity
    unit: str
    
    # Value
    original_value_micros: MoneyMicros
    repurposed_value_micros: MoneyMicros
    
    # Recovery
    net_recovery_micros: MoneyMicros
    
    # Feasibility
    feasible: bool = True
    recipe_id: Optional[uuid.UUID] = None


# =============================================================================
# SALVAGE RECOMMENDATION
# =============================================================================

class DispositionRanking(BaseModel):
    """Ranked disposition option."""
    rank: int
    path: DispositionPath
    
    # Recovery
    estimated_recovery_micros: MoneyMicros
    recovery_rate_pct: Rate
    
    # Confidence
    confidence: RecoveryConfidence
    
    # Details
    details: Optional[dict] = None
    
    # Why this rank
    reasoning: str


class SalvageRecommendation(BaseModel):
    """
    Complete salvage recommendation for an item.
    The main output of the engine.
    """
    recommendation_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    recommended_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Item
    item_id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    
    # Current state
    quantity: Quantity
    unit: str
    condition: AssetCondition
    days_until_expiry: Optional[int] = None
    
    # Original value
    original_value_micros: MoneyMicros
    
    # Recommendation
    recommended_path: DispositionPath
    estimated_recovery_micros: MoneyMicros
    estimated_recovery: Decimal  # In dollars
    recovery_rate_pct: Rate
    
    # All options ranked
    ranked_options: list[DispositionRanking] = []
    
    # Best transfer target (if applicable)
    transfer_target: Optional[TransferOption] = None
    
    # Best donation option (if applicable)
    donation_option: Optional[DonationOption] = None
    
    # Best liquidation option (if applicable)
    liquidation_option: Optional[LiquidationOption] = None
    
    # Urgency
    action_deadline: Optional[datetime] = None
    urgency_hours: int = 0
    
    # Reasoning
    reasoning: str


class BatchSalvageResult(BaseModel):
    """Results for batch salvage analysis."""
    batch_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Summary
    items_analyzed: int
    total_at_risk_value_micros: MoneyMicros
    total_estimated_recovery_micros: MoneyMicros
    overall_recovery_rate_pct: Rate
    
    # By path
    transfer_count: int = 0
    donate_count: int = 0
    liquidate_count: int = 0
    repurpose_count: int = 0
    dispose_count: int = 0
    
    # Recommendations
    recommendations: list[SalvageRecommendation] = []
    
    # Urgent items
    urgent_items: list[uuid.UUID] = []


# =============================================================================
# CONFIGURATION
# =============================================================================

class SalvageConfig(BaseModel):
    """Configuration for salvage bridge."""
    # Recovery thresholds
    min_transfer_recovery_pct: Rate = Decimal("70")  # Only transfer if >70% recovery
    min_liquidation_recovery_pct: Rate = Decimal("20")  # Min 20% for liquidation
    
    # Donation settings
    donation_tax_rate: Rate = Decimal("0.25")  # 25% tax deduction value
    min_days_for_donation: int = 2  # Need 2+ days shelf life
    
    # Transfer settings
    max_transfer_hours: int = 24
    max_transfer_cost_pct: Rate = Decimal("15")  # Max 15% of value for transfer
    
    # Condition thresholds
    excellent_days_remaining: int = 14
    good_days_remaining: int = 7
    fair_days_remaining: int = 3
    poor_days_remaining: int = 1
    
    # Priority weights
    weight_recovery: Rate = Decimal("0.50")
    weight_speed: Rate = Decimal("0.30")
    weight_simplicity: Rate = Decimal("0.20")

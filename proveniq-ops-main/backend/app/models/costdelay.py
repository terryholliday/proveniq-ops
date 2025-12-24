"""
PROVENIQ Ops - Cost of Delay Calculator Schemas
Bishop financial impact quantification data contracts

Quantifies the financial impact of inaction.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, Any

from pydantic import BaseModel, Field

from app.core.types import MoneyMicros, Quantity, Rate


class DelayReason(str, Enum):
    """Reasons for delaying an order."""
    LIQUIDITY_CONSTRAINT = "liquidity_constraint"
    VENDOR_UNAVAILABLE = "vendor_unavailable"
    DEMAND_UNCERTAINTY = "demand_uncertainty"
    PRICE_NEGOTIATION = "price_negotiation"
    INVENTORY_SUFFICIENT = "inventory_sufficient"
    BATCH_CONSOLIDATION = "batch_consolidation"
    MANUAL_HOLD = "manual_hold"


class RiskType(str, Enum):
    """Types of downstream risk from delay."""
    STOCKOUT = "stockout"
    LOST_SALES = "lost_sales"
    EXPEDITED_SHIPPING = "expedited_shipping"
    EMERGENCY_VENDOR = "emergency_vendor"
    WASTE_INCREASE = "waste_increase"
    MARGIN_EROSION = "margin_erosion"
    CUSTOMER_IMPACT = "customer_impact"


class DelayRecommendation(str, Enum):
    """Recommendation based on cost analysis."""
    PROCEED_NOW = "proceed_now"          # Delay cost exceeds savings
    DELAY_SAFE = "delay_safe"            # Safe to delay
    DELAY_RISKY = "delay_risky"          # Can delay but watch closely
    DELAY_PARTIAL = "delay_partial"      # Split the order
    EXPEDITE = "expedite"                # Already delayed too long


# =============================================================================
# INPUT MODELS
# =============================================================================

class PendingOrder(BaseModel):
    """A pending order that could be delayed."""
    order_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    
    # Order details
    vendor_id: uuid.UUID
    vendor_name: str
    
    # Items
    items: list[dict[str, Any]] = Field(default_factory=list)  # product_id, qty, unit_cost
    total_cost_micros: MoneyMicros
    
    # Timing
    created_at: datetime = Field(default_factory=datetime.utcnow)
    original_delivery_date: Optional[datetime] = None
    
    # Priority
    priority: str = "normal"  # critical, high, normal, low
    
    # Current status
    is_delayed: bool = False
    delay_hours: int = 0


class DemandForecastItem(BaseModel):
    """Demand forecast for a single product."""
    product_id: uuid.UUID
    product_name: str
    
    # Current state
    current_inventory: Quantity
    unit: str
    
    # Forecast
    daily_demand: Quantity
    demand_confidence: Rate = Decimal("0.80")
    
    # Risk
    days_of_supply: Quantity
    stockout_risk_pct: Rate = Decimal("0")


class WasteRiskItem(BaseModel):
    """Waste risk for a product."""
    product_id: uuid.UUID
    product_name: str
    
    # Current state
    quantity_at_risk: Quantity
    unit: str
    
    # Expiration
    expires_at: Optional[datetime] = None
    days_until_expiry: int = 0
    
    # Value
    value_at_risk_micros: MoneyMicros = 0
    waste_probability_pct: Rate = Decimal("0")


class LiquidityState(BaseModel):
    """Current liquidity state."""
    cash_balance_micros: MoneyMicros
    available_balance_micros: MoneyMicros
    
    # Obligations
    obligations_24h_micros: MoneyMicros = 0
    obligations_48h_micros: MoneyMicros = 0
    obligations_7d_micros: MoneyMicros = 0
    
    # Runway
    daily_burn_rate_micros: MoneyMicros = 0
    days_of_runway: Decimal = Decimal("30")
    
    # Thresholds
    minimum_reserve_micros: MoneyMicros = 0
    is_constrained: bool = False


# =============================================================================
# COST BREAKDOWN
# =============================================================================

class DelaySavings(BaseModel):
    """Savings from delaying an order."""
    # Cash flow improvement
    cash_retained_micros: MoneyMicros
    
    # Interest/opportunity cost avoided
    interest_saved_micros: MoneyMicros = 0
    
    # Potential negotiation savings
    negotiation_potential_micros: MoneyMicros = 0
    
    # Batch consolidation savings
    consolidation_savings_micros: MoneyMicros = 0
    
    # Total
    total_savings_micros: MoneyMicros


class RiskCost(BaseModel):
    """Cost of a specific downstream risk."""
    risk_type: RiskType
    description: str
    
    # Probability and impact
    probability_pct: Rate
    impact_micros: MoneyMicros
    
    # Expected cost
    expected_cost_micros: MoneyMicros  # probability * impact
    
    # Time sensitivity
    hours_until_risk: int = 0


class DelayRiskCosts(BaseModel):
    """All downstream risk costs from delay."""
    # Individual risks
    risks: list[RiskCost] = Field(default_factory=list)
    
    # Totals
    total_expected_cost_micros: MoneyMicros
    worst_case_cost_micros: MoneyMicros
    
    # Primary risk
    primary_risk: Optional[RiskType] = None
    primary_risk_hours: int = 0


# =============================================================================
# DELAY ANALYSIS RESULT
# =============================================================================

class DelayAnalysis(BaseModel):
    """
    Complete cost of delay analysis.
    The main output of the calculator.
    """
    analysis_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Order context
    order_id: uuid.UUID
    order_total_micros: MoneyMicros
    
    # Delay scenario
    delay_hours: int
    delay_reason: Optional[DelayReason] = None
    
    # Core output
    cash_saved_now_micros: MoneyMicros
    risk_cost_later_micros: MoneyMicros
    net_effect_micros: MoneyMicros  # positive = delay is beneficial
    
    # Human-readable (dollars)
    cash_saved_now: Decimal
    risk_cost_later: Decimal
    net_effect: Decimal
    
    # Breakdown
    savings_breakdown: DelaySavings
    risk_breakdown: DelayRiskCosts
    
    # Recommendation
    recommendation: DelayRecommendation
    recommendation_reason: str
    
    # Confidence
    analysis_confidence: Rate = Decimal("0.80")
    
    # Warnings
    warnings: list[str] = Field(default_factory=list)


class MultiDelayComparison(BaseModel):
    """Compare multiple delay scenarios."""
    comparison_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    
    # Order
    order_id: uuid.UUID
    
    # Scenarios
    scenarios: list[DelayAnalysis] = []
    
    # Optimal
    optimal_delay_hours: int
    optimal_net_effect_micros: MoneyMicros
    
    # Recommendation
    recommendation: str


# =============================================================================
# BATCH ANALYSIS
# =============================================================================

class BatchDelayAnalysis(BaseModel):
    """Analysis of delaying multiple orders."""
    batch_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Orders analyzed
    order_count: int
    total_order_value_micros: MoneyMicros
    
    # Aggregate results
    total_cash_saved_micros: MoneyMicros
    total_risk_cost_micros: MoneyMicros
    net_effect_micros: MoneyMicros
    
    # Individual analyses
    order_analyses: list[DelayAnalysis] = []
    
    # Recommendations
    orders_to_proceed: list[uuid.UUID] = []
    orders_safe_to_delay: list[uuid.UUID] = []
    orders_risky_to_delay: list[uuid.UUID] = []


# =============================================================================
# CONFIGURATION
# =============================================================================

class CostDelayConfig(BaseModel):
    """Configuration for cost of delay calculator."""
    # Risk cost multipliers
    stockout_cost_multiplier: Decimal = Decimal("2.5")  # Cost of stockout vs. item value
    expedited_shipping_multiplier: Decimal = Decimal("1.5")  # Premium for rush delivery
    emergency_vendor_multiplier: Decimal = Decimal("1.3")  # Premium for backup vendor
    
    # Opportunity cost
    daily_interest_rate: Rate = Decimal("0.0001")  # ~3.65% APR
    
    # Risk thresholds
    safe_days_of_supply: int = 7
    risky_days_of_supply: int = 3
    critical_days_of_supply: int = 1
    
    # Delay limits
    max_safe_delay_hours: int = 72
    max_any_delay_hours: int = 168  # 1 week
    
    # Customer impact
    customer_impact_per_stockout_micros: MoneyMicros = 50_000_000_000  # $50 per incident

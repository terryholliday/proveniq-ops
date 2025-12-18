"""
PROVENIQ Ops - What-If Scenario Simulator Schemas
Bishop hypothetical future simulation data contracts

GUARDRAILS:
- Simulation outputs are ADVISORY ONLY
- No downstream execution nodes may consume this output
- NEVER modifies inventory, orders, or ledger entries
"""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, Any

from pydantic import BaseModel, Field

from app.core.types import MoneyMicros, Quantity, Rate


class ScenarioType(str, Enum):
    """Types of what-if scenarios."""
    DELAY_ORDER = "delay_order"
    VENDOR_CHANGE = "vendor_change"
    PRICE_SHIFT = "price_shift"
    DEMAND_SPIKE = "demand_spike"
    DEMAND_DROP = "demand_drop"
    STOCKOUT_EVENT = "stockout_event"
    SUPPLY_DISRUPTION = "supply_disruption"
    COST_INCREASE = "cost_increase"
    LABOR_SHORTAGE = "labor_shortage"
    CUSTOM = "custom"


class ImpactSeverity(str, Enum):
    """Impact severity classification."""
    NEGLIGIBLE = "negligible"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


# =============================================================================
# STATE SNAPSHOT MODELS
# =============================================================================

class InventorySnapshot(BaseModel):
    """Point-in-time inventory state."""
    snapshot_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    taken_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Inventory items: product_id -> quantity
    items: dict[str, Quantity] = Field(default_factory=dict)
    
    # Values
    total_value_micros: MoneyMicros = 0
    total_items: int = 0
    
    # Risk status
    items_at_stockout_risk: int = 0
    items_expiring_soon: int = 0


class DemandForecastSnapshot(BaseModel):
    """Demand forecast state."""
    forecast_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    forecast_date: datetime = Field(default_factory=datetime.utcnow)
    
    # Daily demand by product: product_id -> daily_units
    daily_demand: dict[str, Quantity] = Field(default_factory=dict)
    
    # Forecast horizon
    horizon_days: int = 7
    
    # Confidence
    forecast_confidence: Rate = Decimal("0.80")


class LiquiditySnapshot(BaseModel):
    """Cash/liquidity state."""
    snapshot_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    taken_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Balances
    cash_balance_micros: MoneyMicros
    available_balance_micros: MoneyMicros
    
    # Obligations
    obligations_7d_micros: MoneyMicros = 0
    obligations_14d_micros: MoneyMicros = 0
    
    # Liquidity ratio
    liquidity_ratio: Rate = Decimal("1.0")


class MarginSnapshot(BaseModel):
    """Menu/product margin state."""
    snapshot_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    taken_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Margins by product: product_id -> margin_pct
    margins: dict[str, Rate] = Field(default_factory=dict)
    
    # Averages
    avg_margin_pct: Rate = Decimal("0")
    min_margin_pct: Rate = Decimal("0")
    items_below_threshold: int = 0


class PolicyTokens(BaseModel):
    """Current policy configuration."""
    # Stockout thresholds
    stockout_warning_days: int = 3
    stockout_critical_days: int = 1
    
    # Margin thresholds
    margin_warning_pct: Rate = Decimal("45")
    margin_critical_pct: Rate = Decimal("35")
    
    # Cash flow
    minimum_reserve_micros: MoneyMicros = 50_000_000_000
    
    # Waste
    waste_warning_pct: Rate = Decimal("5")


# =============================================================================
# SCENARIO INPUT MODELS
# =============================================================================

class ScenarioInput(BaseModel):
    """Base scenario input."""
    scenario_type: ScenarioType
    description: str
    
    # Optional parameters based on type
    parameters: dict[str, Any] = Field(default_factory=dict)


class DelayOrderScenario(BaseModel):
    """Delay an order by N hours."""
    scenario_type: ScenarioType = ScenarioType.DELAY_ORDER
    order_id: Optional[uuid.UUID] = None
    vendor_name: Optional[str] = None
    delay_hours: int
    affected_products: list[str] = Field(default_factory=list)


class VendorChangeScenario(BaseModel):
    """Switch vendor for products."""
    scenario_type: ScenarioType = ScenarioType.VENDOR_CHANGE
    from_vendor: str
    to_vendor: str
    affected_products: list[str] = Field(default_factory=list)
    price_change_pct: Rate = Decimal("0")
    lead_time_change_hours: int = 0


class PriceShiftScenario(BaseModel):
    """Simulate price change from vendor."""
    scenario_type: ScenarioType = ScenarioType.PRICE_SHIFT
    vendor_name: Optional[str] = None
    product_id: Optional[str] = None
    price_change_pct: Rate
    effective_date: Optional[datetime] = None


class DemandShiftScenario(BaseModel):
    """Simulate demand spike or drop."""
    scenario_type: ScenarioType
    demand_change_pct: Rate  # +20% = spike, -20% = drop
    duration_days: int = 7
    affected_products: list[str] = Field(default_factory=list)  # Empty = all


class SupplyDisruptionScenario(BaseModel):
    """Simulate supply chain disruption."""
    scenario_type: ScenarioType = ScenarioType.SUPPLY_DISRUPTION
    vendor_name: str
    disruption_days: int
    affected_products: list[str] = Field(default_factory=list)


# =============================================================================
# SIMULATION STATE
# =============================================================================

class SimulationState(BaseModel):
    """
    Cloned state for simulation.
    This is a COPY - never modifies real data.
    """
    state_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    cloned_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Snapshots
    inventory: InventorySnapshot
    demand: DemandForecastSnapshot
    liquidity: LiquiditySnapshot
    margins: MarginSnapshot
    policy: PolicyTokens
    
    # Is this baseline or modified?
    is_baseline: bool = True
    applied_scenario: Optional[str] = None


# =============================================================================
# DELTA CALCULATIONS
# =============================================================================

class StockoutDelta(BaseModel):
    """Change in stockout risk."""
    baseline_risk_hours: Quantity
    scenario_risk_hours: Quantity
    delta_hours: Quantity
    
    # Affected items
    items_newly_at_risk: int = 0
    items_risk_increased: int = 0
    items_risk_decreased: int = 0


class CashFlowDelta(BaseModel):
    """Change in cash flow."""
    baseline_balance_micros: MoneyMicros
    scenario_balance_micros: MoneyMicros
    delta_micros: MoneyMicros
    
    # Impact
    crosses_reserve_threshold: bool = False
    days_of_runway_change: Quantity = Decimal("0")


class WasteDelta(BaseModel):
    """Change in waste risk."""
    baseline_waste_pct: Rate
    scenario_waste_pct: Rate
    delta_pct: Rate
    
    # Value at risk
    baseline_waste_value_micros: MoneyMicros = 0
    scenario_waste_value_micros: MoneyMicros = 0


class MarginDelta(BaseModel):
    """Change in margins."""
    baseline_avg_margin_pct: Rate
    scenario_avg_margin_pct: Rate
    delta_pct: Rate
    
    # Items affected
    items_margin_decreased: int = 0
    items_below_threshold: int = 0


class ScenarioDelta(BaseModel):
    """
    Combined delta output.
    The core output of simulation.
    """
    stockout_risk_hours: Quantity
    cash_flow_change_micros: MoneyMicros
    waste_risk_change_pct: Rate
    margin_change_pct: Rate
    
    # Detailed breakdowns
    stockout_detail: Optional[StockoutDelta] = None
    cashflow_detail: Optional[CashFlowDelta] = None
    waste_detail: Optional[WasteDelta] = None
    margin_detail: Optional[MarginDelta] = None


# =============================================================================
# SIMULATION RESULT
# =============================================================================

class ScenarioResult(BaseModel):
    """
    Complete simulation result.
    
    IMPORTANT: This is ADVISORY ONLY.
    No downstream execution nodes may consume this output.
    """
    scenario_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    
    # Input
    scenario_type: ScenarioType
    scenario_description: str
    
    # Delta (the core output)
    delta: ScenarioDelta
    
    # Confidence in simulation
    confidence: Rate
    
    # Impact classification
    impact_severity: ImpactSeverity
    
    # Recommendations (advisory only)
    recommendations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    
    # Metadata
    simulated_at: datetime = Field(default_factory=datetime.utcnow)
    simulation_duration_ms: int = 0
    
    # GUARDRAIL reminder
    advisory_only: bool = True
    disclaimer: str = "Simulation outputs are advisory only. No actions have been taken."
    
    class Config:
        json_schema_extra = {
            "example": {
                "scenario_id": "uuid",
                "scenario_type": "delay_order",
                "delta": {
                    "stockout_risk_hours": 24,
                    "cash_flow_change_micros": 15000000000,
                    "waste_risk_change_pct": "0.5",
                    "margin_change_pct": "-2.0"
                },
                "confidence": 0.85,
                "advisory_only": True,
                "disclaimer": "Simulation outputs are advisory only."
            }
        }


class ScenarioComparison(BaseModel):
    """Compare multiple scenarios."""
    comparison_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    
    # Baseline
    baseline_description: str = "Current state"
    
    # Scenarios compared
    scenarios: list[ScenarioResult] = []
    
    # Best option
    recommended_scenario_id: Optional[uuid.UUID] = None
    recommendation_reason: Optional[str] = None
    
    # Comparison metadata
    compared_at: datetime = Field(default_factory=datetime.utcnow)
    
    disclaimer: str = "Comparison is advisory only. Human decision required."


# =============================================================================
# SIMULATION CONFIG
# =============================================================================

class SimulatorConfig(BaseModel):
    """Configuration for the what-if simulator."""
    # Forecast horizon
    simulation_horizon_days: int = 14
    
    # Confidence adjustments
    base_confidence: Rate = Decimal("0.85")
    confidence_decay_per_day: Rate = Decimal("0.02")
    
    # Impact thresholds
    negligible_stockout_hours: int = 4
    low_stockout_hours: int = 12
    moderate_stockout_hours: int = 24
    high_stockout_hours: int = 48
    
    # Cash impact thresholds (micros)
    negligible_cash_impact: MoneyMicros = 1_000_000_000  # $1k
    low_cash_impact: MoneyMicros = 5_000_000_000  # $5k
    moderate_cash_impact: MoneyMicros = 15_000_000_000  # $15k
    high_cash_impact: MoneyMicros = 50_000_000_000  # $50k

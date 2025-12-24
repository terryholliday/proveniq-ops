"""
PROVENIQ Ops - Multi-Location Rebalancer Schemas
Bishop network optimization data contracts

DAG Node: N18, N35

GUARDRAILS:
- Respect location autonomy unless enabled
"""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from app.core.types import MoneyMicros, IntQuantity, Quantity, Rate


class TransferAlertType(str, Enum):
    """Transfer alert classifications."""
    INTER_LOCATION_TRANSFER = "INTER_LOCATION_TRANSFER"
    REBALANCE_OPPORTUNITY = "REBALANCE_OPPORTUNITY"
    STOCKOUT_PREVENTION = "STOCKOUT_PREVENTION"
    OVERSTOCK_REDUCTION = "OVERSTOCK_REDUCTION"


class TransferStatus(str, Enum):
    """Transfer proposal status."""
    PROPOSED = "proposed"
    APPROVED = "approved"
    IN_TRANSIT = "in_transit"
    COMPLETED = "completed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class LocationType(str, Enum):
    """Location type for autonomy rules."""
    OWNED = "owned"
    FRANCHISE = "franchise"
    PARTNER = "partner"
    WAREHOUSE = "warehouse"


# =============================================================================
# LOCATION & INVENTORY MODELS
# =============================================================================

class Location(BaseModel):
    """Location in the network."""
    location_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    location_type: LocationType = LocationType.OWNED
    
    # Autonomy settings
    allow_inbound_transfers: bool = True
    allow_outbound_transfers: bool = True
    requires_approval: bool = True
    
    # Capacity
    storage_capacity: Optional[int] = None
    current_utilization_pct: Optional[Quantity] = None


class LocationInventory(BaseModel):
    """Inventory for a product at a location."""
    location_id: uuid.UUID
    location_name: str
    product_id: uuid.UUID
    product_name: str
    canonical_sku: str
    
    # Quantities
    on_hand_qty: IntQuantity
    safety_stock: IntQuantity = 0
    par_level: IntQuantity = 0
    
    # Status
    days_of_supply: Optional[Quantity] = None
    stockout_risk: bool = False
    overstock: bool = False
    
    # Value
    unit_cost_micros: MoneyMicros


class TransferCost(BaseModel):
    """Cost to transfer between locations."""
    from_location_id: uuid.UUID
    to_location_id: uuid.UUID
    
    # Costs
    base_cost_micros: MoneyMicros  # Fixed cost per transfer
    per_unit_cost_micros: MoneyMicros  # Variable cost per unit
    
    # Time
    transit_hours: int
    
    # Constraints
    min_qty: int = 1
    max_qty: Optional[int] = None


class DemandForecast(BaseModel):
    """Demand forecast for a product at a location."""
    location_id: uuid.UUID
    product_id: uuid.UUID
    
    # Forecast
    daily_demand: Quantity
    forecast_days: int = 7
    total_forecast_qty: IntQuantity
    
    # Confidence
    confidence: Rate
    
    # Calculated
    days_until_stockout: Optional[Quantity] = None


# =============================================================================
# TRANSFER PROPOSAL MODELS
# =============================================================================

class TransferProposal(BaseModel):
    """
    Bishop inter-location transfer proposal.
    Deterministic output.
    """
    proposal_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    alert_type: TransferAlertType = TransferAlertType.INTER_LOCATION_TRANSFER
    
    # Product
    product_id: uuid.UUID
    product_name: str
    canonical_sku: str
    
    # Locations
    from_location_id: uuid.UUID
    from_location_name: str
    to_location_id: uuid.UUID
    to_location_name: str
    
    # Quantities
    recommended_qty: IntQuantity
    from_current_qty: IntQuantity
    from_after_qty: IntQuantity
    to_current_qty: IntQuantity
    to_after_qty: IntQuantity
    
    # Costs
    transfer_cost_micros: MoneyMicros
    inventory_value_micros: MoneyMicros
    
    # Benefit
    stockout_prevented: bool = False
    days_of_supply_added: Optional[Quantity] = None
    overstock_reduced: bool = False
    
    # Status
    status: TransferStatus = TransferStatus.PROPOSED
    requires_approval: bool = True
    
    # Reasoning
    reason_codes: list[str] = []
    confidence: Rate
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "alert_type": "INTER_LOCATION_TRANSFER",
                "from_location_name": "Warehouse A",
                "to_location_name": "Store #12",
                "product_name": "Chicken Breast 5lb",
                "recommended_qty": 25,
                "transfer_cost_micros": 15000000,
                "stockout_prevented": True
            }
        }


class RebalanceAlert(BaseModel):
    """
    Bishop network rebalance alert.
    Summary of all transfer opportunities.
    """
    alert_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    alert_type: TransferAlertType = TransferAlertType.REBALANCE_OPPORTUNITY
    
    # Summary
    total_proposals: int
    stockout_preventions: int
    overstock_reductions: int
    
    # Financial
    total_transfer_cost_micros: MoneyMicros
    total_inventory_value_micros: MoneyMicros
    estimated_savings_micros: MoneyMicros  # From prevented stockouts/waste
    
    # Network status
    locations_with_stockout_risk: int
    locations_with_overstock: int
    locations_balanced: int
    
    # Proposals
    proposals: list[TransferProposal] = []
    
    # Approvals needed
    proposals_requiring_approval: int
    auto_approvable: int
    
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# NETWORK ANALYSIS MODELS
# =============================================================================

class ProductNetworkStatus(BaseModel):
    """Network-wide status for a single product."""
    product_id: uuid.UUID
    product_name: str
    canonical_sku: str
    
    # Network totals
    total_network_qty: IntQuantity
    total_network_demand: IntQuantity  # Forecast period
    
    # Location breakdown
    locations_with_stock: int
    locations_at_risk: int
    locations_overstocked: int
    
    # Imbalance score (0 = balanced, 1 = severe imbalance)
    imbalance_score: Quantity
    
    # Rebalance potential
    transferable_qty: IntQuantity  # Can move without creating new risks
    
    # Location details
    location_status: list[dict] = []


class NetworkAnalysis(BaseModel):
    """Complete network inventory analysis."""
    analysis_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Network summary
    total_locations: int
    total_products: int
    
    # Health
    healthy_locations: int
    at_risk_locations: int
    overstocked_locations: int
    
    # Imbalanced products
    products_needing_rebalance: int
    total_imbalance_value_micros: MoneyMicros
    
    # Top issues
    top_stockout_risks: list[ProductNetworkStatus] = []
    top_overstock: list[ProductNetworkStatus] = []
    
    # Recommended actions
    total_recommended_transfers: int


# =============================================================================
# CONFIGURATION
# =============================================================================

class RebalanceConfig(BaseModel):
    """Configuration for multi-location rebalancer."""
    # Thresholds
    stockout_risk_days: int = 3  # Alert if < X days supply
    overstock_days: int = 30  # Alert if > X days supply
    
    # Transfer rules
    min_transfer_qty: int = 1
    min_transfer_value_micros: MoneyMicros = 10_000_000  # $10 minimum
    max_transfer_cost_pct: Quantity = Field(default=Decimal("15"))  # Max 15% of value
    
    # Autonomy
    respect_location_autonomy: bool = True  # GUARDRAIL: Default on
    auto_approve_owned_locations: bool = False
    
    # Optimization
    optimize_for: str = "stockout_prevention"  # stockout_prevention, cost, balance

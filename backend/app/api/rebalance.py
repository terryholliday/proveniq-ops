"""
PROVENIQ Ops - Multi-Location Rebalancer API Routes
Bishop network optimization endpoints

DAG Nodes: N18, N35

GUARDRAILS:
- Respect location autonomy unless enabled
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Query

from app.core.types import Money
from app.models.rebalance import (
    DemandForecast,
    Location,
    LocationInventory,
    LocationType,
    NetworkAnalysis,
    RebalanceAlert,
    RebalanceConfig,
    TransferCost,
    TransferProposal,
    TransferStatus,
)
from app.services.bishop.rebalance_engine import rebalance_engine

router = APIRouter(prefix="/rebalance", tags=["Multi-Location Rebalancer"])


# =============================================================================
# PROPOSALS
# =============================================================================

@router.post("/proposals", response_model=RebalanceAlert)
async def generate_proposals() -> RebalanceAlert:
    """
    Generate transfer proposals for the network.
    
    Bishop Logic (N18/N35):
        1. Identify overstock vs stockout risk
        2. Propose transfers minimizing total cost
    
    GUARDRAILS:
        - Respects location autonomy by default
        - Franchise/partner locations require explicit approval
    """
    return rebalance_engine.generate_proposals()


@router.get("/proposals")
async def get_proposals(
    status: Optional[TransferStatus] = None,
) -> dict:
    """Get transfer proposals, optionally filtered by status."""
    proposals = rebalance_engine.get_proposals(status=status)
    return {
        "total": len(proposals),
        "status_filter": status.value if status else None,
        "proposals": [p.model_dump() for p in proposals],
    }


@router.get("/proposals/{proposal_id}")
async def get_proposal(proposal_id: uuid.UUID) -> dict:
    """Get a specific transfer proposal."""
    proposals = rebalance_engine.get_proposals()
    for p in proposals:
        if p.proposal_id == proposal_id:
            return p.model_dump()
    return {"error": "Proposal not found"}


@router.post("/proposals/{proposal_id}/approve")
async def approve_proposal(proposal_id: uuid.UUID) -> dict:
    """Approve a transfer proposal."""
    proposal = rebalance_engine.approve_proposal(proposal_id)
    if not proposal:
        return {"error": "Proposal not found"}
    return {
        "status": "approved",
        "proposal_id": str(proposal_id),
        "from": proposal.from_location_name,
        "to": proposal.to_location_name,
        "qty": proposal.recommended_qty,
    }


@router.post("/proposals/{proposal_id}/reject")
async def reject_proposal(proposal_id: uuid.UUID) -> dict:
    """Reject a transfer proposal."""
    proposal = rebalance_engine.reject_proposal(proposal_id)
    if not proposal:
        return {"error": "Proposal not found"}
    return {
        "status": "rejected",
        "proposal_id": str(proposal_id),
    }


# =============================================================================
# NETWORK ANALYSIS
# =============================================================================

@router.get("/network", response_model=NetworkAnalysis)
async def analyze_network() -> NetworkAnalysis:
    """
    Analyze the complete inventory network.
    
    Returns network health and imbalance metrics.
    """
    return rebalance_engine.analyze_network()


@router.get("/network/at-risk")
async def get_at_risk_locations() -> dict:
    """Get locations with stockout risk."""
    analysis = rebalance_engine.analyze_network()
    return {
        "at_risk_count": analysis.at_risk_locations,
        "top_risks": [s.model_dump() for s in analysis.top_stockout_risks],
    }


@router.get("/network/overstocked")
async def get_overstocked_locations() -> dict:
    """Get locations with overstock."""
    analysis = rebalance_engine.analyze_network()
    return {
        "overstocked_count": analysis.overstocked_locations,
        "top_overstock": [s.model_dump() for s in analysis.top_overstock],
    }


# =============================================================================
# ALERTS
# =============================================================================

@router.get("/alerts", response_model=list[RebalanceAlert])
async def get_alerts(limit: int = Query(100, ge=1, le=1000)) -> list[RebalanceAlert]:
    """Get rebalance alerts."""
    return rebalance_engine.get_alerts(limit=limit)


# =============================================================================
# CONFIGURATION
# =============================================================================

@router.get("/config", response_model=RebalanceConfig)
async def get_config() -> RebalanceConfig:
    """Get current rebalancer configuration."""
    return rebalance_engine.get_config()


@router.put("/config")
async def update_config(
    stockout_risk_days: Optional[int] = Query(None, ge=1),
    overstock_days: Optional[int] = Query(None, ge=1),
    respect_location_autonomy: Optional[bool] = None,
    auto_approve_owned_locations: Optional[bool] = None,
) -> RebalanceConfig:
    """
    Update rebalancer configuration.
    
    GUARDRAIL: respect_location_autonomy is on by default.
    """
    config = rebalance_engine.get_config()
    
    if stockout_risk_days is not None:
        config.stockout_risk_days = stockout_risk_days
    if overstock_days is not None:
        config.overstock_days = overstock_days
    if respect_location_autonomy is not None:
        config.respect_location_autonomy = respect_location_autonomy
    if auto_approve_owned_locations is not None:
        config.auto_approve_owned_locations = auto_approve_owned_locations
    
    rebalance_engine.configure(config)
    return config


# =============================================================================
# DATA REGISTRATION
# =============================================================================

@router.post("/data/location")
async def register_location(
    name: str,
    location_type: LocationType = LocationType.OWNED,
    allow_inbound_transfers: bool = True,
    allow_outbound_transfers: bool = True,
    requires_approval: bool = True,
) -> dict:
    """Register a location in the network."""
    location = Location(
        name=name,
        location_type=location_type,
        allow_inbound_transfers=allow_inbound_transfers,
        allow_outbound_transfers=allow_outbound_transfers,
        requires_approval=requires_approval,
    )
    rebalance_engine.register_location(location)
    return {
        "status": "registered",
        "location_id": str(location.location_id),
        "name": name,
    }


@router.post("/data/inventory")
async def register_inventory(
    location_id: uuid.UUID,
    location_name: str,
    product_id: uuid.UUID,
    product_name: str,
    canonical_sku: str,
    on_hand_qty: int,
    unit_cost_dollars: str,
    safety_stock: int = 0,
    par_level: int = 0,
) -> dict:
    """Register inventory for a product at a location."""
    inv = LocationInventory(
        location_id=location_id,
        location_name=location_name,
        product_id=product_id,
        product_name=product_name,
        canonical_sku=canonical_sku,
        on_hand_qty=on_hand_qty,
        unit_cost_micros=Money.from_dollars(unit_cost_dollars),
        safety_stock=safety_stock,
        par_level=par_level,
    )
    rebalance_engine.register_inventory(inv)
    return {
        "status": "registered",
        "location_name": location_name,
        "product_name": product_name,
        "on_hand_qty": on_hand_qty,
    }


@router.post("/data/transfer-cost")
async def register_transfer_cost(
    from_location_id: uuid.UUID,
    to_location_id: uuid.UUID,
    base_cost_dollars: str,
    per_unit_cost_dollars: str,
    transit_hours: int,
) -> dict:
    """Register transfer cost between locations."""
    cost = TransferCost(
        from_location_id=from_location_id,
        to_location_id=to_location_id,
        base_cost_micros=Money.from_dollars(base_cost_dollars),
        per_unit_cost_micros=Money.from_dollars(per_unit_cost_dollars),
        transit_hours=transit_hours,
    )
    rebalance_engine.register_transfer_cost(cost)
    return {
        "status": "registered",
        "from": str(from_location_id),
        "to": str(to_location_id),
    }


@router.post("/data/forecast")
async def register_forecast(
    location_id: uuid.UUID,
    product_id: uuid.UUID,
    daily_demand: Decimal,
    forecast_days: int = 7,
    confidence: Decimal = Decimal("0.8"),
) -> dict:
    """Register demand forecast for a product at a location."""
    forecast = DemandForecast(
        location_id=location_id,
        product_id=product_id,
        daily_demand=daily_demand,
        forecast_days=forecast_days,
        total_forecast_qty=int(daily_demand * forecast_days),
        confidence=confidence,
    )
    rebalance_engine.register_forecast(forecast)
    return {
        "status": "registered",
        "location_id": str(location_id),
        "product_id": str(product_id),
        "daily_demand": str(daily_demand),
    }


@router.delete("/data/clear")
async def clear_data() -> dict:
    """Clear all rebalancer data (for testing)."""
    rebalance_engine.clear_data()
    return {"status": "cleared"}


# =============================================================================
# DEMO DATA
# =============================================================================

@router.post("/demo/setup")
async def setup_demo_data() -> dict:
    """
    Set up demo data for multi-location rebalancing.
    
    Creates sample network with imbalanced inventory.
    """
    rebalance_engine.clear_data()
    
    # Locations
    warehouse = Location(
        location_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        name="Central Warehouse",
        location_type=LocationType.WAREHOUSE,
        allow_inbound_transfers=True,
        allow_outbound_transfers=True,
        requires_approval=False,  # Warehouse auto-approves
    )
    
    store1 = Location(
        location_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
        name="Store #12 Downtown",
        location_type=LocationType.OWNED,
        allow_inbound_transfers=True,
        allow_outbound_transfers=True,
        requires_approval=True,
    )
    
    store2 = Location(
        location_id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
        name="Store #15 Uptown",
        location_type=LocationType.OWNED,
        allow_inbound_transfers=True,
        allow_outbound_transfers=True,
        requires_approval=True,
    )
    
    franchise = Location(
        location_id=uuid.UUID("44444444-4444-4444-4444-444444444444"),
        name="Franchise #3",
        location_type=LocationType.FRANCHISE,
        allow_inbound_transfers=True,
        allow_outbound_transfers=False,  # Franchise doesn't give inventory
        requires_approval=True,
    )
    
    for loc in [warehouse, store1, store2, franchise]:
        rebalance_engine.register_location(loc)
    
    # Products
    chicken_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    rice_id = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    
    # Inventory - Chicken (imbalanced)
    # Warehouse has excess, Store #12 at risk
    inventories = [
        (warehouse.location_id, "Central Warehouse", chicken_id, "Chicken Breast 5lb", "CHK-BRST-5LB", 200, "12.50", 20, 50),
        (store1.location_id, "Store #12 Downtown", chicken_id, "Chicken Breast 5lb", "CHK-BRST-5LB", 5, "12.50", 10, 30),  # LOW!
        (store2.location_id, "Store #15 Uptown", chicken_id, "Chicken Breast 5lb", "CHK-BRST-5LB", 45, "12.50", 10, 30),
        (franchise.location_id, "Franchise #3", chicken_id, "Chicken Breast 5lb", "CHK-BRST-5LB", 25, "12.50", 10, 30),
        
        # Rice (balanced)
        (warehouse.location_id, "Central Warehouse", rice_id, "Rice 25lb", "RICE-25LB", 100, "18.99", 10, 25),
        (store1.location_id, "Store #12 Downtown", rice_id, "Rice 25lb", "RICE-25LB", 20, "18.99", 5, 15),
        (store2.location_id, "Store #15 Uptown", rice_id, "Rice 25lb", "RICE-25LB", 18, "18.99", 5, 15),
        (franchise.location_id, "Franchise #3", rice_id, "Rice 25lb", "RICE-25LB", 22, "18.99", 5, 15),
    ]
    
    for loc_id, loc_name, prod_id, prod_name, sku, qty, cost, safety, par in inventories:
        inv = LocationInventory(
            location_id=loc_id,
            location_name=loc_name,
            product_id=prod_id,
            product_name=prod_name,
            canonical_sku=sku,
            on_hand_qty=qty,
            unit_cost_micros=Money.from_dollars(cost),
            safety_stock=safety,
            par_level=par,
        )
        rebalance_engine.register_inventory(inv)
    
    # Forecasts
    forecasts = [
        (store1.location_id, chicken_id, Decimal("8")),  # 8/day = <1 day supply!
        (store2.location_id, chicken_id, Decimal("5")),
        (franchise.location_id, chicken_id, Decimal("4")),
        (store1.location_id, rice_id, Decimal("2")),
        (store2.location_id, rice_id, Decimal("2")),
        (franchise.location_id, rice_id, Decimal("3")),
    ]
    
    for loc_id, prod_id, daily in forecasts:
        forecast = DemandForecast(
            location_id=loc_id,
            product_id=prod_id,
            daily_demand=daily,
            forecast_days=7,
            total_forecast_qty=int(daily * 7),
            confidence=Decimal("0.8"),
        )
        rebalance_engine.register_forecast(forecast)
    
    # Transfer costs
    transfer_pairs = [
        (warehouse.location_id, store1.location_id, "15.00", "0.50", 4),
        (warehouse.location_id, store2.location_id, "20.00", "0.50", 6),
        (warehouse.location_id, franchise.location_id, "25.00", "0.75", 8),
        (store1.location_id, store2.location_id, "10.00", "0.25", 2),
        (store2.location_id, store1.location_id, "10.00", "0.25", 2),
    ]
    
    for from_id, to_id, base, per_unit, hours in transfer_pairs:
        cost = TransferCost(
            from_location_id=from_id,
            to_location_id=to_id,
            base_cost_micros=Money.from_dollars(base),
            per_unit_cost_micros=Money.from_dollars(per_unit),
            transit_hours=hours,
        )
        rebalance_engine.register_transfer_cost(cost)
    
    # Re-register inventory to calculate days of supply
    for loc_id, loc_name, prod_id, prod_name, sku, qty, cost, safety, par in inventories:
        inv = LocationInventory(
            location_id=loc_id,
            location_name=loc_name,
            product_id=prod_id,
            product_name=prod_name,
            canonical_sku=sku,
            on_hand_qty=qty,
            unit_cost_micros=Money.from_dollars(cost),
            safety_stock=safety,
            par_level=par,
        )
        rebalance_engine.register_inventory(inv)
    
    return {
        "status": "demo_data_created",
        "locations": 4,
        "products": 2,
        "expected_proposals": [
            "Warehouse → Store #12: Chicken Breast (stockout risk, <1 day supply)",
        ],
        "autonomy_notes": [
            "Franchise #3 cannot send inventory (outbound disabled)",
            "Store transfers require approval",
            "Warehouse auto-approves",
        ],
    }

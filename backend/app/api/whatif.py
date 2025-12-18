"""
PROVENIQ Ops - What-If Scenario Simulator API Routes
Bishop hypothetical future simulation endpoints

GUARDRAILS:
- Simulation outputs are ADVISORY ONLY
- No downstream execution nodes may consume this output
- NEVER modifies inventory, orders, or ledger entries
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Query

from app.core.types import Money
from app.models.whatif import (
    DemandForecastSnapshot,
    DemandShiftScenario,
    DelayOrderScenario,
    ImpactSeverity,
    InventorySnapshot,
    LiquiditySnapshot,
    MarginSnapshot,
    PolicyTokens,
    PriceShiftScenario,
    ScenarioComparison,
    ScenarioResult,
    ScenarioType,
    SimulatorConfig,
    SupplyDisruptionScenario,
)
from app.services.bishop.whatif_engine import whatif_simulator

router = APIRouter(prefix="/whatif", tags=["What-If Simulator"])


# =============================================================================
# SCENARIO SIMULATIONS
# =============================================================================

@router.post("/simulate/delay-order", response_model=ScenarioResult)
async def simulate_delay_order(
    delay_hours: int,
    affected_products: list[str] = Query(default=[]),
    order_id: Optional[uuid.UUID] = None,
    vendor_name: Optional[str] = None,
) -> ScenarioResult:
    """
    Simulate delaying an order.
    
    ADVISORY ONLY: No actions are taken.
    
    Calculates impact on:
    - Stockout risk (hours added)
    - Cash flow (temporary improvement)
    - Waste risk
    - Margins
    """
    scenario = DelayOrderScenario(
        delay_hours=delay_hours,
        affected_products=affected_products,
        order_id=order_id,
        vendor_name=vendor_name,
    )
    return whatif_simulator.simulate_delay_order(scenario)


@router.post("/simulate/demand-spike", response_model=ScenarioResult)
async def simulate_demand_spike(
    demand_increase_pct: Decimal,
    duration_days: int = 7,
    affected_products: list[str] = Query(default=[]),
) -> ScenarioResult:
    """
    Simulate a demand spike.
    
    ADVISORY ONLY: No actions are taken.
    
    Use case: Holiday rush, promotional event, unexpected popularity
    """
    scenario = DemandShiftScenario(
        scenario_type=ScenarioType.DEMAND_SPIKE,
        demand_change_pct=abs(demand_increase_pct),
        duration_days=duration_days,
        affected_products=affected_products,
    )
    return whatif_simulator.simulate_demand_shift(scenario)


@router.post("/simulate/demand-drop", response_model=ScenarioResult)
async def simulate_demand_drop(
    demand_decrease_pct: Decimal,
    duration_days: int = 7,
    affected_products: list[str] = Query(default=[]),
) -> ScenarioResult:
    """
    Simulate a demand drop.
    
    ADVISORY ONLY: No actions are taken.
    
    Use case: Seasonal slowdown, competitor opening, weather event
    """
    scenario = DemandShiftScenario(
        scenario_type=ScenarioType.DEMAND_DROP,
        demand_change_pct=-abs(demand_decrease_pct),
        duration_days=duration_days,
        affected_products=affected_products,
    )
    return whatif_simulator.simulate_demand_shift(scenario)


@router.post("/simulate/price-shift", response_model=ScenarioResult)
async def simulate_price_shift(
    price_change_pct: Decimal,
    vendor_name: Optional[str] = None,
    product_id: Optional[str] = None,
) -> ScenarioResult:
    """
    Simulate vendor price change.
    
    ADVISORY ONLY: No actions are taken.
    
    Positive = price increase, Negative = price decrease
    """
    scenario = PriceShiftScenario(
        price_change_pct=price_change_pct,
        vendor_name=vendor_name,
        product_id=product_id,
    )
    return whatif_simulator.simulate_price_shift(scenario)


@router.post("/simulate/supply-disruption", response_model=ScenarioResult)
async def simulate_supply_disruption(
    vendor_name: str,
    disruption_days: int,
    affected_products: list[str] = Query(default=[]),
) -> ScenarioResult:
    """
    Simulate supply chain disruption.
    
    ADVISORY ONLY: No actions are taken.
    
    Use case: Vendor outage, logistics failure, weather event
    """
    scenario = SupplyDisruptionScenario(
        vendor_name=vendor_name,
        disruption_days=disruption_days,
        affected_products=affected_products,
    )
    return whatif_simulator.simulate_supply_disruption(scenario)


# =============================================================================
# SCENARIO COMPARISON
# =============================================================================

@router.post("/compare")
async def compare_scenarios(
    scenario_ids: list[uuid.UUID],
) -> dict:
    """
    Compare multiple simulation results.
    
    Returns the recommended scenario based on lowest combined impact.
    """
    comparison = whatif_simulator.compare_scenarios(scenario_ids)
    return {
        "comparison": comparison.model_dump(),
        "disclaimer": "Comparison is advisory only. Human decision required.",
    }


# =============================================================================
# SIMULATION HISTORY
# =============================================================================

@router.get("/history")
async def get_simulation_history(
    limit: int = Query(20, ge=1, le=100),
) -> dict:
    """Get recent simulation history."""
    history = whatif_simulator.get_simulation_history(limit)
    return {
        "count": len(history),
        "simulations": [s.model_dump() for s in history],
        "disclaimer": "All simulations are advisory only.",
    }


@router.delete("/history")
async def clear_history() -> dict:
    """Clear simulation history."""
    whatif_simulator.clear_history()
    return {"status": "cleared"}


# =============================================================================
# STATE SNAPSHOTS (for simulation input)
# =============================================================================

@router.post("/state/inventory")
async def update_inventory_snapshot(
    items: dict[str, Decimal],
    total_value_dollars: str = "0",
) -> dict:
    """
    Update inventory snapshot for simulations.
    
    Items format: {"product_id": quantity, ...}
    """
    snapshot = InventorySnapshot(
        items=items,
        total_value_micros=Money.from_dollars(total_value_dollars),
        total_items=len(items),
    )
    whatif_simulator.update_inventory_snapshot(snapshot)
    return {
        "status": "updated",
        "items": len(items),
        "snapshot_id": str(snapshot.snapshot_id),
    }


@router.post("/state/demand")
async def update_demand_snapshot(
    daily_demand: dict[str, Decimal],
    horizon_days: int = 7,
    forecast_confidence: Decimal = Decimal("0.80"),
) -> dict:
    """
    Update demand forecast snapshot for simulations.
    
    Daily demand format: {"product_id": daily_units, ...}
    """
    snapshot = DemandForecastSnapshot(
        daily_demand=daily_demand,
        horizon_days=horizon_days,
        forecast_confidence=forecast_confidence,
    )
    whatif_simulator.update_demand_snapshot(snapshot)
    return {
        "status": "updated",
        "products": len(daily_demand),
        "forecast_id": str(snapshot.forecast_id),
    }


@router.post("/state/liquidity")
async def update_liquidity_snapshot(
    cash_balance_dollars: str,
    available_balance_dollars: Optional[str] = None,
    obligations_7d_dollars: str = "0",
    obligations_14d_dollars: str = "0",
) -> dict:
    """Update liquidity snapshot for simulations."""
    cash = Money.from_dollars(cash_balance_dollars)
    available = Money.from_dollars(available_balance_dollars) if available_balance_dollars else cash
    
    snapshot = LiquiditySnapshot(
        cash_balance_micros=cash,
        available_balance_micros=available,
        obligations_7d_micros=Money.from_dollars(obligations_7d_dollars),
        obligations_14d_micros=Money.from_dollars(obligations_14d_dollars),
    )
    whatif_simulator.update_liquidity_snapshot(snapshot)
    return {
        "status": "updated",
        "available_balance_micros": available,
        "snapshot_id": str(snapshot.snapshot_id),
    }


@router.post("/state/margins")
async def update_margin_snapshot(
    margins: dict[str, Decimal],
) -> dict:
    """
    Update margin snapshot for simulations.
    
    Margins format: {"product_id": margin_pct, ...}
    """
    avg_margin = sum(margins.values()) / len(margins) if margins else Decimal("0")
    min_margin = min(margins.values()) if margins else Decimal("0")
    
    snapshot = MarginSnapshot(
        margins=margins,
        avg_margin_pct=avg_margin,
        min_margin_pct=min_margin,
    )
    whatif_simulator.update_margin_snapshot(snapshot)
    return {
        "status": "updated",
        "products": len(margins),
        "avg_margin_pct": str(avg_margin),
    }


@router.post("/state/policy")
async def update_policy(
    stockout_warning_days: int = 3,
    stockout_critical_days: int = 1,
    margin_warning_pct: Decimal = Decimal("45"),
    margin_critical_pct: Decimal = Decimal("35"),
    minimum_reserve_dollars: str = "50000",
) -> dict:
    """Update policy tokens for simulations."""
    policy = PolicyTokens(
        stockout_warning_days=stockout_warning_days,
        stockout_critical_days=stockout_critical_days,
        margin_warning_pct=margin_warning_pct,
        margin_critical_pct=margin_critical_pct,
        minimum_reserve_micros=Money.from_dollars(minimum_reserve_dollars),
    )
    whatif_simulator.update_policy(policy)
    return {"status": "updated", "policy": policy.model_dump()}


# =============================================================================
# CONFIGURATION
# =============================================================================

@router.get("/config", response_model=SimulatorConfig)
async def get_config() -> SimulatorConfig:
    """Get simulator configuration."""
    return whatif_simulator.get_config()


@router.put("/config")
async def update_config(
    simulation_horizon_days: Optional[int] = Query(None, ge=1),
    base_confidence: Optional[Decimal] = Query(None, ge=0, le=1),
) -> SimulatorConfig:
    """Update simulator configuration."""
    config = whatif_simulator.get_config()
    
    if simulation_horizon_days is not None:
        config.simulation_horizon_days = simulation_horizon_days
    if base_confidence is not None:
        config.base_confidence = base_confidence
    
    whatif_simulator.configure(config)
    return config


# =============================================================================
# DEMO
# =============================================================================

@router.post("/demo/setup")
async def setup_demo() -> dict:
    """
    Set up demo data for what-if simulation testing.
    
    Creates realistic inventory, demand, and liquidity state.
    """
    whatif_simulator.clear_history()
    
    # Inventory snapshot
    inventory = InventorySnapshot(
        items={
            "chicken_breast": Decimal("150"),  # lbs
            "ground_beef": Decimal("80"),
            "flour": Decimal("200"),
            "rice": Decimal("100"),
            "olive_oil": Decimal("25"),  # gallons
            "tomatoes": Decimal("50"),
            "lettuce": Decimal("30"),
        },
        total_value_micros=Money.from_dollars("15000"),
        total_items=7,
        items_at_stockout_risk=1,
    )
    whatif_simulator.update_inventory_snapshot(inventory)
    
    # Demand forecast
    demand = DemandForecastSnapshot(
        daily_demand={
            "chicken_breast": Decimal("25"),  # lbs/day
            "ground_beef": Decimal("15"),
            "flour": Decimal("30"),
            "rice": Decimal("12"),
            "olive_oil": Decimal("3"),
            "tomatoes": Decimal("20"),
            "lettuce": Decimal("15"),
        },
        horizon_days=7,
        forecast_confidence=Decimal("0.82"),
    )
    whatif_simulator.update_demand_snapshot(demand)
    
    # Liquidity
    liquidity = LiquiditySnapshot(
        cash_balance_micros=Money.from_dollars("85000"),
        available_balance_micros=Money.from_dollars("78000"),
        obligations_7d_micros=Money.from_dollars("45000"),
        obligations_14d_micros=Money.from_dollars("72000"),
    )
    whatif_simulator.update_liquidity_snapshot(liquidity)
    
    # Margins
    margins = MarginSnapshot(
        margins={
            "chicken_breast": Decimal("52"),
            "ground_beef": Decimal("48"),
            "flour": Decimal("65"),
            "rice": Decimal("58"),
            "olive_oil": Decimal("42"),
            "tomatoes": Decimal("55"),
            "lettuce": Decimal("60"),
        },
        avg_margin_pct=Decimal("54.3"),
        min_margin_pct=Decimal("42"),
        items_below_threshold=1,
    )
    whatif_simulator.update_margin_snapshot(margins)
    
    # Run example simulations
    delay_result = whatif_simulator.simulate_delay_order(DelayOrderScenario(
        delay_hours=48,
        affected_products=["chicken_breast", "ground_beef"],
    ))
    
    spike_result = whatif_simulator.simulate_demand_shift(DemandShiftScenario(
        scenario_type=ScenarioType.DEMAND_SPIKE,
        demand_change_pct=Decimal("30"),
        duration_days=3,
        affected_products=[],
    ))
    
    disruption_result = whatif_simulator.simulate_supply_disruption(SupplyDisruptionScenario(
        vendor_name="Sysco",
        disruption_days=5,
        affected_products=["chicken_breast", "lettuce", "tomatoes"],
    ))
    
    return {
        "status": "demo_data_created",
        "state": {
            "inventory_items": 7,
            "inventory_value": "$15,000",
            "available_cash": "$78,000",
            "obligations_7d": "$45,000",
            "avg_margin": "54.3%",
        },
        "example_simulations": [
            {
                "scenario": "Delay order 48h",
                "scenario_id": str(delay_result.scenario_id),
                "impact": delay_result.impact_severity.value,
                "stockout_risk_change": f"{delay_result.delta.stockout_risk_hours}h",
                "confidence": str(delay_result.confidence),
            },
            {
                "scenario": "Demand spike +30%",
                "scenario_id": str(spike_result.scenario_id),
                "impact": spike_result.impact_severity.value,
                "stockout_risk_change": f"{spike_result.delta.stockout_risk_hours}h",
                "confidence": str(spike_result.confidence),
            },
            {
                "scenario": "Sysco disruption 5d",
                "scenario_id": str(disruption_result.scenario_id),
                "impact": disruption_result.impact_severity.value,
                "stockout_risk_change": f"{disruption_result.delta.stockout_risk_hours}h",
                "confidence": str(disruption_result.confidence),
            },
        ],
        "guardrail_reminder": "All simulations are ADVISORY ONLY. No actions taken.",
    }

"""
PROVENIQ Ops - Cost of Delay Calculator API Routes
Bishop financial impact quantification endpoints

Quantifies the financial impact of inaction.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Query

from app.core.types import Money
from app.models.costdelay import (
    BatchDelayAnalysis,
    CostDelayConfig,
    DelayAnalysis,
    DelayReason,
    DemandForecastItem,
    LiquidityState,
    MultiDelayComparison,
    PendingOrder,
    WasteRiskItem,
)
from app.services.bishop.costdelay_engine import costdelay_calculator

router = APIRouter(prefix="/costdelay", tags=["Cost of Delay"])


# =============================================================================
# DELAY ANALYSIS
# =============================================================================

@router.post("/analyze/{order_id}", response_model=DelayAnalysis)
async def analyze_delay(
    order_id: uuid.UUID,
    delay_hours: int = Query(24, ge=0, le=168),
    delay_reason: Optional[DelayReason] = None,
) -> dict:
    """
    Analyze the cost of delaying a specific order.
    
    Returns:
    - delay_hours: Proposed delay duration
    - cash_saved_now: Immediate savings from delay
    - risk_cost_later: Expected downstream costs
    - net_effect: Positive = delay beneficial
    """
    result = costdelay_calculator.analyze_delay(order_id, delay_hours, delay_reason)
    
    if not result:
        return {"error": "Order not found", "order_id": str(order_id)}
    
    return result.model_dump()


@router.post("/compare/{order_id}")
async def compare_delay_scenarios(
    order_id: uuid.UUID,
    delays: list[int] = Query(default=[0, 24, 48, 72]),
) -> dict:
    """
    Compare multiple delay scenarios for an order.
    
    Returns optimal delay duration and net effect.
    """
    result = costdelay_calculator.compare_delay_scenarios(order_id, delays)
    
    if not result:
        return {"error": "Order not found", "order_id": str(order_id)}
    
    return result.model_dump()


@router.post("/analyze-all")
async def analyze_all_orders(
    delay_hours: int = Query(24, ge=0, le=168),
) -> dict:
    """
    Analyze delaying all pending orders.
    
    Returns batch analysis with categorized recommendations.
    """
    result = costdelay_calculator.analyze_all_orders(delay_hours)
    return result.model_dump()


# =============================================================================
# ORDER REGISTRATION
# =============================================================================

@router.post("/order")
async def register_order(
    vendor_id: uuid.UUID,
    vendor_name: str,
    total_cost_dollars: str,
    priority: str = "normal",
    items: Optional[list[dict]] = None,
) -> dict:
    """
    Register a pending order for analysis.
    
    Items format: [{"product_id": uuid, "qty": number, "unit_cost": micros}, ...]
    """
    order = PendingOrder(
        vendor_id=vendor_id,
        vendor_name=vendor_name,
        total_cost_micros=Money.from_dollars(total_cost_dollars),
        priority=priority,
        items=items or [],
    )
    
    costdelay_calculator.register_order(order)
    
    return {
        "status": "registered",
        "order_id": str(order.order_id),
        "vendor": vendor_name,
        "total_cost": total_cost_dollars,
    }


@router.get("/orders")
async def get_pending_orders() -> dict:
    """Get all registered pending orders."""
    orders = list(costdelay_calculator._pending_orders.values())
    return {
        "count": len(orders),
        "orders": [
            {
                "order_id": str(o.order_id),
                "vendor": o.vendor_name,
                "total_micros": o.total_cost_micros,
                "priority": o.priority,
            }
            for o in orders
        ],
    }


# =============================================================================
# DEMAND FORECAST REGISTRATION
# =============================================================================

@router.post("/demand")
async def register_demand_forecast(
    product_id: uuid.UUID,
    product_name: str,
    current_inventory: Decimal,
    unit: str,
    daily_demand: Decimal,
    demand_confidence: Decimal = Decimal("0.80"),
) -> dict:
    """Register demand forecast for a product."""
    days_of_supply = current_inventory / daily_demand if daily_demand > 0 else Decimal("999")
    stockout_risk = Decimal("0")
    
    if days_of_supply < 1:
        stockout_risk = Decimal("0.80")
    elif days_of_supply < 3:
        stockout_risk = Decimal("0.50")
    elif days_of_supply < 7:
        stockout_risk = Decimal("0.20")
    
    forecast = DemandForecastItem(
        product_id=product_id,
        product_name=product_name,
        current_inventory=current_inventory,
        unit=unit,
        daily_demand=daily_demand,
        demand_confidence=demand_confidence,
        days_of_supply=days_of_supply,
        stockout_risk_pct=stockout_risk,
    )
    
    costdelay_calculator.register_demand_forecast(forecast)
    
    return {
        "status": "registered",
        "product": product_name,
        "days_of_supply": str(days_of_supply.quantize(Decimal("0.1"))),
        "stockout_risk_pct": str(stockout_risk * 100),
    }


# =============================================================================
# WASTE RISK REGISTRATION
# =============================================================================

@router.post("/waste-risk")
async def register_waste_risk(
    product_id: uuid.UUID,
    product_name: str,
    quantity_at_risk: Decimal,
    unit: str,
    value_at_risk_dollars: str,
    days_until_expiry: int = 0,
    waste_probability_pct: Decimal = Decimal("0"),
) -> dict:
    """Register waste risk for a product."""
    risk = WasteRiskItem(
        product_id=product_id,
        product_name=product_name,
        quantity_at_risk=quantity_at_risk,
        unit=unit,
        days_until_expiry=days_until_expiry,
        value_at_risk_micros=Money.from_dollars(value_at_risk_dollars),
        waste_probability_pct=waste_probability_pct,
    )
    
    costdelay_calculator.register_waste_risk(risk)
    
    return {
        "status": "registered",
        "product": product_name,
        "value_at_risk": value_at_risk_dollars,
    }


# =============================================================================
# LIQUIDITY STATE
# =============================================================================

@router.post("/liquidity")
async def update_liquidity(
    cash_balance_dollars: str,
    available_balance_dollars: Optional[str] = None,
    obligations_24h_dollars: str = "0",
    obligations_48h_dollars: str = "0",
    obligations_7d_dollars: str = "0",
    minimum_reserve_dollars: str = "50000",
    is_constrained: bool = False,
) -> dict:
    """Update current liquidity state."""
    cash = Money.from_dollars(cash_balance_dollars)
    available = Money.from_dollars(available_balance_dollars) if available_balance_dollars else cash
    
    state = LiquidityState(
        cash_balance_micros=cash,
        available_balance_micros=available,
        obligations_24h_micros=Money.from_dollars(obligations_24h_dollars),
        obligations_48h_micros=Money.from_dollars(obligations_48h_dollars),
        obligations_7d_micros=Money.from_dollars(obligations_7d_dollars),
        minimum_reserve_micros=Money.from_dollars(minimum_reserve_dollars),
        is_constrained=is_constrained,
    )
    
    costdelay_calculator.update_liquidity(state)
    
    return {
        "status": "updated",
        "available_balance": available_balance_dollars or cash_balance_dollars,
        "is_constrained": is_constrained,
    }


# =============================================================================
# CONFIGURATION
# =============================================================================

@router.get("/config", response_model=CostDelayConfig)
async def get_config() -> CostDelayConfig:
    """Get calculator configuration."""
    return costdelay_calculator.get_config()


@router.put("/config")
async def update_config(
    stockout_cost_multiplier: Optional[Decimal] = Query(None, ge=1),
    max_safe_delay_hours: Optional[int] = Query(None, ge=1),
    safe_days_of_supply: Optional[int] = Query(None, ge=1),
) -> CostDelayConfig:
    """Update calculator configuration."""
    config = costdelay_calculator.get_config()
    
    if stockout_cost_multiplier is not None:
        config.stockout_cost_multiplier = stockout_cost_multiplier
    if max_safe_delay_hours is not None:
        config.max_safe_delay_hours = max_safe_delay_hours
    if safe_days_of_supply is not None:
        config.safe_days_of_supply = safe_days_of_supply
    
    costdelay_calculator.configure(config)
    return config


@router.delete("/data/clear")
async def clear_data() -> dict:
    """Clear all data (for testing)."""
    costdelay_calculator.clear_data()
    return {"status": "cleared"}


# =============================================================================
# DEMO
# =============================================================================

@router.post("/demo/setup")
async def setup_demo() -> dict:
    """
    Set up demo data for cost of delay analysis.
    
    Creates sample orders, forecasts, and liquidity state.
    """
    costdelay_calculator.clear_data()
    
    # Product IDs
    chicken_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    beef_id = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    flour_id = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
    
    # Order 1: Protein order - critical (low inventory)
    order1 = PendingOrder(
        vendor_id=uuid.uuid4(),
        vendor_name="Sysco",
        total_cost_micros=Money.from_dollars("5000"),
        priority="high",
        items=[
            {"product_id": chicken_id, "qty": 100, "unit_cost": 30_000_000},
            {"product_id": beef_id, "qty": 50, "unit_cost": 40_000_000},
        ],
    )
    costdelay_calculator.register_order(order1)
    
    # Order 2: Dry goods - safe to delay
    order2 = PendingOrder(
        vendor_id=uuid.uuid4(),
        vendor_name="US Foods",
        total_cost_micros=Money.from_dollars("2000"),
        priority="normal",
        items=[
            {"product_id": flour_id, "qty": 200, "unit_cost": 10_000_000},
        ],
    )
    costdelay_calculator.register_order(order2)
    
    # Demand forecasts
    costdelay_calculator.register_demand_forecast(DemandForecastItem(
        product_id=chicken_id,
        product_name="Chicken Breast",
        current_inventory=Decimal("50"),
        unit="lb",
        daily_demand=Decimal("25"),
        days_of_supply=Decimal("2"),  # Critical!
        stockout_risk_pct=Decimal("0.50"),
    ))
    
    costdelay_calculator.register_demand_forecast(DemandForecastItem(
        product_id=beef_id,
        product_name="Ground Beef",
        current_inventory=Decimal("80"),
        unit="lb",
        daily_demand=Decimal("15"),
        days_of_supply=Decimal("5.3"),
        stockout_risk_pct=Decimal("0.15"),
    ))
    
    costdelay_calculator.register_demand_forecast(DemandForecastItem(
        product_id=flour_id,
        product_name="All-Purpose Flour",
        current_inventory=Decimal("300"),
        unit="lb",
        daily_demand=Decimal("20"),
        days_of_supply=Decimal("15"),  # Very safe
        stockout_risk_pct=Decimal("0.02"),
    ))
    
    # Liquidity - somewhat constrained
    costdelay_calculator.update_liquidity(LiquidityState(
        cash_balance_micros=Money.from_dollars("75000"),
        available_balance_micros=Money.from_dollars("60000"),
        obligations_24h_micros=Money.from_dollars("15000"),
        obligations_48h_micros=Money.from_dollars("25000"),
        obligations_7d_micros=Money.from_dollars("45000"),
        minimum_reserve_micros=Money.from_dollars("50000"),
        is_constrained=True,
    ))
    
    # Run analyses
    analysis1 = costdelay_calculator.analyze_delay(order1.order_id, 48)
    analysis2 = costdelay_calculator.analyze_delay(order2.order_id, 48)
    
    return {
        "status": "demo_data_created",
        "orders": [
            {
                "order_id": str(order1.order_id),
                "vendor": "Sysco",
                "value": "$5,000",
                "priority": "high",
                "products": ["Chicken Breast (2 days supply)", "Ground Beef"],
            },
            {
                "order_id": str(order2.order_id),
                "vendor": "US Foods",
                "value": "$2,000",
                "priority": "normal",
                "products": ["Flour (15 days supply)"],
            },
        ],
        "liquidity": {
            "available": "$60,000",
            "is_constrained": True,
        },
        "48h_delay_analysis": {
            "protein_order": {
                "cash_saved_now": str(analysis1.cash_saved_now) if analysis1 else None,
                "risk_cost_later": str(analysis1.risk_cost_later) if analysis1 else None,
                "net_effect": str(analysis1.net_effect) if analysis1 else None,
                "recommendation": analysis1.recommendation.value if analysis1 else None,
                "reason": analysis1.recommendation_reason if analysis1 else None,
            },
            "dry_goods_order": {
                "cash_saved_now": str(analysis2.cash_saved_now) if analysis2 else None,
                "risk_cost_later": str(analysis2.risk_cost_later) if analysis2 else None,
                "net_effect": str(analysis2.net_effect) if analysis2 else None,
                "recommendation": analysis2.recommendation.value if analysis2 else None,
                "reason": analysis2.recommendation_reason if analysis2 else None,
            },
        },
        "test_endpoints": [
            f"POST /costdelay/analyze/{order1.order_id}?delay_hours=24",
            f"POST /costdelay/compare/{order2.order_id}",
            "POST /costdelay/analyze-all?delay_hours=48",
        ],
    }

"""
PROVENIQ Ops - Salvage Bridge API Routes
Bishop asset disposition endpoints

Identify assets suitable for transfer, donation, or liquidation.
"""

import uuid
from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Query

from app.models.salvage import (
    BatchSalvageResult,
    ExpirationWindow,
    NetworkInventory,
    NetworkLocation,
    OverstockFlag,
    OverstockReason,
    SalvageConfig,
    SalvageRecommendation,
    AssetCondition,
)
from app.services.bishop.salvage_engine import salvage_bridge

router = APIRouter(prefix="/salvage", tags=["Salvage Bridge"])


# =============================================================================
# RECOMMENDATIONS
# =============================================================================

@router.get("/recommend/{item_id}", response_model=SalvageRecommendation)
async def recommend_disposition(item_id: uuid.UUID) -> dict:
    """
    Get salvage recommendation for an item.
    
    Returns:
    - recommended_path: TRANSFER | DONATE | LIQUIDATE
    - estimated_recovery: decimal (dollars)
    """
    result = salvage_bridge.recommend_disposition(item_id)
    
    if not result:
        return {"error": "Item not found or no salvage data", "item_id": str(item_id)}
    
    return result.model_dump()


@router.get("/recommend/{item_id}/simple")
async def recommend_disposition_simple(item_id: uuid.UUID) -> dict:
    """Get simplified salvage recommendation."""
    result = salvage_bridge.recommend_disposition(item_id)
    
    if not result:
        return {"error": "Item not found", "item_id": str(item_id)}
    
    return {
        "item_id": str(result.item_id),
        "recommended_path": result.recommended_path.value,
        "estimated_recovery": str(result.estimated_recovery),
        "recovery_rate_pct": str(result.recovery_rate_pct),
        "urgency_hours": result.urgency_hours,
        "reasoning": result.reasoning,
    }


@router.post("/analyze")
async def analyze_batch(
    item_ids: Optional[list[uuid.UUID]] = None,
) -> dict:
    """
    Analyze multiple items for salvage opportunities.
    
    If no item_ids provided, analyzes all flagged items.
    """
    result = salvage_bridge.analyze_batch(item_ids)
    return result.model_dump()


@router.get("/summary")
async def get_salvage_summary() -> dict:
    """Get summary of all salvage opportunities."""
    result = salvage_bridge.analyze_batch()
    
    return {
        "items_at_risk": result.items_analyzed,
        "total_at_risk_value": f"${result.total_at_risk_value_micros / 1_000_000:,.2f}",
        "potential_recovery": f"${result.total_estimated_recovery_micros / 1_000_000:,.2f}",
        "recovery_rate_pct": str(result.overall_recovery_rate_pct),
        "by_path": {
            "transfer": result.transfer_count,
            "donate": result.donate_count,
            "liquidate": result.liquidate_count,
            "repurpose": result.repurpose_count,
            "dispose": result.dispose_count,
        },
        "urgent_count": len(result.urgent_items),
    }


# =============================================================================
# OVERSTOCK REGISTRATION
# =============================================================================

@router.post("/overstock")
async def register_overstock(
    item_id: uuid.UUID,
    product_id: uuid.UUID,
    product_name: str,
    current_qty: Decimal,
    par_qty: Decimal,
    unit: str,
    unit_cost_dollars: str,
    location_id: uuid.UUID,
    location_name: str,
    reason: OverstockReason = OverstockReason.DEMAND_DROP,
    days_overstocked: int = 0,
) -> dict:
    """Register an overstock flag."""
    excess_qty = max(Decimal("0"), current_qty - par_qty)
    unit_cost_micros = int(Decimal(unit_cost_dollars) * 1_000_000)
    total_value = int(unit_cost_micros * float(excess_qty))
    
    flag = OverstockFlag(
        item_id=item_id,
        product_id=product_id,
        product_name=product_name,
        current_qty=current_qty,
        par_qty=par_qty,
        excess_qty=excess_qty,
        unit=unit,
        unit_cost_micros=unit_cost_micros,
        total_value_micros=total_value,
        location_id=location_id,
        location_name=location_name,
        reason=reason,
        days_overstocked=days_overstocked,
    )
    
    salvage_bridge.register_overstock(flag)
    
    return {
        "status": "registered",
        "item_id": str(item_id),
        "product": product_name,
        "excess_qty": str(excess_qty),
        "excess_value": f"${total_value / 1_000_000:,.2f}",
    }


# =============================================================================
# EXPIRATION REGISTRATION
# =============================================================================

@router.post("/expiration")
async def register_expiration(
    item_id: uuid.UUID,
    product_id: uuid.UUID,
    product_name: str,
    quantity: Decimal,
    unit: str,
    expiration_date: date,
    current_value_dollars: str,
    location_id: uuid.UUID,
    location_name: str,
) -> dict:
    """Register an expiration window."""
    days_until = (expiration_date - date.today()).days
    
    # Assess condition
    if days_until >= 14:
        condition = AssetCondition.EXCELLENT
    elif days_until >= 7:
        condition = AssetCondition.GOOD
    elif days_until >= 3:
        condition = AssetCondition.FAIR
    elif days_until >= 1:
        condition = AssetCondition.POOR
    else:
        condition = AssetCondition.CRITICAL
    
    window = ExpirationWindow(
        item_id=item_id,
        product_id=product_id,
        product_name=product_name,
        quantity=quantity,
        unit=unit,
        expiration_date=expiration_date,
        days_until_expiry=days_until,
        condition=condition,
        current_value_micros=int(Decimal(current_value_dollars) * 1_000_000),
        location_id=location_id,
        location_name=location_name,
    )
    
    salvage_bridge.register_expiration(window)
    
    return {
        "status": "registered",
        "item_id": str(item_id),
        "product": product_name,
        "days_until_expiry": days_until,
        "condition": condition.value,
    }


# =============================================================================
# NETWORK INVENTORY
# =============================================================================

@router.post("/network")
async def register_network_inventory(
    product_id: uuid.UUID,
    product_name: str,
    locations: list[dict],
) -> dict:
    """
    Register network inventory for transfer analysis.
    
    locations format: [
        {
            "location_id": uuid,
            "location_name": str,
            "current_inventory": decimal,
            "daily_demand": decimal,
            "can_accept": bool,
            "transfer_cost_dollars": str,
            "transfer_hours": int
        }
    ]
    """
    network_locations = []
    total_qty = Decimal("0")
    total_demand = Decimal("0")
    surplus = []
    deficit = []
    
    for loc in locations:
        loc_id = uuid.UUID(str(loc["location_id"]))
        inv = Decimal(str(loc.get("current_inventory", 0)))
        demand = Decimal(str(loc.get("daily_demand", 0)))
        days_supply = inv / demand if demand > 0 else Decimal("999")
        
        total_qty += inv
        total_demand += demand
        
        needs = days_supply < 7
        if days_supply > 14:
            surplus.append(loc_id)
        elif days_supply < 5:
            deficit.append(loc_id)
        
        network_locations.append(NetworkLocation(
            location_id=loc_id,
            location_name=loc["location_name"],
            current_inventory=inv,
            daily_demand=demand,
            days_of_supply=days_supply,
            needs_product=needs,
            can_accept=loc.get("can_accept", True),
            max_accept_qty=Decimal(str(loc.get("max_accept_qty"))) if loc.get("max_accept_qty") else None,
            transfer_cost_micros=int(Decimal(str(loc.get("transfer_cost_dollars", "0"))) * 1_000_000),
            transfer_hours=loc.get("transfer_hours", 4),
        ))
    
    network = NetworkInventory(
        product_id=product_id,
        product_name=product_name,
        total_network_qty=total_qty,
        total_network_demand=total_demand,
        locations=network_locations,
        surplus_locations=surplus,
        deficit_locations=deficit,
    )
    
    salvage_bridge.register_network_inventory(network)
    
    return {
        "status": "registered",
        "product": product_name,
        "locations": len(network_locations),
        "surplus_locations": len(surplus),
        "deficit_locations": len(deficit),
    }


# =============================================================================
# CONFIGURATION
# =============================================================================

@router.get("/config", response_model=SalvageConfig)
async def get_config() -> SalvageConfig:
    """Get salvage bridge configuration."""
    return salvage_bridge.get_config()


@router.put("/config")
async def update_config(
    min_transfer_recovery_pct: Optional[Decimal] = Query(None, ge=0, le=100),
    min_liquidation_recovery_pct: Optional[Decimal] = Query(None, ge=0, le=100),
    donation_tax_rate: Optional[Decimal] = Query(None, ge=0, le=1),
) -> SalvageConfig:
    """Update salvage configuration."""
    config = salvage_bridge.get_config()
    
    if min_transfer_recovery_pct is not None:
        config.min_transfer_recovery_pct = min_transfer_recovery_pct
    if min_liquidation_recovery_pct is not None:
        config.min_liquidation_recovery_pct = min_liquidation_recovery_pct
    if donation_tax_rate is not None:
        config.donation_tax_rate = donation_tax_rate
    
    salvage_bridge.configure(config)
    return config


@router.delete("/data/clear")
async def clear_data() -> dict:
    """Clear all data (for testing)."""
    salvage_bridge.clear_data()
    return {"status": "cleared"}


# =============================================================================
# DEMO
# =============================================================================

@router.post("/demo/setup")
async def setup_demo() -> dict:
    """
    Set up demo data for salvage bridge testing.
    
    Creates sample overstock and expiring items.
    """
    salvage_bridge.clear_data()
    
    today = date.today()
    
    # Location IDs
    main_loc = uuid.UUID("11111111-1111-1111-1111-111111111111")
    branch_a = uuid.UUID("22222222-2222-2222-2222-222222222222")
    branch_b = uuid.UUID("33333333-3333-3333-3333-333333333333")
    
    # Product IDs
    chicken_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    produce_id = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    dry_goods_id = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
    
    # Item 1: Chicken - overstock, good condition, transfer opportunity
    chicken_item = uuid.UUID("11111111-aaaa-aaaa-aaaa-111111111111")
    salvage_bridge.register_overstock(OverstockFlag(
        item_id=chicken_item,
        product_id=chicken_id,
        product_name="Chicken Breast",
        current_qty=Decimal("150"),
        par_qty=Decimal("80"),
        excess_qty=Decimal("70"),
        unit="lb",
        unit_cost_micros=5_500_000,  # $5.50/lb
        total_value_micros=385_000_000,  # $385
        location_id=main_loc,
        location_name="Main Kitchen",
        reason=OverstockReason.OVER_ORDER,
        days_overstocked=3,
    ))
    
    # Network for chicken - branch B needs it
    salvage_bridge.register_network_inventory(NetworkInventory(
        product_id=chicken_id,
        product_name="Chicken Breast",
        total_network_qty=Decimal("200"),
        total_network_demand=Decimal("40"),
        locations=[
            NetworkLocation(
                location_id=main_loc,
                location_name="Main Kitchen",
                current_inventory=Decimal("150"),
                daily_demand=Decimal("15"),
                days_of_supply=Decimal("10"),
                needs_product=False,
                can_accept=False,
            ),
            NetworkLocation(
                location_id=branch_a,
                location_name="Branch A",
                current_inventory=Decimal("30"),
                daily_demand=Decimal("12"),
                days_of_supply=Decimal("2.5"),
                needs_product=True,
                can_accept=True,
                max_accept_qty=Decimal("50"),
                transfer_cost_micros=25_000_000,  # $25
                transfer_hours=2,
            ),
            NetworkLocation(
                location_id=branch_b,
                location_name="Branch B",
                current_inventory=Decimal("20"),
                daily_demand=Decimal("13"),
                days_of_supply=Decimal("1.5"),
                needs_product=True,
                can_accept=True,
                max_accept_qty=Decimal("60"),
                transfer_cost_micros=35_000_000,  # $35
                transfer_hours=3,
            ),
        ],
        surplus_locations=[main_loc],
        deficit_locations=[branch_a, branch_b],
    ))
    
    # Item 2: Produce - expiring soon, donation candidate
    produce_item = uuid.UUID("22222222-bbbb-bbbb-bbbb-222222222222")
    from datetime import timedelta
    salvage_bridge.register_expiration(ExpirationWindow(
        item_id=produce_item,
        product_id=produce_id,
        product_name="Mixed Greens",
        quantity=Decimal("25"),
        unit="lb",
        expiration_date=today + timedelta(days=3),
        days_until_expiry=3,
        condition=AssetCondition.FAIR,
        current_value_micros=75_000_000,  # $75
        location_id=main_loc,
        location_name="Main Kitchen",
    ))
    
    # Item 3: Dry goods - overstock, liquidation candidate
    dry_item = uuid.UUID("33333333-cccc-cccc-cccc-333333333333")
    salvage_bridge.register_overstock(OverstockFlag(
        item_id=dry_item,
        product_id=dry_goods_id,
        product_name="Specialty Sauce",
        current_qty=Decimal("48"),
        par_qty=Decimal("12"),
        excess_qty=Decimal("36"),
        unit="bottles",
        unit_cost_micros=8_000_000,  # $8/bottle
        total_value_micros=288_000_000,  # $288
        location_id=main_loc,
        location_name="Main Kitchen",
        reason=OverstockReason.MENU_CHANGE,
        days_overstocked=14,
    ))
    
    # Analyze all
    result = salvage_bridge.analyze_batch()
    
    recommendations = []
    for rec in result.recommendations:
        recommendations.append({
            "product": rec.product_name,
            "recommended_path": rec.recommended_path.value,
            "estimated_recovery": f"${rec.estimated_recovery:,.2f}",
            "recovery_rate": f"{rec.recovery_rate_pct:.0f}%",
            "reasoning": rec.reasoning,
        })
    
    return {
        "status": "demo_data_created",
        "items_created": 3,
        "items": [
            {
                "name": "Chicken Breast",
                "situation": "70 lb overstock",
                "value_at_risk": "$385",
            },
            {
                "name": "Mixed Greens",
                "situation": "Expires in 3 days",
                "value_at_risk": "$75",
            },
            {
                "name": "Specialty Sauce",
                "situation": "36 bottles overstock (menu change)",
                "value_at_risk": "$288",
            },
        ],
        "analysis": {
            "total_at_risk": f"${result.total_at_risk_value_micros / 1_000_000:,.2f}",
            "potential_recovery": f"${result.total_estimated_recovery_micros / 1_000_000:,.2f}",
            "recovery_rate": f"{result.overall_recovery_rate_pct:.1f}%",
        },
        "recommendations": recommendations,
    }

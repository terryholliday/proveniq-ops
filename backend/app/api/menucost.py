"""
PROVENIQ Ops - Cost Per Serving API Routes
Bishop menu profitability endpoints

DAG Nodes: N17, N37

GUARDRAILS:
- Do not suggest menu price changes unless enabled
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Query

from app.core.types import Money
from app.models.menucost import (
    Ingredient,
    IngredientCostImpact,
    MarginAlert,
    MarginStatus,
    MenuCostAnalysis,
    MenuCostConfig,
    MenuItem,
    Recipe,
    RecipeIngredient,
    UnitOfMeasure,
)
from app.services.bishop.menucost_engine import menucost_engine

router = APIRouter(prefix="/menucost", tags=["Cost Per Serving"])


# =============================================================================
# ANALYSIS
# =============================================================================

@router.post("/analyze", response_model=MenuCostAnalysis)
async def analyze_menu_costs() -> MenuCostAnalysis:
    """
    Analyze all menu items for cost and margin status.
    
    Bishop Logic (N17/N37):
        1. Calculate rolling cost-per-serving
        2. Detect margin compression
        3. Flag threshold breaches
    
    GUARDRAILS:
        - Price suggestions only if explicitly enabled
    """
    return menucost_engine.analyze_menu_costs()


@router.post("/recalculate")
async def recalculate_costs() -> dict:
    """
    Recalculate all recipe and menu item costs.
    
    Call after ingredient cost updates to refresh margins.
    """
    menucost_engine.recalculate_all_costs()
    return {"status": "recalculated", "timestamp": datetime.utcnow().isoformat()}


@router.get("/ingredient/{ingredient_id}/impact", response_model=IngredientCostImpact)
async def analyze_ingredient_impact(ingredient_id: uuid.UUID) -> IngredientCostImpact:
    """
    Analyze impact of ingredient cost change across the menu.
    
    Shows which menu items are affected and total margin impact.
    """
    impact = menucost_engine.analyze_ingredient_impact(ingredient_id)
    if not impact:
        return IngredientCostImpact(
            ingredient_id=ingredient_id,
            ingredient_name="Not found",
            previous_cost_micros=0,
            current_cost_micros=0,
            change_percent=Decimal("0"),
            affected_items=0,
            total_margin_impact_micros=0,
        )
    return impact


# =============================================================================
# MENU ITEMS
# =============================================================================

@router.get("/items")
async def get_menu_items() -> dict:
    """Get all menu items sorted by margin (highest first)."""
    items = menucost_engine.get_all_menu_items()
    return {
        "total": len(items),
        "items": [i.model_dump() for i in items],
    }


@router.get("/items/{menu_item_id}")
async def get_menu_item(menu_item_id: uuid.UUID) -> dict:
    """Get a specific menu item with cost details."""
    item = menucost_engine.get_menu_item(menu_item_id)
    if not item:
        return {"error": "Menu item not found"}
    return item.model_dump()


@router.get("/items/status/{status}")
async def get_items_by_status(status: MarginStatus) -> dict:
    """Get menu items by margin status."""
    items = menucost_engine.get_items_by_status(status)
    return {
        "status": status.value,
        "count": len(items),
        "items": [i.model_dump() for i in items],
    }


@router.get("/items/critical")
async def get_critical_items() -> dict:
    """Get menu items with critical or negative margins."""
    critical = menucost_engine.get_items_by_status(MarginStatus.CRITICAL)
    negative = menucost_engine.get_items_by_status(MarginStatus.NEGATIVE)
    
    all_critical = critical + negative
    total_exposure = sum(i.cost_per_serving_micros for i in all_critical)
    
    return {
        "critical_count": len(critical),
        "negative_count": len(negative),
        "total_items": len(all_critical),
        "items": [i.model_dump() for i in all_critical],
    }


# =============================================================================
# ALERTS
# =============================================================================

@router.get("/alerts", response_model=list[MarginAlert])
async def get_alerts(limit: int = Query(100, ge=1, le=1000)) -> list[MarginAlert]:
    """Get margin alerts."""
    return menucost_engine.get_alerts(limit=limit)


# =============================================================================
# CONFIGURATION
# =============================================================================

@router.get("/config", response_model=MenuCostConfig)
async def get_config() -> MenuCostConfig:
    """Get current menu cost configuration."""
    return menucost_engine.get_config()


@router.put("/config")
async def update_config(
    margin_warning_percent: Optional[Decimal] = Query(None, ge=0, le=100),
    margin_critical_percent: Optional[Decimal] = Query(None, ge=0, le=100),
    cost_change_alert_percent: Optional[Decimal] = Query(None, ge=0, le=100),
    price_suggestions_enabled: Optional[bool] = None,
) -> MenuCostConfig:
    """
    Update menu cost configuration.
    
    GUARDRAIL: price_suggestions_enabled is off by default.
    """
    config = menucost_engine.get_config()
    
    if margin_warning_percent is not None:
        config.margin_warning_percent = margin_warning_percent
    if margin_critical_percent is not None:
        config.margin_critical_percent = margin_critical_percent
    if cost_change_alert_percent is not None:
        config.cost_change_alert_percent = cost_change_alert_percent
    if price_suggestions_enabled is not None:
        config.price_suggestions_enabled = price_suggestions_enabled
    
    menucost_engine.configure(config)
    return config


# =============================================================================
# DATA REGISTRATION
# =============================================================================

@router.post("/data/ingredient")
async def register_ingredient(
    product_id: uuid.UUID,
    name: str,
    canonical_sku: str,
    purchase_unit: UnitOfMeasure,
    purchase_qty: Decimal,
    cost_dollars: str,
) -> dict:
    """Register an ingredient with current cost."""
    ingredient = Ingredient(
        product_id=product_id,
        name=name,
        canonical_sku=canonical_sku,
        purchase_unit=purchase_unit,
        purchase_qty=purchase_qty,
        current_cost_micros=Money.from_dollars(cost_dollars),
        cost_per_unit_micros=0,  # Calculated on registration
    )
    menucost_engine.register_ingredient(ingredient)
    return {
        "status": "registered",
        "ingredient_id": str(ingredient.ingredient_id),
        "name": name,
        "cost_per_unit_micros": ingredient.cost_per_unit_micros,
    }


@router.put("/data/ingredient/{ingredient_id}/cost")
async def update_ingredient_cost(
    ingredient_id: uuid.UUID,
    cost_dollars: str,
) -> dict:
    """Update ingredient cost (e.g., from new invoice)."""
    ingredient = menucost_engine.update_ingredient_cost(
        ingredient_id,
        Money.from_dollars(cost_dollars),
    )
    if not ingredient:
        return {"error": "Ingredient not found"}
    
    return {
        "status": "updated",
        "ingredient_id": str(ingredient_id),
        "new_cost_micros": ingredient.current_cost_micros,
        "cost_trend": ingredient.cost_trend,
    }


@router.post("/data/menu-item")
async def register_menu_item(
    name: str,
    category: str,
    menu_price_dollars: str,
    cost_per_serving_dollars: str,
    target_margin_percent: Decimal = Decimal("65"),
    recipe_id: Optional[uuid.UUID] = None,
) -> dict:
    """Register a menu item."""
    item = MenuItem(
        name=name,
        category=category,
        menu_price_micros=Money.from_dollars(menu_price_dollars),
        cost_per_serving_micros=Money.from_dollars(cost_per_serving_dollars),
        gross_margin_micros=0,
        gross_margin_percent=Decimal("0"),
        margin_status=MarginStatus.HEALTHY,
        target_margin_percent=target_margin_percent,
        recipe_id=recipe_id,
    )
    menucost_engine.register_menu_item(item)
    return {
        "status": "registered",
        "menu_item_id": str(item.menu_item_id),
        "name": name,
        "margin_percent": str(item.gross_margin_percent),
        "margin_status": item.margin_status.value,
    }


@router.delete("/data/clear")
async def clear_data() -> dict:
    """Clear all menu cost data (for testing)."""
    menucost_engine.clear_data()
    return {"status": "cleared"}


# =============================================================================
# DEMO DATA
# =============================================================================

@router.post("/demo/setup")
async def setup_demo_data() -> dict:
    """
    Set up demo data for menu cost testing.
    
    Creates sample ingredients, recipes, and menu items.
    """
    menucost_engine.clear_data()
    
    # Register ingredients
    ingredients = [
        ("Chicken Breast", "CHK-BRST-LB", UnitOfMeasure.LB, Decimal("1"), "4.99"),
        ("Mixed Greens", "PROD-GREENS-LB", UnitOfMeasure.LB, Decimal("1"), "3.99"),
        ("Caesar Dressing", "DRESS-CAESAR-GAL", UnitOfMeasure.GAL, Decimal("1"), "12.99"),
        ("Croutons", "BREAD-CROUTON-LB", UnitOfMeasure.LB, Decimal("1"), "2.49"),
        ("Parmesan", "CHEESE-PARM-LB", UnitOfMeasure.LB, Decimal("1"), "14.99"),
        ("Salmon Fillet", "FISH-SALMON-LB", UnitOfMeasure.LB, Decimal("1"), "12.99"),
        ("Rice", "RICE-LB", UnitOfMeasure.LB, Decimal("1"), "0.89"),
        ("Broccoli", "PROD-BROC-LB", UnitOfMeasure.LB, Decimal("1"), "2.49"),
        ("Burger Patty", "BEEF-PATTY-EA", UnitOfMeasure.EACH, Decimal("1"), "2.25"),
        ("Burger Bun", "BREAD-BUN-EA", UnitOfMeasure.EACH, Decimal("1"), "0.35"),
        ("Fries", "POTATO-FRIES-LB", UnitOfMeasure.LB, Decimal("1"), "1.89"),
    ]
    
    ingredient_ids = {}
    for name, sku, unit, qty, cost in ingredients:
        ing = Ingredient(
            product_id=uuid.uuid4(),
            name=name,
            canonical_sku=sku,
            purchase_unit=unit,
            purchase_qty=qty,
            current_cost_micros=Money.from_dollars(cost),
            cost_per_unit_micros=0,
        )
        menucost_engine.register_ingredient(ing)
        ingredient_ids[name] = ing.ingredient_id
    
    # Register menu items with costs
    menu_items = [
        # Healthy margin
        {
            "name": "Caesar Salad",
            "category": "Salads",
            "price": "12.99",
            "cost": "3.50",
            "target": Decimal("70"),
        },
        # Healthy margin
        {
            "name": "Grilled Chicken Salad",
            "category": "Salads",
            "price": "15.99",
            "cost": "5.25",
            "target": Decimal("65"),
        },
        # Warning margin (cost spike simulated)
        {
            "name": "Grilled Salmon",
            "category": "Entrees",
            "price": "24.99",
            "cost": "11.50",  # High cost due to salmon price
            "target": Decimal("60"),
        },
        # Critical margin
        {
            "name": "Surf & Turf",
            "category": "Entrees",
            "price": "34.99",
            "cost": "19.50",  # Very high cost
            "target": Decimal("55"),
        },
        # Healthy margin
        {
            "name": "Classic Burger",
            "category": "Burgers",
            "price": "14.99",
            "cost": "4.25",
            "target": Decimal("70"),
        },
        # Warning - cost creep
        {
            "name": "Gourmet Burger",
            "category": "Burgers",
            "price": "18.99",
            "cost": "8.50",
            "target": Decimal("60"),
        },
    ]
    
    for item in menu_items:
        mi = MenuItem(
            name=item["name"],
            category=item["category"],
            menu_price_micros=Money.from_dollars(item["price"]),
            cost_per_serving_micros=Money.from_dollars(item["cost"]),
            gross_margin_micros=0,
            gross_margin_percent=Decimal("0"),
            margin_status=MarginStatus.HEALTHY,
            target_margin_percent=item["target"],
        )
        menucost_engine.register_menu_item(mi)
    
    # Run analysis
    analysis = menucost_engine.analyze_menu_costs()
    
    return {
        "status": "demo_data_created",
        "ingredients": len(ingredients),
        "menu_items": len(menu_items),
        "analysis_summary": {
            "healthy": analysis.healthy_count,
            "warning": analysis.warning_count,
            "critical": analysis.critical_count,
            "avg_margin": str(analysis.avg_margin_percent),
        },
        "expected_alerts": [
            "Grilled Salmon: 54% margin → WARNING",
            "Surf & Turf: 44% margin → CRITICAL",
            "Gourmet Burger: 55% margin → WARNING (at threshold)",
        ],
    }

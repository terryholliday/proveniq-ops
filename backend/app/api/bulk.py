"""
PROVENIQ Ops - Bulk Normalization API Routes
Bishop Canonical Unit Model endpoints

DAG Node: N5 - Bulk Normalization Engine

UX PHILOSOPHY:
Instead of asking "How many units?", Bishop asks "What do you observe?"
Then guided inputs, never raw math.

THREE METHODS:
1. 🧺 Count containers
2. ⚖️ Weigh it
3. 🧠 Let Bishop estimate from usage
"""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Query

from app.models.units import (
    BaseUnit,
    BulkItemConfig,
    ConfidenceDecayConfig,
    ContainerCountInput,
    DirectWeightInput,
    HandlingUnit,
    HandlingUnitType,
    MeasurementMethod,
    NormalizedQuantity,
    PartialContainer,
    RecipeDepletionInput,
    UnitCategory,
    VerificationRequest,
    VolumeEstimateInput,
)
from app.services.bishop.bulk_engine import bulk_engine

router = APIRouter(prefix="/bulk", tags=["Bulk Normalization"])


# =============================================================================
# COUNTING METHODS
# =============================================================================

@router.post("/count/containers", response_model=NormalizedQuantity)
async def count_by_containers(
    product_id: uuid.UUID,
    full_containers: int,
    partial_containers: Optional[list[dict]] = None,
    measured_by: Optional[str] = None,
) -> NormalizedQuantity:
    """
    Method 1: Container Count × Standard Weight (fastest, default)
    
    UX Example:
        How many full bags? [3]
        Any partial bag? [Slider: 50%]
    
    Bishop calculation:
        3 × 50 lb = 150 lb
        + (0.5 × 50 lb) = 25 lb
        Total = 175 lb
        Confidence = 0.92
    """
    partials = []
    if partial_containers:
        for p in partial_containers:
            partials.append(PartialContainer(
                fullness_pct=Decimal(str(p.get("fullness_pct", 50))),
                estimated_quantity=Decimal("0"),
                was_weighed=p.get("was_weighed", False),
                actual_weight=Decimal(str(p["actual_weight"])) if p.get("actual_weight") else None,
            ))
    
    input_data = ContainerCountInput(
        full_containers=full_containers,
        partial_containers=partials,
    )
    
    return bulk_engine.normalize_container_count(product_id, input_data, measured_by)


@router.post("/count/weight", response_model=NormalizedQuantity)
async def count_by_weight(
    product_id: uuid.UUID,
    gross_weight: Decimal,
    weight_unit: BaseUnit,
    container_count: int = 1,
    include_tare: bool = True,
    tare_override: Optional[Decimal] = None,
    measured_by: Optional[str] = None,
) -> NormalizedQuantity:
    """
    Method 2: Weigh What's There (highest accuracy)
    
    UX Example:
        Weighed bin: [18.4] lb
        Include container weight? [Yes]
    
    Bishop calculation:
        18.4 − 2.1 (tare) = 16.3 lb net
        Confidence = 0.99
    
    Used for:
        - High-value items (meat, alcohol)
        - End-of-period reconciliation
        - Shrinkage investigations
    """
    input_data = DirectWeightInput(
        gross_weight=gross_weight,
        weight_unit=weight_unit,
        container_count=container_count,
        include_container_tare=include_tare,
        tare_weight_override=tare_override,
    )
    
    return bulk_engine.normalize_direct_weight(product_id, input_data, measured_by)


@router.post("/count/depletion", response_model=NormalizedQuantity)
async def count_by_depletion(
    product_id: uuid.UUID,
    last_known_quantity: Decimal,
    last_known_unit: BaseUnit,
    last_known_at: datetime,
    servings_since: int,
    usage_per_serving: Decimal,
    usage_unit: BaseUnit,
    measured_by: Optional[str] = None,
) -> NormalizedQuantity:
    """
    Method 3: Depletion by Usage (recipe-driven projection)
    
    KEY RULE: This is a PROJECTION, not reality.
    Bishop labels it clearly and will:
        - Downgrade confidence
        - Trigger verification sooner
    
    Bishop calculation:
        Last known flour = 200 lb
        Usage since = 180 plates × 0.18 lb
        Usage = 32.4 lb
        Remaining = 167.6 lb
        Confidence = 0.74
    """
    input_data = RecipeDepletionInput(
        last_known_quantity=last_known_quantity,
        last_known_unit=last_known_unit,
        last_known_at=last_known_at,
        servings_since_last_count=servings_since,
        usage_per_serving=usage_per_serving,
        usage_unit=usage_unit,
    )
    
    return bulk_engine.normalize_recipe_depletion(product_id, input_data, measured_by)


@router.post("/count/volume", response_model=NormalizedQuantity)
async def count_by_volume(
    product_id: uuid.UUID,
    container_capacity: Decimal,
    container_unit: BaseUnit,
    fill_level_pct: Decimal,
    container_count: int = 1,
    measured_by: Optional[str] = None,
) -> NormalizedQuantity:
    """
    Volume estimation for liquids.
    Confidence capped unless weighed.
    
    For irregular containers, use fill level markings or estimate.
    """
    input_data = VolumeEstimateInput(
        container_capacity=container_capacity,
        container_unit=container_unit,
        fill_level_pct=fill_level_pct,
        container_count=container_count,
    )
    
    return bulk_engine.normalize_volume_estimate(product_id, input_data, measured_by)


# =============================================================================
# INVENTORY QUERY
# =============================================================================

@router.get("/inventory/{product_id}", response_model=NormalizedQuantity)
async def get_inventory(product_id: uuid.UUID) -> dict:
    """Get current normalized inventory for a product."""
    # Apply decay first
    bulk_engine.apply_confidence_decay(product_id)
    
    qty = bulk_engine.get_inventory(product_id)
    if not qty:
        return {"error": "No inventory data for product", "product_id": str(product_id)}
    
    return qty.model_dump()


@router.get("/inventory")
async def get_all_inventory() -> dict:
    """Get all normalized inventory with confidence scores."""
    inventory = bulk_engine.get_all_inventory()
    
    # Apply decay to all
    for product_id in inventory.keys():
        bulk_engine.apply_confidence_decay(product_id)
    
    return {
        "total_items": len(inventory),
        "inventory": {
            str(pid): qty.model_dump() for pid, qty in inventory.items()
        },
    }


@router.get("/inventory/low-confidence")
async def get_low_confidence_items(
    threshold: Decimal = Query(Decimal("0.70"), ge=0, le=1),
) -> dict:
    """
    Get items with confidence below threshold.
    
    THE SECRET WEAPON: Prevents false certainty.
    """
    items = bulk_engine.get_low_confidence_items(threshold)
    
    return {
        "threshold": str(threshold),
        "count": len(items),
        "items": [
            {
                "product_id": str(pid),
                "quantity": str(qty.quantity_base_units),
                "unit": qty.base_unit.value,
                "confidence": str(qty.confidence),
                "method": qty.measurement_method.value,
                "measured_at": qty.measured_at.isoformat(),
            }
            for pid, qty in items
        ],
    }


# =============================================================================
# VERIFICATION REQUESTS
# =============================================================================

@router.get("/verifications")
async def get_verification_requests(
    priority: Optional[str] = None,
) -> dict:
    """Get pending verification requests."""
    requests = bulk_engine.get_verification_requests(priority)
    
    return {
        "count": len(requests),
        "requests": [r.model_dump() for r in requests],
    }


@router.post("/verifications/{request_id}/complete")
async def complete_verification(request_id: uuid.UUID) -> dict:
    """Mark a verification request as complete."""
    success = bulk_engine.complete_verification(request_id)
    return {"status": "completed" if success else "not_found"}


# =============================================================================
# ITEM CONFIGURATION
# =============================================================================

@router.post("/config/item")
async def register_item_config(
    product_id: uuid.UUID,
    product_name: str,
    canonical_sku: str,
    base_unit: BaseUnit,
    handling_unit_type: HandlingUnitType,
    handling_unit_name: str,
    standard_quantity: Decimal,
    container_tare_weight: Optional[Decimal] = None,
    is_regulated: bool = False,
    force_weigh: bool = False,
    usage_per_serving: Optional[Decimal] = None,
) -> dict:
    """Register bulk item configuration."""
    handling = HandlingUnit(
        unit_type=handling_unit_type,
        display_name=handling_unit_name,
        base_unit=base_unit,
        standard_quantity=standard_quantity,
        container_tare_weight=container_tare_weight,
        container_tare_unit=base_unit if container_tare_weight else None,
    )
    
    # Determine unit category
    if base_unit in (BaseUnit.GRAMS, BaseUnit.KILOGRAMS, BaseUnit.POUNDS, BaseUnit.OUNCES):
        category = UnitCategory.WEIGHT
    elif base_unit in (BaseUnit.MILLILITERS, BaseUnit.LITERS, BaseUnit.FLUID_OUNCES, BaseUnit.GALLONS):
        category = UnitCategory.VOLUME
    else:
        category = UnitCategory.COUNT
    
    # Determine allowed methods
    allowed = [MeasurementMethod.CONTAINER_COUNT, MeasurementMethod.DIRECT_WEIGHT]
    if usage_per_serving:
        allowed.append(MeasurementMethod.RECIPE_DEPLETION)
    if category == UnitCategory.VOLUME:
        allowed.append(MeasurementMethod.VOLUME_ESTIMATE)
    if is_regulated:
        allowed = [MeasurementMethod.DIRECT_WEIGHT, MeasurementMethod.DUAL_VERIFICATION]
    
    config = BulkItemConfig(
        product_id=product_id,
        product_name=product_name,
        canonical_sku=canonical_sku,
        base_unit=base_unit,
        unit_category=category,
        primary_handling_unit=handling,
        allowed_methods=allowed,
        default_method=MeasurementMethod.DIRECT_WEIGHT if force_weigh else MeasurementMethod.CONTAINER_COUNT,
        is_regulated=is_regulated,
        force_weigh_method=force_weigh,
        usage_per_serving=usage_per_serving,
        usage_unit=base_unit if usage_per_serving else None,
    )
    
    bulk_engine.register_item_config(config)
    
    return {
        "status": "registered",
        "product_id": str(product_id),
        "product_name": product_name,
        "base_unit": base_unit.value,
        "handling_unit": handling_unit_name,
        "allowed_methods": [m.value for m in allowed],
    }


@router.get("/config/item/{product_id}")
async def get_item_config(product_id: uuid.UUID) -> dict:
    """Get item configuration."""
    config = bulk_engine.get_item_config(product_id)
    if not config:
        return {"error": "No configuration for product", "product_id": str(product_id)}
    return config.model_dump()


@router.delete("/data/clear")
async def clear_data() -> dict:
    """Clear all bulk normalization data (for testing)."""
    bulk_engine.clear_data()
    return {"status": "cleared"}


# =============================================================================
# UNIT CONVERSION
# =============================================================================

@router.get("/convert")
async def convert_units(
    quantity: Decimal,
    from_unit: BaseUnit,
    to_unit: BaseUnit,
) -> dict:
    """Convert between compatible base units."""
    try:
        result = bulk_engine.convert_units(quantity, from_unit, to_unit)
        return {
            "input": str(quantity),
            "from_unit": from_unit.value,
            "result": str(result),
            "to_unit": to_unit.value,
        }
    except ValueError as e:
        return {"error": str(e)}


# =============================================================================
# DEMO DATA
# =============================================================================

@router.post("/demo/setup")
async def setup_demo_data() -> dict:
    """
    Set up demo data for Canonical Unit Model testing.
    
    Creates sample bulk items with different measurement methods.
    """
    bulk_engine.clear_data()
    
    now = datetime.utcnow()
    
    # 1. Flour - typical bulk item (container count)
    flour_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    flour_handling = HandlingUnit(
        unit_type=HandlingUnitType.BAG,
        display_name="50 lb flour bag",
        base_unit=BaseUnit.POUNDS,
        standard_quantity=Decimal("50"),
        variance_allowed_pct=Decimal("2"),
        container_tare_weight=Decimal("0.5"),
        container_tare_unit=BaseUnit.POUNDS,
    )
    flour_config = BulkItemConfig(
        product_id=flour_id,
        product_name="All-Purpose Flour",
        canonical_sku="FLOUR-AP-50LB",
        base_unit=BaseUnit.POUNDS,
        unit_category=UnitCategory.WEIGHT,
        primary_handling_unit=flour_handling,
        allowed_methods=[
            MeasurementMethod.CONTAINER_COUNT,
            MeasurementMethod.DIRECT_WEIGHT,
            MeasurementMethod.RECIPE_DEPLETION,
        ],
        usage_per_serving=Decimal("0.18"),
        usage_unit=BaseUnit.POUNDS,
    )
    bulk_engine.register_item_config(flour_config)
    
    # 2. Olive Oil - liquid (volume estimate or weight)
    oil_id = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    oil_handling = HandlingUnit(
        unit_type=HandlingUnitType.CONTAINER,
        display_name="1 gallon jug",
        base_unit=BaseUnit.GALLONS,
        standard_quantity=Decimal("1"),
        container_tare_weight=Decimal("0.3"),
        container_tare_unit=BaseUnit.POUNDS,
    )
    oil_config = BulkItemConfig(
        product_id=oil_id,
        product_name="Extra Virgin Olive Oil",
        canonical_sku="OIL-OLV-1G",
        base_unit=BaseUnit.GALLONS,
        unit_category=UnitCategory.VOLUME,
        primary_handling_unit=oil_handling,
        allowed_methods=[
            MeasurementMethod.CONTAINER_COUNT,
            MeasurementMethod.VOLUME_ESTIMATE,
            MeasurementMethod.DIRECT_WEIGHT,
        ],
    )
    bulk_engine.register_item_config(oil_config)
    
    # 3. Cooking Wine - REGULATED (force weigh)
    wine_id = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
    wine_handling = HandlingUnit(
        unit_type=HandlingUnitType.BOTTLE,
        display_name="750ml bottle",
        base_unit=BaseUnit.MILLILITERS,
        standard_quantity=Decimal("750"),
    )
    wine_config = BulkItemConfig(
        product_id=wine_id,
        product_name="Cooking Wine",
        canonical_sku="WINE-COOK-750",
        base_unit=BaseUnit.MILLILITERS,
        unit_category=UnitCategory.VOLUME,
        primary_handling_unit=wine_handling,
        is_regulated=True,
        force_weigh_method=True,
        allowed_methods=[MeasurementMethod.DIRECT_WEIGHT, MeasurementMethod.DUAL_VERIFICATION],
    )
    bulk_engine.register_item_config(wine_config)
    
    # 4. Ground Beef - high value (recommend weigh)
    beef_id = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
    beef_handling = HandlingUnit(
        unit_type=HandlingUnitType.CONTAINER,
        display_name="5 lb chub",
        base_unit=BaseUnit.POUNDS,
        standard_quantity=Decimal("5"),
        container_tare_weight=Decimal("0.1"),
        container_tare_unit=BaseUnit.POUNDS,
    )
    beef_config = BulkItemConfig(
        product_id=beef_id,
        product_name="Ground Beef 80/20",
        canonical_sku="BEEF-GND-5LB",
        base_unit=BaseUnit.POUNDS,
        unit_category=UnitCategory.WEIGHT,
        primary_handling_unit=beef_handling,
        force_weigh_method=True,
        allowed_methods=[MeasurementMethod.DIRECT_WEIGHT, MeasurementMethod.CONTAINER_COUNT],
    )
    bulk_engine.register_item_config(beef_config)
    
    # Demo counts
    # Flour: 3 full bags + 1 half bag via container count
    flour_input = ContainerCountInput(
        full_containers=3,
        partial_containers=[PartialContainer(fullness_pct=Decimal("50"), estimated_quantity=Decimal("0"))],
    )
    flour_result = bulk_engine.normalize_container_count(flour_id, flour_input, "demo_user")
    
    # Oil: 2 full gallons + 1 at 75% via volume estimate
    oil_input = VolumeEstimateInput(
        container_capacity=Decimal("1"),
        container_unit=BaseUnit.GALLONS,
        fill_level_pct=Decimal("75"),
        container_count=1,
    )
    # First count full containers
    oil_full = ContainerCountInput(full_containers=2, partial_containers=[])
    bulk_engine.normalize_container_count(oil_id, oil_full, "demo_user")
    
    # Wine: Weighed at 2.1 kg gross
    wine_input = DirectWeightInput(
        gross_weight=Decimal("2100"),
        weight_unit=BaseUnit.GRAMS,
        container_count=3,
        include_container_tare=False,
    )
    wine_result = bulk_engine.normalize_direct_weight(wine_id, wine_input, "demo_user")
    
    # Beef: Recipe depletion (projected)
    beef_input = RecipeDepletionInput(
        last_known_quantity=Decimal("25"),
        last_known_unit=BaseUnit.POUNDS,
        last_known_at=now - timedelta(hours=8),
        servings_since_last_count=45,
        usage_per_serving=Decimal("0.33"),
        usage_unit=BaseUnit.POUNDS,
    )
    beef_result = bulk_engine.normalize_recipe_depletion(beef_id, beef_input, "demo_user")
    
    return {
        "status": "demo_data_created",
        "items_configured": 4,
        "counts_recorded": 4,
        "results": {
            "flour": {
                "method": "CONTAINER_COUNT",
                "input": "3 full + 1 half bag",
                "result": f"{flour_result.quantity_base_units} lb",
                "confidence": str(flour_result.confidence),
            },
            "olive_oil": {
                "method": "CONTAINER_COUNT",
                "input": "2 full gallons",
                "result": "2 gal",
                "confidence": "0.92",
            },
            "cooking_wine": {
                "method": "DIRECT_WEIGHT (regulated)",
                "input": "2100g gross",
                "result": f"{wine_result.quantity_base_units} ml",
                "confidence": str(wine_result.confidence),
            },
            "ground_beef": {
                "method": "RECIPE_DEPLETION (projection)",
                "input": "25lb - (45 × 0.33lb)",
                "result": f"{beef_result.quantity_base_units} lb",
                "confidence": str(beef_result.confidence),
                "note": "⚠️ This is a projection, not reality",
            },
        },
        "philosophy": "Bishop asks 'What do you observe?' — never raw math.",
    }

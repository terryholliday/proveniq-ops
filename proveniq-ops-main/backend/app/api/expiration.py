"""
PROVENIQ Ops - Expiration Cascade Planner API Routes
Bishop waste-to-decision endpoints

DAG Nodes: N13, N33

GUARDRAILS:
- Donation suggestions must respect compliance rules
"""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Query

from app.core.types import Money
from app.models.expiration import (
    DonationRule,
    ExpirationActionPlan,
    ExpirationCascadeAlert,
    ExpirationConfig,
    ItemCategory,
    LotRecord,
)
from app.services.bishop.expiration_engine import expiration_engine

router = APIRouter(prefix="/expiration", tags=["Expiration Cascade"])


# =============================================================================
# ANALYSIS
# =============================================================================

@router.post("/analyze", response_model=ExpirationCascadeAlert)
async def analyze_expirations(
    location_id: Optional[uuid.UUID] = None,
    category: Optional[ItemCategory] = None,
) -> ExpirationCascadeAlert:
    """
    Analyze lots for upcoming expirations.
    
    Bishop Logic (N13):
        1. Bucket items into 24h / 48h / 72h windows
        2. Estimate loss value
        3. Recommend disposition actions
    
    GUARDRAILS:
        - Donation suggestions respect compliance rules
    
    Returns:
        ExpirationCascadeAlert with items by action
    """
    return expiration_engine.analyze_expirations(
        location_id=location_id,
        category=category,
    )


@router.get("/window/{hours}")
async def get_expiring_in_window(hours: int = 24) -> dict:
    """
    Get items expiring within a specific time window.
    
    Args:
        hours: Window in hours (24, 48, 72)
    """
    items = expiration_engine.get_expiring_by_window(hours)
    total_value = sum(i.total_value_micros for i in items)
    
    return {
        "window_hours": hours,
        "item_count": len(items),
        "total_value_micros": total_value,
        "total_value_display": Money.to_dollars_str(total_value),
        "items": [i.model_dump() for i in items],
    }


# =============================================================================
# ACTION PLANS
# =============================================================================

@router.post("/plan", response_model=ExpirationActionPlan)
async def generate_action_plan() -> ExpirationActionPlan:
    """
    Generate detailed action plan for expiring items.
    
    Bishop Logic (N33):
        Creates disposition plans for discount, donate, dispose.
    """
    return expiration_engine.generate_action_plan()


@router.get("/plan/discount")
async def get_discount_items() -> dict:
    """Get items recommended for discount."""
    plan = expiration_engine.generate_action_plan()
    total_recovery = sum(p.recovery_value_micros for p in plan.discount_plans)
    
    return {
        "action": "discount",
        "item_count": len(plan.discount_plans),
        "total_recovery_micros": total_recovery,
        "total_recovery_display": Money.to_dollars_str(total_recovery),
        "plans": [p.model_dump() for p in plan.discount_plans],
    }


@router.get("/plan/donate")
async def get_donation_items() -> dict:
    """
    Get items recommended for donation.
    
    GUARDRAIL: Only compliance-approved items shown as ready.
    """
    plan = expiration_engine.generate_action_plan()
    
    approved = [p for p in plan.donate_plans if p.compliance_approved]
    pending = [p for p in plan.donate_plans if not p.compliance_approved]
    
    return {
        "action": "donate",
        "approved_count": len(approved),
        "pending_review_count": len(pending),
        "approved_plans": [p.model_dump() for p in approved],
        "pending_plans": [p.model_dump() for p in pending],
    }


@router.get("/plan/dispose")
async def get_disposal_items() -> dict:
    """Get items requiring disposal."""
    plan = expiration_engine.generate_action_plan()
    total_loss = sum(p.loss_value_micros for p in plan.dispose_plans)
    
    return {
        "action": "dispose",
        "item_count": len(plan.dispose_plans),
        "total_loss_micros": total_loss,
        "total_loss_display": Money.to_dollars_str(total_loss),
        "plans": [p.model_dump() for p in plan.dispose_plans],
    }


# =============================================================================
# ALERTS
# =============================================================================

@router.get("/alerts", response_model=list[ExpirationCascadeAlert])
async def get_alerts(limit: int = Query(100, ge=1, le=1000)) -> list[ExpirationCascadeAlert]:
    """Get historical expiration alerts."""
    return expiration_engine.get_alerts(limit=limit)


# =============================================================================
# CONFIGURATION
# =============================================================================

@router.get("/config", response_model=ExpirationConfig)
async def get_config() -> ExpirationConfig:
    """Get current expiration planner configuration."""
    return expiration_engine.get_config()


@router.put("/config")
async def update_config(
    discount_window_hours: Optional[int] = Query(None, ge=1),
    donate_window_hours: Optional[int] = Query(None, ge=1),
    dispose_window_hours: Optional[int] = Query(None, ge=1),
    default_discount_percent: Optional[Decimal] = Query(None, ge=0, le=100),
) -> ExpirationConfig:
    """Update expiration planner configuration."""
    config = expiration_engine.get_config()
    
    if discount_window_hours is not None:
        config.discount_window_hours = discount_window_hours
    if donate_window_hours is not None:
        config.donate_window_hours = donate_window_hours
    if dispose_window_hours is not None:
        config.dispose_window_hours = dispose_window_hours
    if default_discount_percent is not None:
        config.default_discount_percent = default_discount_percent
    
    expiration_engine.configure(config)
    return config


# =============================================================================
# DATA REGISTRATION
# =============================================================================

@router.post("/data/lot")
async def register_lot(
    product_id: uuid.UUID,
    product_name: str,
    canonical_sku: str,
    lot_number: str,
    quantity: int,
    unit_cost_dollars: str,
    received_date: datetime,
    expiration_date: datetime,
    location_id: uuid.UUID,
    location_name: str,
    category: ItemCategory = ItemCategory.PERISHABLE,
    donation_eligible: bool = True,
) -> dict:
    """Register a lot with expiration tracking."""
    lot = LotRecord(
        product_id=product_id,
        product_name=product_name,
        canonical_sku=canonical_sku,
        lot_number=lot_number,
        quantity=quantity,
        unit_cost_micros=Money.from_dollars(unit_cost_dollars),
        received_date=received_date,
        expiration_date=expiration_date,
        location_id=location_id,
        location_name=location_name,
        category=category,
        donation_eligible=donation_eligible,
    )
    expiration_engine.register_lot(lot)
    return {
        "status": "registered",
        "lot_id": str(lot.lot_id),
        "product_name": product_name,
        "expiration_date": expiration_date.isoformat(),
    }


@router.post("/data/donation-rule")
async def register_donation_rule(
    category: ItemCategory,
    min_days_before_expiry: int = 1,
    requires_temp_control: bool = False,
) -> dict:
    """Register a donation compliance rule."""
    rule = DonationRule(
        category=category,
        min_days_before_expiry=min_days_before_expiry,
        requires_temp_control=requires_temp_control,
    )
    expiration_engine.register_donation_rule(rule)
    return {
        "status": "registered",
        "category": category.value,
        "min_days": min_days_before_expiry,
    }


@router.put("/data/lot/{lot_id}/quantity")
async def update_lot_quantity(lot_id: uuid.UUID, quantity: int) -> dict:
    """Update lot quantity after partial use."""
    success = expiration_engine.update_lot_quantity(lot_id, quantity)
    return {
        "status": "updated" if success else "not_found",
        "lot_id": str(lot_id),
        "new_quantity": quantity,
    }


@router.delete("/data/clear")
async def clear_data() -> dict:
    """Clear all expiration data (for testing)."""
    expiration_engine.clear_data()
    return {"status": "cleared"}


# =============================================================================
# DEMO DATA
# =============================================================================

@router.post("/demo/setup")
async def setup_demo_data() -> dict:
    """
    Set up demo data for expiration cascade testing.
    
    Creates sample lots with varying expiration dates.
    """
    expiration_engine.clear_data()
    
    now = datetime.utcnow()
    
    # Location
    kitchen_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    cooler_id = uuid.UUID("22222222-2222-2222-2222-222222222222")
    
    # Register donation rules
    expiration_engine.register_donation_rule(DonationRule(
        category=ItemCategory.MEAT,
        min_days_before_expiry=2,  # Must have 2 days left
        requires_temp_control=True,
    ))
    expiration_engine.register_donation_rule(DonationRule(
        category=ItemCategory.DAIRY,
        min_days_before_expiry=3,  # Must have 3 days left
        requires_temp_control=True,
    ))
    expiration_engine.register_donation_rule(DonationRule(
        category=ItemCategory.PRODUCE,
        min_days_before_expiry=1,
        requires_temp_control=False,
    ))
    
    # Lots with varying expiration
    lots = [
        # URGENT - Expires in 12 hours, must dispose
        {
            "product_id": uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            "product_name": "Ground Beef 1lb",
            "sku": "BEEF-GND-1LB",
            "lot": "LOT-2024-001",
            "qty": 15,
            "cost": "5.99",
            "received": now - timedelta(days=5),
            "expires": now + timedelta(hours=12),
            "location": cooler_id,
            "loc_name": "Walk-in Cooler",
            "category": ItemCategory.MEAT,
        },
        # 24h window - Can donate (meat, 2 days required, but only 1 day left - blocked)
        {
            "product_id": uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
            "product_name": "Chicken Thighs 5lb",
            "sku": "CHK-THIGH-5LB",
            "lot": "LOT-2024-002",
            "qty": 10,
            "cost": "8.99",
            "received": now - timedelta(days=4),
            "expires": now + timedelta(hours=20),
            "location": cooler_id,
            "loc_name": "Walk-in Cooler",
            "category": ItemCategory.MEAT,
        },
        # 48h window - Eligible for donation (produce)
        {
            "product_id": uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
            "product_name": "Mixed Greens 1lb",
            "sku": "PROD-GREENS-1LB",
            "lot": "LOT-2024-003",
            "qty": 20,
            "cost": "3.99",
            "received": now - timedelta(days=3),
            "expires": now + timedelta(hours=36),
            "location": cooler_id,
            "loc_name": "Walk-in Cooler",
            "category": ItemCategory.PRODUCE,
        },
        # 72h window - Discount
        {
            "product_id": uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd"),
            "product_name": "Yogurt 32oz",
            "sku": "DAIRY-YOG-32",
            "lot": "LOT-2024-004",
            "qty": 25,
            "cost": "4.49",
            "received": now - timedelta(days=10),
            "expires": now + timedelta(hours=60),
            "location": cooler_id,
            "loc_name": "Walk-in Cooler",
            "category": ItemCategory.DAIRY,
        },
        # 72h window - Discount (high value)
        {
            "product_id": uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"),
            "product_name": "Salmon Fillet",
            "sku": "FISH-SALMON-LB",
            "lot": "LOT-2024-005",
            "qty": 8,
            "cost": "14.99",
            "received": now - timedelta(days=2),
            "expires": now + timedelta(hours=65),
            "location": cooler_id,
            "loc_name": "Walk-in Cooler",
            "category": ItemCategory.SEAFOOD,
        },
        # Not expiring soon - should not be flagged
        {
            "product_id": uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff"),
            "product_name": "Milk 1gal",
            "sku": "DAIRY-MILK-1G",
            "lot": "LOT-2024-006",
            "qty": 12,
            "cost": "3.99",
            "received": now - timedelta(days=1),
            "expires": now + timedelta(days=7),
            "location": cooler_id,
            "loc_name": "Walk-in Cooler",
            "category": ItemCategory.DAIRY,
        },
    ]
    
    for l in lots:
        lot = LotRecord(
            product_id=l["product_id"],
            product_name=l["product_name"],
            canonical_sku=l["sku"],
            lot_number=l["lot"],
            quantity=l["qty"],
            unit_cost_micros=Money.from_dollars(l["cost"]),
            received_date=l["received"],
            expiration_date=l["expires"],
            location_id=l["location"],
            location_name=l["loc_name"],
            category=l["category"],
        )
        expiration_engine.register_lot(lot)
    
    return {
        "status": "demo_data_created",
        "lots_created": len(lots) - 1,  # Minus the one not expiring soon
        "expected_results": {
            "dispose": ["Ground Beef: 12h left → DISPOSE"],
            "donate_blocked": ["Chicken Thighs: 20h left, needs 48h for donation → DISPOSE"],
            "donate_eligible": ["Mixed Greens: 36h left, produce eligible → DONATE"],
            "discount": ["Yogurt: 60h left → DISCOUNT", "Salmon: 65h left → DISCOUNT"],
            "not_flagged": ["Milk: 7 days left → not in window"],
        },
    }

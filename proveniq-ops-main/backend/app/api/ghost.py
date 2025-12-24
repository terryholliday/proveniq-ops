"""
PROVENIQ Ops - Ghost Inventory Detector API Routes
Bishop shrinkage detection endpoints

DAG Node: N12

GUARDRAILS:
- Do not accuse users
- This is a loss-signal, not a disciplinary tool
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Query

from app.core.types import Money
from app.models.ghost import (
    GhostDetectorConfig,
    GhostDetectorSummary,
    GhostInventoryAlert,
    InventoryRecord,
    ScanRecord,
)
from app.services.bishop.ghost_engine import ghost_engine

router = APIRouter(prefix="/ghost", tags=["Ghost Inventory"])


# =============================================================================
# DETECTION
# =============================================================================

@router.post("/detect", response_model=GhostInventoryAlert)
async def detect_ghost_inventory(
    location_id: Optional[uuid.UUID] = None,
    category: Optional[str] = None,
) -> GhostInventoryAlert:
    """
    Detect ghost inventory across specified scope.
    
    Bishop Logic (N12):
        1. Identify items with no scan activity for X days
        2. Calculate theoretical vs observed variance
        3. Compute financial exposure
    
    GUARDRAILS:
        - Results indicate loss-signals, not accusations
        - Use for operational improvement, not discipline
    
    Args:
        location_id: Optional filter by location
        category: Optional filter by category
    
    Returns:
        GhostInventoryAlert with flagged items
    """
    return ghost_engine.detect_ghost_inventory(
        location_id=location_id,
        category=category,
    )


@router.get("/summary", response_model=GhostDetectorSummary)
async def get_summary() -> GhostDetectorSummary:
    """
    Get summary of ghost inventory analysis.
    
    Provides breakdown by category and location.
    """
    return ghost_engine.get_summary()


@router.get("/alerts", response_model=list[GhostInventoryAlert])
async def get_alerts(limit: int = Query(100, ge=1, le=1000)) -> list[GhostInventoryAlert]:
    """Get historical ghost inventory alerts."""
    return ghost_engine.get_alerts(limit=limit)


@router.get("/item/{product_id}/{location_id}")
async def get_item_status(
    product_id: uuid.UUID,
    location_id: uuid.UUID,
) -> dict:
    """
    Get ghost status for a specific item at a location.
    
    Returns scan history and ghost status.
    """
    status = ghost_engine.get_item_status(product_id, location_id)
    if not status:
        return {"error": "Item not found", "product_id": str(product_id)}
    return status


# =============================================================================
# CONFIGURATION
# =============================================================================

@router.get("/config", response_model=GhostDetectorConfig)
async def get_config() -> GhostDetectorConfig:
    """Get current ghost detector configuration."""
    return ghost_engine.get_config()


@router.put("/config")
async def update_config(
    unscanned_threshold_days: Optional[int] = Query(None, ge=1, le=365),
    high_value_threshold_dollars: Optional[str] = None,
    critical_exposure_threshold_dollars: Optional[str] = None,
) -> GhostDetectorConfig:
    """Update ghost detector configuration."""
    config = ghost_engine.get_config()
    
    if unscanned_threshold_days is not None:
        config.unscanned_threshold_days = unscanned_threshold_days
    if high_value_threshold_dollars is not None:
        config.high_value_threshold_micros = Money.from_dollars(high_value_threshold_dollars)
    if critical_exposure_threshold_dollars is not None:
        config.critical_exposure_threshold_micros = Money.from_dollars(critical_exposure_threshold_dollars)
    
    ghost_engine.configure(config)
    return config


# =============================================================================
# DATA REGISTRATION
# =============================================================================

@router.post("/data/inventory")
async def register_inventory(
    product_id: uuid.UUID,
    product_name: str,
    canonical_sku: str,
    location_id: uuid.UUID,
    location_name: str,
    system_qty: int,
    unit_cost_dollars: str,
    category: str = "general",
    is_high_value: bool = False,
    is_controlled: bool = False,
) -> dict:
    """Register an inventory record."""
    record = InventoryRecord(
        product_id=product_id,
        product_name=product_name,
        canonical_sku=canonical_sku,
        location_id=location_id,
        location_name=location_name,
        system_qty=system_qty,
        unit_cost_micros=Money.from_dollars(unit_cost_dollars),
        category=category,
        is_high_value=is_high_value,
        is_controlled=is_controlled,
    )
    ghost_engine.register_inventory(record)
    return {
        "status": "registered",
        "product_id": str(product_id),
        "location_id": str(location_id),
    }


@router.post("/data/scan")
async def register_scan(
    product_id: uuid.UUID,
    location_id: uuid.UUID,
    scanned_qty: int,
    scanned_by: str = "bishop",
    scan_type: str = "cycle_count",
    scanned_at: Optional[datetime] = None,
) -> dict:
    """Register a scan event."""
    scan = ScanRecord(
        product_id=product_id,
        location_id=location_id,
        scanned_qty=scanned_qty,
        scanned_at=scanned_at or datetime.utcnow(),
        scanned_by=scanned_by,
        scan_type=scan_type,
    )
    ghost_engine.register_scan(scan)
    return {
        "status": "registered",
        "scan_id": str(scan.scan_id),
        "product_id": str(product_id),
    }


@router.delete("/data/clear")
async def clear_data() -> dict:
    """Clear all ghost detector data (for testing)."""
    ghost_engine.clear_data()
    return {"status": "cleared"}


# =============================================================================
# DEMO DATA
# =============================================================================

@router.post("/demo/setup")
async def setup_demo_data() -> dict:
    """
    Set up demo data for ghost inventory testing.
    
    Creates sample inventory with varying scan recency.
    """
    ghost_engine.clear_data()
    
    now = datetime.utcnow()
    
    # Locations
    main_loc = uuid.UUID("11111111-1111-1111-1111-111111111111")
    storage_loc = uuid.UUID("22222222-2222-2222-2222-222222222222")
    cold_loc = uuid.UUID("33333333-3333-3333-3333-333333333333")
    
    ghost_engine.register_location(main_loc, "Main Kitchen")
    ghost_engine.register_location(storage_loc, "Dry Storage")
    ghost_engine.register_location(cold_loc, "Walk-in Cooler")
    
    # Products
    products = [
        # Recently scanned - should NOT be flagged
        {
            "id": uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            "name": "Olive Oil 1gal",
            "sku": "OIL-OLV-1G",
            "location": main_loc,
            "loc_name": "Main Kitchen",
            "qty": 8,
            "cost": "24.99",
            "category": "oils",
            "last_scan_days": 3,
            "scan_qty": 8,
        },
        # Ghost - not scanned in 20 days, variance detected
        {
            "id": uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
            "name": "Chicken Breast 5lb",
            "sku": "CHK-BRST-5LB",
            "location": cold_loc,
            "loc_name": "Walk-in Cooler",
            "qty": 25,
            "cost": "12.50",
            "category": "protein",
            "last_scan_days": 20,
            "scan_qty": 18,  # 7 unit variance!
        },
        # Ghost - never scanned, high value
        {
            "id": uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
            "name": "Wagyu Ribeye",
            "sku": "BEEF-WAGYU-RIB",
            "location": cold_loc,
            "loc_name": "Walk-in Cooler",
            "qty": 10,
            "cost": "89.99",
            "category": "protein",
            "is_high_value": True,
            "last_scan_days": None,  # Never scanned
            "scan_qty": None,
        },
        # Ghost - not scanned in 30 days, controlled item
        {
            "id": uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd"),
            "name": "Cooking Wine",
            "sku": "WINE-COOK-750",
            "location": storage_loc,
            "loc_name": "Dry Storage",
            "qty": 12,
            "cost": "8.99",
            "category": "alcohol",
            "is_controlled": True,
            "last_scan_days": 30,
            "scan_qty": 10,  # 2 unit variance
        },
        # Recently scanned - should NOT be flagged
        {
            "id": uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"),
            "name": "Rice 25lb",
            "sku": "RICE-25LB",
            "location": storage_loc,
            "loc_name": "Dry Storage",
            "qty": 15,
            "cost": "18.99",
            "category": "dry_goods",
            "last_scan_days": 7,
            "scan_qty": 15,
        },
        # Ghost - 15 days, low value (may or may not flag based on config)
        {
            "id": uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff"),
            "name": "Salt 1lb",
            "sku": "SALT-1LB",
            "location": main_loc,
            "loc_name": "Main Kitchen",
            "qty": 20,
            "cost": "1.50",
            "category": "spices",
            "last_scan_days": 15,
            "scan_qty": 20,
        },
    ]
    
    for p in products:
        record = InventoryRecord(
            product_id=p["id"],
            product_name=p["name"],
            canonical_sku=p["sku"],
            location_id=p["location"],
            location_name=p["loc_name"],
            system_qty=p["qty"],
            unit_cost_micros=Money.from_dollars(p["cost"]),
            category=p["category"],
            is_high_value=p.get("is_high_value", False),
            is_controlled=p.get("is_controlled", False),
        )
        ghost_engine.register_inventory(record)
        
        # Register scan if applicable
        if p.get("last_scan_days") is not None and p.get("scan_qty") is not None:
            scan = ScanRecord(
                product_id=p["id"],
                location_id=p["location"],
                scanned_qty=p["scan_qty"],
                scanned_at=now - timedelta(days=p["last_scan_days"]),
                scanned_by="demo_user",
                scan_type="cycle_count",
            )
            ghost_engine.register_scan(scan)
    
    return {
        "status": "demo_data_created",
        "locations": 3,
        "products": len(products),
        "expected_ghosts": [
            "Chicken Breast 5lb: 20 days, 7 unit variance → HIGH",
            "Wagyu Ribeye: Never scanned, $899 exposure → CRITICAL",
            "Cooking Wine: 30 days, controlled, 2 unit variance → HIGH",
            "Salt 1lb: 15 days, no variance, low value → LOW/MEDIUM",
        ],
        "not_flagged": [
            "Olive Oil: scanned 3 days ago",
            "Rice 25lb: scanned 7 days ago",
        ],
    }

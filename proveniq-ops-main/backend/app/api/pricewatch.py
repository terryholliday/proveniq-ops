"""
PROVENIQ Ops - Vendor Price Watch API Routes
Bishop price arbitrage monitoring endpoints

DAG Nodes: N3, N14, N23, N34
"""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Query

from app.core.types import Money
from app.models.pricewatch import (
    ActiveContract,
    ContractStatus,
    PriceAlertType,
    PriceWatchConfig,
    PriceWatchSummary,
    SKUMapping,
    VendorPriceAlert,
    VendorPriceFeed,
)
from app.services.bishop.pricewatch_engine import pricewatch_engine

router = APIRouter(prefix="/pricewatch", tags=["Vendor Price Watch"])


# =============================================================================
# ANALYSIS
# =============================================================================

@router.post("/analyze", response_model=PriceWatchSummary)
async def analyze_prices() -> PriceWatchSummary:
    """
    Analyze all SKUs for price variance.
    
    Bishop Logic (N14):
        1. Normalize SKUs across vendors
        2. Compare current prices to alternatives
        3. Generate alerts where delta > threshold
    
    GUARDRAILS:
        - Never auto-switch without approval
        - Respect locked contracts
    """
    return pricewatch_engine.analyze_all()


@router.get("/analyze/{canonical_sku}")
async def analyze_sku(canonical_sku: str) -> dict:
    """Analyze a single SKU for price variance."""
    alert = pricewatch_engine.analyze_sku(canonical_sku)
    comparison = pricewatch_engine.get_sku_price_comparison(canonical_sku)
    
    return {
        "canonical_sku": canonical_sku,
        "alert": alert.model_dump() if alert else None,
        "comparison": comparison,
    }


# =============================================================================
# ALERTS
# =============================================================================

@router.get("/alerts", response_model=list[VendorPriceAlert])
async def get_alerts(
    alert_type: Optional[PriceAlertType] = None,
    min_savings_percent: Optional[Decimal] = Query(None, ge=0),
) -> list[VendorPriceAlert]:
    """
    Get price variance alerts.
    
    Filter by type or minimum savings percentage.
    """
    return pricewatch_engine.get_alerts(
        alert_type=alert_type,
        min_savings_percent=min_savings_percent,
    )


@router.get("/alerts/switch-opportunities")
async def get_switch_opportunities() -> dict:
    """
    Get alerts where vendor switch is recommended.
    
    These are unlocked opportunities with significant savings.
    """
    alerts = pricewatch_engine.get_alerts(
        alert_type=PriceAlertType.VENDOR_PRICE_VARIANCE
    )
    
    switch_alerts = [
        a for a in alerts 
        if not a.contract_locked and a.action_prompt.value == "SWITCH_VENDOR?"
    ]
    
    total_savings = sum(a.annual_savings_micros or 0 for a in switch_alerts)
    
    return {
        "opportunities": len(switch_alerts),
        "total_annual_savings_micros": total_savings,
        "total_annual_savings_display": Money.to_dollars_str(total_savings),
        "alerts": [a.model_dump() for a in switch_alerts],
    }


@router.get("/alerts/locked")
async def get_locked_alerts() -> dict:
    """
    Get alerts blocked by locked contracts.
    
    Shows potential savings if contracts were renegotiated.
    """
    alerts = pricewatch_engine.get_alerts()
    locked_alerts = [a for a in alerts if a.contract_locked]
    
    blocked_savings = sum(a.annual_savings_micros or 0 for a in locked_alerts)
    
    return {
        "locked_opportunities": len(locked_alerts),
        "blocked_savings_micros": blocked_savings,
        "blocked_savings_display": Money.to_dollars_str(blocked_savings),
        "alerts": [a.model_dump() for a in locked_alerts],
    }


# =============================================================================
# PRICE COMPARISON
# =============================================================================

@router.get("/compare/{canonical_sku}")
async def compare_prices(canonical_sku: str) -> dict:
    """
    Get price comparison for a SKU across all vendors.
    
    Shows current vendor and all alternatives sorted by price.
    """
    return pricewatch_engine.get_sku_price_comparison(canonical_sku)


# =============================================================================
# CONFIGURATION
# =============================================================================

@router.get("/config", response_model=PriceWatchConfig)
async def get_config() -> PriceWatchConfig:
    """Get current price watch configuration."""
    return pricewatch_engine.get_config()


@router.put("/config")
async def update_config(
    alert_threshold_percent: Optional[Decimal] = Query(None, ge=0, le=100),
    spike_threshold_percent: Optional[Decimal] = Query(None, ge=0, le=100),
    rolling_window_days: Optional[int] = Query(None, ge=1, le=365),
) -> PriceWatchConfig:
    """Update price watch configuration."""
    config = pricewatch_engine.get_config()
    
    if alert_threshold_percent is not None:
        config.alert_threshold_percent = alert_threshold_percent
    if spike_threshold_percent is not None:
        config.spike_threshold_percent = spike_threshold_percent
    if rolling_window_days is not None:
        config.rolling_window_days = rolling_window_days
    
    pricewatch_engine.configure(config)
    return config


# =============================================================================
# DATA REGISTRATION
# =============================================================================

@router.post("/data/sku-mapping")
async def register_sku_mapping(
    canonical_sku: str,
    product_id: uuid.UUID,
    product_name: str,
    category: str,
) -> dict:
    """Register a SKU normalization mapping."""
    mapping = SKUMapping(
        canonical_sku=canonical_sku,
        product_id=product_id,
        product_name=product_name,
        category=category,
    )
    pricewatch_engine.register_sku_mapping(mapping)
    return {"status": "registered", "canonical_sku": canonical_sku}


@router.post("/data/sku-mapping/{canonical_sku}/vendor")
async def add_vendor_to_sku(
    canonical_sku: str,
    vendor_id: uuid.UUID,
    vendor_sku: str,
    vendor_name: str,
) -> dict:
    """Add a vendor mapping to an existing SKU."""
    # This would update the SKU mapping
    return {
        "status": "added",
        "canonical_sku": canonical_sku,
        "vendor_id": str(vendor_id),
        "vendor_sku": vendor_sku,
    }


@router.post("/data/price-feed")
async def register_price_feed(
    vendor_id: uuid.UUID,
    vendor_name: str,
    vendor_sku: str,
    canonical_sku: str,
    price_dollars: str,  # String to avoid float
    unit_of_measure: str = "each",
    min_order_qty: int = 1,
    lead_time_hours: Optional[int] = None,
    stock_available: Optional[int] = None,
) -> dict:
    """Register a vendor price feed."""
    feed = VendorPriceFeed(
        vendor_id=vendor_id,
        vendor_name=vendor_name,
        vendor_sku=vendor_sku,
        canonical_sku=canonical_sku,
        price_micros=Money.from_dollars(price_dollars),
        unit_of_measure=unit_of_measure,
        min_order_qty=min_order_qty,
        lead_time_hours=lead_time_hours,
        stock_available=stock_available,
    )
    pricewatch_engine.register_price_feed(feed)
    return {
        "status": "registered",
        "canonical_sku": canonical_sku,
        "vendor_name": vendor_name,
        "price_micros": feed.price_micros,
    }


@router.post("/data/contract")
async def register_contract(
    vendor_id: uuid.UUID,
    vendor_name: str,
    product_id: uuid.UUID,
    canonical_sku: str,
    contracted_price_dollars: str,
    start_date: datetime,
    end_date: datetime,
    is_locked: bool = False,
    lock_reason: Optional[str] = None,
) -> dict:
    """Register an active vendor contract."""
    contract = ActiveContract(
        contract_id=uuid.uuid4(),
        vendor_id=vendor_id,
        vendor_name=vendor_name,
        product_id=product_id,
        canonical_sku=canonical_sku,
        contracted_price_micros=Money.from_dollars(contracted_price_dollars),
        start_date=start_date,
        end_date=end_date,
        is_locked=is_locked,
        lock_reason=lock_reason,
    )
    pricewatch_engine.register_contract(contract)
    return {
        "status": "registered",
        "contract_id": str(contract.contract_id),
        "canonical_sku": canonical_sku,
        "vendor_name": vendor_name,
    }


@router.post("/data/current-vendor")
async def set_current_vendor(
    canonical_sku: str,
    vendor_id: uuid.UUID,
) -> dict:
    """Set the current vendor for a SKU."""
    pricewatch_engine.set_current_vendor(canonical_sku, vendor_id)
    return {
        "status": "set",
        "canonical_sku": canonical_sku,
        "vendor_id": str(vendor_id),
    }


@router.delete("/data/clear")
async def clear_data() -> dict:
    """Clear all price watch data (for testing)."""
    pricewatch_engine.clear_data()
    return {"status": "cleared"}


# =============================================================================
# DEMO DATA
# =============================================================================

@router.post("/demo/setup")
async def setup_demo_data() -> dict:
    """
    Set up demo data for price watch testing.
    
    Creates sample SKUs, vendors, prices, and contracts.
    """
    pricewatch_engine.clear_data()
    
    # Product IDs
    chicken_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    tomato_id = uuid.UUID("22222222-2222-2222-2222-222222222222")
    rice_id = uuid.UUID("33333333-3333-3333-3333-333333333333")
    
    # Vendor IDs
    sysco_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    usfoods_id = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    pfg_id = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
    
    # Register SKU mappings
    pricewatch_engine.register_sku_mapping(SKUMapping(
        canonical_sku="CHK-BRST-5LB",
        product_id=chicken_id,
        product_name="Chicken Breast 5lb",
        category="Protein",
        vendor_mappings=[
            {"vendor_id": sysco_id, "vendor_sku": "SYS-CHK-001", "vendor_name": "Sysco"},
            {"vendor_id": usfoods_id, "vendor_sku": "USF-CHKN-5", "vendor_name": "US Foods"},
            {"vendor_id": pfg_id, "vendor_sku": "PFG-CB5", "vendor_name": "PFG"},
        ],
    ))
    
    pricewatch_engine.register_sku_mapping(SKUMapping(
        canonical_sku="TOM-PASTE-6OZ",
        product_id=tomato_id,
        product_name="Tomato Paste 6oz",
        category="Canned Goods",
        vendor_mappings=[
            {"vendor_id": sysco_id, "vendor_sku": "SYS-TOM-006", "vendor_name": "Sysco"},
            {"vendor_id": usfoods_id, "vendor_sku": "USF-TP-6", "vendor_name": "US Foods"},
        ],
    ))
    
    pricewatch_engine.register_sku_mapping(SKUMapping(
        canonical_sku="RICE-25LB",
        product_id=rice_id,
        product_name="Rice 25lb Bag",
        category="Dry Goods",
        vendor_mappings=[
            {"vendor_id": sysco_id, "vendor_sku": "SYS-RICE-25", "vendor_name": "Sysco"},
            {"vendor_id": pfg_id, "vendor_sku": "PFG-R25", "vendor_name": "PFG"},
        ],
    ))
    
    # Register price feeds - Chicken (Sysco is current but expensive)
    pricewatch_engine.register_price_feed(VendorPriceFeed(
        vendor_id=sysco_id,
        vendor_name="Sysco",
        vendor_sku="SYS-CHK-001",
        canonical_sku="CHK-BRST-5LB",
        price_micros=Money.from_dollars("12.50"),
        unit_of_measure="each",
        lead_time_hours=24,
    ))
    pricewatch_engine.register_price_feed(VendorPriceFeed(
        vendor_id=usfoods_id,
        vendor_name="US Foods",
        vendor_sku="USF-CHKN-5",
        canonical_sku="CHK-BRST-5LB",
        price_micros=Money.from_dollars("10.85"),  # 13% cheaper!
        unit_of_measure="each",
        lead_time_hours=24,
    ))
    pricewatch_engine.register_price_feed(VendorPriceFeed(
        vendor_id=pfg_id,
        vendor_name="PFG",
        vendor_sku="PFG-CB5",
        canonical_sku="CHK-BRST-5LB",
        price_micros=Money.from_dollars("11.25"),
        unit_of_measure="each",
        lead_time_hours=48,
    ))
    
    # Tomato Paste - Similar prices
    pricewatch_engine.register_price_feed(VendorPriceFeed(
        vendor_id=sysco_id,
        vendor_name="Sysco",
        vendor_sku="SYS-TOM-006",
        canonical_sku="TOM-PASTE-6OZ",
        price_micros=Money.from_dollars("1.25"),
        unit_of_measure="each",
    ))
    pricewatch_engine.register_price_feed(VendorPriceFeed(
        vendor_id=usfoods_id,
        vendor_name="US Foods",
        vendor_sku="USF-TP-6",
        canonical_sku="TOM-PASTE-6OZ",
        price_micros=Money.from_dollars("1.22"),  # Only 2.4% cheaper
        unit_of_measure="each",
    ))
    
    # Rice - Locked contract with Sysco
    pricewatch_engine.register_price_feed(VendorPriceFeed(
        vendor_id=sysco_id,
        vendor_name="Sysco",
        vendor_sku="SYS-RICE-25",
        canonical_sku="RICE-25LB",
        price_micros=Money.from_dollars("18.99"),
        unit_of_measure="each",
    ))
    pricewatch_engine.register_price_feed(VendorPriceFeed(
        vendor_id=pfg_id,
        vendor_name="PFG",
        vendor_sku="PFG-R25",
        canonical_sku="RICE-25LB",
        price_micros=Money.from_dollars("15.99"),  # 16% cheaper but locked
        unit_of_measure="each",
    ))
    
    # Register contract (locked)
    pricewatch_engine.register_contract(ActiveContract(
        contract_id=uuid.uuid4(),
        vendor_id=sysco_id,
        vendor_name="Sysco",
        product_id=rice_id,
        canonical_sku="RICE-25LB",
        contracted_price_micros=Money.from_dollars("18.99"),
        start_date=datetime.utcnow() - timedelta(days=180),
        end_date=datetime.utcnow() + timedelta(days=180),
        is_locked=True,
        lock_reason="Volume rebate agreement",
    ))
    
    # Set current vendors
    pricewatch_engine.set_current_vendor("CHK-BRST-5LB", sysco_id)
    pricewatch_engine.set_current_vendor("TOM-PASTE-6OZ", sysco_id)
    pricewatch_engine.set_current_vendor("RICE-25LB", sysco_id)
    
    return {
        "status": "demo_data_created",
        "skus": ["CHK-BRST-5LB", "TOM-PASTE-6OZ", "RICE-25LB"],
        "vendors": ["Sysco", "US Foods", "PFG"],
        "expected_alerts": [
            "CHK-BRST-5LB: US Foods 13% cheaper → SWITCH_VENDOR?",
            "TOM-PASTE-6OZ: Below threshold (2.4%) → No alert",
            "RICE-25LB: PFG 16% cheaper but LOCKED → MONITOR",
        ],
    }

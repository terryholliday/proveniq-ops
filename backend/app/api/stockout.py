"""
PROVENIQ Ops - Stockout Prediction API Routes
Bishop foresight engine endpoints
"""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.stockout import (
    AlertSeverity,
    AlertType,
    HistoricalUsage,
    InventoryLevel,
    OpenPurchaseOrder,
    ScanEvent,
    StockoutAlert,
    StockoutPredictionRequest,
    StockoutPredictionResponse,
    VendorLeadTime,
)
from app.services.bishop.stockout_engine import stockout_engine

router = APIRouter(prefix="/stockout", tags=["Predictive Stockout"])


# =============================================================================
# PREDICTION ENDPOINTS
# =============================================================================

@router.post("/analyze", response_model=StockoutPredictionResponse)
async def analyze_stockout_risk(
    request: StockoutPredictionRequest,
) -> StockoutPredictionResponse:
    """
    Analyze stockout risk for specified products.
    
    Bishop Logic:
        1. Calculate real-time burn rate from scan velocity
        2. Compare against historical averages to detect acceleration
        3. Project stockout timestamp
        4. If projected stockout < (lead_time + safety_buffer):
           - Generate STOCKOUT_RISK alert
           - Pre-build reorder recommendation
    """
    return stockout_engine.analyze(
        product_ids=request.product_ids,
        safety_buffer_hours=request.safety_buffer_hours,
        include_warnings=True,
    )


@router.get("/alerts", response_model=list[StockoutAlert])
async def get_active_alerts(
    severity: Optional[AlertSeverity] = None,
    limit: int = Query(50, le=200),
) -> list[StockoutAlert]:
    """Get active stockout alerts, optionally filtered by severity."""
    response = stockout_engine.analyze(include_warnings=True)
    alerts = response.alerts
    
    if severity:
        alerts = [a for a in alerts if a.severity == severity]
    
    return alerts[:limit]


@router.get("/alerts/critical", response_model=list[StockoutAlert])
async def get_critical_alerts() -> list[StockoutAlert]:
    """
    Get CRITICAL stockout alerts only.
    
    These require immediate attention - stockout projected within 12 hours.
    """
    return stockout_engine.get_critical_alerts()


@router.get("/product/{product_id}", response_model=Optional[StockoutAlert])
async def get_product_stockout_risk(
    product_id: uuid.UUID,
    safety_buffer_hours: int = Query(24, ge=0),
) -> Optional[StockoutAlert]:
    """Get stockout risk assessment for a specific product."""
    response = stockout_engine.analyze(
        product_ids=[product_id],
        safety_buffer_hours=safety_buffer_hours,
    )
    return response.alerts[0] if response.alerts else None


# =============================================================================
# DATA REGISTRATION ENDPOINTS (for testing/mock data injection)
# =============================================================================

@router.post("/data/inventory")
async def register_inventory_level(
    product_id: uuid.UUID,
    product_name: str,
    on_hand_qty: int,
    safety_stock: int = 0,
    location_id: Optional[str] = None,
) -> dict:
    """Register current inventory level for stockout analysis."""
    level = InventoryLevel(
        product_id=product_id,
        on_hand_qty=on_hand_qty,
        safety_stock=safety_stock,
        location_id=location_id,
    )
    stockout_engine.register_inventory(level, product_name)
    return {"status": "registered", "product_id": str(product_id)}


@router.post("/data/consumption")
async def register_consumption_event(
    product_id: uuid.UUID,
    qty_delta: int,
    timestamp: Optional[datetime] = None,
    location_id: Optional[str] = None,
    scan_type: str = "consumption",
) -> dict:
    """
    Register a consumption or receiving event.
    
    qty_delta: negative for consumption, positive for receiving
    """
    event = ScanEvent(
        product_id=product_id,
        qty_delta=qty_delta,
        timestamp=timestamp or datetime.utcnow(),
        location_id=location_id,
        scan_type=scan_type,
    )
    stockout_engine.register_scan_event(event)
    return {"status": "registered", "event_type": scan_type}


@router.post("/data/historical")
async def register_historical_usage(
    product_id: uuid.UUID,
    avg_daily_burn_7d: float,
    avg_daily_burn_30d: float,
    avg_daily_burn_90d: float,
    variance_coefficient: float = 0.0,
) -> dict:
    """Register historical usage statistics for a product."""
    usage = HistoricalUsage(
        product_id=product_id,
        avg_daily_burn_7d=avg_daily_burn_7d,
        avg_daily_burn_30d=avg_daily_burn_30d,
        avg_daily_burn_90d=avg_daily_burn_90d,
        variance_coefficient=variance_coefficient,
    )
    stockout_engine.register_historical_usage(usage)
    return {"status": "registered", "product_id": str(product_id)}


@router.post("/data/lead-time")
async def register_vendor_lead_time(
    product_id: uuid.UUID,
    vendor_id: uuid.UUID,
    vendor_name: str,
    avg_lead_time_hours: int,
    reliability_score: float = 1.0,
) -> dict:
    """Register vendor lead time for a product."""
    lead_time = VendorLeadTime(
        product_id=product_id,
        vendor_id=vendor_id,
        vendor_name=vendor_name,
        avg_lead_time_hours=avg_lead_time_hours,
        reliability_score=reliability_score,
    )
    stockout_engine.register_vendor_lead_time(lead_time)
    return {"status": "registered", "vendor_id": str(vendor_id)}


@router.post("/data/price")
async def register_vendor_price(
    product_id: uuid.UUID,
    vendor_id: uuid.UUID,
    unit_price: Decimal,
) -> dict:
    """Register vendor price for a product."""
    stockout_engine.register_vendor_price(product_id, vendor_id, unit_price)
    return {"status": "registered"}


@router.post("/data/purchase-order")
async def register_open_po(
    order_id: uuid.UUID,
    product_id: uuid.UUID,
    vendor_id: uuid.UUID,
    qty_ordered: int,
    expected_delivery: datetime,
    status: str = "pending",
) -> dict:
    """Register an open purchase order."""
    po = OpenPurchaseOrder(
        order_id=order_id,
        product_id=product_id,
        vendor_id=vendor_id,
        qty_ordered=qty_ordered,
        expected_delivery=expected_delivery,
        status=status,
    )
    stockout_engine.register_open_po(po)
    return {"status": "registered", "order_id": str(order_id)}


@router.delete("/data/clear")
async def clear_stockout_data() -> dict:
    """Clear all stockout engine data (for testing)."""
    stockout_engine.clear_data()
    return {"status": "cleared"}


# =============================================================================
# DEMO DATA ENDPOINT
# =============================================================================

@router.post("/demo/setup")
async def setup_demo_data() -> dict:
    """
    Set up demo data for stockout prediction testing.
    
    Creates sample products with varying stockout risk levels.
    """
    stockout_engine.clear_data()
    
    # Product 1: CRITICAL - Very low stock, high burn rate
    product1_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    vendor1_id = uuid.UUID("aaaaaaa1-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    
    stockout_engine.register_inventory(
        InventoryLevel(product_id=product1_id, on_hand_qty=5, safety_stock=10),
        "Chicken Breast 5lb"
    )
    stockout_engine.register_historical_usage(HistoricalUsage(
        product_id=product1_id,
        avg_daily_burn_7d=8.0,
        avg_daily_burn_30d=7.5,
        avg_daily_burn_90d=7.0,
    ))
    stockout_engine.register_vendor_lead_time(VendorLeadTime(
        product_id=product1_id,
        vendor_id=vendor1_id,
        vendor_name="Sysco",
        avg_lead_time_hours=24,
        reliability_score=0.95,
    ))
    stockout_engine.register_vendor_price(product1_id, vendor1_id, Decimal("2.55"))
    
    # Simulate recent high consumption
    now = datetime.utcnow()
    for i in range(10):
        stockout_engine.register_scan_event(ScanEvent(
            product_id=product1_id,
            qty_delta=-3,
            timestamp=now - timedelta(hours=i * 2),
        ))
    
    # Product 2: HIGH - Below safety stock
    product2_id = uuid.UUID("22222222-2222-2222-2222-222222222222")
    vendor2_id = uuid.UUID("bbbbbbb1-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    
    stockout_engine.register_inventory(
        InventoryLevel(product_id=product2_id, on_hand_qty=15, safety_stock=20),
        "Tomato Paste 6oz"
    )
    stockout_engine.register_historical_usage(HistoricalUsage(
        product_id=product2_id,
        avg_daily_burn_7d=4.0,
        avg_daily_burn_30d=3.8,
        avg_daily_burn_90d=3.5,
    ))
    stockout_engine.register_vendor_lead_time(VendorLeadTime(
        product_id=product2_id,
        vendor_id=vendor2_id,
        vendor_name="United Foods",
        avg_lead_time_hours=48,
        reliability_score=0.88,
    ))
    stockout_engine.register_vendor_price(product2_id, vendor2_id, Decimal("1.25"))
    
    for i in range(8):
        stockout_engine.register_scan_event(ScanEvent(
            product_id=product2_id,
            qty_delta=-2,
            timestamp=now - timedelta(hours=i * 4),
        ))
    
    # Product 3: LOW - Healthy stock levels
    product3_id = uuid.UUID("33333333-3333-3333-3333-333333333333")
    
    stockout_engine.register_inventory(
        InventoryLevel(product_id=product3_id, on_hand_qty=100, safety_stock=20),
        "Rice 25lb Bag"
    )
    stockout_engine.register_historical_usage(HistoricalUsage(
        product_id=product3_id,
        avg_daily_burn_7d=2.0,
        avg_daily_burn_30d=2.0,
        avg_daily_burn_90d=2.0,
    ))
    
    return {
        "status": "demo_data_created",
        "products": [
            {"id": str(product1_id), "name": "Chicken Breast 5lb", "expected_risk": "CRITICAL"},
            {"id": str(product2_id), "name": "Tomato Paste 6oz", "expected_risk": "HIGH"},
            {"id": str(product3_id), "name": "Rice 25lb Bag", "expected_risk": "LOW/NONE"},
        ]
    }

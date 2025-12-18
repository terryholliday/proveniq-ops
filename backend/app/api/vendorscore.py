"""
PROVENIQ Ops - Vendor Reliability Scorer API Routes
Bishop vendor execution scoring endpoints

Score vendors based on execution, not promises.
"""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Query

from app.models.vendorscore import (
    DeliveryEvent,
    FillEvent,
    PriceEvent,
    QualityEvent,
    ScoringWeights,
    SubstitutionEvent,
    VendorComparison,
    VendorReliabilityScore,
    VendorScoreHistory,
    VendorScorerConfig,
)
from app.services.bishop.vendorscore_engine import vendor_scorer

router = APIRouter(prefix="/vendorscore", tags=["Vendor Reliability"])


# =============================================================================
# SCORING
# =============================================================================

@router.get("/score/{vendor_id}", response_model=VendorReliabilityScore)
async def score_vendor(
    vendor_id: uuid.UUID,
    period_days: int = Query(30, ge=7, le=365),
) -> dict:
    """
    Calculate reliability score for a vendor.
    
    Returns:
    - reliability_score: 0-100
    - trend: UP | FLAT | DOWN
    - tier: platinum/gold/silver/bronze/watch/probation
    """
    result = vendor_scorer.score_vendor(vendor_id, period_days)
    
    if not result:
        return {"error": "Vendor not found or insufficient data", "vendor_id": str(vendor_id)}
    
    return result.model_dump()


@router.get("/scores")
async def score_all_vendors(
    period_days: int = Query(30, ge=7, le=365),
) -> dict:
    """Score all registered vendors."""
    scores = vendor_scorer.score_all_vendors(period_days)
    
    return {
        "count": len(scores),
        "period_days": period_days,
        "vendors": [
            {
                "vendor_id": str(s.vendor_id),
                "vendor_name": s.vendor_name,
                "reliability_score": s.reliability_score,
                "trend": s.trend.value,
                "tier": s.tier.value,
            }
            for s in scores
        ],
    }


@router.get("/compare")
async def compare_vendors(
    vendor_ids: Optional[list[uuid.UUID]] = Query(default=None),
    period_days: int = Query(30, ge=7, le=365),
) -> dict:
    """Compare multiple vendors."""
    comparison = vendor_scorer.compare_vendors(vendor_ids, period_days)
    return comparison.model_dump()


@router.get("/history/{vendor_id}")
async def get_vendor_history(vendor_id: uuid.UUID) -> dict:
    """Get historical scores for a vendor."""
    history = vendor_scorer.get_vendor_history(vendor_id)
    
    if not history:
        return {"error": "Vendor not found", "vendor_id": str(vendor_id)}
    
    return history.model_dump()


# =============================================================================
# VENDOR REGISTRATION
# =============================================================================

@router.post("/vendor")
async def register_vendor(
    vendor_id: uuid.UUID,
    vendor_name: str,
) -> dict:
    """Register a vendor for scoring."""
    vendor_scorer.register_vendor(vendor_id, vendor_name)
    return {
        "status": "registered",
        "vendor_id": str(vendor_id),
        "vendor_name": vendor_name,
    }


@router.get("/vendors")
async def get_vendors() -> dict:
    """Get all registered vendors."""
    vendors = vendor_scorer.get_vendors()
    return {
        "count": len(vendors),
        "vendors": [
            {"vendor_id": str(k), "vendor_name": v}
            for k, v in vendors.items()
        ],
    }


# =============================================================================
# EVENT RECORDING
# =============================================================================

@router.post("/event/delivery")
async def record_delivery(
    vendor_id: uuid.UUID,
    order_id: uuid.UUID,
    promised_date: datetime,
    actual_date: datetime,
    po_number: Optional[str] = None,
    delivery_window_hours: int = 4,
) -> dict:
    """Record a delivery event for timeliness tracking."""
    event = DeliveryEvent(
        vendor_id=vendor_id,
        order_id=order_id,
        promised_date=promised_date,
        actual_date=actual_date,
        po_number=po_number,
        delivery_window_hours=delivery_window_hours,
    )
    
    vendor_scorer.record_delivery(event)
    
    return {
        "status": "recorded",
        "event_id": str(event.event_id),
        "variance_hours": event.variance_hours,
        "on_time": event.on_time,
    }


@router.post("/event/fill")
async def record_fill(
    vendor_id: uuid.UUID,
    order_id: uuid.UUID,
    lines_ordered: int,
    lines_filled: int,
    lines_shorted: int = 0,
    lines_substituted: int = 0,
) -> dict:
    """Record a fill accuracy event."""
    event = FillEvent(
        vendor_id=vendor_id,
        order_id=order_id,
        lines_ordered=lines_ordered,
        lines_filled=lines_filled,
        lines_shorted=lines_shorted,
        lines_substituted=lines_substituted,
        fill_rate_pct=Decimal(lines_filled) / Decimal(lines_ordered) * 100 if lines_ordered > 0 else Decimal("0"),
    )
    
    vendor_scorer.record_fill(event)
    
    return {
        "status": "recorded",
        "event_id": str(event.event_id),
        "fill_rate_pct": str(event.fill_rate_pct.quantize(Decimal("0.1"))),
    }


@router.post("/event/substitution")
async def record_substitution(
    vendor_id: uuid.UUID,
    order_id: uuid.UUID,
    original_product_id: uuid.UUID,
    original_product_name: str,
    original_qty: Decimal,
    substitute_product_name: Optional[str] = None,
    substitute_qty: Optional[Decimal] = None,
    was_acceptable: bool = True,
    price_difference_pct: Decimal = Decimal("0"),
) -> dict:
    """Record a substitution event."""
    event = SubstitutionEvent(
        vendor_id=vendor_id,
        order_id=order_id,
        original_product_id=original_product_id,
        original_product_name=original_product_name,
        original_qty=original_qty,
        substitute_product_name=substitute_product_name,
        substitute_qty=substitute_qty,
        was_acceptable=was_acceptable,
        price_difference_pct=price_difference_pct,
    )
    
    vendor_scorer.record_substitution(event)
    
    return {
        "status": "recorded",
        "event_id": str(event.event_id),
        "was_acceptable": was_acceptable,
    }


@router.post("/event/price")
async def record_price_change(
    vendor_id: uuid.UUID,
    product_id: uuid.UUID,
    product_name: str,
    previous_price_dollars: str,
    new_price_dollars: str,
    change_reason: Optional[str] = None,
) -> dict:
    """Record a price change event."""
    prev_micros = int(Decimal(previous_price_dollars) * 1_000_000)
    new_micros = int(Decimal(new_price_dollars) * 1_000_000)
    
    change_pct = Decimal("0")
    if prev_micros > 0:
        change_pct = Decimal((new_micros - prev_micros) / prev_micros * 100)
    
    event = PriceEvent(
        vendor_id=vendor_id,
        product_id=product_id,
        product_name=product_name,
        previous_price_micros=prev_micros,
        new_price_micros=new_micros,
        change_pct=change_pct,
        change_reason=change_reason,
    )
    
    vendor_scorer.record_price_change(event)
    
    return {
        "status": "recorded",
        "event_id": str(event.event_id),
        "change_pct": str(change_pct.quantize(Decimal("0.01"))),
    }


@router.post("/event/quality")
async def record_quality_issue(
    vendor_id: uuid.UUID,
    order_id: uuid.UUID,
    issue_type: str,
    severity: str,
    description: str,
    resolved: bool = False,
    credit_issued: bool = False,
) -> dict:
    """Record a quality issue event."""
    event = QualityEvent(
        vendor_id=vendor_id,
        order_id=order_id,
        issue_type=issue_type,
        severity=severity,
        description=description,
        resolved=resolved,
        credit_issued=credit_issued,
    )
    
    vendor_scorer.record_quality_issue(event)
    
    return {
        "status": "recorded",
        "event_id": str(event.event_id),
        "severity": severity,
    }


# =============================================================================
# CONFIGURATION
# =============================================================================

@router.get("/config", response_model=VendorScorerConfig)
async def get_config() -> VendorScorerConfig:
    """Get scorer configuration."""
    return vendor_scorer.get_config()


@router.put("/config/weights")
async def update_weights(
    timeliness: Decimal = Query(Decimal("0.30"), ge=0, le=1),
    fill_accuracy: Decimal = Query(Decimal("0.35"), ge=0, le=1),
    substitution: Decimal = Query(Decimal("0.20"), ge=0, le=1),
    price_volatility: Decimal = Query(Decimal("0.15"), ge=0, le=1),
) -> dict:
    """Update scoring weights (must sum to 1.0)."""
    weights = ScoringWeights(
        timeliness=timeliness,
        fill_accuracy=fill_accuracy,
        substitution=substitution,
        price_volatility=price_volatility,
    )
    
    if not weights.validate_sum():
        return {"error": "Weights must sum to 1.0"}
    
    vendor_scorer.set_weights(weights)
    
    return {
        "status": "updated",
        "weights": {
            "timeliness": str(timeliness),
            "fill_accuracy": str(fill_accuracy),
            "substitution": str(substitution),
            "price_volatility": str(price_volatility),
        },
    }


@router.delete("/data/clear")
async def clear_data() -> dict:
    """Clear all data (for testing)."""
    vendor_scorer.clear_data()
    return {"status": "cleared"}


# =============================================================================
# DEMO
# =============================================================================

@router.post("/demo/setup")
async def setup_demo() -> dict:
    """
    Set up demo data for vendor reliability scoring.
    
    Creates sample vendors with varied performance.
    """
    vendor_scorer.clear_data()
    
    now = datetime.utcnow()
    
    # Vendor 1: Sysco - Good performer
    sysco_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    vendor_scorer.register_vendor(sysco_id, "Sysco")
    
    # Sysco deliveries - mostly on time
    for i in range(10):
        promised = now - timedelta(days=i*3)
        variance = -1 if i % 3 == 0 else (2 if i % 4 == 0 else 0)  # Mostly on time
        actual = promised + timedelta(hours=variance)
        
        vendor_scorer.record_delivery(DeliveryEvent(
            vendor_id=sysco_id,
            order_id=uuid.uuid4(),
            promised_date=promised,
            actual_date=actual,
        ))
    
    # Sysco fills - high accuracy
    for i in range(10):
        vendor_scorer.record_fill(FillEvent(
            vendor_id=sysco_id,
            order_id=uuid.uuid4(),
            lines_ordered=20,
            lines_filled=19 if i % 5 == 0 else 20,
            lines_shorted=1 if i % 5 == 0 else 0,
            fill_rate_pct=Decimal("95") if i % 5 == 0 else Decimal("100"),
        ))
    
    # Vendor 2: US Foods - Average performer
    usfoods_id = uuid.UUID("22222222-2222-2222-2222-222222222222")
    vendor_scorer.register_vendor(usfoods_id, "US Foods")
    
    # US Foods deliveries - some late
    for i in range(8):
        promised = now - timedelta(days=i*4)
        variance = 6 if i % 3 == 0 else (3 if i % 2 == 0 else 0)  # Some late
        actual = promised + timedelta(hours=variance)
        
        vendor_scorer.record_delivery(DeliveryEvent(
            vendor_id=usfoods_id,
            order_id=uuid.uuid4(),
            promised_date=promised,
            actual_date=actual,
        ))
    
    # US Foods fills - decent
    for i in range(8):
        order_id = uuid.uuid4()
        filled = 17 if i % 3 == 0 else 19
        
        vendor_scorer.record_fill(FillEvent(
            vendor_id=usfoods_id,
            order_id=order_id,
            lines_ordered=20,
            lines_filled=filled,
            lines_shorted=20 - filled,
            fill_rate_pct=Decimal(filled) / Decimal(20) * 100,
        ))
        
        # Some substitutions
        if i % 3 == 0:
            vendor_scorer.record_substitution(SubstitutionEvent(
                vendor_id=usfoods_id,
                order_id=order_id,
                original_product_id=uuid.uuid4(),
                original_product_name="Chicken Breast",
                original_qty=Decimal("50"),
                substitute_product_name="Chicken Thigh",
                substitute_qty=Decimal("50"),
                was_acceptable=True,
            ))
    
    # Vendor 3: Local Produce - Poor performer
    local_id = uuid.UUID("33333333-3333-3333-3333-333333333333")
    vendor_scorer.register_vendor(local_id, "Local Produce Co")
    
    # Local deliveries - frequently late
    for i in range(6):
        promised = now - timedelta(days=i*5)
        variance = 8 if i % 2 == 0 else 12  # Often late
        actual = promised + timedelta(hours=variance)
        
        vendor_scorer.record_delivery(DeliveryEvent(
            vendor_id=local_id,
            order_id=uuid.uuid4(),
            promised_date=promised,
            actual_date=actual,
        ))
    
    # Local fills - issues
    for i in range(6):
        order_id = uuid.uuid4()
        filled = 15 if i % 2 == 0 else 17
        
        vendor_scorer.record_fill(FillEvent(
            vendor_id=local_id,
            order_id=order_id,
            lines_ordered=20,
            lines_filled=filled,
            lines_shorted=20 - filled,
            fill_rate_pct=Decimal(filled) / Decimal(20) * 100,
        ))
        
        # Quality issues
        if i % 2 == 0:
            vendor_scorer.record_quality_issue(QualityEvent(
                vendor_id=local_id,
                order_id=order_id,
                issue_type="freshness",
                severity="minor",
                description="Produce not as fresh as expected",
            ))
    
    # Price volatility for Local
    for i in range(4):
        prev_price = 100 + i * 5
        new_price = prev_price + 8
        vendor_scorer.record_price_change(PriceEvent(
            vendor_id=local_id,
            product_id=uuid.uuid4(),
            product_name=f"Produce Item {i+1}",
            previous_price_micros=prev_price * 1_000_000,
            new_price_micros=new_price * 1_000_000,
            change_pct=Decimal((new_price - prev_price) / prev_price * 100),
            change_reason="market",
        ))
    
    # Score all vendors
    sysco_score = vendor_scorer.score_vendor(sysco_id)
    usfoods_score = vendor_scorer.score_vendor(usfoods_id)
    local_score = vendor_scorer.score_vendor(local_id)
    
    return {
        "status": "demo_data_created",
        "vendors_created": 3,
        "scores": [
            {
                "vendor": "Sysco",
                "reliability_score": sysco_score.reliability_score if sysco_score else None,
                "tier": sysco_score.tier.value if sysco_score else None,
                "trend": sysco_score.trend.value if sysco_score else None,
            },
            {
                "vendor": "US Foods",
                "reliability_score": usfoods_score.reliability_score if usfoods_score else None,
                "tier": usfoods_score.tier.value if usfoods_score else None,
                "trend": usfoods_score.trend.value if usfoods_score else None,
            },
            {
                "vendor": "Local Produce Co",
                "reliability_score": local_score.reliability_score if local_score else None,
                "tier": local_score.tier.value if local_score else None,
                "trend": local_score.trend.value if local_score else None,
                "warnings": local_score.warnings if local_score else [],
            },
        ],
        "weights": {
            "timeliness": "30%",
            "fill_accuracy": "35%",
            "substitution": "20%",
            "price_volatility": "15%",
        },
    }

"""
PROVENIQ Ops - Predictions API

API endpoints for ML-powered predictions:
- Burn rate calculations
- Stockout predictions
- Alerts
"""

from typing import Optional, List
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.ml import (
    get_burn_rate_calculator,
    get_stockout_predictor,
    BurnRateResult,
    StockoutPrediction,
    StockoutAlert,
)

router = APIRouter(prefix="/predictions", tags=["Predictions"])


# ============================================
# Request/Response Models
# ============================================

class BurnRateResponse(BaseModel):
    """Burn rate calculation response"""
    product_id: str
    burn_rate_7d: float
    burn_rate_30d: float
    burn_rate_90d: float
    weighted_burn_rate: float
    trend: str
    confidence: float
    data_points_7d: int
    data_points_30d: int


class StockoutResponse(BaseModel):
    """Stockout prediction response"""
    product_id: str
    product_name: Optional[str]
    current_quantity: int
    par_level: int
    hours_to_stockout: float
    stockout_date: Optional[str]
    risk_level: str
    risk_score: float
    action: str
    recommended_order_qty: int
    burn_rate: float
    confidence: float


class AlertResponse(BaseModel):
    """Stockout alert response"""
    alert_id: str
    product_id: str
    product_name: str
    severity: str
    hours_remaining: float
    stockout_date: str
    current_quantity: int
    recommended_order_qty: int
    message: str


class ProductInput(BaseModel):
    """Product input for predictions"""
    product_id: str
    name: Optional[str] = None
    current_quantity: int
    par_level: int


class BulkPredictionRequest(BaseModel):
    """Request for bulk predictions"""
    products: List[ProductInput]


# ============================================
# Endpoints
# ============================================

@router.get("/burn-rate/{product_id}", response_model=BurnRateResponse)
async def get_burn_rate(product_id: UUID) -> BurnRateResponse:
    """
    Get burn rate calculation for a product.
    
    Calculates daily consumption rate from historical snapshots.
    Returns rates for 7d, 30d, 90d windows plus weighted average.
    """
    calculator = get_burn_rate_calculator()
    result = await calculator.calculate_burn_rate(product_id)
    
    return BurnRateResponse(
        product_id=str(result.product_id),
        burn_rate_7d=float(result.burn_rate_7d),
        burn_rate_30d=float(result.burn_rate_30d),
        burn_rate_90d=float(result.burn_rate_90d),
        weighted_burn_rate=float(result.weighted_burn_rate),
        trend=result.trend,
        confidence=float(result.confidence),
        data_points_7d=result.data_points_7d,
        data_points_30d=result.data_points_30d,
    )


@router.post("/stockout", response_model=StockoutResponse)
async def predict_stockout(
    product_id: UUID,
    current_quantity: int,
    par_level: int,
    product_name: Optional[str] = None,
) -> StockoutResponse:
    """
    Predict stockout for a single product.
    
    Returns:
    - Hours until stockout
    - Risk level (low, medium, high, critical)
    - Recommended action
    - Suggested order quantity
    """
    predictor = get_stockout_predictor()
    result = await predictor.predict_stockout(
        product_id=product_id,
        current_quantity=current_quantity,
        par_level=par_level,
        product_name=product_name,
    )
    
    return StockoutResponse(
        product_id=str(result.product_id),
        product_name=result.product_name,
        current_quantity=result.current_quantity,
        par_level=result.par_level,
        hours_to_stockout=float(result.hours_to_stockout),
        stockout_date=result.stockout_date.isoformat() if result.stockout_date else None,
        risk_level=result.risk_level,
        risk_score=float(result.risk_score),
        action=result.action,
        recommended_order_qty=result.recommended_order_qty,
        burn_rate=float(result.burn_rate),
        confidence=float(result.confidence),
    )


@router.post("/stockout/bulk", response_model=List[StockoutResponse])
async def predict_stockouts_bulk(request: BulkPredictionRequest) -> List[StockoutResponse]:
    """
    Predict stockouts for multiple products.
    
    Returns predictions sorted by risk (highest first).
    """
    predictor = get_stockout_predictor()
    
    products = [
        {
            "id": UUID(p.product_id),
            "name": p.name,
            "current_quantity": p.current_quantity,
            "par_level": p.par_level,
        }
        for p in request.products
    ]
    
    results = await predictor.predict_all_stockouts(products)
    
    return [
        StockoutResponse(
            product_id=str(r.product_id),
            product_name=r.product_name,
            current_quantity=r.current_quantity,
            par_level=r.par_level,
            hours_to_stockout=float(r.hours_to_stockout),
            stockout_date=r.stockout_date.isoformat() if r.stockout_date else None,
            risk_level=r.risk_level,
            risk_score=float(r.risk_score),
            action=r.action,
            recommended_order_qty=r.recommended_order_qty,
            burn_rate=float(r.burn_rate),
            confidence=float(r.confidence),
        )
        for r in results
    ]


@router.post("/alerts", response_model=List[AlertResponse])
async def get_stockout_alerts(
    request: BulkPredictionRequest,
    threshold_hours: int = Query(72, description="Alert if stockout within this many hours"),
) -> List[AlertResponse]:
    """
    Get stockout alerts for products at risk.
    
    Returns alerts for products predicted to stockout within threshold.
    Alerts are sorted by severity (emergency > critical > warning).
    """
    predictor = get_stockout_predictor()
    
    products = [
        {
            "id": UUID(p.product_id),
            "name": p.name,
            "current_quantity": p.current_quantity,
            "par_level": p.par_level,
        }
        for p in request.products
    ]
    
    alerts = await predictor.get_alerts(products, threshold_hours=threshold_hours)
    
    # Sort by severity
    severity_order = {"emergency": 0, "critical": 1, "warning": 2}
    alerts.sort(key=lambda a: severity_order.get(a.severity, 99))
    
    return [
        AlertResponse(
            alert_id=str(a.alert_id),
            product_id=str(a.product_id),
            product_name=a.product_name,
            severity=a.severity,
            hours_remaining=float(a.hours_remaining),
            stockout_date=a.stockout_date.isoformat(),
            current_quantity=a.current_quantity,
            recommended_order_qty=a.recommended_order_qty,
            message=a.message,
        )
        for a in alerts
    ]


@router.get("/dashboard")
async def get_prediction_dashboard() -> dict:
    """
    Get prediction dashboard summary.
    
    Returns overview of all predictions with counts by risk level.
    Uses mock data for demo purposes.
    """
    predictor = get_stockout_predictor()
    
    # Mock product data for demo
    from uuid import uuid4
    mock_products = [
        {"id": uuid4(), "name": "Chicken Breast", "current_quantity": 15, "par_level": 20},
        {"id": uuid4(), "name": "Ground Beef", "current_quantity": 8, "par_level": 15},
        {"id": uuid4(), "name": "Salmon Fillet", "current_quantity": 3, "par_level": 10},
        {"id": uuid4(), "name": "Yellow Onions", "current_quantity": 45, "par_level": 30},
        {"id": uuid4(), "name": "Romaine Lettuce", "current_quantity": 12, "par_level": 25},
    ]
    
    predictions = await predictor.predict_all_stockouts(mock_products)
    alerts = await predictor.get_alerts(mock_products, threshold_hours=72)
    
    # Count by risk level
    risk_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for p in predictions:
        risk_counts[p.risk_level] = risk_counts.get(p.risk_level, 0) + 1
    
    # Count by severity
    alert_counts = {"emergency": 0, "critical": 0, "warning": 0}
    for a in alerts:
        alert_counts[a.severity] = alert_counts.get(a.severity, 0) + 1
    
    return {
        "summary": {
            "total_products": len(predictions),
            "products_at_risk": len([p for p in predictions if p.risk_level in ["critical", "high"]]),
            "active_alerts": len(alerts),
        },
        "risk_breakdown": risk_counts,
        "alert_breakdown": alert_counts,
        "top_risks": [
            {
                "product_name": p.product_name,
                "hours_to_stockout": float(p.hours_to_stockout),
                "risk_level": p.risk_level,
                "action": p.action,
            }
            for p in predictions[:5]
        ],
    }

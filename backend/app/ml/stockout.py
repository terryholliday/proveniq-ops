"""
PROVENIQ Ops - Stockout Prediction Service

Predicts when products will run out based on:
- Current inventory levels
- Calculated burn rates
- Pending orders
- Historical patterns

This is P0 ML - enables proactive reordering.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any
from uuid import UUID
import logging

from pydantic import BaseModel, Field

from .burn_rate import BurnRateCalculator, BurnRateResult, get_burn_rate_calculator

logger = logging.getLogger(__name__)


# ============================================
# Data Models
# ============================================

class StockoutPrediction(BaseModel):
    """Stockout prediction for a product"""
    product_id: UUID
    product_name: Optional[str] = None
    
    # Current state
    current_quantity: int
    par_level: int
    
    # Prediction
    hours_to_stockout: Decimal
    stockout_date: Optional[datetime] = None
    hours_to_par: Decimal  # When it hits par level
    par_date: Optional[datetime] = None
    
    # Risk assessment
    risk_level: str = "low"  # low, medium, high, critical
    risk_score: Decimal = Decimal("0")  # 0-1
    
    # Action recommendation
    action: str = "none"  # none, monitor, order_soon, order_now, emergency
    recommended_order_qty: int = 0
    
    # Confidence
    confidence: Decimal = Decimal("0.5")
    
    # Context
    burn_rate: Decimal = Decimal("0")
    pending_orders_qty: int = 0
    
    # Timestamps
    predicted_at: datetime = Field(default_factory=datetime.utcnow)


class StockoutAlert(BaseModel):
    """Alert for impending stockout"""
    alert_id: UUID = Field(default_factory=lambda: __import__('uuid').uuid4())
    product_id: UUID
    product_name: str
    
    severity: str  # warning, critical, emergency
    hours_remaining: Decimal
    stockout_date: datetime
    
    current_quantity: int
    recommended_order_qty: int
    
    message: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================
# Stockout Predictor
# ============================================

class StockoutPredictor:
    """
    Predicts stockouts based on burn rates and current inventory.
    
    Algorithm:
    1. Get current inventory level
    2. Calculate burn rate from historical data
    3. Account for pending orders
    4. Predict hours to stockout
    5. Assess risk level
    6. Generate action recommendation
    """
    
    def __init__(self, burn_calculator: Optional[BurnRateCalculator] = None):
        self.burn_calculator = burn_calculator or get_burn_rate_calculator()
    
    async def predict_stockout(
        self,
        product_id: UUID,
        current_quantity: int,
        par_level: int,
        pending_orders: Optional[List[Dict[str, Any]]] = None,
        product_name: Optional[str] = None,
    ) -> StockoutPrediction:
        """
        Predict stockout for a single product.
        
        Args:
            product_id: Product to predict
            current_quantity: Current on-hand inventory
            par_level: Target minimum inventory level
            pending_orders: List of pending orders for this product
            product_name: Optional product name for display
        
        Returns:
            StockoutPrediction with timing and recommendations
        """
        now = datetime.utcnow()
        
        # Get burn rate
        burn_result = await self.burn_calculator.calculate_burn_rate(product_id)
        burn_rate = burn_result.weighted_burn_rate
        
        # Account for pending orders
        pending_qty = 0
        if pending_orders:
            pending_qty = sum(o.get("quantity", 0) for o in pending_orders)
        
        # Calculate hours to stockout
        if burn_rate <= 0:
            hours_to_stockout = Decimal("9999")
            hours_to_par = Decimal("9999")
        else:
            daily_burn = float(burn_rate)
            hourly_burn = daily_burn / 24
            
            # Effective inventory (current + pending)
            effective_qty = current_quantity + pending_qty
            
            hours_to_stockout = Decimal(str(effective_qty / hourly_burn)) if hourly_burn > 0 else Decimal("9999")
            
            # Hours until hitting par level
            qty_above_par = max(0, effective_qty - par_level)
            hours_to_par = Decimal(str(qty_above_par / hourly_burn)) if hourly_burn > 0 else Decimal("9999")
        
        # Calculate dates
        stockout_date = None
        par_date = None
        if hours_to_stockout < Decimal("9999"):
            stockout_date = now + timedelta(hours=float(hours_to_stockout))
        if hours_to_par < Decimal("9999"):
            par_date = now + timedelta(hours=float(hours_to_par))
        
        # Assess risk
        risk_level, risk_score = self._assess_risk(
            hours_to_stockout,
            hours_to_par,
            current_quantity,
            par_level,
        )
        
        # Generate action recommendation
        action, recommended_qty = self._recommend_action(
            risk_level,
            current_quantity,
            par_level,
            burn_rate,
            pending_qty,
        )
        
        # Calculate confidence
        confidence = self._calculate_confidence(burn_result, current_quantity)
        
        return StockoutPrediction(
            product_id=product_id,
            product_name=product_name,
            current_quantity=current_quantity,
            par_level=par_level,
            hours_to_stockout=hours_to_stockout,
            stockout_date=stockout_date,
            hours_to_par=hours_to_par,
            par_date=par_date,
            risk_level=risk_level,
            risk_score=risk_score,
            action=action,
            recommended_order_qty=recommended_qty,
            confidence=confidence,
            burn_rate=burn_rate,
            pending_orders_qty=pending_qty,
        )
    
    async def predict_all_stockouts(
        self,
        products: List[Dict[str, Any]],
        pending_orders: Optional[Dict[UUID, List[Dict[str, Any]]]] = None,
    ) -> List[StockoutPrediction]:
        """
        Predict stockouts for all products.
        
        Args:
            products: List of product dicts with id, name, current_quantity, par_level
            pending_orders: Dict mapping product_id to list of pending orders
        
        Returns:
            List of predictions sorted by risk (highest first)
        """
        predictions = []
        
        for product in products:
            product_id = product.get("id") or product.get("product_id")
            if isinstance(product_id, str):
                product_id = UUID(product_id)
            
            product_orders = None
            if pending_orders and product_id in pending_orders:
                product_orders = pending_orders[product_id]
            
            prediction = await self.predict_stockout(
                product_id=product_id,
                current_quantity=product.get("current_quantity", 0),
                par_level=product.get("par_level", 0),
                pending_orders=product_orders,
                product_name=product.get("name"),
            )
            predictions.append(prediction)
        
        # Sort by risk (highest first)
        predictions.sort(key=lambda p: float(p.risk_score), reverse=True)
        
        return predictions
    
    async def get_alerts(
        self,
        products: List[Dict[str, Any]],
        threshold_hours: int = 72,
    ) -> List[StockoutAlert]:
        """
        Get stockout alerts for products at risk.
        
        Args:
            products: List of products to check
            threshold_hours: Alert if stockout within this many hours
        
        Returns:
            List of alerts for at-risk products
        """
        predictions = await self.predict_all_stockouts(products)
        alerts = []
        
        for pred in predictions:
            if pred.hours_to_stockout > threshold_hours:
                continue
            
            # Determine severity
            if pred.hours_to_stockout <= 12:
                severity = "emergency"
            elif pred.hours_to_stockout <= 24:
                severity = "critical"
            else:
                severity = "warning"
            
            # Generate message
            if severity == "emergency":
                message = f"EMERGENCY: {pred.product_name or pred.product_id} will stockout in {pred.hours_to_stockout:.0f} hours. Order immediately."
            elif severity == "critical":
                message = f"CRITICAL: {pred.product_name or pred.product_id} will stockout in {pred.hours_to_stockout:.0f} hours. Order now."
            else:
                message = f"WARNING: {pred.product_name or pred.product_id} will stockout in {pred.hours_to_stockout:.0f} hours. Consider ordering."
            
            alerts.append(StockoutAlert(
                product_id=pred.product_id,
                product_name=pred.product_name or str(pred.product_id),
                severity=severity,
                hours_remaining=pred.hours_to_stockout,
                stockout_date=pred.stockout_date or datetime.utcnow(),
                current_quantity=pred.current_quantity,
                recommended_order_qty=pred.recommended_order_qty,
                message=message,
            ))
        
        return alerts
    
    def _assess_risk(
        self,
        hours_to_stockout: Decimal,
        hours_to_par: Decimal,
        current_quantity: int,
        par_level: int,
    ) -> tuple[str, Decimal]:
        """
        Assess risk level based on time to stockout.
        
        Risk levels:
        - critical: < 12 hours
        - high: < 24 hours
        - medium: < 72 hours
        - low: >= 72 hours
        """
        hours = float(hours_to_stockout)
        
        if hours < 12:
            return "critical", Decimal("0.95")
        elif hours < 24:
            return "high", Decimal("0.75")
        elif hours < 72:
            return "medium", Decimal("0.50")
        else:
            # Score based on how close to par
            if current_quantity <= par_level:
                return "medium", Decimal("0.40")
            else:
                # Calculate score based on buffer above par
                buffer_ratio = (current_quantity - par_level) / par_level if par_level > 0 else 1
                risk_score = max(Decimal("0.1"), Decimal("0.3") - Decimal(str(buffer_ratio * 0.2)))
                return "low", risk_score
    
    def _recommend_action(
        self,
        risk_level: str,
        current_quantity: int,
        par_level: int,
        burn_rate: Decimal,
        pending_qty: int,
    ) -> tuple[str, int]:
        """
        Recommend action and order quantity.
        
        Actions:
        - emergency: Stockout imminent, expedited order
        - order_now: Should order immediately
        - order_soon: Should order within 24 hours
        - monitor: Keep watching
        - none: No action needed
        """
        # Calculate recommended quantity
        # Target: 7 days of coverage + buffer to par
        daily_burn = float(burn_rate)
        target_coverage_days = 7
        target_qty = max(par_level, int(daily_burn * target_coverage_days * 1.2))
        
        effective_qty = current_quantity + pending_qty
        order_qty = max(0, target_qty - effective_qty)
        
        if risk_level == "critical":
            return "emergency", order_qty
        elif risk_level == "high":
            return "order_now", order_qty
        elif risk_level == "medium":
            return "order_soon", order_qty
        elif current_quantity <= par_level:
            return "monitor", order_qty
        else:
            return "none", 0
    
    def _calculate_confidence(
        self,
        burn_result: BurnRateResult,
        current_quantity: int,
    ) -> Decimal:
        """Calculate prediction confidence"""
        # Base on burn rate confidence
        base_confidence = burn_result.confidence
        
        # Adjust for data quality
        if burn_result.data_points_7d < 3:
            base_confidence *= Decimal("0.7")
        
        # Higher confidence with more inventory (more time to correct)
        if current_quantity > 100:
            base_confidence = min(Decimal("0.95"), base_confidence * Decimal("1.1"))
        
        return min(Decimal("0.95"), base_confidence)


# ============================================
# Singleton Instance
# ============================================

_predictor_instance: Optional[StockoutPredictor] = None


def get_stockout_predictor() -> StockoutPredictor:
    """Get stockout predictor instance"""
    global _predictor_instance
    if _predictor_instance is None:
        _predictor_instance = StockoutPredictor()
    return _predictor_instance

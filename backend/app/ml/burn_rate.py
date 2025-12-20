"""
PROVENIQ Ops - Burn Rate Calculation Service

Calculates daily burn rates from historical inventory snapshots.
Uses time-series analysis for accurate consumption tracking.

This is P0 ML - the foundation for all predictive features.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any
from uuid import UUID
import logging

from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ============================================
# Data Models
# ============================================

class BurnRateResult(BaseModel):
    """Calculated burn rate for a product"""
    product_id: UUID
    product_name: Optional[str] = None
    
    # Burn rates (units per day)
    burn_rate_7d: Decimal = Decimal("0")
    burn_rate_30d: Decimal = Decimal("0")
    burn_rate_90d: Decimal = Decimal("0")
    
    # Weighted average (for predictions)
    weighted_burn_rate: Decimal = Decimal("0")
    
    # Variance metrics
    variance_coefficient: Decimal = Decimal("0")  # CV = std/mean
    trend: str = "stable"  # increasing, decreasing, stable
    
    # Data quality
    data_points_7d: int = 0
    data_points_30d: int = 0
    data_points_90d: int = 0
    confidence: Decimal = Decimal("0.5")
    
    # Timestamps
    calculated_at: datetime = Field(default_factory=datetime.utcnow)
    last_snapshot_at: Optional[datetime] = None


class DailyConsumption(BaseModel):
    """Daily consumption record"""
    date: datetime
    starting_qty: int
    ending_qty: int
    consumed: int
    received: int = 0
    net_change: int = 0


# ============================================
# Burn Rate Calculator
# ============================================

class BurnRateCalculator:
    """
    Calculates burn rates from inventory snapshot history.
    
    Algorithm:
    1. Fetch snapshots for product over time windows (7d, 30d, 90d)
    2. Calculate daily deltas (accounting for receiving)
    3. Compute average burn rate per window
    4. Calculate variance for confidence scoring
    5. Detect trend (increasing/decreasing/stable)
    """
    
    def __init__(self, db: Optional[AsyncSession] = None):
        self.db = db
    
    async def calculate_burn_rate(
        self,
        product_id: UUID,
        as_of: Optional[datetime] = None,
    ) -> BurnRateResult:
        """
        Calculate burn rates for a product.
        
        Args:
            product_id: Product to analyze
            as_of: Calculate as of this date (default: now)
        
        Returns:
            BurnRateResult with burn rates and confidence
        """
        if as_of is None:
            as_of = datetime.utcnow()
        
        # Get snapshots for each window
        snapshots_7d = await self._get_snapshots(product_id, as_of, days=7)
        snapshots_30d = await self._get_snapshots(product_id, as_of, days=30)
        snapshots_90d = await self._get_snapshots(product_id, as_of, days=90)
        
        # Calculate daily consumption for each window
        consumption_7d = self._calculate_daily_consumption(snapshots_7d)
        consumption_30d = self._calculate_daily_consumption(snapshots_30d)
        consumption_90d = self._calculate_daily_consumption(snapshots_90d)
        
        # Calculate burn rates
        burn_7d = self._average_burn_rate(consumption_7d)
        burn_30d = self._average_burn_rate(consumption_30d)
        burn_90d = self._average_burn_rate(consumption_90d)
        
        # Weighted average: 50% 7d, 30% 30d, 20% 90d
        weighted = (
            burn_7d * Decimal("0.5") +
            burn_30d * Decimal("0.3") +
            burn_90d * Decimal("0.2")
        )
        
        # Calculate variance coefficient
        all_burns = [c.consumed for c in consumption_30d if c.consumed > 0]
        variance_coef = self._calculate_variance_coefficient(all_burns)
        
        # Detect trend
        trend = self._detect_trend(consumption_30d)
        
        # Calculate confidence based on data quality
        confidence = self._calculate_confidence(
            len(consumption_7d),
            len(consumption_30d),
            len(consumption_90d),
            variance_coef,
        )
        
        # Get last snapshot timestamp
        last_snapshot_at = None
        if snapshots_7d:
            last_snapshot_at = max(s["scanned_at"] for s in snapshots_7d)
        
        return BurnRateResult(
            product_id=product_id,
            burn_rate_7d=burn_7d,
            burn_rate_30d=burn_30d,
            burn_rate_90d=burn_90d,
            weighted_burn_rate=weighted,
            variance_coefficient=variance_coef,
            trend=trend,
            data_points_7d=len(consumption_7d),
            data_points_30d=len(consumption_30d),
            data_points_90d=len(consumption_90d),
            confidence=confidence,
            last_snapshot_at=last_snapshot_at,
        )
    
    async def calculate_all_burn_rates(
        self,
        product_ids: Optional[List[UUID]] = None,
    ) -> List[BurnRateResult]:
        """Calculate burn rates for multiple products"""
        if product_ids is None:
            # Get all products with snapshots
            product_ids = await self._get_products_with_snapshots()
        
        results = []
        for product_id in product_ids:
            result = await self.calculate_burn_rate(product_id)
            results.append(result)
        
        return results
    
    async def _get_snapshots(
        self,
        product_id: UUID,
        as_of: datetime,
        days: int,
    ) -> List[Dict[str, Any]]:
        """
        Fetch snapshots for a product within time window.
        
        In production, this queries the database.
        Currently uses mock data for testing.
        """
        if self.db is None:
            # Mock data for testing
            return self._generate_mock_snapshots(product_id, as_of, days)
        
        # Real database query
        from app.db import InventorySnapshot
        
        start_date = as_of - timedelta(days=days)
        
        query = (
            select(InventorySnapshot)
            .where(InventorySnapshot.product_id == product_id)
            .where(InventorySnapshot.scanned_at >= start_date)
            .where(InventorySnapshot.scanned_at <= as_of)
            .order_by(InventorySnapshot.scanned_at)
        )
        
        result = await self.db.execute(query)
        snapshots = result.scalars().all()
        
        return [
            {
                "id": s.id,
                "product_id": s.product_id,
                "quantity": s.quantity,
                "scanned_at": s.scanned_at,
                "scan_method": s.scan_method,
            }
            for s in snapshots
        ]
    
    def _generate_mock_snapshots(
        self,
        product_id: UUID,
        as_of: datetime,
        days: int,
    ) -> List[Dict[str, Any]]:
        """Generate mock snapshot data for testing"""
        import random
        from uuid import uuid4
        
        snapshots = []
        current_qty = random.randint(50, 200)
        
        for day in range(days, 0, -1):
            date = as_of - timedelta(days=day)
            
            # Simulate daily consumption (5-15 units)
            consumed = random.randint(5, 15)
            
            # Occasional receiving (every 5-7 days)
            received = 0
            if day % random.randint(5, 7) == 0:
                received = random.randint(30, 60)
            
            current_qty = max(0, current_qty - consumed + received)
            
            snapshots.append({
                "id": uuid4(),
                "product_id": product_id,
                "quantity": current_qty,
                "scanned_at": date,
                "scan_method": "barcode",
            })
        
        return snapshots
    
    def _calculate_daily_consumption(
        self,
        snapshots: List[Dict[str, Any]],
    ) -> List[DailyConsumption]:
        """Calculate daily consumption from sequential snapshots"""
        if len(snapshots) < 2:
            return []
        
        consumption = []
        
        for i in range(1, len(snapshots)):
            prev = snapshots[i - 1]
            curr = snapshots[i]
            
            starting = prev["quantity"]
            ending = curr["quantity"]
            
            # Net change (negative = consumption, positive = receiving)
            net_change = ending - starting
            
            # Estimate consumed vs received
            if net_change < 0:
                consumed = abs(net_change)
                received = 0
            else:
                consumed = 0
                received = net_change
            
            consumption.append(DailyConsumption(
                date=curr["scanned_at"],
                starting_qty=starting,
                ending_qty=ending,
                consumed=consumed,
                received=received,
                net_change=net_change,
            ))
        
        return consumption
    
    def _average_burn_rate(
        self,
        consumption: List[DailyConsumption],
    ) -> Decimal:
        """Calculate average daily burn rate"""
        if not consumption:
            return Decimal("0")
        
        total_consumed = sum(c.consumed for c in consumption)
        days = len(consumption)
        
        return Decimal(str(total_consumed / days)) if days > 0 else Decimal("0")
    
    def _calculate_variance_coefficient(
        self,
        values: List[int],
    ) -> Decimal:
        """Calculate coefficient of variation (std/mean)"""
        if not values or len(values) < 2:
            return Decimal("0")
        
        mean = sum(values) / len(values)
        if mean == 0:
            return Decimal("0")
        
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        std = variance ** 0.5
        
        cv = std / mean
        return Decimal(str(round(cv, 4)))
    
    def _detect_trend(
        self,
        consumption: List[DailyConsumption],
    ) -> str:
        """
        Detect consumption trend.
        
        Uses simple linear regression slope.
        """
        if len(consumption) < 7:
            return "stable"
        
        # Get recent vs older consumption
        midpoint = len(consumption) // 2
        first_half = [c.consumed for c in consumption[:midpoint]]
        second_half = [c.consumed for c in consumption[midpoint:]]
        
        avg_first = sum(first_half) / len(first_half) if first_half else 0
        avg_second = sum(second_half) / len(second_half) if second_half else 0
        
        # 10% threshold for trend detection
        if avg_second > avg_first * 1.1:
            return "increasing"
        elif avg_second < avg_first * 0.9:
            return "decreasing"
        else:
            return "stable"
    
    def _calculate_confidence(
        self,
        points_7d: int,
        points_30d: int,
        points_90d: int,
        variance_coef: Decimal,
    ) -> Decimal:
        """
        Calculate confidence score based on data quality.
        
        Factors:
        - More data points = higher confidence
        - Lower variance = higher confidence
        """
        # Base confidence from data availability
        data_score = min(1.0, (points_7d * 0.1 + points_30d * 0.02 + points_90d * 0.005))
        
        # Penalize high variance
        variance_penalty = min(0.3, float(variance_coef) * 0.3)
        
        confidence = max(0.2, data_score - variance_penalty)
        
        return Decimal(str(round(confidence, 2)))
    
    async def _get_products_with_snapshots(self) -> List[UUID]:
        """Get all products that have snapshot data"""
        if self.db is None:
            # Mock: return some UUIDs
            from uuid import uuid4
            return [uuid4() for _ in range(5)]
        
        from app.db import InventorySnapshot
        
        query = select(InventorySnapshot.product_id).distinct()
        result = await self.db.execute(query)
        return [row[0] for row in result.fetchall()]


# ============================================
# Singleton Instance
# ============================================

_calculator_instance: Optional[BurnRateCalculator] = None


def get_burn_rate_calculator(db: Optional[AsyncSession] = None) -> BurnRateCalculator:
    """Get burn rate calculator instance"""
    global _calculator_instance
    if _calculator_instance is None or db is not None:
        _calculator_instance = BurnRateCalculator(db)
    return _calculator_instance

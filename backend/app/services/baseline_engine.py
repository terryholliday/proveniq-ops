"""
PROVENIQ Ops - Baseline Engine
Phase 0-1: DATA GRAVITY - Baselines Earned Over Time

CRITICAL GOVERNANCE:
- Baselines are EARNED from operational data over time
- Baselines can NEVER be imported from external systems
- After 6-12 months, these baselines cannot be replicated elsewhere
- This is the foundation of the moat

What "normal" looks like:
- Daily consumption patterns per product
- Weekly order patterns per location
- Shrinkage rates by category
- Delivery times by vendor
- Price variance patterns
"""

import uuid
import json
import statistics
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field
import logging

from app.db.session import async_session_maker

logger = logging.getLogger(__name__)


class BaselineType(str, Enum):
    """Types of operational baselines we track."""
    DAILY_CONSUMPTION = "daily_consumption"
    WEEKLY_ORDERS = "weekly_orders"
    SHRINKAGE_RATE = "shrinkage_rate"
    DELIVERY_TIME = "delivery_time"
    PRICE_VARIANCE = "price_variance"
    SCAN_FREQUENCY = "scan_frequency"


class BaselineWindow(int, Enum):
    """Time windows for baseline calculation."""
    SEVEN_DAYS = 7
    THIRTY_DAYS = 30
    NINETY_DAYS = 90


class OperationalBaseline(BaseModel):
    """
    An operational baseline calculated from historical data.
    
    These baselines are EARNED over time - they cannot be imported.
    This is the data gravity that creates the moat.
    """
    baseline_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    org_id: uuid.UUID
    location_id: Optional[uuid.UUID] = None
    product_id: Optional[uuid.UUID] = None
    
    baseline_type: BaselineType
    window_days: int
    window_start: datetime
    window_end: datetime
    
    # Statistical measures (earned from data)
    mean_value: Decimal
    std_dev: Decimal
    min_value: Decimal
    max_value: Decimal
    median_value: Decimal
    sample_count: int
    
    # Confidence increases with more data
    confidence_score: Decimal = Field(ge=0, le=1)
    
    # Percentiles for anomaly detection
    p05: Optional[Decimal] = None
    p25: Optional[Decimal] = None
    p75: Optional[Decimal] = None
    p95: Optional[Decimal] = None
    
    calculated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BaselineEngine:
    """
    Engine for calculating and managing operational baselines.
    
    MOAT PRINCIPLE:
    - Baselines are earned from YOUR operational data over time
    - They cannot be purchased, imported, or replicated
    - After months of use, switching costs become prohibitive
    - Competitors starting later cannot catch up
    """
    
    # Minimum samples required for different confidence levels
    MIN_SAMPLES_LOW = 7      # 0.3 confidence
    MIN_SAMPLES_MEDIUM = 30  # 0.6 confidence
    MIN_SAMPLES_HIGH = 90    # 0.9 confidence
    
    async def calculate_baseline(
        self,
        org_id: uuid.UUID,
        baseline_type: BaselineType,
        window_days: int,
        location_id: Optional[uuid.UUID] = None,
        product_id: Optional[uuid.UUID] = None,
    ) -> Optional[OperationalBaseline]:
        """
        Calculate a baseline from historical operational data.
        
        This is where data gravity is created - the baseline is
        computed from YOUR historical data and cannot be imported.
        """
        window_end = datetime.now(timezone.utc)
        window_start = window_end - timedelta(days=window_days)
        
        # Get historical data based on baseline type
        data_points = await self._get_data_points(
            org_id=org_id,
            baseline_type=baseline_type,
            window_start=window_start,
            window_end=window_end,
            location_id=location_id,
            product_id=product_id,
        )
        
        if not data_points or len(data_points) < self.MIN_SAMPLES_LOW:
            logger.warning(f"Insufficient data for baseline: {len(data_points)} points")
            return None
        
        # Calculate statistics
        values = [float(d) for d in data_points]
        
        mean_val = Decimal(str(statistics.mean(values)))
        std_dev = Decimal(str(statistics.stdev(values))) if len(values) > 1 else Decimal("0")
        min_val = Decimal(str(min(values)))
        max_val = Decimal(str(max(values)))
        median_val = Decimal(str(statistics.median(values)))
        
        # Calculate percentiles
        sorted_values = sorted(values)
        p05 = Decimal(str(self._percentile(sorted_values, 5)))
        p25 = Decimal(str(self._percentile(sorted_values, 25)))
        p75 = Decimal(str(self._percentile(sorted_values, 75)))
        p95 = Decimal(str(self._percentile(sorted_values, 95)))
        
        # Confidence based on sample count
        confidence = self._calculate_confidence(len(data_points))
        
        baseline = OperationalBaseline(
            org_id=org_id,
            location_id=location_id,
            product_id=product_id,
            baseline_type=baseline_type,
            window_days=window_days,
            window_start=window_start,
            window_end=window_end,
            mean_value=mean_val,
            std_dev=std_dev,
            min_value=min_val,
            max_value=max_val,
            median_value=median_val,
            sample_count=len(data_points),
            confidence_score=confidence,
            p05=p05,
            p25=p25,
            p75=p75,
            p95=p95,
        )
        
        # Persist the baseline
        await self._save_baseline(baseline)
        
        logger.info(f"Baseline calculated: {baseline_type.value} for org {org_id} "
                   f"({len(data_points)} samples, confidence={confidence})")
        
        return baseline
    
    async def _get_data_points(
        self,
        org_id: uuid.UUID,
        baseline_type: BaselineType,
        window_start: datetime,
        window_end: datetime,
        location_id: Optional[uuid.UUID] = None,
        product_id: Optional[uuid.UUID] = None,
    ) -> List[Decimal]:
        """
        Get historical data points for baseline calculation.
        
        Data is pulled from ops_events - the persistent event store.
        """
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            if baseline_type == BaselineType.DAILY_CONSUMPTION:
                # Get daily consumption from inventory updates
                query = """
                    SELECT ABS((payload->>'delta')::numeric) as value
                    FROM ops_events
                    WHERE event_type = 'ops.inventory.updated'
                    AND timestamp >= :window_start
                    AND timestamp <= :window_end
                    AND payload->>'reason' = 'consumption'
                """
            elif baseline_type == BaselineType.SHRINKAGE_RATE:
                # Get shrinkage values
                query = """
                    SELECT (payload->>'variance')::numeric as value
                    FROM ops_events
                    WHERE event_type = 'ops.shrinkage.detected'
                    AND timestamp >= :window_start
                    AND timestamp <= :window_end
                """
            elif baseline_type == BaselineType.WEEKLY_ORDERS:
                # Get order totals
                query = """
                    SELECT (payload->>'total_amount_micros')::numeric / 1000000 as value
                    FROM ops_events
                    WHERE event_type = 'ops.order.queued'
                    AND timestamp >= :window_start
                    AND timestamp <= :window_end
                """
            elif baseline_type == BaselineType.SCAN_FREQUENCY:
                # Get scan events per day
                query = """
                    SELECT COUNT(*) as value
                    FROM ops_events
                    WHERE event_type = 'ops.scan.initiated'
                    AND timestamp >= :window_start
                    AND timestamp <= :window_end
                    GROUP BY DATE(timestamp)
                """
            else:
                return []
            
            params: Dict[str, Any] = {
                "window_start": window_start,
                "window_end": window_end,
            }
            
            # Add filters
            if location_id:
                query += " AND payload->>'location_id' = :location_id"
                params["location_id"] = str(location_id)
            if product_id:
                query += " AND payload->>'product_id' = :product_id"
                params["product_id"] = str(product_id)
            
            result = await session.execute(text(query), params)
            return [Decimal(str(row.value)) for row in result.fetchall() if row.value is not None]
    
    def _percentile(self, sorted_data: List[float], percentile: int) -> float:
        """Calculate percentile from sorted data."""
        if not sorted_data:
            return 0.0
        k = (len(sorted_data) - 1) * percentile / 100
        f = int(k)
        c = f + 1 if f + 1 < len(sorted_data) else f
        return sorted_data[f] + (sorted_data[c] - sorted_data[f]) * (k - f)
    
    def _calculate_confidence(self, sample_count: int) -> Decimal:
        """
        Calculate confidence score based on sample count.
        
        More data = higher confidence = stronger moat.
        """
        if sample_count >= self.MIN_SAMPLES_HIGH:
            return Decimal("0.9")
        elif sample_count >= self.MIN_SAMPLES_MEDIUM:
            # Linear interpolation between 0.6 and 0.9
            ratio = (sample_count - self.MIN_SAMPLES_MEDIUM) / (self.MIN_SAMPLES_HIGH - self.MIN_SAMPLES_MEDIUM)
            return Decimal(str(0.6 + 0.3 * ratio))
        elif sample_count >= self.MIN_SAMPLES_LOW:
            # Linear interpolation between 0.3 and 0.6
            ratio = (sample_count - self.MIN_SAMPLES_LOW) / (self.MIN_SAMPLES_MEDIUM - self.MIN_SAMPLES_LOW)
            return Decimal(str(0.3 + 0.3 * ratio))
        else:
            return Decimal("0.1")
    
    async def _save_baseline(self, baseline: OperationalBaseline) -> None:
        """Persist a baseline to the database."""
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            await session.execute(
                text("""
                    INSERT INTO operational_baselines (
                        id, org_id, location_id, product_id,
                        baseline_type, window_days, window_start, window_end,
                        mean_value, std_dev, min_value, max_value, median_value,
                        sample_count, confidence_score,
                        p05, p25, p75, p95,
                        calculated_at, created_at
                    ) VALUES (
                        :id, :org_id, :location_id, :product_id,
                        :baseline_type, :window_days, :window_start, :window_end,
                        :mean_value, :std_dev, :min_value, :max_value, :median_value,
                        :sample_count, :confidence_score,
                        :p05, :p25, :p75, :p95,
                        :calculated_at, :created_at
                    )
                    ON CONFLICT ON CONSTRAINT uq_baselines_scope DO UPDATE SET
                        window_start = :window_start,
                        window_end = :window_end,
                        mean_value = :mean_value,
                        std_dev = :std_dev,
                        min_value = :min_value,
                        max_value = :max_value,
                        median_value = :median_value,
                        sample_count = :sample_count,
                        confidence_score = :confidence_score,
                        p05 = :p05,
                        p25 = :p25,
                        p75 = :p75,
                        p95 = :p95,
                        calculated_at = :calculated_at
                """),
                {
                    "id": baseline.baseline_id,
                    "org_id": baseline.org_id,
                    "location_id": baseline.location_id,
                    "product_id": baseline.product_id,
                    "baseline_type": baseline.baseline_type.value,
                    "window_days": baseline.window_days,
                    "window_start": baseline.window_start,
                    "window_end": baseline.window_end,
                    "mean_value": baseline.mean_value,
                    "std_dev": baseline.std_dev,
                    "min_value": baseline.min_value,
                    "max_value": baseline.max_value,
                    "median_value": baseline.median_value,
                    "sample_count": baseline.sample_count,
                    "confidence_score": baseline.confidence_score,
                    "p05": baseline.p05,
                    "p25": baseline.p25,
                    "p75": baseline.p75,
                    "p95": baseline.p95,
                    "calculated_at": baseline.calculated_at,
                    "created_at": datetime.now(timezone.utc),
                }
            )
            await session.commit()
    
    async def get_baseline(
        self,
        org_id: uuid.UUID,
        baseline_type: BaselineType,
        window_days: int,
        location_id: Optional[uuid.UUID] = None,
        product_id: Optional[uuid.UUID] = None,
    ) -> Optional[OperationalBaseline]:
        """Get the most recent baseline for given parameters."""
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            query = """
                SELECT * FROM operational_baselines
                WHERE org_id = :org_id
                AND baseline_type = :baseline_type
                AND window_days = :window_days
            """
            params: Dict[str, Any] = {
                "org_id": org_id,
                "baseline_type": baseline_type.value,
                "window_days": window_days,
            }
            
            if location_id:
                query += " AND location_id = :location_id"
                params["location_id"] = location_id
            else:
                query += " AND location_id IS NULL"
            
            if product_id:
                query += " AND product_id = :product_id"
                params["product_id"] = product_id
            else:
                query += " AND product_id IS NULL"
            
            query += " ORDER BY calculated_at DESC LIMIT 1"
            
            result = await session.execute(text(query), params)
            row = result.fetchone()
            
            if not row:
                return None
            
            return OperationalBaseline(
                baseline_id=row.id,
                org_id=row.org_id,
                location_id=row.location_id,
                product_id=row.product_id,
                baseline_type=BaselineType(row.baseline_type),
                window_days=row.window_days,
                window_start=row.window_start,
                window_end=row.window_end,
                mean_value=row.mean_value,
                std_dev=row.std_dev,
                min_value=row.min_value,
                max_value=row.max_value,
                median_value=row.median_value,
                sample_count=row.sample_count,
                confidence_score=row.confidence_score,
                p05=row.p05,
                p25=row.p25,
                p75=row.p75,
                p95=row.p95,
                calculated_at=row.calculated_at,
            )
    
    async def check_anomaly(
        self,
        org_id: uuid.UUID,
        baseline_type: BaselineType,
        observed_value: Decimal,
        location_id: Optional[uuid.UUID] = None,
        product_id: Optional[uuid.UUID] = None,
    ) -> Tuple[bool, Optional[Decimal], Optional[OperationalBaseline]]:
        """
        Check if an observed value is anomalous compared to baseline.
        
        Returns: (is_anomaly, deviation_sigma, baseline_used)
        """
        # Try to get baseline (prefer longer windows for stability)
        baseline = None
        for window in [90, 30, 7]:
            baseline = await self.get_baseline(
                org_id=org_id,
                baseline_type=baseline_type,
                window_days=window,
                location_id=location_id,
                product_id=product_id,
            )
            if baseline and baseline.confidence_score >= Decimal("0.5"):
                break
        
        if not baseline or baseline.std_dev == 0:
            return (False, None, baseline)
        
        # Calculate deviation in standard deviations
        deviation = abs(observed_value - baseline.mean_value) / baseline.std_dev
        
        # Anomaly if > 2 standard deviations
        is_anomaly = deviation > Decimal("2.0")
        
        return (is_anomaly, deviation, baseline)
    
    async def recalculate_all_baselines(
        self,
        org_id: uuid.UUID,
    ) -> Dict[str, int]:
        """
        Recalculate all baselines for an organization.
        
        Should be run periodically (e.g., daily) to keep baselines current.
        """
        results = {}
        
        for baseline_type in BaselineType:
            for window in BaselineWindow:
                try:
                    baseline = await self.calculate_baseline(
                        org_id=org_id,
                        baseline_type=baseline_type,
                        window_days=window.value,
                    )
                    key = f"{baseline_type.value}_{window.value}d"
                    results[key] = baseline.sample_count if baseline else 0
                except Exception as e:
                    logger.error(f"Failed to calculate {baseline_type.value} {window.value}d: {e}")
                    results[f"{baseline_type.value}_{window.value}d"] = -1
        
        return results


# Singleton instance
baseline_engine = BaselineEngine()

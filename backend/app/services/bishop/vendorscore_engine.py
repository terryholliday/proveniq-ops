"""
PROVENIQ Ops - Bishop Vendor Reliability Scorer
Score vendors based on execution, not promises.

LOGIC:
1. Weight metrics by importance
2. Produce rolling score
"""

import uuid
from collections import defaultdict
from datetime import datetime, timedelta, date
from decimal import Decimal
from typing import Optional

from app.models.vendorscore import (
    DeliveryEvent,
    FillEvent,
    FillScore,
    MetricType,
    PriceEvent,
    PriceVolatilityScore,
    QualityEvent,
    ReliabilityTier,
    ScoreTrend,
    ScoringWeights,
    SubstitutionEvent,
    SubstitutionScore,
    TimelinessScore,
    VendorComparison,
    VendorReliabilityScore,
    VendorScoreHistory,
    VendorScorerConfig,
)


class VendorReliabilityScorer:
    """
    Bishop Vendor Reliability Scorer
    
    Scores vendors based on execution, not promises.
    """
    
    def __init__(self) -> None:
        self._config = VendorScorerConfig()
        
        # Vendor registry
        self._vendors: dict[uuid.UUID, str] = {}  # vendor_id -> name
        
        # Event storage
        self._deliveries: dict[uuid.UUID, list[DeliveryEvent]] = defaultdict(list)
        self._fills: dict[uuid.UUID, list[FillEvent]] = defaultdict(list)
        self._substitutions: dict[uuid.UUID, list[SubstitutionEvent]] = defaultdict(list)
        self._prices: dict[uuid.UUID, list[PriceEvent]] = defaultdict(list)
        self._quality: dict[uuid.UUID, list[QualityEvent]] = defaultdict(list)
        
        # Score history
        self._score_history: dict[uuid.UUID, list[VendorReliabilityScore]] = defaultdict(list)
    
    # =========================================================================
    # CONFIGURATION
    # =========================================================================
    
    def configure(self, config: VendorScorerConfig) -> None:
        """Update configuration."""
        self._config = config
    
    def get_config(self) -> VendorScorerConfig:
        """Get current configuration."""
        return self._config
    
    def set_weights(self, weights: ScoringWeights) -> None:
        """Set scoring weights."""
        if weights.validate_sum():
            self._config.weights = weights
    
    # =========================================================================
    # VENDOR REGISTRATION
    # =========================================================================
    
    def register_vendor(self, vendor_id: uuid.UUID, vendor_name: str) -> None:
        """Register a vendor."""
        self._vendors[vendor_id] = vendor_name
    
    def get_vendors(self) -> dict[uuid.UUID, str]:
        """Get all registered vendors."""
        return self._vendors.copy()
    
    # =========================================================================
    # EVENT RECORDING
    # =========================================================================
    
    def record_delivery(self, event: DeliveryEvent) -> None:
        """Record a delivery event."""
        # Calculate variance
        variance = (event.actual_date - event.promised_date).total_seconds() / 3600
        event.variance_hours = int(variance)
        event.on_time = abs(variance) <= event.delivery_window_hours
        
        self._deliveries[event.vendor_id].append(event)
        
        # Auto-register vendor
        if event.vendor_id not in self._vendors:
            self._vendors[event.vendor_id] = f"Vendor-{str(event.vendor_id)[:8]}"
    
    def record_fill(self, event: FillEvent) -> None:
        """Record a fill accuracy event."""
        # Calculate fill rate
        if event.lines_ordered > 0:
            event.fill_rate_pct = Decimal(event.lines_filled) / Decimal(event.lines_ordered) * 100
        
        self._fills[event.vendor_id].append(event)
    
    def record_substitution(self, event: SubstitutionEvent) -> None:
        """Record a substitution event."""
        self._substitutions[event.vendor_id].append(event)
    
    def record_price_change(self, event: PriceEvent) -> None:
        """Record a price change event."""
        # Calculate change percentage
        if event.previous_price_micros > 0:
            change = (event.new_price_micros - event.previous_price_micros) / event.previous_price_micros * 100
            event.change_pct = Decimal(str(change))
        
        self._prices[event.vendor_id].append(event)
    
    def record_quality_issue(self, event: QualityEvent) -> None:
        """Record a quality issue event."""
        self._quality[event.vendor_id].append(event)
    
    # =========================================================================
    # SCORE CALCULATION
    # =========================================================================
    
    def _calculate_timeliness_score(
        self,
        vendor_id: uuid.UUID,
        period_start: datetime,
        period_end: datetime,
    ) -> Optional[TimelinessScore]:
        """Calculate delivery timeliness score."""
        deliveries = [
            d for d in self._deliveries.get(vendor_id, [])
            if period_start <= d.recorded_at <= period_end
        ]
        
        if len(deliveries) < self._config.min_deliveries_for_score:
            return None
        
        on_time = len([d for d in deliveries if d.on_time])
        late = len([d for d in deliveries if d.variance_hours > self._config.on_time_window_hours])
        early = len([d for d in deliveries if d.variance_hours < -self._config.on_time_window_hours])
        
        on_time_pct = Decimal(on_time) / Decimal(len(deliveries)) * 100
        avg_variance = sum(d.variance_hours for d in deliveries) / len(deliveries)
        
        # Score: 100 if 100% on time, decreases with late deliveries
        score = int(on_time_pct)
        
        # Penalize for chronic lateness
        if avg_variance > 8:
            score = max(0, score - 10)
        
        return TimelinessScore(
            score=score,
            weight=self._config.weights.timeliness,
            weighted_score=Decimal(score) * self._config.weights.timeliness,
            sample_count=len(deliveries),
            total_deliveries=len(deliveries),
            on_time_deliveries=on_time,
            late_deliveries=late,
            early_deliveries=early,
            avg_variance_hours=Decimal(str(avg_variance)).quantize(Decimal("0.1")),
            on_time_pct=on_time_pct.quantize(Decimal("0.1")),
        )
    
    def _calculate_fill_score(
        self,
        vendor_id: uuid.UUID,
        period_start: datetime,
        period_end: datetime,
    ) -> Optional[FillScore]:
        """Calculate fill accuracy score."""
        fills = [
            f for f in self._fills.get(vendor_id, [])
            if period_start <= f.recorded_at <= period_end
        ]
        
        if len(fills) < self._config.min_orders_for_score:
            return None
        
        total_lines = sum(f.lines_ordered for f in fills)
        filled_lines = sum(f.lines_filled for f in fills)
        shorted_lines = sum(f.lines_shorted for f in fills)
        
        avg_fill_rate = Decimal(filled_lines) / Decimal(total_lines) * 100 if total_lines > 0 else Decimal("0")
        
        # Score based on fill rate
        score = int(avg_fill_rate)
        
        return FillScore(
            score=score,
            weight=self._config.weights.fill_accuracy,
            weighted_score=Decimal(score) * self._config.weights.fill_accuracy,
            sample_count=len(fills),
            total_orders=len(fills),
            total_lines=total_lines,
            filled_lines=filled_lines,
            shorted_lines=shorted_lines,
            avg_fill_rate_pct=avg_fill_rate.quantize(Decimal("0.1")),
        )
    
    def _calculate_substitution_score(
        self,
        vendor_id: uuid.UUID,
        period_start: datetime,
        period_end: datetime,
    ) -> Optional[SubstitutionScore]:
        """Calculate substitution frequency score."""
        subs = [
            s for s in self._substitutions.get(vendor_id, [])
            if period_start <= s.recorded_at <= period_end
        ]
        
        fills = [
            f for f in self._fills.get(vendor_id, [])
            if period_start <= f.recorded_at <= period_end
        ]
        
        if len(fills) < self._config.min_orders_for_score:
            return None
        
        total_orders = len(fills)
        orders_with_subs = len(set(s.order_id for s in subs))
        acceptable = len([s for s in subs if s.was_acceptable])
        
        # Lower substitution rate = better score
        sub_rate = Decimal(orders_with_subs) / Decimal(total_orders) * 100 if total_orders > 0 else Decimal("0")
        
        # Invert: 0% subs = 100, 50% subs = 50, 100% subs = 0
        score = max(0, 100 - int(sub_rate))
        
        # Bonus for acceptable substitutions
        if subs and acceptable == len(subs):
            score = min(100, score + 5)
        
        return SubstitutionScore(
            score=score,
            weight=self._config.weights.substitution,
            weighted_score=Decimal(score) * self._config.weights.substitution,
            sample_count=len(subs),
            total_orders=total_orders,
            orders_with_subs=orders_with_subs,
            total_substitutions=len(subs),
            acceptable_substitutions=acceptable,
            substitution_rate_pct=sub_rate.quantize(Decimal("0.1")),
        )
    
    def _calculate_price_volatility_score(
        self,
        vendor_id: uuid.UUID,
        period_start: datetime,
        period_end: datetime,
    ) -> Optional[PriceVolatilityScore]:
        """Calculate price volatility score."""
        prices = [
            p for p in self._prices.get(vendor_id, [])
            if period_start <= p.recorded_at <= period_end
        ]
        
        if not prices:
            # No price changes = stable = good
            return PriceVolatilityScore(
                score=95,
                weight=self._config.weights.price_volatility,
                weighted_score=Decimal("95") * self._config.weights.price_volatility,
                sample_count=0,
                products_tracked=0,
                price_changes=0,
                avg_change_pct=Decimal("0"),
                max_change_pct=Decimal("0"),
            )
        
        products = len(set(p.product_id for p in prices))
        increases = len([p for p in prices if p.change_pct > 0])
        decreases = len([p for p in prices if p.change_pct < 0])
        
        avg_change = sum(abs(p.change_pct) for p in prices) / len(prices)
        max_change = max(abs(p.change_pct) for p in prices)
        
        # Lower volatility = better score
        # 0% avg change = 100, 10% avg change = 50, 20%+ = 0
        score = max(0, 100 - int(avg_change * 5))
        
        # Penalize for many increases
        if increases > decreases * 2:
            score = max(0, score - 10)
        
        return PriceVolatilityScore(
            score=score,
            weight=self._config.weights.price_volatility,
            weighted_score=Decimal(score) * self._config.weights.price_volatility,
            sample_count=len(prices),
            products_tracked=products,
            price_changes=len(prices),
            avg_change_pct=Decimal(str(avg_change)).quantize(Decimal("0.01")),
            max_change_pct=max_change,
            increases=increases,
            decreases=decreases,
        )
    
    def _determine_tier(self, score: int) -> ReliabilityTier:
        """Determine reliability tier from score."""
        if score >= self._config.platinum_threshold:
            return ReliabilityTier.PLATINUM
        elif score >= self._config.gold_threshold:
            return ReliabilityTier.GOLD
        elif score >= self._config.silver_threshold:
            return ReliabilityTier.SILVER
        elif score >= self._config.bronze_threshold:
            return ReliabilityTier.BRONZE
        elif score >= self._config.watch_threshold:
            return ReliabilityTier.WATCH
        else:
            return ReliabilityTier.PROBATION
    
    def _determine_trend(
        self,
        current_score: int,
        previous_score: Optional[int],
    ) -> ScoreTrend:
        """Determine score trend."""
        if previous_score is None:
            return ScoreTrend.FLAT
        
        change_pct = abs(current_score - previous_score) / max(1, previous_score) * 100
        
        if change_pct < float(self._config.trend_threshold_pct):
            return ScoreTrend.FLAT
        elif current_score > previous_score:
            return ScoreTrend.UP
        else:
            return ScoreTrend.DOWN
    
    # =========================================================================
    # MAIN SCORING
    # =========================================================================
    
    def score_vendor(
        self,
        vendor_id: uuid.UUID,
        period_days: Optional[int] = None,
    ) -> Optional[VendorReliabilityScore]:
        """
        Calculate reliability score for a vendor.
        
        Returns score based on weighted metrics.
        """
        if vendor_id not in self._vendors:
            return None
        
        period_days = period_days or self._config.default_period_days
        period_end = datetime.utcnow()
        period_start = period_end - timedelta(days=period_days)
        
        # Calculate component scores
        timeliness = self._calculate_timeliness_score(vendor_id, period_start, period_end)
        fill = self._calculate_fill_score(vendor_id, period_start, period_end)
        substitution = self._calculate_substitution_score(vendor_id, period_start, period_end)
        price_vol = self._calculate_price_volatility_score(vendor_id, period_start, period_end)
        
        # Calculate weighted overall score
        components = [timeliness, fill, substitution, price_vol]
        valid_components = [c for c in components if c is not None]
        
        if not valid_components:
            return None
        
        # Adjust weights for missing components
        total_weight = sum(c.weight for c in valid_components)
        overall_score = sum(c.score * c.weight for c in valid_components) / total_weight
        overall_score = int(overall_score)
        
        # Get previous score for trend
        history = self._score_history.get(vendor_id, [])
        previous_score = history[-1].reliability_score if history else None
        
        trend = self._determine_trend(overall_score, previous_score)
        tier = self._determine_tier(overall_score)
        
        # Generate warnings
        warnings = []
        if timeliness and timeliness.late_deliveries > timeliness.on_time_deliveries:
            warnings.append("More late deliveries than on-time")
        if fill and fill.avg_fill_rate_pct < 90:
            warnings.append(f"Fill rate below 90% ({fill.avg_fill_rate_pct}%)")
        if substitution and substitution.substitution_rate_pct > 20:
            warnings.append(f"High substitution rate ({substitution.substitution_rate_pct}%)")
        if price_vol and price_vol.avg_change_pct > 5:
            warnings.append(f"Price volatility elevated ({price_vol.avg_change_pct}%)")
        if tier == ReliabilityTier.PROBATION:
            warnings.append("Vendor on probation - consider alternatives")
        
        # Recommendation
        recommendation = None
        if tier in (ReliabilityTier.PLATINUM, ReliabilityTier.GOLD):
            recommendation = "Preferred vendor - prioritize for orders"
        elif tier == ReliabilityTier.PROBATION:
            recommendation = "Review vendor relationship - significant issues detected"
        elif trend == ScoreTrend.DOWN:
            recommendation = "Monitor closely - score declining"
        
        result = VendorReliabilityScore(
            vendor_id=vendor_id,
            vendor_name=self._vendors[vendor_id],
            reliability_score=overall_score,
            trend=trend,
            previous_score=previous_score,
            score_change=overall_score - previous_score if previous_score else 0,
            tier=tier,
            timeliness=timeliness,
            fill_accuracy=fill,
            substitution=substitution,
            price_volatility=price_vol,
            period_days=period_days,
            period_start=period_start.date(),
            period_end=period_end.date(),
            warnings=warnings,
            recommendation=recommendation,
        )
        
        # Store in history
        self._score_history[vendor_id].append(result)
        
        return result
    
    def score_all_vendors(
        self,
        period_days: Optional[int] = None,
    ) -> list[VendorReliabilityScore]:
        """Score all registered vendors."""
        scores = []
        for vendor_id in self._vendors:
            score = self.score_vendor(vendor_id, period_days)
            if score:
                scores.append(score)
        
        return sorted(scores, key=lambda s: s.reliability_score, reverse=True)
    
    def compare_vendors(
        self,
        vendor_ids: Optional[list[uuid.UUID]] = None,
        period_days: Optional[int] = None,
    ) -> VendorComparison:
        """Compare multiple vendors."""
        if vendor_ids:
            scores = [self.score_vendor(v, period_days) for v in vendor_ids]
            scores = [s for s in scores if s]
        else:
            scores = self.score_all_vendors(period_days)
        
        # Rankings
        by_score = sorted(scores, key=lambda s: s.reliability_score, reverse=True)
        by_timeliness = sorted(
            [s for s in scores if s.timeliness],
            key=lambda s: s.timeliness.score,
            reverse=True
        )
        by_fill = sorted(
            [s for s in scores if s.fill_accuracy],
            key=lambda s: s.fill_accuracy.score,
            reverse=True
        )
        by_price = sorted(
            [s for s in scores if s.price_volatility],
            key=lambda s: s.price_volatility.score,
            reverse=True
        )
        
        return VendorComparison(
            vendors=scores,
            ranked_by_score=[s.vendor_id for s in by_score],
            ranked_by_timeliness=[s.vendor_id for s in by_timeliness],
            ranked_by_fill=[s.vendor_id for s in by_fill],
            ranked_by_price_stability=[s.vendor_id for s in by_price],
            best_overall=by_score[0].vendor_id if by_score else None,
            best_timeliness=by_timeliness[0].vendor_id if by_timeliness else None,
            best_fill_rate=by_fill[0].vendor_id if by_fill else None,
            most_stable_pricing=by_price[0].vendor_id if by_price else None,
        )
    
    def get_vendor_history(
        self,
        vendor_id: uuid.UUID,
    ) -> Optional[VendorScoreHistory]:
        """Get historical scores for a vendor."""
        if vendor_id not in self._vendors:
            return None
        
        history = self._score_history.get(vendor_id, [])
        
        if not history:
            return VendorScoreHistory(
                vendor_id=vendor_id,
                vendor_name=self._vendors[vendor_id],
            )
        
        # Calculate trends
        scores_30d = [s for s in history if (datetime.utcnow() - s.scored_at).days <= 30]
        scores_90d = [s for s in history if (datetime.utcnow() - s.scored_at).days <= 90]
        
        avg_30d = sum(s.reliability_score for s in scores_30d) // len(scores_30d) if scores_30d else None
        avg_90d = sum(s.reliability_score for s in scores_90d) // len(scores_90d) if scores_90d else None
        
        trend_30d = ScoreTrend.FLAT
        if len(scores_30d) >= 2:
            recent = scores_30d[-1].reliability_score
            older = scores_30d[0].reliability_score
            if recent > older + 5:
                trend_30d = ScoreTrend.UP
            elif recent < older - 5:
                trend_30d = ScoreTrend.DOWN
        
        return VendorScoreHistory(
            vendor_id=vendor_id,
            vendor_name=self._vendors[vendor_id],
            scores=history,
            avg_score_30d=avg_30d,
            avg_score_90d=avg_90d,
            trend_30d=trend_30d,
            highest_score=max(s.reliability_score for s in history),
            lowest_score=min(s.reliability_score for s in history),
        )
    
    def clear_data(self) -> None:
        """Clear all data (for testing)."""
        self._vendors.clear()
        self._deliveries.clear()
        self._fills.clear()
        self._substitutions.clear()
        self._prices.clear()
        self._quality.clear()
        self._score_history.clear()


# Singleton instance
vendor_scorer = VendorReliabilityScorer()

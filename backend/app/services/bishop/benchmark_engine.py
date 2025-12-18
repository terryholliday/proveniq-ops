"""
PROVENIQ Ops - Bishop Peer Benchmark Engine
Provide anonymous, opt-in performance context.

GUARDRAILS:
- No peer identities exposed
- Opt-in only
- Minimum pool size required

LOGIC:
1. Normalize by size/category
2. Compare quartiles
"""

import uuid
from collections import defaultdict
from datetime import datetime, date
from decimal import Decimal
from typing import Optional
import statistics

from app.models.benchmark import (
    AnonymizedPeerMetric,
    BenchmarkConfig,
    BenchmarkMetric,
    BenchmarkReport,
    MetricBenchmark,
    MetricComparison,
    OptInStatus,
    OrgCategory,
    OrgMetrics,
    OrgSize,
    PeerPool,
    Quartile,
    TrendDirection,
)


class PeerBenchmarkEngine:
    """
    Bishop Peer Benchmark Engine
    
    Provides anonymous, opt-in performance context.
    
    GUARDRAIL: No peer identities are EVER exposed.
    """
    
    def __init__(self) -> None:
        self._config = BenchmarkConfig()
        
        # Org data (opted-in only)
        self._org_metrics: dict[uuid.UUID, list[OrgMetrics]] = defaultdict(list)
        self._opt_in_status: dict[uuid.UUID, OptInStatus] = {}
        
        # Anonymized peer pools (aggregated, no individual data)
        self._peer_pools: dict[str, PeerPool] = {}  # key: category_size_metric_month_year
        
        # Benchmark history
        self._benchmark_history: dict[uuid.UUID, list[BenchmarkReport]] = defaultdict(list)
    
    # =========================================================================
    # CONFIGURATION
    # =========================================================================
    
    def configure(self, config: BenchmarkConfig) -> None:
        """Update configuration."""
        self._config = config
    
    def get_config(self) -> BenchmarkConfig:
        """Get current configuration."""
        return self._config
    
    # =========================================================================
    # OPT-IN MANAGEMENT
    # =========================================================================
    
    def opt_in(
        self,
        org_id: uuid.UUID,
        shares_waste: bool = True,
        shares_accuracy: bool = True,
        shares_turnover: bool = True,
        shares_financials: bool = False,
    ) -> OptInStatus:
        """
        Opt an organization into benchmarking.
        
        GUARDRAIL: Explicit consent required.
        """
        status = OptInStatus(
            org_id=org_id,
            opted_in=True,
            consent_timestamp=datetime.utcnow(),
            shares_waste=shares_waste,
            shares_accuracy=shares_accuracy,
            shares_turnover=shares_turnover,
            shares_financials=shares_financials,
            receives_benchmarks=True,
        )
        
        self._opt_in_status[org_id] = status
        return status
    
    def opt_out(self, org_id: uuid.UUID) -> OptInStatus:
        """Opt out of benchmarking."""
        status = self._opt_in_status.get(org_id, OptInStatus(org_id=org_id))
        status.opted_in = False
        self._opt_in_status[org_id] = status
        
        # Remove their data from pools
        if org_id in self._org_metrics:
            del self._org_metrics[org_id]
        
        return status
    
    def get_opt_in_status(self, org_id: uuid.UUID) -> OptInStatus:
        """Get opt-in status for an org."""
        return self._opt_in_status.get(org_id, OptInStatus(org_id=org_id))
    
    # =========================================================================
    # METRICS SUBMISSION
    # =========================================================================
    
    def submit_metrics(self, metrics: OrgMetrics) -> bool:
        """
        Submit organization metrics for benchmarking.
        
        GUARDRAIL: Only stores if opted in.
        """
        status = self._opt_in_status.get(metrics.org_id)
        
        if not status or not status.opted_in:
            return False
        
        # Store metrics
        metrics.opted_in = True
        metrics.consent_timestamp = status.consent_timestamp
        self._org_metrics[metrics.org_id].append(metrics)
        
        # Update peer pools (anonymized)
        self._update_peer_pools(metrics, status)
        
        return True
    
    def _update_peer_pools(self, metrics: OrgMetrics, status: OptInStatus) -> None:
        """Update anonymized peer pools with new metrics."""
        month = metrics.period_end.month
        year = metrics.period_end.year
        
        metric_mapping = {
            BenchmarkMetric.WASTE: (metrics.waste_pct, status.shares_waste),
            BenchmarkMetric.INVENTORY_ACCURACY: (metrics.inventory_accuracy_pct, status.shares_accuracy),
            BenchmarkMetric.INVENTORY_TURNOVER: (metrics.inventory_turnover, status.shares_turnover),
            BenchmarkMetric.STOCKOUT_RATE: (metrics.stockout_rate_pct, status.shares_accuracy),
            BenchmarkMetric.ORDER_ACCURACY: (metrics.order_accuracy_pct, status.shares_accuracy),
            BenchmarkMetric.RECEIVING_ACCURACY: (metrics.receiving_accuracy_pct, status.shares_accuracy),
            BenchmarkMetric.FOOD_COST_PCT: (metrics.food_cost_pct, status.shares_financials),
            BenchmarkMetric.MARGIN: (metrics.margin_pct, status.shares_financials),
            BenchmarkMetric.VENDOR_FILL_RATE: (metrics.vendor_fill_rate_pct, status.shares_accuracy),
        }
        
        for metric_type, (value, allowed) in metric_mapping.items():
            if value is not None and allowed:
                # Add to anonymized pool
                self._add_to_pool(
                    category=metrics.category,
                    size=metrics.size,
                    metric_type=metric_type,
                    value=value,
                    month=month,
                    year=year,
                )
    
    def _add_to_pool(
        self,
        category: OrgCategory,
        size: OrgSize,
        metric_type: BenchmarkMetric,
        value: Decimal,
        month: int,
        year: int,
    ) -> None:
        """Add a value to an anonymized peer pool."""
        key = f"{category.value}_{size.value}_{metric_type.value}_{month}_{year}"
        
        # We track aggregates, not individual values
        # For simplicity in this implementation, we'll rebuild the pool
        # In production, this would use incremental statistics
        
        if key not in self._peer_pools:
            self._peer_pools[key] = PeerPool(
                category=category,
                size=size,
                metric_type=metric_type,
                peer_count=0,
                min_value=value,
                max_value=value,
                avg_value=value,
                median_value=value,
                p25=value,
                p50=value,
                p75=value,
                period_month=month,
                period_year=year,
            )
        
        # Recalculate pool stats
        self._recalculate_pool(key)
    
    def _recalculate_pool(self, key: str) -> None:
        """Recalculate pool statistics from all opted-in orgs."""
        pool = self._peer_pools.get(key)
        if not pool:
            return
        
        # Collect all values for this pool
        values = []
        for org_id, metrics_list in self._org_metrics.items():
            status = self._opt_in_status.get(org_id)
            if not status or not status.opted_in:
                continue
            
            for metrics in metrics_list:
                if metrics.category != pool.category or metrics.size != pool.size:
                    continue
                
                month = metrics.period_end.month
                year = metrics.period_end.year
                if month != pool.period_month or year != pool.period_year:
                    continue
                
                value = self._get_metric_value(metrics, pool.metric_type)
                if value is not None:
                    values.append(float(value))
        
        if not values:
            return
        
        values.sort()
        n = len(values)
        
        pool.peer_count = n
        pool.min_value = Decimal(str(min(values)))
        pool.max_value = Decimal(str(max(values)))
        pool.avg_value = Decimal(str(statistics.mean(values))).quantize(Decimal("0.01"))
        pool.median_value = Decimal(str(statistics.median(values))).quantize(Decimal("0.01"))
        
        # Quartiles
        pool.p25 = Decimal(str(values[int(n * 0.25)] if n > 0 else 0)).quantize(Decimal("0.01"))
        pool.p50 = pool.median_value
        pool.p75 = Decimal(str(values[int(n * 0.75)] if n > 0 else 0)).quantize(Decimal("0.01"))
        
        pool.minimum_peers_met = n >= self._config.minimum_peer_pool_size
    
    def _get_metric_value(self, metrics: OrgMetrics, metric_type: BenchmarkMetric) -> Optional[Decimal]:
        """Get a specific metric value from org metrics."""
        mapping = {
            BenchmarkMetric.WASTE: metrics.waste_pct,
            BenchmarkMetric.INVENTORY_ACCURACY: metrics.inventory_accuracy_pct,
            BenchmarkMetric.INVENTORY_TURNOVER: metrics.inventory_turnover,
            BenchmarkMetric.STOCKOUT_RATE: metrics.stockout_rate_pct,
            BenchmarkMetric.ORDER_ACCURACY: metrics.order_accuracy_pct,
            BenchmarkMetric.RECEIVING_ACCURACY: metrics.receiving_accuracy_pct,
            BenchmarkMetric.FOOD_COST_PCT: metrics.food_cost_pct,
            BenchmarkMetric.MARGIN: metrics.margin_pct,
            BenchmarkMetric.VENDOR_FILL_RATE: metrics.vendor_fill_rate_pct,
        }
        return mapping.get(metric_type)
    
    # =========================================================================
    # BENCHMARKING (Step 2: Compare Quartiles)
    # =========================================================================
    
    def benchmark_metric(
        self,
        org_id: uuid.UUID,
        metric_type: BenchmarkMetric,
        month: Optional[int] = None,
        year: Optional[int] = None,
    ) -> Optional[MetricBenchmark]:
        """
        Benchmark a single metric against peers.
        
        GUARDRAIL: Only returns aggregated peer data, no identities.
        """
        # Get org's latest metrics
        org_metrics_list = self._org_metrics.get(org_id, [])
        if not org_metrics_list:
            return None
        
        latest = org_metrics_list[-1]
        your_value = self._get_metric_value(latest, metric_type)
        
        if your_value is None:
            return None
        
        # Get peer pool
        month = month or latest.period_end.month
        year = year or latest.period_end.year
        key = f"{latest.category.value}_{latest.size.value}_{metric_type.value}_{month}_{year}"
        
        pool = self._peer_pools.get(key)
        
        if not pool or not pool.minimum_peers_met:
            return None
        
        # Calculate percentile
        lower_is_better = metric_type in self._config.lower_is_better
        percentile = self._calculate_percentile(your_value, pool, lower_is_better)
        quartile = self._determine_quartile(percentile)
        
        # Gap analysis
        gap_to_top = your_value - pool.p75 if not lower_is_better else pool.p25 - your_value
        gap_to_median = your_value - pool.p50 if not lower_is_better else pool.p50 - your_value
        
        # Interpretation
        interpretation = self._generate_interpretation(
            metric_type, your_value, percentile, quartile, pool, lower_is_better
        )
        
        return MetricBenchmark(
            metric=metric_type,
            your_value=your_value,
            your_percentile=percentile,
            your_quartile=quartile,
            peer_avg=pool.avg_value,
            peer_median=pool.median_value,
            peer_count=pool.peer_count,
            top_quartile_threshold=pool.p75 if not lower_is_better else pool.p25,
            median_threshold=pool.p50,
            bottom_quartile_threshold=pool.p25 if not lower_is_better else pool.p75,
            gap_to_top_quartile=gap_to_top.quantize(Decimal("0.01")),
            gap_to_median=gap_to_median.quantize(Decimal("0.01")),
            interpretation=interpretation,
        )
    
    def _calculate_percentile(
        self,
        value: Decimal,
        pool: PeerPool,
        lower_is_better: bool,
    ) -> int:
        """Calculate percentile position."""
        # Normalize value between min and max
        range_val = float(pool.max_value - pool.min_value)
        if range_val == 0:
            return 50
        
        position = float(value - pool.min_value) / range_val
        
        if lower_is_better:
            # Lower value = higher percentile
            percentile = int((1 - position) * 100)
        else:
            # Higher value = higher percentile
            percentile = int(position * 100)
        
        return max(0, min(100, percentile))
    
    def _determine_quartile(self, percentile: int) -> Quartile:
        """Determine quartile from percentile."""
        if percentile >= 75:
            return Quartile.TOP
        elif percentile >= 50:
            return Quartile.UPPER_MID
        elif percentile >= 25:
            return Quartile.LOWER_MID
        else:
            return Quartile.BOTTOM
    
    def _generate_interpretation(
        self,
        metric_type: BenchmarkMetric,
        value: Decimal,
        percentile: int,
        quartile: Quartile,
        pool: PeerPool,
        lower_is_better: bool,
    ) -> str:
        """Generate human-readable interpretation."""
        metric_name = metric_type.value.replace("_", " ").title()
        
        if quartile == Quartile.TOP:
            return f"Top performer: Your {metric_name} ({value}%) is in the top 25% of peers."
        elif quartile == Quartile.UPPER_MID:
            return f"Above average: Your {metric_name} ({value}%) is above the peer median of {pool.p50}%."
        elif quartile == Quartile.LOWER_MID:
            gap = abs(value - pool.p50)
            return f"Below average: Your {metric_name} ({value}%) is {gap}% from the peer median."
        else:
            gap = abs(value - pool.p25) if lower_is_better else abs(pool.p75 - value)
            return f"Improvement opportunity: Your {metric_name} ({value}%) is in the bottom quartile."
    
    # =========================================================================
    # FULL BENCHMARK REPORT
    # =========================================================================
    
    def generate_report(
        self,
        org_id: uuid.UUID,
        month: Optional[int] = None,
        year: Optional[int] = None,
    ) -> Optional[BenchmarkReport]:
        """
        Generate complete benchmark report.
        
        GUARDRAIL: Only aggregated peer data returned.
        """
        org_metrics_list = self._org_metrics.get(org_id, [])
        if not org_metrics_list:
            return None
        
        latest = org_metrics_list[-1]
        month = month or latest.period_end.month
        year = year or latest.period_end.year
        
        # Benchmark all available metrics
        benchmarks = []
        for metric_type in BenchmarkMetric:
            benchmark = self.benchmark_metric(org_id, metric_type, month, year)
            if benchmark:
                benchmarks.append(benchmark)
        
        if not benchmarks:
            return None
        
        # Summary stats
        top_count = len([b for b in benchmarks if b.your_quartile == Quartile.TOP])
        bottom_count = len([b for b in benchmarks if b.your_quartile == Quartile.BOTTOM])
        avg_percentile = sum(b.your_percentile for b in benchmarks) // len(benchmarks)
        
        # Opportunities and strengths
        opportunities = [
            f"Improve {b.metric.value.replace('_', ' ')}: currently at {b.your_percentile}th percentile"
            for b in benchmarks if b.your_quartile in (Quartile.BOTTOM, Quartile.LOWER_MID)
        ]
        strengths = [
            f"{b.metric.value.replace('_', ' ').title()}: {b.your_percentile}th percentile"
            for b in benchmarks if b.your_quartile == Quartile.TOP
        ]
        
        report = BenchmarkReport(
            org_id=org_id,
            category=latest.category,
            size=latest.size,
            period_month=month,
            period_year=year,
            benchmarks=benchmarks,
            metrics_benchmarked=len(benchmarks),
            top_quartile_count=top_count,
            bottom_quartile_count=bottom_count,
            overall_percentile=avg_percentile,
            overall_quartile=self._determine_quartile(avg_percentile),
            improvement_opportunities=opportunities[:5],
            strengths=strengths[:5],
        )
        
        # Store in history
        self._benchmark_history[org_id].append(report)
        
        return report
    
    def get_peer_pool_stats(
        self,
        category: OrgCategory,
        size: OrgSize,
    ) -> dict:
        """Get anonymized peer pool statistics."""
        pools = {}
        
        for key, pool in self._peer_pools.items():
            if pool.category == category and pool.size == size:
                if pool.minimum_peers_met:
                    pools[pool.metric_type.value] = {
                        "peer_count": pool.peer_count,
                        "avg": str(pool.avg_value),
                        "median": str(pool.median_value),
                        "p25": str(pool.p25),
                        "p75": str(pool.p75),
                    }
        
        return pools
    
    def clear_data(self) -> None:
        """Clear all data (for testing)."""
        self._org_metrics.clear()
        self._opt_in_status.clear()
        self._peer_pools.clear()
        self._benchmark_history.clear()


# Singleton instance
benchmark_engine = PeerBenchmarkEngine()

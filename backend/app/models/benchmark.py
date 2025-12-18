"""
PROVENIQ Ops - Peer Benchmark Engine Schemas
Bishop anonymous performance comparison data contracts

GUARDRAILS:
- No peer identities exposed
- Opt-in only
- All peer data is anonymized
"""

import uuid
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from app.core.types import Rate


class BenchmarkMetric(str, Enum):
    """Metrics available for benchmarking."""
    WASTE = "waste"
    INVENTORY_ACCURACY = "inventory_accuracy"
    INVENTORY_TURNOVER = "inventory_turnover"
    STOCKOUT_RATE = "stockout_rate"
    ORDER_ACCURACY = "order_accuracy"
    RECEIVING_ACCURACY = "receiving_accuracy"
    LABOR_EFFICIENCY = "labor_efficiency"
    FOOD_COST_PCT = "food_cost_pct"
    MARGIN = "margin"
    VENDOR_FILL_RATE = "vendor_fill_rate"


class OrgCategory(str, Enum):
    """Organization categories for peer grouping."""
    FAST_CASUAL = "fast_casual"
    FINE_DINING = "fine_dining"
    QSR = "qsr"  # Quick Service Restaurant
    CASUAL_DINING = "casual_dining"
    CATERING = "catering"
    HOTEL_FB = "hotel_fb"
    HEALTHCARE = "healthcare"
    EDUCATION = "education"
    CORPORATE = "corporate"


class OrgSize(str, Enum):
    """Organization size tiers."""
    SMALL = "small"           # <$500k annual
    MEDIUM = "medium"         # $500k-$2M
    LARGE = "large"           # $2M-$10M
    ENTERPRISE = "enterprise" # >$10M


class Quartile(str, Enum):
    """Performance quartiles."""
    TOP = "top"           # 75-100th percentile
    UPPER_MID = "upper_mid"   # 50-75th percentile
    LOWER_MID = "lower_mid"   # 25-50th percentile
    BOTTOM = "bottom"     # 0-25th percentile


class TrendDirection(str, Enum):
    """Trend direction for benchmarks."""
    IMPROVING = "improving"
    STABLE = "stable"
    DECLINING = "declining"


# =============================================================================
# ORG METRICS (Your Data)
# =============================================================================

class OrgMetrics(BaseModel):
    """Organization's own metrics for benchmarking."""
    org_id: uuid.UUID
    
    # Classification
    category: OrgCategory
    size: OrgSize
    region: Optional[str] = None  # For regional comparison
    
    # Metrics (all as percentages or rates)
    waste_pct: Optional[Rate] = None
    inventory_accuracy_pct: Optional[Rate] = None
    inventory_turnover: Optional[Rate] = None  # Times per month
    stockout_rate_pct: Optional[Rate] = None
    order_accuracy_pct: Optional[Rate] = None
    receiving_accuracy_pct: Optional[Rate] = None
    labor_efficiency_pct: Optional[Rate] = None
    food_cost_pct: Optional[Rate] = None
    margin_pct: Optional[Rate] = None
    vendor_fill_rate_pct: Optional[Rate] = None
    
    # Period
    period_start: date
    period_end: date
    
    # Opt-in consent
    opted_in: bool = False
    consent_timestamp: Optional[datetime] = None


# =============================================================================
# ANONYMIZED PEER DATA
# =============================================================================

class AnonymizedPeerMetric(BaseModel):
    """
    Single anonymized peer metric.
    
    GUARDRAIL: No identifying information.
    """
    # No org_id - completely anonymous
    
    # Only classification (for grouping)
    category: OrgCategory
    size: OrgSize
    
    # Single metric value
    metric_type: BenchmarkMetric
    value: Rate
    
    # Period (month/year only - no specific dates)
    period_month: int
    period_year: int


class PeerPool(BaseModel):
    """
    Anonymized pool of peer metrics.
    
    GUARDRAIL: Minimum pool size to prevent identification.
    """
    pool_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    
    # Grouping
    category: OrgCategory
    size: OrgSize
    
    # Metric
    metric_type: BenchmarkMetric
    
    # Aggregated stats (no individual values exposed)
    peer_count: int
    min_value: Rate
    max_value: Rate
    avg_value: Rate
    median_value: Rate
    
    # Quartile boundaries
    p25: Rate  # 25th percentile
    p50: Rate  # 50th percentile (median)
    p75: Rate  # 75th percentile
    
    # Period
    period_month: int
    period_year: int
    
    # Privacy
    minimum_peers_met: bool = True  # Must have 5+ peers


# =============================================================================
# BENCHMARK RESULT
# =============================================================================

class MetricBenchmark(BaseModel):
    """
    Benchmark result for a single metric.
    The core output.
    """
    metric: BenchmarkMetric
    
    # Your performance
    your_value: Rate
    your_percentile: int  # 0-100
    your_quartile: Quartile
    
    # Peer context (anonymized)
    peer_avg: Rate
    peer_median: Rate
    peer_count: int
    
    # Quartile boundaries
    top_quartile_threshold: Rate  # 75th percentile
    median_threshold: Rate        # 50th percentile
    bottom_quartile_threshold: Rate  # 25th percentile
    
    # Gap analysis
    gap_to_top_quartile: Rate
    gap_to_median: Rate
    
    # Trend
    trend: Optional[TrendDirection] = None
    previous_percentile: Optional[int] = None
    
    # Interpretation
    interpretation: str


class BenchmarkReport(BaseModel):
    """
    Complete benchmark report for an organization.
    """
    report_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Organization context (no identifiable peer data)
    org_id: uuid.UUID
    category: OrgCategory
    size: OrgSize
    
    # Period
    period_month: int
    period_year: int
    
    # Benchmarks
    benchmarks: list[MetricBenchmark] = []
    
    # Summary
    metrics_benchmarked: int = 0
    top_quartile_count: int = 0
    bottom_quartile_count: int = 0
    
    # Overall standing
    overall_percentile: Optional[int] = None
    overall_quartile: Optional[Quartile] = None
    
    # Opportunities
    improvement_opportunities: list[str] = []
    strengths: list[str] = []
    
    # Privacy notice
    privacy_notice: str = "All peer data is anonymized. No organization identities are revealed."


class MetricComparison(BaseModel):
    """Compare a single metric across time."""
    metric: BenchmarkMetric
    
    # Historical percentiles
    percentile_history: list[dict] = []  # [{month, year, percentile}, ...]
    
    # Trend
    trend_3m: Optional[TrendDirection] = None
    trend_6m: Optional[TrendDirection] = None
    
    # Best/worst
    best_percentile: int = 0
    worst_percentile: int = 100
    
    avg_percentile: int = 50


# =============================================================================
# OPT-IN MANAGEMENT
# =============================================================================

class OptInStatus(BaseModel):
    """Organization's opt-in status for benchmarking."""
    org_id: uuid.UUID
    
    # Consent
    opted_in: bool = False
    consent_timestamp: Optional[datetime] = None
    consent_version: str = "1.0"
    
    # What's shared (all anonymized)
    shares_waste: bool = True
    shares_accuracy: bool = True
    shares_turnover: bool = True
    shares_financials: bool = False  # More sensitive
    
    # What's received
    receives_benchmarks: bool = True


# =============================================================================
# CONFIGURATION
# =============================================================================

class BenchmarkConfig(BaseModel):
    """Configuration for peer benchmark engine."""
    # Privacy thresholds
    minimum_peer_pool_size: int = 5  # Need 5+ peers to show benchmark
    
    # Percentile calculation
    use_weighted_percentile: bool = True
    
    # Metric interpretation (lower is better)
    lower_is_better: list[BenchmarkMetric] = Field(default=[
        BenchmarkMetric.WASTE,
        BenchmarkMetric.STOCKOUT_RATE,
        BenchmarkMetric.FOOD_COST_PCT,
    ])
    
    # Trend thresholds
    improving_threshold_pct: Rate = Decimal("5")  # 5+ percentile gain
    declining_threshold_pct: Rate = Decimal("5")  # 5+ percentile drop

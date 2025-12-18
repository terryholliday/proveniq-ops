"""
PROVENIQ Ops - Vendor Reliability Scorer Schemas
Bishop vendor execution scoring data contracts

Score vendors based on execution, not promises.
"""

import uuid
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from app.core.types import Rate


class ScoreTrend(str, Enum):
    """Trend direction for reliability score."""
    UP = "UP"
    FLAT = "FLAT"
    DOWN = "DOWN"


class ReliabilityTier(str, Enum):
    """Reliability tier classification."""
    PLATINUM = "platinum"   # 90-100
    GOLD = "gold"           # 80-89
    SILVER = "silver"       # 70-79
    BRONZE = "bronze"       # 60-69
    WATCH = "watch"         # 50-59
    PROBATION = "probation" # <50


class MetricType(str, Enum):
    """Types of reliability metrics."""
    DELIVERY_TIMELINESS = "delivery_timeliness"
    FILL_ACCURACY = "fill_accuracy"
    SUBSTITUTION_FREQUENCY = "substitution_frequency"
    PRICE_VOLATILITY = "price_volatility"
    QUALITY_ISSUES = "quality_issues"
    COMMUNICATION = "communication"


# =============================================================================
# RAW METRIC EVENTS
# =============================================================================

class DeliveryEvent(BaseModel):
    """A delivery event for timeliness tracking."""
    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    vendor_id: uuid.UUID
    
    # Order reference
    order_id: uuid.UUID
    po_number: Optional[str] = None
    
    # Timing
    promised_date: datetime
    actual_date: datetime
    
    # Calculated
    variance_hours: int = 0  # Negative = early, positive = late
    on_time: bool = True
    
    # Context
    delivery_window_hours: int = 4  # Acceptable variance
    
    recorded_at: datetime = Field(default_factory=datetime.utcnow)


class FillEvent(BaseModel):
    """A fill accuracy event."""
    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    vendor_id: uuid.UUID
    order_id: uuid.UUID
    
    # Fill details
    lines_ordered: int
    lines_filled: int
    lines_shorted: int = 0
    lines_substituted: int = 0
    
    # Calculated
    fill_rate_pct: Rate  # lines_filled / lines_ordered * 100
    
    recorded_at: datetime = Field(default_factory=datetime.utcnow)


class SubstitutionEvent(BaseModel):
    """A substitution event."""
    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    vendor_id: uuid.UUID
    order_id: uuid.UUID
    
    # Original
    original_product_id: uuid.UUID
    original_product_name: str
    original_qty: Decimal
    
    # Substitution
    substitute_product_id: Optional[uuid.UUID] = None
    substitute_product_name: Optional[str] = None
    substitute_qty: Optional[Decimal] = None
    
    # Quality of substitution
    was_acceptable: bool = True
    price_difference_pct: Rate = Decimal("0")
    
    recorded_at: datetime = Field(default_factory=datetime.utcnow)


class PriceEvent(BaseModel):
    """A price change event for volatility tracking."""
    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    vendor_id: uuid.UUID
    
    # Product
    product_id: uuid.UUID
    product_name: str
    
    # Prices
    previous_price_micros: int
    new_price_micros: int
    change_pct: Rate
    
    # Context
    change_reason: Optional[str] = None  # "market", "contract", "spot", etc.
    
    recorded_at: datetime = Field(default_factory=datetime.utcnow)


class QualityEvent(BaseModel):
    """A quality issue event."""
    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    vendor_id: uuid.UUID
    order_id: uuid.UUID
    
    # Issue
    issue_type: str  # "temperature", "packaging", "damage", "freshness", etc.
    severity: str  # "minor", "major", "critical"
    description: str
    
    # Resolution
    resolved: bool = False
    credit_issued: bool = False
    
    recorded_at: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# METRIC SCORES
# =============================================================================

class MetricScore(BaseModel):
    """Score for a single metric."""
    metric_type: MetricType
    
    # Score
    score: int  # 0-100
    weight: Rate  # Weight in overall calculation
    weighted_score: Rate
    
    # Raw data
    sample_count: int = 0
    period_days: int = 30
    
    # Trend
    previous_score: Optional[int] = None
    trend: ScoreTrend = ScoreTrend.FLAT


class TimelinessScore(MetricScore):
    """Delivery timeliness score details."""
    metric_type: MetricType = MetricType.DELIVERY_TIMELINESS
    
    # Details
    total_deliveries: int = 0
    on_time_deliveries: int = 0
    late_deliveries: int = 0
    early_deliveries: int = 0
    
    avg_variance_hours: Decimal = Decimal("0")
    on_time_pct: Rate = Decimal("0")


class FillScore(MetricScore):
    """Fill accuracy score details."""
    metric_type: MetricType = MetricType.FILL_ACCURACY
    
    # Details
    total_orders: int = 0
    total_lines: int = 0
    filled_lines: int = 0
    shorted_lines: int = 0
    
    avg_fill_rate_pct: Rate = Decimal("0")


class SubstitutionScore(MetricScore):
    """Substitution frequency score details."""
    metric_type: MetricType = MetricType.SUBSTITUTION_FREQUENCY
    
    # Details
    total_orders: int = 0
    orders_with_subs: int = 0
    total_substitutions: int = 0
    acceptable_substitutions: int = 0
    
    substitution_rate_pct: Rate = Decimal("0")


class PriceVolatilityScore(MetricScore):
    """Price volatility score details."""
    metric_type: MetricType = MetricType.PRICE_VOLATILITY
    
    # Details
    products_tracked: int = 0
    price_changes: int = 0
    avg_change_pct: Rate = Decimal("0")
    max_change_pct: Rate = Decimal("0")
    
    # Direction
    increases: int = 0
    decreases: int = 0


# =============================================================================
# VENDOR RELIABILITY SCORE
# =============================================================================

class VendorReliabilityScore(BaseModel):
    """
    Complete vendor reliability score.
    The main output of the scorer.
    """
    score_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    scored_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Vendor
    vendor_id: uuid.UUID
    vendor_name: str
    
    # Overall score (0-100)
    reliability_score: int
    
    # Trend
    trend: ScoreTrend
    previous_score: Optional[int] = None
    score_change: int = 0
    
    # Tier
    tier: ReliabilityTier
    
    # Component scores
    timeliness: Optional[TimelinessScore] = None
    fill_accuracy: Optional[FillScore] = None
    substitution: Optional[SubstitutionScore] = None
    price_volatility: Optional[PriceVolatilityScore] = None
    
    # Period
    period_days: int = 30
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    
    # Warnings
    warnings: list[str] = Field(default_factory=list)
    
    # Recommendation
    recommendation: Optional[str] = None


class VendorComparison(BaseModel):
    """Compare multiple vendors."""
    comparison_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    compared_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Vendors
    vendors: list[VendorReliabilityScore] = []
    
    # Rankings
    ranked_by_score: list[uuid.UUID] = []
    ranked_by_timeliness: list[uuid.UUID] = []
    ranked_by_fill: list[uuid.UUID] = []
    ranked_by_price_stability: list[uuid.UUID] = []
    
    # Best for...
    best_overall: Optional[uuid.UUID] = None
    best_timeliness: Optional[uuid.UUID] = None
    best_fill_rate: Optional[uuid.UUID] = None
    most_stable_pricing: Optional[uuid.UUID] = None


class VendorScoreHistory(BaseModel):
    """Historical scores for a vendor."""
    vendor_id: uuid.UUID
    vendor_name: str
    
    # History
    scores: list[VendorReliabilityScore] = []
    
    # Trend analysis
    avg_score_30d: Optional[int] = None
    avg_score_90d: Optional[int] = None
    trend_30d: ScoreTrend = ScoreTrend.FLAT
    
    # Best/worst
    highest_score: Optional[int] = None
    lowest_score: Optional[int] = None


# =============================================================================
# CONFIGURATION
# =============================================================================

class ScoringWeights(BaseModel):
    """Weights for each metric in overall score."""
    timeliness: Rate = Decimal("0.30")
    fill_accuracy: Rate = Decimal("0.35")
    substitution: Rate = Decimal("0.20")
    price_volatility: Rate = Decimal("0.15")
    
    def validate_sum(self) -> bool:
        """Ensure weights sum to 1.0."""
        total = self.timeliness + self.fill_accuracy + self.substitution + self.price_volatility
        return abs(total - Decimal("1.0")) < Decimal("0.01")


class VendorScorerConfig(BaseModel):
    """Configuration for vendor reliability scorer."""
    # Scoring weights
    weights: ScoringWeights = Field(default_factory=ScoringWeights)
    
    # Rolling period
    default_period_days: int = 30
    
    # Timeliness thresholds
    on_time_window_hours: int = 4  # ±4 hours = on time
    
    # Tier thresholds
    platinum_threshold: int = 90
    gold_threshold: int = 80
    silver_threshold: int = 70
    bronze_threshold: int = 60
    watch_threshold: int = 50
    
    # Trend calculation
    trend_threshold_pct: Rate = Decimal("5")  # ±5% = flat
    
    # Minimum samples
    min_deliveries_for_score: int = 3
    min_orders_for_score: int = 3

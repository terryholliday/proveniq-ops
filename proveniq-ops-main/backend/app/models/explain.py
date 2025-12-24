"""
PROVENIQ Ops - Explain Engine Schemas
Bishop decision explanation data contracts

Explain any Bishop recommendation in plain language.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, Any

from pydantic import BaseModel, Field

from app.core.types import Rate


class DecisionType(str, Enum):
    """Types of Bishop decisions."""
    ORDER_RECOMMENDATION = "order_recommendation"
    STOCKOUT_ALERT = "stockout_alert"
    VENDOR_SELECTION = "vendor_selection"
    DELAY_RECOMMENDATION = "delay_recommendation"
    SALVAGE_RECOMMENDATION = "salvage_recommendation"
    REBALANCE_RECOMMENDATION = "rebalance_recommendation"
    WASTE_ALERT = "waste_alert"
    PRICE_ALERT = "price_alert"
    AUDIT_ALERT = "audit_alert"
    BENCHMARK_INSIGHT = "benchmark_insight"


class ConfidenceLevel(str, Enum):
    """Confidence level categories."""
    VERY_HIGH = "very_high"   # 90-100%
    HIGH = "high"             # 75-89%
    MEDIUM = "medium"         # 50-74%
    LOW = "low"               # 25-49%
    VERY_LOW = "very_low"     # 0-24%


class AlternativeStatus(str, Enum):
    """Why an alternative was rejected."""
    LOWER_SCORE = "lower_score"
    POLICY_VIOLATION = "policy_violation"
    INSUFFICIENT_DATA = "insufficient_data"
    RISK_TOO_HIGH = "risk_too_high"
    COST_TOO_HIGH = "cost_too_high"
    NOT_FEASIBLE = "not_feasible"
    TIMING_ISSUE = "timing_issue"


# =============================================================================
# DECISION TRACE
# =============================================================================

class InputUsed(BaseModel):
    """An input that was used in the decision."""
    input_name: str
    input_type: str  # "inventory", "forecast", "policy", "price", etc.
    value: str
    source: str  # Where it came from
    weight: Optional[Rate] = None  # How much it influenced decision


class PolicyApplied(BaseModel):
    """A policy that was applied in the decision."""
    policy_name: str
    policy_type: str  # "hard_rule", "soft_preference", "threshold"
    description: str
    was_satisfied: bool
    impact: str  # "allowed", "blocked", "modified"


class AlternativeConsidered(BaseModel):
    """An alternative that was considered but rejected."""
    alternative_name: str
    description: str
    
    # Why rejected
    rejection_reason: AlternativeStatus
    rejection_detail: str
    
    # Comparison
    score: Optional[Rate] = None
    score_gap: Optional[Rate] = None  # How much worse than chosen


class DecisionTrace(BaseModel):
    """
    Complete trace of a Bishop decision.
    Used as input for explanation.
    """
    trace_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    
    # Decision metadata
    decision_type: DecisionType
    decision_timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # What was decided
    recommendation: str
    recommendation_value: Optional[Any] = None
    
    # Inputs
    inputs_used: list[InputUsed] = []
    
    # Policies
    policies_applied: list[PolicyApplied] = []
    
    # Scoring
    confidence_score: Rate = Decimal("0.80")
    
    # Alternatives
    alternatives_considered: list[AlternativeConsidered] = []
    
    # Context
    context: dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# EXPLANATION OUTPUT
# =============================================================================

class Explanation(BaseModel):
    """
    Plain language explanation of a Bishop decision.
    The main output of the engine.
    """
    explanation_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    explained_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Reference
    decision_trace_id: uuid.UUID
    decision_type: DecisionType
    
    # Core output
    summary: str
    inputs_used: list[str]
    confidence: Rate
    alternatives_rejected: list[str]
    
    # Confidence breakdown
    confidence_level: ConfidenceLevel
    confidence_factors: list[str] = []
    
    # Detailed explanation
    reasoning_steps: list[str] = []
    
    # Key factors
    primary_factor: Optional[str] = None
    secondary_factors: list[str] = []
    
    # What-if hints
    what_would_change: list[str] = []
    
    # Policy context
    policies_summary: Optional[str] = None


class QuickExplanation(BaseModel):
    """Abbreviated explanation for UI display."""
    decision_trace_id: uuid.UUID
    one_liner: str
    confidence_pct: int
    key_reason: str


class DetailedExplanation(BaseModel):
    """Full detailed explanation with all context."""
    explanation: Explanation
    
    # Full trace
    trace: DecisionTrace
    
    # Additional context
    similar_past_decisions: list[dict] = []
    related_alerts: list[str] = []
    
    # Audit info
    can_be_overridden: bool = True
    override_requires: Optional[str] = None


# =============================================================================
# EXPLANATION TEMPLATES
# =============================================================================

class ExplanationTemplate(BaseModel):
    """Template for generating explanations."""
    template_id: str
    decision_type: DecisionType
    
    # Template parts
    summary_template: str
    reasoning_template: str
    alternative_template: str
    
    # Placeholders
    placeholders: list[str] = []


# =============================================================================
# CONFIGURATION
# =============================================================================

class ExplainConfig(BaseModel):
    """Configuration for explain engine."""
    # Output settings
    max_inputs_to_show: int = 5
    max_alternatives_to_show: int = 3
    max_reasoning_steps: int = 5
    
    # Confidence thresholds
    very_high_threshold: Rate = Decimal("0.90")
    high_threshold: Rate = Decimal("0.75")
    medium_threshold: Rate = Decimal("0.50")
    low_threshold: Rate = Decimal("0.25")
    
    # Language settings
    use_technical_terms: bool = False
    include_numbers: bool = True

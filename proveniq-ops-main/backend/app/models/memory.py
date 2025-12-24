"""
PROVENIQ Ops - Decision Memory Schemas
Bishop decision recording and outcome tracking data contracts

GUARDRAILS:
- Memory INFORMS recommendations but NEVER overrides policy
- All records are immutable once created
- Outcomes are linked after resolution window
"""

import uuid
import hashlib
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, Any

from pydantic import BaseModel, Field

from app.core.types import MoneyMicros, Quantity, Rate


class DecisionType(str, Enum):
    """Types of decisions Bishop makes."""
    ORDER_PLACEMENT = "order_placement"
    ORDER_DELAY = "order_delay"
    VENDOR_SELECTION = "vendor_selection"
    REORDER_RECOMMENDATION = "reorder_recommendation"
    STOCKOUT_ALERT = "stockout_alert"
    WASTE_DISPOSITION = "waste_disposition"
    PRICE_ARBITRAGE = "price_arbitrage"
    TRANSFER_PROPOSAL = "transfer_proposal"
    MARGIN_ALERT = "margin_alert"
    SCAN_ANOMALY = "scan_anomaly"
    GHOST_INVENTORY = "ghost_inventory"


class OutcomeQuality(str, Enum):
    """Quality classification of decision outcomes."""
    EXCELLENT = "excellent"    # Better than expected
    GOOD = "good"              # Met expectations
    ACCEPTABLE = "acceptable"  # Minor issues
    POOR = "poor"              # Significant issues
    FAILURE = "failure"        # Complete failure


class ResolutionStatus(str, Enum):
    """Resolution status of a decision."""
    PENDING = "pending"        # Awaiting outcome
    RESOLVED = "resolved"      # Outcome recorded
    SUPERSEDED = "superseded"  # Overridden by newer decision
    EXPIRED = "expired"        # Resolution window passed


# =============================================================================
# INPUT SNAPSHOT
# =============================================================================

class InputsSnapshot(BaseModel):
    """
    Snapshot of inputs at decision time.
    Used for similarity matching.
    """
    snapshot_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    
    # Context at decision time
    inventory_levels: dict[str, Quantity] = Field(default_factory=dict)
    demand_forecast: dict[str, Quantity] = Field(default_factory=dict)
    liquidity_available_micros: Optional[MoneyMicros] = None
    
    # Key metrics
    stockout_risk_items: int = 0
    waste_risk_items: int = 0
    avg_margin_pct: Optional[Rate] = None
    
    # Policy state
    policy_tokens: dict[str, Any] = Field(default_factory=dict)
    
    # Timing
    day_of_week: int = 0  # 0=Monday
    hour_of_day: int = 0
    
    # Hash for quick comparison
    snapshot_hash: Optional[str] = None
    
    def compute_hash(self) -> str:
        """Compute deterministic hash of inputs."""
        # Create a string representation of key inputs
        key_data = f"{sorted(self.inventory_levels.items())}"
        key_data += f"{sorted(self.demand_forecast.items())}"
        key_data += f"{self.stockout_risk_items}:{self.waste_risk_items}"
        key_data += f"{self.day_of_week}:{self.hour_of_day}"
        
        self.snapshot_hash = hashlib.sha256(key_data.encode()).hexdigest()[:16]
        return self.snapshot_hash


# =============================================================================
# DECISION RECORD
# =============================================================================

class DecisionRecord(BaseModel):
    """
    Immutable record of a decision made by Bishop.
    Core unit of decision memory.
    """
    decision_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    
    # Decision metadata
    decision_type: DecisionType
    decision_description: str
    
    # Trace linkage
    decision_trace_id: uuid.UUID
    dag_node_id: Optional[str] = None
    
    # Input context
    inputs_snapshot: InputsSnapshot
    inputs_hash: str  # For quick similarity lookup
    
    # What was decided
    action_taken: str
    action_parameters: dict[str, Any] = Field(default_factory=dict)
    
    # Confidence at decision time
    confidence: Rate
    
    # Policy reference
    policy_tokens_hash: Optional[str] = None
    
    # Resolution
    resolution_status: ResolutionStatus = ResolutionStatus.PENDING
    resolution_window_hours: int = 72  # Default 3 days
    
    # Timestamps
    decided_at: datetime = Field(default_factory=datetime.utcnow)
    resolution_due_at: Optional[datetime] = None
    
    # Immutability marker
    is_immutable: bool = True


# =============================================================================
# OUTCOME RECORD
# =============================================================================

class OutcomeMetrics(BaseModel):
    """Post-outcome metrics for a decision."""
    # Waste impact
    waste_actual_pct: Optional[Rate] = None
    waste_expected_pct: Optional[Rate] = None
    waste_delta_pct: Optional[Rate] = None
    
    # Margin impact
    margin_actual_pct: Optional[Rate] = None
    margin_expected_pct: Optional[Rate] = None
    margin_delta_pct: Optional[Rate] = None
    
    # Delay/timing
    delivery_delay_hours: Optional[int] = None
    stockout_occurred: bool = False
    stockout_duration_hours: Optional[int] = None
    
    # Financial
    cost_actual_micros: Optional[MoneyMicros] = None
    cost_expected_micros: Optional[MoneyMicros] = None
    cost_delta_micros: Optional[MoneyMicros] = None
    
    # Value captured/lost
    value_captured_micros: Optional[MoneyMicros] = None
    value_lost_micros: Optional[MoneyMicros] = None


class OutcomeRecord(BaseModel):
    """
    Outcome linked to a decision after resolution.
    """
    outcome_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    decision_id: uuid.UUID
    
    # Outcome assessment
    outcome_quality: OutcomeQuality
    outcome_score: Rate  # 0.0-1.0, higher is better
    
    # Metrics
    metrics: OutcomeMetrics
    
    # What happened
    outcome_description: str
    
    # Human feedback (if any)
    human_feedback: Optional[str] = None
    human_override_applied: bool = False
    
    # Timestamps
    resolved_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Learnings
    lessons_learned: list[str] = Field(default_factory=list)


# =============================================================================
# SIMILARITY MATCHING
# =============================================================================

class SimilarDecision(BaseModel):
    """A historical decision similar to current context."""
    decision_id: uuid.UUID
    decision_type: DecisionType
    similarity_score: Rate  # 0.0-1.0
    
    # Outcome (if resolved)
    outcome_score: Optional[Rate] = None
    outcome_quality: Optional[OutcomeQuality] = None
    
    # Context comparison
    context_delta: dict[str, Any] = Field(default_factory=dict)
    
    # When it happened
    decided_at: datetime


class MemoryLookupResult(BaseModel):
    """
    Result of looking up historical analogs.
    The core output of Decision Memory.
    """
    memory_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    lookup_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Current context hash
    current_context_hash: str
    
    # Similar past decisions
    similar_past_decisions: list[SimilarDecision] = []
    
    # Aggregate insights
    total_similar_found: int = 0
    avg_outcome_score: Optional[Rate] = None
    
    # Recommendations (INFORMATIONAL ONLY)
    historical_success_rate: Optional[Rate] = None
    suggested_adjustments: list[str] = Field(default_factory=list)
    
    # GUARDRAIL reminder
    disclaimer: str = "Memory informs recommendations but never overrides policy."


# =============================================================================
# MEMORY STATISTICS
# =============================================================================

class DecisionMemoryStats(BaseModel):
    """Statistics about decision memory."""
    total_decisions: int = 0
    resolved_decisions: int = 0
    pending_decisions: int = 0
    
    # By type
    decisions_by_type: dict[str, int] = Field(default_factory=dict)
    
    # Outcome distribution
    outcomes_excellent: int = 0
    outcomes_good: int = 0
    outcomes_acceptable: int = 0
    outcomes_poor: int = 0
    outcomes_failure: int = 0
    
    # Overall quality
    avg_outcome_score: Optional[Rate] = None
    success_rate: Optional[Rate] = None  # Good or better
    
    # Time coverage
    earliest_decision: Optional[datetime] = None
    latest_decision: Optional[datetime] = None


# =============================================================================
# CONFIGURATION
# =============================================================================

class MemoryConfig(BaseModel):
    """Configuration for decision memory."""
    # Resolution windows by type
    default_resolution_hours: int = 72
    order_resolution_hours: int = 48
    alert_resolution_hours: int = 24
    
    # Similarity thresholds
    similarity_threshold: Rate = Decimal("0.70")  # Min similarity to include
    max_similar_results: int = 10
    
    # Retention
    retention_days: int = 365  # Keep decisions for 1 year
    
    # Scoring weights
    recency_weight: Rate = Decimal("0.3")
    outcome_weight: Rate = Decimal("0.5")
    similarity_weight: Rate = Decimal("0.2")

"""
PROVENIQ Ops - Audit Log Schemas
Immutable audit trail for Bishop decisions and human overrides.

PURPOSE: Training data for future ML models.
- What Bishop proposed
- What humans approved/rejected/modified
- Why (reason codes)
- When
- Outcome

This data is IMMUTABLE. Append-only. Never delete.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.core.types import MoneyMicros, IntQuantity


# =============================================================================
# AUDIT EVENT TYPES
# =============================================================================

class AuditEventType(str, Enum):
    """Classification of audit events."""
    # FSM State Changes
    STATE_TRANSITION = "state_transition"
    
    # Bishop Decisions
    PROPOSAL_GENERATED = "proposal_generated"
    ALERT_GENERATED = "alert_generated"
    RISK_DETECTED = "risk_detected"
    
    # Human Actions
    PROPOSAL_APPROVED = "proposal_approved"
    PROPOSAL_REJECTED = "proposal_rejected"
    PROPOSAL_MODIFIED = "proposal_modified"
    OVERRIDE_APPLIED = "override_applied"
    
    # Execution
    ORDER_SUBMITTED = "order_submitted"
    ORDER_BLOCKED = "order_blocked"
    RECEIVING_CLOSED = "receiving_closed"
    
    # Policy
    POLICY_GATE_PASSED = "policy_gate_passed"
    POLICY_GATE_BLOCKED = "policy_gate_blocked"
    CONFIDENCE_DOWNGRADE = "confidence_downgrade"


class OverrideType(str, Enum):
    """Types of human overrides on Bishop decisions."""
    APPROVE_BELOW_THRESHOLD = "approve_below_threshold"
    REJECT_ABOVE_THRESHOLD = "reject_above_threshold"
    QUANTITY_CHANGED = "quantity_changed"
    VENDOR_CHANGED = "vendor_changed"
    PRICE_OVERRIDE = "price_override"
    SKIP_POLICY_GATE = "skip_policy_gate"
    FORCE_EXECUTE = "force_execute"
    CANCEL_PROPOSAL = "cancel_proposal"
    DEFER_ACTION = "defer_action"


class ReasonCode(str, Enum):
    """Standardized reason codes for blocks/overrides."""
    # Block Reasons
    INSUFFICIENT_FUNDS = "insufficient_funds"
    RISK_TOO_HIGH = "risk_too_high"
    LOW_CONFIDENCE = "low_confidence"
    VENDOR_UNAVAILABLE = "vendor_unavailable"
    POLICY_VIOLATION = "policy_violation"
    APPROVAL_REQUIRED = "approval_required"
    BUDGET_EXCEEDED = "budget_exceeded"
    
    # Override Reasons (Human)
    MANAGER_DISCRETION = "manager_discretion"
    CUSTOMER_PRIORITY = "customer_priority"
    VENDOR_RELATIONSHIP = "vendor_relationship"
    SEASONAL_DEMAND = "seasonal_demand"
    EVENT_PREPARATION = "event_preparation"
    QUALITY_PREFERENCE = "quality_preference"
    COST_NEGOTIATED = "cost_negotiated"
    EMERGENCY_STOCK = "emergency_stock"
    
    # System Reasons
    SYSTEM_ERROR = "system_error"
    DATA_MISSING = "data_missing"
    TIMEOUT = "timeout"


# =============================================================================
# AUDIT LOG ENTRIES
# =============================================================================

class BishopStateLog(BaseModel):
    """
    FSM state transition log.
    Every state change is recorded with context.
    """
    log_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # State transition
    previous_state: Optional[str] = None
    new_state: str
    trigger_event: str
    
    # Context
    user_id: Optional[uuid.UUID] = None
    session_id: Optional[uuid.UUID] = None
    location_id: Optional[uuid.UUID] = None
    
    # Data snapshot at transition
    context_data: dict = Field(default_factory=dict)
    
    # Tracing
    trace_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    
    class Config:
        json_schema_extra = {
            "example": {
                "previous_state": "IDLE",
                "new_state": "SCANNING",
                "trigger_event": "scan_initiated",
                "context_data": {"product_count": 0}
            }
        }


class ProposalAuditLog(BaseModel):
    """
    Audit log for Bishop proposals and human decisions.
    This is the core training data for ML.
    """
    log_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Event classification
    event_type: AuditEventType
    
    # What Bishop proposed
    proposal_id: uuid.UUID
    proposal_type: str  # reorder, receiving_adjustment, vendor_switch, etc.
    dag_node_id: str  # N30, N31, N32, etc.
    
    # Bishop's recommendation
    bishop_recommendation: dict  # Full proposal payload
    bishop_confidence: Decimal = Field(..., ge=0, le=1)
    bishop_reason_codes: list[str] = []
    
    # Human decision (if applicable)
    human_decision: Optional[str] = None  # approved, rejected, modified
    human_user_id: Optional[uuid.UUID] = None
    human_reason_codes: list[str] = []
    human_notes: Optional[str] = None
    
    # What actually happened (for modified proposals)
    final_action: Optional[dict] = None
    
    # Policy context
    policy_tokens: list[uuid.UUID] = []
    gates_passed: list[str] = []
    gates_blocked: list[str] = []
    
    # Tracing
    trace_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    parent_trace_id: Optional[uuid.UUID] = None


class OverrideAuditLog(BaseModel):
    """
    Detailed log when a human overrides Bishop.
    Critical for understanding where Bishop needs improvement.
    """
    log_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Override details
    override_type: OverrideType
    reason_codes: list[ReasonCode]
    
    # What Bishop said
    bishop_proposal_id: uuid.UUID
    bishop_value: Any  # Original value (qty, price, vendor, etc.)
    bishop_confidence: Decimal
    
    # What human chose
    human_value: Any  # Overridden value
    human_user_id: uuid.UUID
    human_role: str
    human_notes: Optional[str] = None
    
    # Context for ML
    context_snapshot: dict = Field(default_factory=dict)  # Inventory, demand, etc.
    
    # Outcome tracking (filled in later)
    outcome_tracked: bool = False
    outcome_was_correct: Optional[bool] = None  # Did human override lead to better result?
    outcome_notes: Optional[str] = None
    
    # Tracing
    trace_id: uuid.UUID = Field(default_factory=uuid.uuid4)


class BlockAuditLog(BaseModel):
    """
    Log when Bishop or a policy gate blocks an action.
    """
    log_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # What was blocked
    blocked_action: str  # order_submission, receiving_close, etc.
    blocked_entity_id: uuid.UUID  # Order ID, PO ID, etc.
    blocked_entity_type: str
    
    # Why
    blocker: str  # bishop, ledger_gate, risk_gate, etc.
    dag_node_id: str  # N20, N21, etc.
    reason_codes: list[ReasonCode]
    reason_details: dict = Field(default_factory=dict)
    
    # Values at block time
    blocked_value_micros: Optional[MoneyMicros] = None
    threshold_value_micros: Optional[MoneyMicros] = None
    confidence_at_block: Optional[Decimal] = None
    
    # Resolution (filled in later)
    resolved: bool = False
    resolution_type: Optional[str] = None  # approved_override, modified, cancelled
    resolved_by: Optional[uuid.UUID] = None
    resolved_at: Optional[datetime] = None
    
    # Tracing
    trace_id: uuid.UUID = Field(default_factory=uuid.uuid4)


class ExecutionAuditLog(BaseModel):
    """
    Log when an action is actually executed.
    Links back to the proposal that authorized it.
    """
    log_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # What was executed
    execution_type: str  # order_submitted, po_closed, transfer_created
    entity_id: uuid.UUID
    entity_type: str
    dag_node_id: str  # N41, N44, etc.
    
    # Authorization chain
    proposal_id: uuid.UUID
    approval_token_id: Optional[uuid.UUID] = None
    policy_tokens: list[uuid.UUID] = []
    
    # Execution details
    executed_by: str  # bishop_auto, human:{user_id}
    execution_method: str  # auto, one_tap, manual_approval
    
    # Values
    executed_value_micros: Optional[MoneyMicros] = None
    executed_quantity: Optional[IntQuantity] = None
    
    # Side effects
    side_effects_declared: list[str] = []
    side_effects_actual: list[str] = []
    
    # Tracing
    trace_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    decision_trace_id: uuid.UUID  # Links to full decision chain


# =============================================================================
# AGGREGATED METRICS (For ML Training)
# =============================================================================

class OverrideMetrics(BaseModel):
    """
    Aggregated metrics for human overrides.
    Used to identify where Bishop needs calibration.
    """
    period_start: datetime
    period_end: datetime
    
    # Counts
    total_proposals: int
    total_approvals: int
    total_rejections: int
    total_modifications: int
    
    # Override breakdown by type
    overrides_by_type: dict[str, int] = Field(default_factory=dict)
    
    # Override breakdown by reason
    overrides_by_reason: dict[str, int] = Field(default_factory=dict)
    
    # Confidence analysis
    avg_confidence_approved: Decimal
    avg_confidence_rejected: Decimal
    avg_confidence_modified: Decimal
    
    # Outcome tracking
    override_success_rate: Optional[Decimal] = None  # When tracked


class TrainingDataExport(BaseModel):
    """
    Export format for ML training data.
    """
    export_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    exported_at: datetime = Field(default_factory=datetime.utcnow)
    
    period_start: datetime
    period_end: datetime
    
    # Counts
    state_transitions: int
    proposals: int
    overrides: int
    blocks: int
    executions: int
    
    # Data URLs (if exported to files)
    state_log_url: Optional[str] = None
    proposal_log_url: Optional[str] = None
    override_log_url: Optional[str] = None
    block_log_url: Optional[str] = None
    execution_log_url: Optional[str] = None

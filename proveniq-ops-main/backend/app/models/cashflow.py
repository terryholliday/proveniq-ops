"""
PROVENIQ Ops - Cash Flow Aware Ordering Schemas
Bishop liquidity-gated ordering data contracts

DAG Node: N20, N40

Gates inventory orders through liquidity reality via the Ledger.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from app.core.types import MoneyMicros, IntQuantity, Quantity, Rate


class OrderAlertType(str, Enum):
    """Order alert classifications."""
    ORDER_DELAYED = "ORDER_DELAYED"
    ORDER_APPROVED = "ORDER_APPROVED"
    ORDER_BLOCKED = "ORDER_BLOCKED"
    LIQUIDITY_WARNING = "LIQUIDITY_WARNING"


class OrderPriority(str, Enum):
    """Order priority classification."""
    CRITICAL = "critical"      # Must order - stockout imminent
    HIGH = "high"              # Important but can wait hours
    NORMAL = "normal"          # Standard reorder
    DEFERRABLE = "deferrable"  # Can wait days
    OPTIONAL = "optional"      # Nice to have


class DelayReason(str, Enum):
    """Reasons for order delay."""
    LIQUIDITY_CONSTRAINT = "LIQUIDITY_CONSTRAINT"
    UPCOMING_OBLIGATIONS = "UPCOMING_OBLIGATIONS"
    CASH_RESERVE_PROTECTION = "CASH_RESERVE_PROTECTION"
    PAYROLL_WINDOW = "PAYROLL_WINDOW"
    VENDOR_PAYMENT_DUE = "VENDOR_PAYMENT_DUE"


class ObligationType(str, Enum):
    """Types of upcoming financial obligations."""
    PAYROLL = "payroll"
    VENDOR_PAYMENT = "vendor_payment"
    RENT = "rent"
    UTILITIES = "utilities"
    LOAN_PAYMENT = "loan_payment"
    TAX_PAYMENT = "tax_payment"
    OTHER = "other"


# =============================================================================
# LEDGER DATA MODELS
# =============================================================================

class LedgerBalance(BaseModel):
    """Current ledger/cash balance."""
    balance_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    
    # Balances
    cash_balance_micros: MoneyMicros
    available_balance_micros: MoneyMicros  # After holds/pending
    
    # Reserves
    minimum_reserve_micros: MoneyMicros = 0
    
    # As of
    as_of: datetime = Field(default_factory=datetime.utcnow)


class UpcomingObligation(BaseModel):
    """Upcoming financial obligation."""
    obligation_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    
    # Details
    obligation_type: ObligationType
    description: str
    amount_micros: MoneyMicros
    
    # Timing
    due_date: datetime
    days_until_due: int
    
    # Priority
    is_mandatory: bool = True
    can_defer: bool = False


class CashFlowForecast(BaseModel):
    """Cash flow forecast for decision making."""
    forecast_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    
    # Current state
    current_balance_micros: MoneyMicros
    
    # Upcoming
    total_obligations_7d_micros: MoneyMicros
    total_obligations_14d_micros: MoneyMicros
    
    # Projected
    projected_balance_7d_micros: MoneyMicros
    projected_balance_14d_micros: MoneyMicros
    
    # Expected inflows (if tracked)
    expected_revenue_7d_micros: Optional[MoneyMicros] = None
    
    # Risk
    liquidity_risk_level: str = "low"  # low, medium, high, critical
    
    as_of: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# ORDER MODELS
# =============================================================================

class PendingOrder(BaseModel):
    """Order pending cash flow approval."""
    order_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    
    # Order details
    vendor_id: uuid.UUID
    vendor_name: str
    
    # Items
    line_items: list[dict] = []  # [{product_id, name, qty, unit_price_micros}]
    total_amount_micros: MoneyMicros
    
    # Priority
    priority: OrderPriority
    priority_reason: Optional[str] = None
    
    # Timing
    created_at: datetime = Field(default_factory=datetime.utcnow)
    needed_by: Optional[datetime] = None
    
    # Status
    status: str = "pending"  # pending, approved, delayed, blocked


class OrderDecision(BaseModel):
    """Bishop's decision on an order."""
    decision_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    order_id: uuid.UUID
    
    # Decision
    approved: bool
    delayed: bool = False
    blocked: bool = False
    
    # If delayed
    delay_hours: Optional[int] = None
    delay_reason: Optional[DelayReason] = None
    review_at: Optional[datetime] = None
    
    # Context
    available_balance_micros: MoneyMicros
    order_amount_micros: MoneyMicros
    remaining_after_micros: Optional[MoneyMicros] = None
    
    # Reasoning
    reason_codes: list[str] = []
    
    decided_at: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# ALERT MODELS
# =============================================================================

class OrderDelayAlert(BaseModel):
    """
    Bishop order delay alert.
    Deterministic output.
    """
    alert_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    alert_type: OrderAlertType = OrderAlertType.ORDER_DELAYED
    
    # Order
    order_id: uuid.UUID
    vendor_name: str
    order_amount_micros: MoneyMicros
    order_priority: OrderPriority
    
    # Delay
    delay_hours: int
    reason: DelayReason
    review_at: datetime
    
    # Context
    current_balance_micros: MoneyMicros
    upcoming_obligations_micros: MoneyMicros
    shortfall_micros: Optional[MoneyMicros] = None
    
    # What triggered the delay
    blocking_obligation: Optional[str] = None
    
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "alert_type": "ORDER_DELAYED",
                "order_id": "uuid",
                "delay_hours": 48,
                "reason": "LIQUIDITY_CONSTRAINT",
                "vendor_name": "Sysco",
                "order_amount_micros": 250000000
            }
        }


class LiquidityWarningAlert(BaseModel):
    """Warning when liquidity is constrained."""
    alert_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    alert_type: OrderAlertType = OrderAlertType.LIQUIDITY_WARNING
    
    # Current state
    current_balance_micros: MoneyMicros
    minimum_reserve_micros: MoneyMicros
    
    # Upcoming
    obligations_next_7d: list[UpcomingObligation] = []
    total_obligations_micros: MoneyMicros
    
    # Impact
    orders_at_risk: int
    orders_value_at_risk_micros: MoneyMicros
    
    # Projected shortfall
    projected_shortfall_micros: Optional[MoneyMicros] = None
    shortfall_date: Optional[datetime] = None
    
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# ANALYSIS MODELS
# =============================================================================

class OrderQueueAnalysis(BaseModel):
    """Analysis of pending order queue."""
    analysis_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Queue summary
    total_pending_orders: int
    total_pending_value_micros: MoneyMicros
    
    # By priority
    critical_orders: int
    critical_value_micros: MoneyMicros
    deferrable_orders: int
    deferrable_value_micros: MoneyMicros
    
    # Liquidity status
    available_balance_micros: MoneyMicros
    can_fund_critical: bool
    can_fund_all: bool
    
    # Decisions
    orders_approved: int
    orders_delayed: int
    orders_blocked: int
    
    # Alerts
    alerts: list[OrderDelayAlert] = []


# =============================================================================
# CONFIGURATION
# =============================================================================

class CashFlowConfig(BaseModel):
    """Configuration for cash flow aware ordering."""
    # Reserve requirements
    minimum_reserve_micros: MoneyMicros = 50_000_000_000  # $50k default
    reserve_days_coverage: int = 3  # Keep 3 days of obligations in reserve
    
    # Delay rules
    default_delay_hours: int = 24
    max_delay_hours: int = 72
    
    # Priority thresholds
    auto_approve_critical: bool = True
    defer_optional_when_tight: bool = True
    
    # Obligation windows
    payroll_protection_days: int = 3  # Protect cash 3 days before payroll
    
    # Thresholds
    tight_liquidity_threshold_pct: Quantity = Field(default=Decimal("20"))  # <20% of obligations

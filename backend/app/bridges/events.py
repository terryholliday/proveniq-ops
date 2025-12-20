"""
PROVENIQ Ops - Cross-System Event Types

Events that flow between Ops and other PROVENIQ systems.
All events are immutable and include trace IDs for audit.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


class EventSource(str, Enum):
    """Origin system for events"""
    OPS = "ops"
    CLAIMSIQ = "claimsiq"
    BIDS = "bids"
    CAPITAL = "capital"


class BaseEvent(BaseModel):
    """Base class for all cross-system events"""
    event_id: UUID = Field(default_factory=uuid4)
    trace_id: UUID = Field(default_factory=uuid4)
    source: EventSource
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    org_id: UUID
    location_id: Optional[UUID] = None
    
    class Config:
        frozen = True  # Immutable


# ============================================
# OPS → CLAIMSIQ Events (Loss → Recovery)
# ============================================

class LossType(str, Enum):
    """Classification of inventory loss"""
    THEFT = "theft"
    SPOILAGE = "spoilage"
    DAMAGE = "damage"
    ADMIN_ERROR = "admin_error"
    VENDOR_ERROR = "vendor_error"
    UNKNOWN = "unknown"


class LossDetectedEvent(BaseEvent):
    """
    Emitted when Ops detects inventory loss.
    ClaimsIQ uses this to check coverage and initiate claim workflow.
    """
    source: EventSource = EventSource.OPS
    
    item_id: UUID
    item_name: str
    quantity_lost: float
    unit: str  # e.g., "lb", "each", "qt"
    loss_type: LossType
    estimated_value_cents: int
    detected_by: UUID  # User who detected
    detection_method: str  # "scan_variance", "manual_count", "expiration"
    
    # Evidence
    photo_urls: List[str] = []
    notes: Optional[str] = None


class EvidenceCapturedEvent(BaseEvent):
    """
    Emitted when evidence is captured for a loss event.
    ClaimsIQ uses this to build claim packets.
    """
    source: EventSource = EventSource.OPS
    
    loss_event_id: UUID
    evidence_type: str  # "photo", "document", "receipt", "scan_log"
    evidence_url: str
    evidence_hash: str  # SHA-256 for immutability
    captured_by: UUID
    metadata: dict = {}


class DisposalPendingEvent(BaseEvent):
    """
    Emitted BEFORE disposal to prompt evidence capture.
    ClaimsIQ responds with coverage info and required evidence.
    """
    source: EventSource = EventSource.OPS
    
    item_id: UUID
    item_name: str
    quantity: float
    unit: str
    disposal_reason: str  # "expiration", "damage", "contamination"
    estimated_value_cents: int
    scheduled_disposal_time: datetime
    
    # ClaimsIQ will respond with required_evidence list


# ============================================
# OPS → BIDS Events (Excess → Liquidity)
# ============================================

class SalvageCondition(str, Enum):
    """Condition grading for salvage items"""
    NEW = "new"
    LIKE_NEW = "like_new"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    SALVAGE_ONLY = "salvage_only"


class ExcessInventoryEvent(BaseEvent):
    """
    Emitted when Ops detects excess inventory that could be liquidated.
    Bids uses this to suggest liquidation paths.
    """
    source: EventSource = EventSource.OPS
    
    item_id: UUID
    item_name: str
    excess_quantity: float
    unit: str
    days_until_expiration: Optional[int] = None
    current_value_cents: int
    reason: str  # "overstock", "slow_moving", "seasonal", "near_expiration"


class SalvageReadyEvent(BaseEvent):
    """
    Emitted when item is ready for salvage/auction.
    Bids uses this to create auction listings.
    """
    source: EventSource = EventSource.OPS
    
    item_id: UUID
    item_name: str
    quantity: float
    unit: str
    condition: SalvageCondition
    original_value_cents: int
    minimum_acceptable_cents: int
    photo_urls: List[str] = []
    description: Optional[str] = None
    
    # Liquidation path preference
    preferred_path: str = "auction"  # "transfer", "discount", "donate", "auction"


class AuctionListedEvent(BaseEvent):
    """
    Emitted when Bids creates an auction listing.
    Ops uses this to track item status.
    """
    source: EventSource = EventSource.BIDS
    
    item_id: UUID
    auction_id: UUID
    listing_url: str
    starting_price_cents: int
    reserve_price_cents: Optional[int] = None
    auction_end_time: datetime


# ============================================
# OPS ⇄ CAPITAL Events (Inventory → Cash)
# ============================================

class LiquiditySnapshotEvent(BaseEvent):
    """
    Received from Capital with current liquidity status.
    Ops uses this to gate ordering decisions.
    """
    source: EventSource = EventSource.CAPITAL
    
    available_cash_cents: int
    committed_orders_cents: int
    pending_receivables_cents: int
    credit_limit_cents: int
    credit_used_cents: int
    
    # Derived
    @property
    def effective_liquidity_cents(self) -> int:
        return (
            self.available_cash_cents 
            + (self.credit_limit_cents - self.credit_used_cents)
            - self.committed_orders_cents
        )


class CreditConstraintEvent(BaseEvent):
    """
    Received from Capital when credit constraints change.
    Ops uses this to adjust ordering behavior.
    """
    source: EventSource = EventSource.CAPITAL
    
    constraint_type: str  # "credit_limit_reduced", "payment_overdue", "credit_hold"
    severity: str  # "warning", "soft_block", "hard_block"
    affected_vendors: List[str] = []
    message: str
    resolution_required: Optional[str] = None


class SettlementCompleteEvent(BaseEvent):
    """
    Received from Capital when a liquidation settles.
    Ops uses this to close out salvage workflows.
    """
    source: EventSource = EventSource.CAPITAL
    
    auction_id: Optional[UUID] = None
    item_id: UUID
    settlement_amount_cents: int
    fees_cents: int
    net_amount_cents: int
    settlement_date: datetime
    ledger_entry_id: UUID


# ============================================
# Coverage Response (ClaimsIQ → Ops)
# ============================================

class CoverageInfo(BaseModel):
    """Coverage information returned by ClaimsIQ"""
    is_covered: bool
    coverage_type: Optional[str] = None  # "spoilage", "theft", "damage"
    coverage_limit_cents: Optional[int] = None
    deductible_cents: Optional[int] = None
    required_evidence: List[str] = []  # ["photo", "receipt", "police_report"]
    claim_deadline_days: Optional[int] = None
    notes: Optional[str] = None

"""
PROVENIQ Ops - Chain of Custody Schemas
Bishop high-risk item tracking data contracts

GUARDRAILS:
- No disciplinary language
- This is TRACEABILITY, not surveillance
- Track movement without assigning blame
"""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, Any

from pydantic import BaseModel, Field

from app.core.types import Quantity


class CustodyAction(str, Enum):
    """Actions that create custody hops."""
    # Receiving
    RECEIVED = "received"
    INSPECTED = "inspected"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    
    # Storage
    STORED = "stored"
    RELOCATED = "relocated"
    
    # Prep
    RETRIEVED = "retrieved"
    PREPPED = "prepped"
    PORTIONED = "portioned"
    
    # Transfer
    TRANSFERRED_OUT = "transferred_out"
    TRANSFERRED_IN = "transferred_in"
    
    # Usage
    USED_IN_RECIPE = "used_in_recipe"
    SERVED = "served"
    
    # Disposal
    DISPOSED = "disposed"
    DONATED = "donated"
    RETURNED_TO_VENDOR = "returned_to_vendor"
    
    # Verification
    COUNTED = "counted"
    VERIFIED = "verified"
    ADJUSTED = "adjusted"


class ActorRole(str, Enum):
    """Roles that can hold custody (not individual names)."""
    RECEIVING_TEAM = "receiving_team"
    STORAGE_TEAM = "storage_team"
    PREP_TEAM = "prep_team"
    LINE_COOK = "line_cook"
    MANAGER = "manager"
    INVENTORY_TEAM = "inventory_team"
    DELIVERY_DRIVER = "delivery_driver"
    VENDOR = "vendor"
    SYSTEM = "system"  # Automated actions


class ChainStatus(str, Enum):
    """Status of a custody chain."""
    COMPLETE = "complete"       # All hops accounted for
    ACTIVE = "active"           # Item still in custody
    GAP_DETECTED = "gap"        # Missing hop(s)
    BREAK_DETECTED = "break"    # Chain broken
    DISPOSED = "disposed"       # Item no longer tracked


class ItemRiskLevel(str, Enum):
    """Risk level for custody tracking."""
    STANDARD = "standard"       # Normal tracking
    ELEVATED = "elevated"       # Extra scrutiny
    HIGH = "high"               # Full chain required
    REGULATED = "regulated"     # Compliance required (alcohol, etc.)


# =============================================================================
# CUSTODY HOP
# =============================================================================

class CustodyHop(BaseModel):
    """
    Single custody event in the chain.
    
    Each hop represents a state change for the item.
    """
    hop_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    
    # Who (role, not individual)
    actor_role: ActorRole
    
    # What
    action: CustodyAction
    
    # When
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Where
    location_id: Optional[uuid.UUID] = None
    location_name: Optional[str] = None
    
    # Quantity at this hop
    quantity: Optional[Quantity] = None
    quantity_unit: Optional[str] = None
    
    # Context (neutral, no blame)
    notes: Optional[str] = None
    
    # Verification
    verified: bool = False
    verification_method: Optional[str] = None  # "scan", "manual", "photo"
    
    # Linkage
    source_event_id: Optional[uuid.UUID] = None  # receiving_event, prep_event, etc.
    source_event_type: Optional[str] = None


# =============================================================================
# CUSTODY CHAIN
# =============================================================================

class CustodyChain(BaseModel):
    """
    Complete chain of custody for an item.
    
    GUARDRAIL: This is traceability, not surveillance.
    """
    chain_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    
    # Item being tracked
    item_id: uuid.UUID
    product_id: Optional[uuid.UUID] = None
    product_name: Optional[str] = None
    
    # Batch/lot tracking
    batch_id: Optional[str] = None
    lot_number: Optional[str] = None
    
    # Risk level
    risk_level: ItemRiskLevel = ItemRiskLevel.STANDARD
    
    # The chain itself
    custody_chain: list[CustodyHop] = Field(default_factory=list)
    
    # Status
    status: ChainStatus = ChainStatus.ACTIVE
    
    # Current holder
    current_actor: Optional[ActorRole] = None
    current_location_id: Optional[uuid.UUID] = None
    
    # Gap/break detection
    gaps_detected: int = 0
    gap_details: list[str] = Field(default_factory=list)
    
    # Timestamps
    chain_started: datetime = Field(default_factory=datetime.utcnow)
    last_hop_at: Optional[datetime] = None
    chain_closed: Optional[datetime] = None
    
    # GUARDRAIL reminder
    disclaimer: str = "Traceability record. Not for disciplinary purposes."


# =============================================================================
# INPUT EVENT MODELS
# =============================================================================

class ReceivingEvent(BaseModel):
    """Receiving dock event."""
    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    item_id: uuid.UUID
    product_id: uuid.UUID
    
    # Receiving details
    vendor_id: uuid.UUID
    vendor_name: str
    po_number: Optional[str] = None
    
    # Quantity
    quantity_received: Quantity
    quantity_unit: str
    
    # Inspection
    inspection_passed: bool = True
    temperature_ok: Optional[bool] = None
    packaging_ok: Optional[bool] = None
    
    # Timing
    received_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Location
    location_id: uuid.UUID
    location_name: str


class PrepEvent(BaseModel):
    """Prep station event."""
    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    item_id: uuid.UUID
    
    # Prep details
    prep_type: str  # "portioning", "cutting", "mixing", etc.
    
    # Input/output
    input_quantity: Quantity
    output_quantity: Optional[Quantity] = None
    quantity_unit: str
    
    # Timing
    prepped_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Location
    location_id: uuid.UUID
    location_name: str


class TransferEvent(BaseModel):
    """Inter-location transfer event."""
    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    item_id: uuid.UUID
    
    # Transfer details
    from_location_id: uuid.UUID
    from_location_name: str
    to_location_id: uuid.UUID
    to_location_name: str
    
    # Quantity
    quantity_transferred: Quantity
    quantity_unit: str
    
    # Timing
    transferred_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Verification
    sent_verified: bool = False
    received_verified: bool = False


class DisposalEvent(BaseModel):
    """Disposal/waste event."""
    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    item_id: uuid.UUID
    
    # Disposal details
    disposal_type: str  # "expired", "spoiled", "damaged", "donated", "returned"
    disposal_reason: str
    
    # Quantity
    quantity_disposed: Quantity
    quantity_unit: str
    
    # Timing
    disposed_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Location
    location_id: uuid.UUID
    location_name: str
    
    # Verification
    verified_by_role: Optional[ActorRole] = None


# =============================================================================
# GAP ANALYSIS
# =============================================================================

class ChainGap(BaseModel):
    """Detected gap in custody chain."""
    gap_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    chain_id: uuid.UUID
    item_id: uuid.UUID
    
    # Gap details
    gap_type: str  # "time_gap", "location_gap", "quantity_gap", "missing_hop"
    gap_description: str
    
    # Between which hops
    before_hop_id: Optional[uuid.UUID] = None
    after_hop_id: Optional[uuid.UUID] = None
    
    # Gap metrics
    time_gap_hours: Optional[Decimal] = None
    quantity_discrepancy: Optional[Quantity] = None
    
    # Detected
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Resolution
    resolved: bool = False
    resolution_notes: Optional[str] = None
    
    # GUARDRAIL: Neutral language
    note: str = "Gap detected for traceability. Not an accusation."


# =============================================================================
# QUERY & REPORT MODELS
# =============================================================================

class CustodyQuery(BaseModel):
    """Query parameters for custody lookup."""
    item_id: Optional[uuid.UUID] = None
    product_id: Optional[uuid.UUID] = None
    batch_id: Optional[str] = None
    location_id: Optional[uuid.UUID] = None
    risk_level: Optional[ItemRiskLevel] = None
    status: Optional[ChainStatus] = None
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    has_gaps: Optional[bool] = None


class CustodyReport(BaseModel):
    """Summary report of custody chains."""
    report_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Counts
    total_chains: int = 0
    active_chains: int = 0
    complete_chains: int = 0
    chains_with_gaps: int = 0
    
    # By risk level
    high_risk_chains: int = 0
    regulated_chains: int = 0
    
    # Gap summary
    total_gaps_detected: int = 0
    unresolved_gaps: int = 0
    
    # Coverage
    items_tracked: int = 0
    locations_covered: int = 0


# =============================================================================
# CONFIGURATION
# =============================================================================

class CustodyConfig(BaseModel):
    """Configuration for custody tracking."""
    # Time thresholds for gap detection
    max_hours_between_hops: int = 24
    receiving_to_storage_max_hours: int = 2
    
    # Auto-escalation
    auto_escalate_gaps: bool = True
    gap_escalation_threshold: int = 2  # Escalate after N gaps
    
    # Risk levels requiring full chain
    require_full_chain_levels: list[ItemRiskLevel] = Field(
        default=[ItemRiskLevel.HIGH, ItemRiskLevel.REGULATED]
    )
    
    # Retention
    chain_retention_days: int = 365

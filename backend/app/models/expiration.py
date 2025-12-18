"""
PROVENIQ Ops - Expiration Cascade Schemas
Bishop waste-to-decision data contracts

DAG Node: N13, N33

GUARDRAILS:
- Donation suggestions must respect compliance rules
"""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from app.core.types import MoneyMicros, IntQuantity, Quantity, Rate


class ExpirationAlertType(str, Enum):
    """Expiration alert classifications."""
    EXPIRATION_CASCADE = "EXPIRATION_CASCADE"
    URGENT_EXPIRATION = "URGENT_EXPIRATION"
    BATCH_EXPIRATION = "BATCH_EXPIRATION"


class ItemCategory(str, Enum):
    """Item category for expiration handling."""
    PERISHABLE = "perishable"
    NON_PERISHABLE = "non_perishable"
    FROZEN = "frozen"
    REFRIGERATED = "refrigerated"
    DRY_GOODS = "dry_goods"
    PRODUCE = "produce"
    DAIRY = "dairy"
    MEAT = "meat"
    SEAFOOD = "seafood"
    BAKERY = "bakery"


class DispositionAction(str, Enum):
    """Recommended disposition actions."""
    DISCOUNT = "discount"
    DONATE = "donate"
    DISPOSE = "dispose"
    TRANSFER = "transfer"
    USE_FIRST = "use_first"  # FIFO priority
    HOLD = "hold"  # Needs review


class DonationEligibility(str, Enum):
    """Donation eligibility status."""
    ELIGIBLE = "eligible"
    NOT_ELIGIBLE = "not_eligible"
    REQUIRES_REVIEW = "requires_review"
    COMPLIANCE_BLOCK = "compliance_block"


# =============================================================================
# LOT TRACKING MODELS
# =============================================================================

class LotRecord(BaseModel):
    """Lot tracking record with expiration."""
    lot_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    product_id: uuid.UUID
    product_name: str
    canonical_sku: str
    
    # Lot details
    lot_number: str
    quantity: IntQuantity
    unit_cost_micros: MoneyMicros
    
    # Dates
    received_date: datetime
    expiration_date: datetime
    
    # Location
    location_id: uuid.UUID
    location_name: str
    
    # Category
    category: ItemCategory
    
    # Compliance
    donation_eligible: bool = True
    donation_restrictions: list[str] = []
    disposal_requirements: list[str] = []


class DonationRule(BaseModel):
    """Donation compliance rule."""
    rule_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    category: ItemCategory
    min_days_before_expiry: int = 1  # Must have at least X days left
    requires_temp_control: bool = False
    requires_packaging_intact: bool = True
    prohibited_items: list[str] = []
    documentation_required: list[str] = []
    partner_restrictions: list[str] = []


# =============================================================================
# EXPIRATION WINDOW MODELS
# =============================================================================

class ExpiringItem(BaseModel):
    """Individual item approaching expiration."""
    lot_id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    canonical_sku: str
    lot_number: str
    
    # Quantity and value
    quantity: IntQuantity
    unit_cost_micros: MoneyMicros
    total_value_micros: MoneyMicros
    
    # Expiration
    expiration_date: datetime
    hours_until_expiry: int
    window_bucket: int  # 24, 48, 72
    
    # Location
    location_id: uuid.UUID
    location_name: str
    
    # Category
    category: ItemCategory
    
    # Recommended action
    recommended_action: DispositionAction
    action_reason: str
    
    # Donation eligibility
    donation_eligibility: DonationEligibility
    donation_notes: Optional[str] = None
    
    # Compliance
    compliance_flags: list[str] = []


class WindowSummary(BaseModel):
    """Summary for a specific time window."""
    window_hours: int
    item_count: int
    total_quantity: int
    total_value_micros: MoneyMicros
    
    # By action
    discount_count: int = 0
    donate_count: int = 0
    dispose_count: int = 0
    transfer_count: int = 0
    
    # Value by action
    discount_value_micros: MoneyMicros = 0
    donate_value_micros: MoneyMicros = 0
    dispose_value_micros: MoneyMicros = 0


class ExpirationCascadeAlert(BaseModel):
    """
    Bishop expiration cascade alert.
    Converts waste into intentional decisions.
    """
    alert_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    alert_type: ExpirationAlertType = ExpirationAlertType.EXPIRATION_CASCADE
    
    # Windows
    window_hours: list[int] = [24, 48, 72]
    
    # Summary by action
    items_by_action: dict[str, int] = Field(default_factory=dict)
    value_by_action: dict[str, int] = Field(default_factory=dict)
    
    # Totals
    total_items: int
    total_quantity: int
    estimated_loss_micros: MoneyMicros
    recoverable_value_micros: MoneyMicros  # Via discount/donate
    
    # Window breakdowns
    window_24h: Optional[WindowSummary] = None
    window_48h: Optional[WindowSummary] = None
    window_72h: Optional[WindowSummary] = None
    
    # All expiring items
    expiring_items: list[ExpiringItem] = []
    
    # Compliance summary
    donation_eligible_count: int = 0
    compliance_blocked_count: int = 0
    
    # Recommendations
    urgent_actions: list[str] = []
    
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "alert_type": "EXPIRATION_CASCADE",
                "window_hours": [24, 48, 72],
                "items_by_action": {
                    "discount": 5,
                    "donate": 3,
                    "dispose": 2
                },
                "estimated_loss_micros": 125000000,
                "recoverable_value_micros": 87500000
            }
        }


# =============================================================================
# ACTION PLAN MODELS
# =============================================================================

class DispositionPlan(BaseModel):
    """Planned disposition for an expiring item."""
    plan_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    lot_id: uuid.UUID
    product_name: str
    
    # Action
    action: DispositionAction
    quantity: IntQuantity
    
    # Value
    original_value_micros: MoneyMicros
    recovery_value_micros: MoneyMicros  # After discount or $0 for dispose
    loss_value_micros: MoneyMicros
    
    # For discount action
    discount_percent: Optional[Quantity] = None
    discount_price_micros: Optional[MoneyMicros] = None
    
    # For donate action
    donation_partner: Optional[str] = None
    donation_documentation: list[str] = []
    
    # Compliance
    compliance_approved: bool = False
    compliance_notes: Optional[str] = None
    
    # Timing
    action_deadline: datetime
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ExpirationActionPlan(BaseModel):
    """Complete action plan for expiration cascade."""
    plan_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    
    # Summary
    total_items: int
    total_original_value_micros: MoneyMicros
    total_recovery_value_micros: MoneyMicros
    total_loss_value_micros: MoneyMicros
    
    # Plans by action
    discount_plans: list[DispositionPlan] = []
    donate_plans: list[DispositionPlan] = []
    dispose_plans: list[DispositionPlan] = []
    
    # Compliance
    requires_approval: bool = True
    approval_notes: list[str] = []
    
    created_at: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# CONFIGURATION
# =============================================================================

class ExpirationConfig(BaseModel):
    """Configuration for expiration cascade planner."""
    # Windows
    window_hours: list[int] = [24, 48, 72]
    
    # Thresholds for actions
    discount_window_hours: int = 72  # Discount if expiring within this
    donate_window_hours: int = 48    # Donate if expiring within this
    dispose_window_hours: int = 24   # Must dispose if within this
    
    # Discount settings
    default_discount_percent: Quantity = Field(default=Decimal("25"))
    max_discount_percent: Quantity = Field(default=Decimal("50"))
    
    # Donation settings
    min_donation_value_micros: MoneyMicros = 5_000_000  # $5 minimum
    donation_lead_time_hours: int = 24
    
    # Compliance
    enforce_donation_rules: bool = True
    require_disposal_documentation: bool = True

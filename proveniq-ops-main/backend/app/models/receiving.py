"""
PROVENIQ Ops - Smart Receiving Schemas
Bishop scan-to-PO reconciliation data contracts

RULE: No floats for money/quantities. Use MoneyMicros/IntQuantity.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from app.core.types import MoneyMicros, IntQuantity, Quantity


class DiscrepancyType(str, Enum):
    """Types of receiving discrepancies."""
    SHORT = "short"
    OVERAGE = "overage"
    SUBSTITUTION = "substitution"
    DAMAGED = "damaged"
    WRONG_ITEM = "wrong_item"
    QUALITY_ISSUE = "quality_issue"


class ReceivingAlertType(str, Enum):
    """Receiving alert classifications."""
    RECEIVING_DISCREPANCY = "RECEIVING_DISCREPANCY"
    RECEIVING_COMPLETE = "RECEIVING_COMPLETE"
    RECEIVING_PARTIAL = "RECEIVING_PARTIAL"
    SUBSTITUTION_DETECTED = "SUBSTITUTION_DETECTED"


class POStatus(str, Enum):
    """Purchase order status."""
    PENDING = "pending"
    PARTIALLY_RECEIVED = "partially_received"
    RECEIVED = "received"
    CLOSED = "closed"
    DISPUTED = "disputed"


class POLineItem(BaseModel):
    """Individual line item on a purchase order."""
    line_id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    vendor_sku: str
    quantity_ordered: IntQuantity = Field(..., gt=0)
    unit_price_micros: MoneyMicros = Field(..., gt=0)
    quantity_received: IntQuantity = Field(0, ge=0)


class PurchaseOrder(BaseModel):
    """Purchase order for receiving reconciliation."""
    po_id: uuid.UUID
    po_number: str
    vendor_id: uuid.UUID
    vendor_name: str
    order_date: datetime
    expected_delivery: datetime
    status: POStatus = POStatus.PENDING
    line_items: list[POLineItem]
    notes: Optional[str] = None


class DockScan(BaseModel):
    """Individual scan at receiving dock."""
    scan_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    barcode: str
    product_id: Optional[uuid.UUID] = None
    product_name: Optional[str] = None
    quantity_scanned: IntQuantity = Field(..., gt=0)
    scanned_at: datetime = Field(default_factory=datetime.utcnow)
    scanned_by: str = "bishop"
    location: str = "dock"
    condition: str = "good"  # good, damaged, expired
    lot_number: Optional[str] = None
    expiry_date: Optional[datetime] = None


class VendorSubstitutionRule(BaseModel):
    """Allowed substitution mapping from vendor."""
    vendor_id: uuid.UUID
    original_product_id: uuid.UUID
    substitute_product_id: uuid.UUID
    substitute_sku: str
    price_adjustment_micros: MoneyMicros = 0  # Can be negative for credit
    requires_approval: bool = True
    valid_until: Optional[datetime] = None


class LineItemDiscrepancy(BaseModel):
    """Discrepancy detected on a single line item."""
    line_id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    discrepancy_type: DiscrepancyType
    expected_qty: IntQuantity
    received_qty: IntQuantity
    variance: int  # positive = overage, negative = short (int OK for delta)
    substitute_product_id: Optional[uuid.UUID] = None
    substitute_name: Optional[str] = None
    damage_notes: Optional[str] = None
    cost_impact_micros: MoneyMicros = 0


class ReceivingReconciliation(BaseModel):
    """
    Bishop receiving reconciliation result.
    Deterministic output - no free-form text.
    """
    alert_type: ReceivingAlertType
    po_id: uuid.UUID
    po_number: str
    vendor_name: str
    total_lines: int
    lines_matched: int
    lines_with_discrepancy: int
    short_items: int
    overages: int
    substitutions: int
    damaged_items: int
    discrepancies: list[LineItemDiscrepancy]
    total_expected_value_micros: MoneyMicros
    total_received_value_micros: MoneyMicros
    variance_value_micros: MoneyMicros  # Can be negative
    requires_confirmation: bool = True
    recommended_action: str
    reconciled_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "alert_type": "RECEIVING_DISCREPANCY",
                "po_id": "550e8400-e29b-41d4-a716-446655440000",
                "po_number": "PO-2024-001234",
                "vendor_name": "Sysco",
                "total_lines": 5,
                "lines_matched": 3,
                "lines_with_discrepancy": 2,
                "short_items": 1,
                "overages": 0,
                "substitutions": 1,
                "damaged_items": 0,
                "total_expected_value": "523.50",
                "total_received_value": "498.75",
                "variance_value": "-24.75",
                "requires_confirmation": True,
                "recommended_action": "Accept with adjustments"
            }
        }


class ReceivingSession(BaseModel):
    """Active receiving session for a PO."""
    session_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    po_id: uuid.UUID
    started_at: datetime = Field(default_factory=datetime.utcnow)
    scans: list[DockScan] = []
    status: str = "in_progress"  # in_progress, pending_review, completed, cancelled


class AcceptReceivingRequest(BaseModel):
    """Request to accept receiving with adjustments."""
    session_id: uuid.UUID
    accept_substitutions: bool = False
    accept_shorts: bool = False
    dispute_items: list[uuid.UUID] = []  # line_ids to dispute
    notes: Optional[str] = None


class ReceivingResponse(BaseModel):
    """Standard receiving operation response."""
    success: bool
    message: str
    po_id: Optional[uuid.UUID] = None
    po_status: Optional[POStatus] = None
    reconciliation: Optional[ReceivingReconciliation] = None

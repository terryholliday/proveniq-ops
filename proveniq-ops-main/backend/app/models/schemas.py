"""
PROVENIQ Ops - Pydantic Schemas
Strict validation for all request/response bodies

RULE: No floats allowed for money or quantities.
      Money uses MoneyMicros (int), Quantity uses Decimal (serialized as string).
"""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.types import MoneyMicros, Quantity, IntQuantity, Rate, Money


# =============================================================================
# BISHOP FSM SCHEMAS
# =============================================================================

class BishopState(str, Enum):
    """Authorized Bishop FSM states."""
    IDLE = "IDLE"
    SCANNING = "SCANNING"
    ANALYZING_RISK = "ANALYZING_RISK"
    CHECKING_FUNDS = "CHECKING_FUNDS"
    ORDER_QUEUED = "ORDER_QUEUED"


class BishopStateTransition(BaseModel):
    """State transition record."""
    model_config = ConfigDict(from_attributes=True)
    
    previous_state: Optional[BishopState] = None
    current_state: BishopState
    trigger_event: str
    context_data: Optional[dict] = None
    output_message: str


class BishopResponse(BaseModel):
    """Standard Bishop output format."""
    state: BishopState
    message: str
    context: Optional[dict] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# VENDOR SCHEMAS
# =============================================================================

class VendorBase(BaseModel):
    """Base vendor attributes."""
    name: str = Field(..., min_length=1, max_length=255)
    api_endpoint: Optional[str] = Field(None, max_length=512)
    priority_level: int = Field(1, ge=1)
    is_active: bool = True


class VendorCreate(VendorBase):
    """Vendor creation payload."""
    pass


class VendorRead(VendorBase):
    """Vendor response model."""
    model_config = ConfigDict(from_attributes=True)
    
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# =============================================================================
# PRODUCT SCHEMAS
# =============================================================================

class RiskCategory(str, Enum):
    """Product risk classification."""
    STANDARD = "standard"
    PERISHABLE = "perishable"
    HAZARDOUS = "hazardous"
    CONTROLLED = "controlled"


class ProductBase(BaseModel):
    """Base product attributes."""
    name: str = Field(..., min_length=1, max_length=255)
    barcode: Optional[str] = Field(None, max_length=100)
    par_level: int = Field(0, ge=0)
    risk_category: RiskCategory = RiskCategory.STANDARD


class ProductCreate(ProductBase):
    """Product creation payload."""
    pass


class ProductRead(ProductBase):
    """Product response model."""
    model_config = ConfigDict(from_attributes=True)
    
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# =============================================================================
# VENDOR PRODUCT SCHEMAS
# =============================================================================

class VendorProductBase(BaseModel):
    """Base vendor-product mapping attributes."""
    vendor_id: uuid.UUID
    product_id: uuid.UUID
    vendor_sku: str = Field(..., min_length=1, max_length=100)
    current_price_micros: MoneyMicros = Field(..., gt=0, description="Price in micros (1 USD = 1,000,000)")
    stock_available: Optional[IntQuantity] = Field(None, ge=0)


class VendorProductRead(VendorProductBase):
    """Vendor product response model."""
    model_config = ConfigDict(from_attributes=True)
    
    id: uuid.UUID
    last_synced_at: datetime
    created_at: datetime
    updated_at: datetime


# =============================================================================
# INVENTORY SNAPSHOT SCHEMAS
# =============================================================================

class ScanMethod(str, Enum):
    """Inventory scan method types."""
    MANUAL = "manual"
    BARCODE = "barcode"
    SILHOUETTE = "silhouette"
    VOLUMETRIC = "volumetric"


class InventorySnapshotCreate(BaseModel):
    """Inventory snapshot creation payload."""
    product_id: uuid.UUID
    quantity: int = Field(..., ge=0)
    confidence_score: Optional[Decimal] = Field(None, ge=0, le=1)
    scanned_by: str = Field("bishop", max_length=100)
    scan_method: ScanMethod = ScanMethod.MANUAL
    location_tag: Optional[str] = Field(None, max_length=255)


class InventorySnapshotRead(InventorySnapshotCreate):
    """Inventory snapshot response model."""
    model_config = ConfigDict(from_attributes=True)
    
    id: uuid.UUID
    scanned_at: datetime


# =============================================================================
# ORDER SCHEMAS
# =============================================================================

class OrderStatus(str, Enum):
    """Order lifecycle states."""
    QUEUED = "queued"
    SUBMITTED = "submitted"
    CONFIRMED = "confirmed"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"


class OrderItemCreate(BaseModel):
    """Order line item creation payload."""
    product_id: uuid.UUID
    quantity: IntQuantity = Field(..., gt=0)
    unit_price_micros: MoneyMicros = Field(..., gt=0, description="Price in micros")
    vendor_product_id: Optional[uuid.UUID] = None


class OrderCreate(BaseModel):
    """Order creation payload."""
    vendor_id: uuid.UUID
    items: list[OrderItemCreate] = Field(..., min_length=1)


class OrderItemRead(BaseModel):
    """Order item response model."""
    model_config = ConfigDict(from_attributes=True)
    
    id: uuid.UUID
    product_id: uuid.UUID
    vendor_product_id: Optional[uuid.UUID]
    quantity: IntQuantity
    unit_price_micros: MoneyMicros


class OrderRead(BaseModel):
    """Order response model."""
    model_config = ConfigDict(from_attributes=True)
    
    id: uuid.UUID
    vendor_id: uuid.UUID
    status: OrderStatus
    total_amount_micros: Optional[MoneyMicros] = None
    blocked_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    submitted_at: Optional[datetime] = None
    items: list[OrderItemRead] = []


# =============================================================================
# EXTERNAL SYSTEM INTERFACE SCHEMAS (Mock Contracts)
# =============================================================================

class LedgerCheckRequest(BaseModel):
    """Request to Ledger system for balance verification."""
    order_total_micros: MoneyMicros = Field(..., gt=0, description="Order total in micros")
    currency: str = Field("USD", max_length=3)


class LedgerCheckResponse(BaseModel):
    """Response from Ledger system."""
    sufficient_funds: bool
    available_balance_micros: MoneyMicros
    currency: str
    checked_at: datetime = Field(default_factory=datetime.utcnow)


class RiskCheckRequest(BaseModel):
    """Request to ClaimsIQ for risk assessment."""
    product_id: uuid.UUID
    expiry_date: Optional[datetime] = None
    quantity: IntQuantity = Field(..., ge=0)


class RiskCheckResponse(BaseModel):
    """Response from ClaimsIQ risk system."""
    is_flagged: bool
    risk_level: Literal["none", "low", "medium", "high", "critical"]
    liability_flags: list[str] = []
    recommended_action: Optional[str] = None
    checked_at: datetime = Field(default_factory=datetime.utcnow)


class VendorQueryRequest(BaseModel):
    """Request to query vendor for product availability."""
    product_id: uuid.UUID
    vendor_sku: str
    quantity_needed: IntQuantity = Field(..., gt=0)


class VendorQueryResponse(BaseModel):
    """Response from vendor availability check."""
    vendor_id: uuid.UUID
    vendor_name: str
    in_stock: bool
    available_quantity: IntQuantity
    unit_price_micros: MoneyMicros
    estimated_delivery_hours: Optional[int] = None
    queried_at: datetime = Field(default_factory=datetime.utcnow)

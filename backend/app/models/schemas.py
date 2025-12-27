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


# =============================================================================
# FOOD MANAGEMENT SCHEMAS (Migration 008)
# =============================================================================

class IngredientCategory(str, Enum):
    """Ingredient categories for food management."""
    PROTEIN = "protein"
    PRODUCE = "produce"
    DAIRY = "dairy"
    DRY_GOODS = "dry_goods"
    BEVERAGES = "beverages"
    FROZEN = "frozen"
    BAKERY = "bakery"
    CONDIMENTS = "condiments"
    SUPPLIES = "supplies"


class IngredientStatus(str, Enum):
    """Ingredient lifecycle status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    DISCONTINUED = "discontinued"


class IngredientBase(BaseModel):
    """Base ingredient attributes."""
    name: str = Field(..., min_length=1, max_length=255)
    category: IngredientCategory
    subcategory: Optional[str] = Field(None, max_length=100)
    base_unit: str = Field(..., max_length=20)  # lb, oz, each, case, gal
    purchase_unit: str = Field(..., max_length=20)
    purchase_to_base_ratio: Decimal = Field(Decimal("1.0"), gt=0)
    current_cost_cents: int = Field(..., gt=0, description="Cost in cents")
    is_perishable: bool = True
    shelf_life_days: Optional[int] = Field(None, ge=1)
    requires_refrigeration: bool = False
    requires_freezer: bool = False
    par_level: Optional[Decimal] = Field(None, ge=0)
    reorder_point: Optional[Decimal] = Field(None, ge=0)
    min_order_qty: Optional[Decimal] = Field(None, ge=0)
    preferred_vendor_id: Optional[uuid.UUID] = None
    status: IngredientStatus = IngredientStatus.ACTIVE


class IngredientCreate(IngredientBase):
    """Ingredient creation payload."""
    org_id: uuid.UUID


class IngredientRead(IngredientBase):
    """Ingredient response model."""
    model_config = ConfigDict(from_attributes=True)
    
    id: uuid.UUID
    org_id: uuid.UUID
    cost_updated_at: Optional[datetime] = None
    avg_cost_30d: Optional[int] = None
    avg_cost_90d: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class MenuItemStatus(str, Enum):
    """Menu item status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SEASONAL = "seasonal"
    EIGHTYSIXED = "86d"  # Industry term for "out of stock"


class MenuItemBase(BaseModel):
    """Base menu item attributes."""
    name: str = Field(..., min_length=1, max_length=255)
    category: str = Field(..., max_length=100)
    subcategory: Optional[str] = Field(None, max_length=100)
    menu_price_cents: int = Field(..., gt=0, description="Menu price in cents")
    target_food_cost_pct: Optional[Decimal] = Field(Decimal("30.00"), ge=0, le=100)
    status: MenuItemStatus = MenuItemStatus.ACTIVE
    is_seasonal: bool = False


class MenuItemCreate(MenuItemBase):
    """Menu item creation payload."""
    org_id: uuid.UUID


class MenuItemRead(MenuItemBase):
    """Menu item response model."""
    model_config = ConfigDict(from_attributes=True)
    
    id: uuid.UUID
    org_id: uuid.UUID
    calculated_food_cost_cents: Optional[int] = None
    food_cost_percentage: Optional[Decimal] = None
    avg_daily_sales: Optional[Decimal] = None
    last_sold_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class RecipeBase(BaseModel):
    """Base recipe (menu item ingredient) attributes."""
    menu_item_id: uuid.UUID
    ingredient_id: uuid.UUID
    quantity: Decimal = Field(..., gt=0)
    unit: str = Field(..., max_length=20)
    waste_factor: Decimal = Field(Decimal("1.0"), ge=1.0)  # 1.1 = 10% waste


class RecipeCreate(RecipeBase):
    """Recipe creation payload."""
    pass


class RecipeRead(RecipeBase):
    """Recipe response model."""
    model_config = ConfigDict(from_attributes=True)
    
    id: uuid.UUID
    calculated_cost_cents: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class WasteType(str, Enum):
    """Food waste type classification."""
    SPOILAGE = "spoilage"
    EXPIRED = "expired"
    PREP_WASTE = "prep_waste"
    COOKING_ERROR = "cooking_error"
    CUSTOMER_RETURN = "customer_return"
    OVERPRODUCTION = "overproduction"
    DAMAGED = "damaged"
    THEFT = "theft"
    UNKNOWN = "unknown"


class WasteReason(str, Enum):
    """Food waste reason classification."""
    PAST_EXPIRATION = "past_expiration"
    TEMPERATURE_ABUSE = "temperature_abuse"
    IMPROPER_STORAGE = "improper_storage"
    OVER_PREP = "over_prep"
    DROPPED = "dropped"
    BURNT = "burnt"
    WRONG_ORDER = "wrong_order"
    QUALITY_ISSUE = "quality_issue"
    INVENTORY_SHRINK = "inventory_shrink"
    SPILLAGE = "spillage"
    OTHER = "other"


class FoodWasteCreate(BaseModel):
    """Food waste record creation."""
    org_id: uuid.UUID
    ingredient_id: Optional[uuid.UUID] = None
    menu_item_id: Optional[uuid.UUID] = None
    inventory_id: Optional[uuid.UUID] = None
    waste_type: WasteType
    waste_reason: WasteReason
    quantity: Decimal = Field(..., gt=0)
    unit: str = Field(..., max_length=20)
    estimated_cost_cents: int = Field(..., ge=0)
    photo_url: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = None
    recorded_by: Optional[uuid.UUID] = None


class FoodWasteRead(FoodWasteCreate):
    """Food waste response model."""
    model_config = ConfigDict(from_attributes=True)
    
    id: uuid.UUID
    waste_date: datetime
    recorded_at: datetime


class FoodOrderType(str, Enum):
    """Food order type."""
    REGULAR = "regular"
    EMERGENCY = "emergency"
    STANDING = "standing"
    SPECIAL = "special"


class FoodOrderStatus(str, Enum):
    """Food order status."""
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    SUBMITTED = "submitted"
    CONFIRMED = "confirmed"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    PARTIAL = "partial"


class FoodOrderItemCreate(BaseModel):
    """Food order line item."""
    ingredient_id: Optional[uuid.UUID] = None
    vendor_product_id: Optional[uuid.UUID] = None
    product_name: str = Field(..., max_length=255)
    vendor_sku: Optional[str] = Field(None, max_length=100)
    quantity_ordered: Decimal = Field(..., gt=0)
    unit: str = Field(..., max_length=20)
    unit_price_cents: int = Field(..., gt=0)


class FoodOrderCreate(BaseModel):
    """Food order creation payload."""
    org_id: uuid.UUID
    vendor_id: uuid.UUID
    order_type: FoodOrderType = FoodOrderType.REGULAR
    expected_delivery: Optional[datetime] = None
    bishop_session_id: Optional[uuid.UUID] = None
    auto_generated: bool = False
    items: list[FoodOrderItemCreate] = Field(..., min_length=1)


class FoodOrderItemRead(BaseModel):
    """Food order item response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: uuid.UUID
    ingredient_id: Optional[uuid.UUID]
    vendor_product_id: Optional[uuid.UUID]
    product_name: str
    vendor_sku: Optional[str]
    quantity_ordered: Decimal
    quantity_received: Optional[Decimal]
    unit: str
    unit_price_cents: int
    line_total_cents: int
    received_date: Optional[datetime]
    received_by: Optional[uuid.UUID]
    receiving_notes: Optional[str]


class FoodOrderRead(BaseModel):
    """Food order response model."""
    model_config = ConfigDict(from_attributes=True)
    
    id: uuid.UUID
    org_id: uuid.UUID
    vendor_id: uuid.UUID
    order_number: str
    order_type: FoodOrderType
    status: FoodOrderStatus
    subtotal_cents: int
    tax_cents: int
    delivery_fee_cents: int
    total_cents: int
    order_date: Optional[datetime]
    expected_delivery: Optional[datetime]
    actual_delivery: Optional[datetime]
    bishop_session_id: Optional[uuid.UUID]
    auto_generated: bool
    approved_by: Optional[uuid.UUID]
    approved_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    items: list[FoodOrderItemRead] = []


class FoodCostReportType(str, Enum):
    """Food cost report period type."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class FoodCostReportRead(BaseModel):
    """Food cost report response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: uuid.UUID
    org_id: uuid.UUID
    report_date: datetime
    report_type: FoodCostReportType
    total_food_sales_cents: Optional[int]
    beginning_inventory_value_cents: Optional[int]
    purchases_cents: Optional[int]
    ending_inventory_value_cents: Optional[int]
    calculated_cogs_cents: Optional[int]
    total_waste_value_cents: Optional[int]
    waste_by_type: Optional[dict]
    food_cost_percentage: Optional[Decimal]
    target_food_cost_pct: Optional[Decimal]
    variance_from_target: Optional[Decimal]
    alerts: Optional[list[dict]]
    generated_at: datetime

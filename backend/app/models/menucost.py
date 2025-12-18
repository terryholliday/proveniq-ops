"""
PROVENIQ Ops - Cost Per Serving Schemas
Bishop menu profitability data contracts

DAG Node: N17, N37

GUARDRAILS:
- Do not suggest menu price changes unless enabled
"""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from app.core.types import MoneyMicros, Quantity, Rate


class MarginAlertType(str, Enum):
    """Margin alert classifications."""
    MARGIN_SHIFT = "MARGIN_SHIFT"
    MARGIN_COMPRESSION = "MARGIN_COMPRESSION"
    COST_SPIKE = "COST_SPIKE"
    THRESHOLD_BREACH = "THRESHOLD_BREACH"


class MarginStatus(str, Enum):
    """Menu item margin status."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    NEGATIVE = "negative"


class UnitOfMeasure(str, Enum):
    """Standard units for ingredients."""
    EACH = "each"
    OZ = "oz"
    LB = "lb"
    GAL = "gal"
    QT = "qt"
    CUP = "cup"
    TBSP = "tbsp"
    TSP = "tsp"
    G = "g"
    KG = "kg"
    ML = "ml"
    L = "l"


# =============================================================================
# RECIPE & INGREDIENT MODELS
# =============================================================================

class Ingredient(BaseModel):
    """Ingredient definition with cost tracking."""
    ingredient_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    product_id: uuid.UUID  # Links to inventory
    name: str
    canonical_sku: str
    
    # Purchase unit (how we buy it)
    purchase_unit: UnitOfMeasure
    purchase_qty: Quantity  # e.g., 5 for "5lb bag"
    current_cost_micros: MoneyMicros  # Cost for purchase_qty
    
    # Cost per base unit
    cost_per_unit_micros: MoneyMicros  # Calculated: cost / qty
    
    # Tracking
    last_cost_update: datetime = Field(default_factory=datetime.utcnow)
    cost_30d_avg_micros: Optional[MoneyMicros] = None
    cost_trend: Optional[str] = None  # up, down, stable


class RecipeIngredient(BaseModel):
    """Ingredient usage in a recipe."""
    ingredient_id: uuid.UUID
    ingredient_name: str
    
    # How much we use
    quantity: Quantity
    unit: UnitOfMeasure
    
    # Calculated cost
    cost_micros: MoneyMicros
    
    # Waste factor (e.g., 1.1 for 10% prep waste)
    waste_factor: Quantity = Field(default=Decimal("1.0"))


class Recipe(BaseModel):
    """Menu item recipe with cost calculation."""
    recipe_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    menu_item_id: uuid.UUID
    menu_item_name: str
    
    # Ingredients
    ingredients: list[RecipeIngredient] = []
    
    # Yield
    portions_per_batch: int = 1
    
    # Calculated costs
    total_ingredient_cost_micros: MoneyMicros = 0
    cost_per_serving_micros: MoneyMicros = 0
    
    # Version tracking
    version: int = 1
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class MenuItem(BaseModel):
    """Menu item with pricing and margin."""
    menu_item_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    category: str
    
    # Pricing
    menu_price_micros: MoneyMicros
    
    # Current cost (from recipe)
    cost_per_serving_micros: MoneyMicros
    
    # Margins
    gross_margin_micros: MoneyMicros  # price - cost
    gross_margin_percent: Quantity
    
    # Status
    margin_status: MarginStatus
    
    # Targets
    target_margin_percent: Quantity = Field(default=Decimal("65"))
    min_margin_percent: Quantity = Field(default=Decimal("50"))
    
    # Tracking
    cost_30d_avg_micros: Optional[MoneyMicros] = None
    margin_30d_avg_percent: Optional[Quantity] = None
    
    # Recipe reference
    recipe_id: Optional[uuid.UUID] = None


# =============================================================================
# ALERT MODELS
# =============================================================================

class MarginAlert(BaseModel):
    """
    Bishop margin shift alert.
    Deterministic output - cost/margin facts only.
    """
    alert_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    alert_type: MarginAlertType
    
    # Menu item
    menu_item_id: uuid.UUID
    menu_item_name: str
    category: str
    
    # Cost change
    previous_cost_micros: MoneyMicros
    current_cost_micros: MoneyMicros
    cost_change_micros: MoneyMicros
    cost_change_percent: Quantity
    
    # Margin impact
    previous_margin_percent: Quantity
    new_margin_percent: Quantity
    margin_change_percent: Quantity
    
    # Status
    margin_status: MarginStatus
    threshold_breached: Optional[str] = None  # target, minimum, critical
    
    # Top cost drivers
    cost_drivers: list[dict] = []  # [{ingredient, change_pct, impact_micros}]
    
    # Recommendation (only if price_suggestions_enabled)
    price_suggestion_micros: Optional[MoneyMicros] = None
    price_suggestion_enabled: bool = False
    
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "alert_type": "MARGIN_SHIFT",
                "menu_item_name": "Grilled Chicken Salad",
                "cost_change_percent": "8.5",
                "new_margin_percent": "58.2",
                "margin_status": "warning"
            }
        }


# =============================================================================
# ANALYSIS MODELS
# =============================================================================

class MenuCostAnalysis(BaseModel):
    """Complete menu cost analysis."""
    analysis_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Summary
    total_menu_items: int
    items_analyzed: int
    
    # Status breakdown
    healthy_count: int = 0
    warning_count: int = 0
    critical_count: int = 0
    negative_margin_count: int = 0
    
    # Alerts generated
    alerts: list[MarginAlert] = []
    
    # Top issues
    top_margin_compression: list[MenuItem] = []
    top_cost_increases: list[MenuItem] = []
    
    # Aggregate metrics
    avg_margin_percent: Quantity
    total_daily_cost_micros: Optional[MoneyMicros] = None  # If volume data available


class IngredientCostImpact(BaseModel):
    """Impact of ingredient cost change across menu."""
    ingredient_id: uuid.UUID
    ingredient_name: str
    
    # Cost change
    previous_cost_micros: MoneyMicros
    current_cost_micros: MoneyMicros
    change_percent: Quantity
    
    # Menu impact
    affected_items: int
    total_margin_impact_micros: MoneyMicros
    
    # Affected menu items
    affected_menu_items: list[str] = []


# =============================================================================
# CONFIGURATION
# =============================================================================

class MenuCostConfig(BaseModel):
    """Configuration for cost per serving engine."""
    # Thresholds
    margin_warning_percent: Quantity = Field(default=Decimal("55"))
    margin_critical_percent: Quantity = Field(default=Decimal("45"))
    cost_change_alert_percent: Quantity = Field(default=Decimal("5"))
    
    # Target
    default_target_margin_percent: Quantity = Field(default=Decimal("65"))
    
    # Features
    price_suggestions_enabled: bool = False  # GUARDRAIL: Default off
    include_waste_factor: bool = True
    
    # Analysis
    rolling_avg_days: int = 30

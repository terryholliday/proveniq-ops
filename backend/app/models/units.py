"""
PROVENIQ Ops - Canonical Unit Model
Bishop foundational inventory truth system

DAG Node: N5 - Bulk Normalization Engine

THREE LAYERS OF TRUTH:
A. Base Unit - What Bishop stores internally (g, ml, lb, L)
B. Handling Unit - What humans see (bag, case, can, scoop)
C. Measurement Method - How reality is sampled

PHILOSOPHY:
Other systems ask: "How many units do you have?"
Bishop asks: "What do you observe?"
And then quietly does the math better than any human ever could.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from app.core.types import Quantity, Rate


# =============================================================================
# A. BASE UNITS - What Bishop stores internally
# =============================================================================

class BaseUnit(str, Enum):
    """
    Canonical base units for internal storage.
    All inventory is normalized to these units.
    """
    # Weight
    GRAMS = "g"
    KILOGRAMS = "kg"
    POUNDS = "lb"
    OUNCES = "oz"
    
    # Volume
    MILLILITERS = "ml"
    LITERS = "L"
    FLUID_OUNCES = "fl_oz"
    GALLONS = "gal"
    
    # Count (for items that can't be weight/volume)
    EACH = "each"


class UnitCategory(str, Enum):
    """Unit categories for conversion logic."""
    WEIGHT = "weight"
    VOLUME = "volume"
    COUNT = "count"


# Unit metadata for conversions
UNIT_METADATA: dict[BaseUnit, dict] = {
    # Weight (base: grams)
    BaseUnit.GRAMS: {"category": UnitCategory.WEIGHT, "to_base": Decimal("1")},
    BaseUnit.KILOGRAMS: {"category": UnitCategory.WEIGHT, "to_base": Decimal("1000")},
    BaseUnit.POUNDS: {"category": UnitCategory.WEIGHT, "to_base": Decimal("453.592")},
    BaseUnit.OUNCES: {"category": UnitCategory.WEIGHT, "to_base": Decimal("28.3495")},
    
    # Volume (base: milliliters)
    BaseUnit.MILLILITERS: {"category": UnitCategory.VOLUME, "to_base": Decimal("1")},
    BaseUnit.LITERS: {"category": UnitCategory.VOLUME, "to_base": Decimal("1000")},
    BaseUnit.FLUID_OUNCES: {"category": UnitCategory.VOLUME, "to_base": Decimal("29.5735")},
    BaseUnit.GALLONS: {"category": UnitCategory.VOLUME, "to_base": Decimal("3785.41")},
    
    # Count
    BaseUnit.EACH: {"category": UnitCategory.COUNT, "to_base": Decimal("1")},
}


# =============================================================================
# B. HANDLING UNITS - What humans see
# =============================================================================

class HandlingUnitType(str, Enum):
    """Standard handling unit types for human interaction."""
    BAG = "bag"
    BOX = "box"
    CASE = "case"
    CAN = "can"
    JAR = "jar"
    BOTTLE = "bottle"
    CONTAINER = "container"
    BIN = "bin"
    SCOOP = "scoop"
    PORTION = "portion"
    SLEEVE = "sleeve"
    PALLET = "pallet"
    CUSTOM = "custom"


class HandlingUnit(BaseModel):
    """
    Definition of how humans interact with an item.
    Maps human-readable containers to base units.
    """
    handling_unit_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    
    # What the human sees
    unit_type: HandlingUnitType
    display_name: str  # "50 lb flour bag", "#10 can", "case of 12"
    
    # Conversion to base unit
    base_unit: BaseUnit
    standard_quantity: Quantity  # How much base unit per handling unit
    
    # Variance tolerance
    variance_allowed_pct: Quantity = Field(default=Decimal("2"))  # ±2% default
    
    # For containers
    container_tare_weight: Optional[Quantity] = None  # Weight of empty container
    container_tare_unit: Optional[BaseUnit] = None
    
    # For nested units (case of 12 cans)
    contains_unit_id: Optional[uuid.UUID] = None
    contains_count: Optional[int] = None


# =============================================================================
# C. MEASUREMENT METHODS - How reality is sampled
# =============================================================================

class MeasurementMethod(str, Enum):
    """
    The three legit ways a user can count bulk inventory.
    """
    # Method 1: Container Count × Standard Weight (fastest, default)
    CONTAINER_COUNT = "CONTAINER_COUNT"
    
    # Method 2: Weigh What's There (highest accuracy)
    DIRECT_WEIGHT = "DIRECT_WEIGHT"
    
    # Method 3: Depletion by Usage (recipe-driven projection)
    RECIPE_DEPLETION = "RECIPE_DEPLETION"
    
    # Additional methods
    VOLUME_ESTIMATE = "VOLUME_ESTIMATE"
    STANDARD_DEPLETION = "STANDARD_DEPLETION"
    DUAL_VERIFICATION = "DUAL_VERIFICATION"  # For regulated goods


# Confidence ceilings by method
METHOD_CONFIDENCE_CEILING: dict[MeasurementMethod, Decimal] = {
    MeasurementMethod.CONTAINER_COUNT: Decimal("0.92"),
    MeasurementMethod.DIRECT_WEIGHT: Decimal("0.99"),
    MeasurementMethod.RECIPE_DEPLETION: Decimal("0.74"),
    MeasurementMethod.VOLUME_ESTIMATE: Decimal("0.70"),
    MeasurementMethod.STANDARD_DEPLETION: Decimal("0.75"),
    MeasurementMethod.DUAL_VERIFICATION: Decimal("0.99"),
}


# =============================================================================
# NORMALIZED QUANTITY - The output of N5
# =============================================================================

class NormalizedQuantity(BaseModel):
    """
    The canonical output of the Bulk Normalization Engine.
    Every downstream node consumes this — not raw user input.
    """
    # The truth
    quantity_base_units: Quantity
    base_unit: BaseUnit
    
    # Confidence (THE SECRET WEAPON)
    confidence: Rate  # 0.0 - 1.0
    
    # How we got here
    measurement_method: MeasurementMethod
    
    # Original observation (for audit)
    original_input: Optional[str] = None
    
    # Metadata
    measured_at: datetime = Field(default_factory=datetime.utcnow)
    measured_by: Optional[str] = None


class PartialContainer(BaseModel):
    """Representation of a partial/open container."""
    fullness_pct: Quantity  # 0-100, from slider or weight
    estimated_quantity: Quantity
    was_weighed: bool = False
    actual_weight: Optional[Quantity] = None


# =============================================================================
# BULK COUNT INPUT MODELS - User observation inputs
# =============================================================================

class ContainerCountInput(BaseModel):
    """
    Method 1: Container Count × Standard Weight
    Fast, default method.
    """
    full_containers: int
    partial_containers: list[PartialContainer] = []
    
    # Optional: override standard weight
    override_standard_weight: Optional[Quantity] = None


class DirectWeightInput(BaseModel):
    """
    Method 2: Weigh What's There
    Highest accuracy method.
    """
    gross_weight: Quantity
    weight_unit: BaseUnit
    
    # Container info
    container_count: int = 1
    include_container_tare: bool = True
    
    # Manual tare override
    tare_weight_override: Optional[Quantity] = None


class RecipeDepletionInput(BaseModel):
    """
    Method 3: Depletion by Usage
    Recipe-driven projection (NOT reality).
    """
    last_known_quantity: Quantity
    last_known_unit: BaseUnit
    last_known_at: datetime
    
    # Usage data
    servings_since_last_count: int
    usage_per_serving: Quantity
    usage_unit: BaseUnit


class VolumeEstimateInput(BaseModel):
    """
    Volume estimation for liquids.
    Confidence capped unless weighed.
    """
    container_capacity: Quantity
    container_unit: BaseUnit
    fill_level_pct: Quantity  # From markings or estimate
    container_count: int = 1


# =============================================================================
# ITEM CONFIGURATION - How Bishop knows about each product
# =============================================================================

class BulkItemConfig(BaseModel):
    """
    Configuration for how Bishop handles a bulk item.
    Stored per-product, defines the truth layers.
    """
    config_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    product_id: uuid.UUID
    product_name: str
    canonical_sku: str
    
    # Base unit for this item
    base_unit: BaseUnit
    unit_category: UnitCategory
    
    # Primary handling unit
    primary_handling_unit: HandlingUnit
    
    # Additional handling units (case, pallet, etc.)
    alternate_handling_units: list[HandlingUnit] = []
    
    # Allowed measurement methods
    allowed_methods: list[MeasurementMethod] = [
        MeasurementMethod.CONTAINER_COUNT,
        MeasurementMethod.DIRECT_WEIGHT,
    ]
    
    # Default/preferred method
    default_method: MeasurementMethod = MeasurementMethod.CONTAINER_COUNT
    
    # Regulated item flags
    is_regulated: bool = False  # Alcohol, controlled substances
    requires_dual_verification: bool = False
    force_weigh_method: bool = False  # High-value items
    
    # Confidence rules
    min_confidence_for_ops: Rate = Field(default=Decimal("0.70"))
    reweigh_trigger_confidence: Rate = Field(default=Decimal("0.60"))
    
    # Recipe usage (for depletion method)
    usage_per_serving: Optional[Quantity] = None
    usage_unit: Optional[BaseUnit] = None


# =============================================================================
# VERIFICATION & AUDIT
# =============================================================================

class VerificationTrigger(str, Enum):
    """Reasons Bishop triggers a re-verification."""
    LOW_CONFIDENCE = "low_confidence"
    CONFIDENCE_DECAY = "confidence_decay"
    VARIANCE_GROWTH = "variance_growth"
    SCHEDULED_AUDIT = "scheduled_audit"
    SHRINKAGE_SIGNAL = "shrinkage_signal"
    REGULATED_ITEM = "regulated_item"


class VerificationRequest(BaseModel):
    """Request for user to re-verify inventory."""
    request_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    product_id: uuid.UUID
    product_name: str
    
    # Current state
    current_quantity: NormalizedQuantity
    
    # Why verification needed
    trigger: VerificationTrigger
    trigger_reason: str
    
    # Recommended method
    recommended_method: MeasurementMethod
    
    # Urgency
    priority: str = "normal"  # low, normal, high, critical
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    due_by: Optional[datetime] = None


# =============================================================================
# CONFIDENCE DECAY MODEL
# =============================================================================

class ConfidenceDecayConfig(BaseModel):
    """
    How confidence decays over time without re-measurement.
    Prevents stale data from being trusted.
    """
    # Decay rate per day (multiplicative)
    daily_decay_rate: Rate = Field(default=Decimal("0.98"))  # Loses 2% per day
    
    # Minimum confidence floor
    floor_confidence: Rate = Field(default=Decimal("0.40"))
    
    # Max days before forced re-verification
    max_days_without_verification: int = 7
    
    # High-turnover items decay faster
    high_turnover_decay_rate: Rate = Field(default=Decimal("0.95"))
    
    # Regulated items decay faster
    regulated_decay_rate: Rate = Field(default=Decimal("0.90"))

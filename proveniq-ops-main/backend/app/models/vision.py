"""
PROVENIQ Ops - Vision Estimation Pydantic Models
Strict contracts for bulk inventory vision pipeline.

RULES:
- Vision is upstream-only: produces observations with confidence, never actions
- No item identity → no mass conversion (volume-only)
- No container identity → no volume calculation (request selection)
- No density profile → no volume→mass conversion
- Must include component confidences for explainability
"""

import uuid
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Optional, Literal, Any

from pydantic import BaseModel, Field, field_validator

from app.core.types import Rate, Quantity


# =============================================================================
# ENUMS
# =============================================================================

class BaseUoM(str, Enum):
    """Base units of measure - what Bishop stores internally."""
    GRAMS = "g"
    MILLILITERS = "ml"
    EACH = "each"


class MeasurementMethodCode(str, Enum):
    """
    Allowed measurement methods.
    Each has a typical confidence range.
    """
    COUNT_STD = "COUNT_STD"      # Count containers × standard weight (0.75–0.95)
    WEIGH_NET = "WEIGH_NET"      # Weigh gross - tare (0.95–0.99)
    VOLUME_GEOM = "VOLUME_GEOM"  # Container volume × fill ratio (0.60–0.90)
    RECIPE_DEPL = "RECIPE_DEPL"  # Recipe usage projection (0.50–0.80)
    MANUAL_VOL = "MANUAL_VOL"    # Human-entered volume (0.60–0.90)


class ContainerShape(str, Enum):
    """Container geometry shapes."""
    RECT_PRISM = "RECT_PRISM"
    CYLINDER = "CYLINDER"
    HOTEL_PAN = "HOTEL_PAN"
    OTHER = "OTHER"


class DensitySourceType(str, Enum):
    """Source of density profile data."""
    MANUFACTURER = "MANUFACTURER"
    USDA = "USDA"
    CALIBRATED_WEIGH = "CALIBRATED_WEIGH"
    OTHER = "OTHER"


class PartialEntryMode(str, Enum):
    """How partial containers are entered."""
    RATIO = "RATIO"   # Slider 0-100%
    WEIGH = "WEIGH"   # Weigh the partial
    VOLUME = "VOLUME" # Enter volume directly


class VisionNextStep(str, Enum):
    """Recommended next step after vision observation."""
    ACCEPT_VOLUME = "ACCEPT_VOLUME"
    SELECT_CONTAINER = "SELECT_CONTAINER"
    RETAKE_PHOTO = "RETAKE_PHOTO"
    WEIGH_REQUIRED = "WEIGH_REQUIRED"
    CONFIRM_ITEM = "CONFIRM_ITEM"


class ForceWeighReason(str, Enum):
    """Reasons Bishop forces a weigh-in."""
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    HIGH_VALUE_ITEM = "HIGH_VALUE_ITEM"
    STOCKOUT_CRITICAL = "STOCKOUT_CRITICAL"
    REGULATED_ITEM = "REGULATED_ITEM"
    SHRINKAGE_ESCALATION = "SHRINKAGE_ESCALATION"
    RECEIVING_DISPUTE = "RECEIVING_DISPUTE"


# =============================================================================
# CONTAINER MODELS
# =============================================================================

class ContainerTypeOut(BaseModel):
    """Container type from reference library."""
    id: uuid.UUID
    manufacturer: str
    model_family: str
    display_name: str
    shape: ContainerShape
    nominal_volume_ml: int
    internal_height_mm: Optional[int] = None
    internal_length_mm: Optional[int] = None
    internal_width_mm: Optional[int] = None
    internal_diameter_mm: Optional[int] = None
    has_graduation_marks: bool = False
    image_ref: Optional[str] = None


class ContainerTypeCreate(BaseModel):
    """Create a new container type."""
    manufacturer: str
    model_family: str
    display_name: str
    shape: ContainerShape
    nominal_volume_ml: int
    internal_height_mm: Optional[int] = None
    internal_length_mm: Optional[int] = None
    internal_width_mm: Optional[int] = None
    internal_diameter_mm: Optional[int] = None
    has_graduation_marks: bool = False


class ContainerInstanceOut(BaseModel):
    """Physical container instance."""
    id: uuid.UUID
    container_type_id: uuid.UUID
    container_type: Optional[ContainerTypeOut] = None
    label_code: Optional[str] = None
    tare_g: Optional[int] = None
    notes: Optional[str] = None
    active: bool = True


# =============================================================================
# DENSITY MODELS
# =============================================================================

class DensityProfileOut(BaseModel):
    """Density profile for volume→mass conversion."""
    id: uuid.UUID
    product_id: uuid.UUID
    density_g_per_ml: Decimal
    variance_pct: Decimal = Decimal("0")
    source_type: DensitySourceType
    source_note: Optional[str] = None
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None


class DensityProfileCreate(BaseModel):
    """Create a density profile."""
    product_id: uuid.UUID
    density_g_per_ml: Decimal
    variance_pct: Decimal = Decimal("0")
    source_type: DensitySourceType
    source_note: Optional[str] = None


# =============================================================================
# BULK ITEM CONFIG
# =============================================================================

class BulkItemConfigOut(BaseModel):
    """Bulk item configuration."""
    id: uuid.UUID
    product_id: uuid.UUID
    base_uom: BaseUoM
    handling_uom: str
    preferred_methods: list[MeasurementMethodCode]
    require_density_for_mass: bool = True
    default_density_profile_id: Optional[uuid.UUID] = None
    default_container_type_id: Optional[uuid.UUID] = None
    default_container_tare_g: Optional[int] = None
    partial_allowed: bool = True
    partial_entry_mode: PartialEntryMode = PartialEntryMode.RATIO
    min_confidence_to_autouse: Decimal = Decimal("0.700")
    min_confidence_to_convert_mass: Decimal = Decimal("0.800")
    force_weigh_below_confidence: Decimal = Decimal("0.650")


class BulkItemConfigCreate(BaseModel):
    """Create bulk item config."""
    product_id: uuid.UUID
    base_uom: BaseUoM
    handling_uom: str
    preferred_methods: list[MeasurementMethodCode]
    require_density_for_mass: bool = True
    default_container_type_id: Optional[uuid.UUID] = None
    default_container_tare_g: Optional[int] = None
    partial_allowed: bool = True
    partial_entry_mode: PartialEntryMode = PartialEntryMode.RATIO


# =============================================================================
# VISION OBSERVATION MODELS
# =============================================================================

class VisionObservationOut(BaseModel):
    """
    Raw vision observation output.
    Observation-only - does NOT make decisions.
    """
    id: uuid.UUID
    image_asset_key: str
    captured_at: datetime
    
    # Container detection
    detected_container_type_id: Optional[uuid.UUID] = None
    container_conf: Rate = Decimal("0")
    
    # Fill estimation
    fill_ratio: Optional[Rate] = None  # 0..1
    fill_conf: Rate = Decimal("0")
    
    # OCR
    ocr_text: Optional[str] = None
    ocr_conf: Rate = Decimal("0")
    
    # Item identification
    parsed_item_hint: Optional[str] = None
    item_hint_conf: Rate = Decimal("0")
    
    # Additional
    notes: dict[str, Any] = Field(default_factory=dict)
    
    @field_validator('container_conf', 'fill_conf', 'ocr_conf', 'item_hint_conf', mode='before')
    @classmethod
    def clamp_confidence(cls, v):
        if v is None:
            return Decimal("0")
        return max(Decimal("0"), min(Decimal("1"), Decimal(str(v))))


class VisionEstimateRequest(BaseModel):
    """Request for vision estimation."""
    org_id: uuid.UUID
    location_id: Optional[uuid.UUID] = None
    image_asset_key: str
    candidate_container_type_ids: list[uuid.UUID] = Field(default_factory=list)
    hint_product_id: Optional[uuid.UUID] = None


class VisionEstimateResponse(BaseModel):
    """Response from vision estimation."""
    vision_observation: VisionObservationOut
    recommended_next_step: VisionNextStep
    
    # Computed values (if applicable)
    estimated_volume_ml: Optional[int] = None
    volume_confidence: Optional[Rate] = None
    
    # Warnings
    warnings: list[str] = Field(default_factory=list)


# =============================================================================
# INVENTORY MEASUREMENT MODELS
# =============================================================================

class InventoryMeasurementIn(BaseModel):
    """Input for creating an inventory measurement."""
    product_id: uuid.UUID
    location_id: uuid.UUID
    method_code: MeasurementMethodCode
    observed_value: Decimal
    observed_uom: str
    normalized_qty: Decimal
    base_uom: BaseUoM
    confidence: Rate
    density_profile_id: Optional[uuid.UUID] = None
    container_instance_id: Optional[uuid.UUID] = None
    vision_observation_id: Optional[uuid.UUID] = None


class InventoryMeasurementOut(BaseModel):
    """Output for inventory measurement."""
    id: uuid.UUID
    product_id: uuid.UUID
    location_id: uuid.UUID
    measured_at: datetime
    method_code: MeasurementMethodCode
    observed_value: Decimal
    observed_uom: str
    normalized_qty: Decimal
    base_uom: BaseUoM
    confidence: Rate
    density_profile_id: Optional[uuid.UUID] = None
    container_instance_id: Optional[uuid.UUID] = None
    vision_observation_id: Optional[uuid.UUID] = None
    created_by_user_id: Optional[uuid.UUID] = None


# =============================================================================
# CONFIDENCE MATH MODELS
# =============================================================================

class ConfidenceComponents(BaseModel):
    """
    Component confidences for vision estimation.
    Combining rule is conservative (weakest link).
    """
    container_conf: Rate = Decimal("0")
    fill_conf: Rate = Decimal("0")
    ocr_conf: Rate = Decimal("0")
    item_hint_conf: Rate = Decimal("0")
    density_conf: Rate = Decimal("1")  # 1.0 if verified, <1.0 if stale
    
    def compute_volume_confidence(self) -> Rate:
        """
        C_volume = 0.45*C_container + 0.55*C_fill
        """
        return (
            Decimal("0.45") * self.container_conf +
            Decimal("0.55") * self.fill_conf
        ).quantize(Decimal("0.001"))
    
    def compute_identity_confidence(self) -> Rate:
        """
        C_identity = 0.60*C_ocr + 0.40*C_item
        """
        return (
            Decimal("0.60") * self.ocr_conf +
            Decimal("0.40") * self.item_hint_conf
        ).quantize(Decimal("0.001"))
    
    def compute_mass_confidence(self) -> Rate:
        """
        C_mass = min(C_volume, C_identity, C_density)
        Capped by weakest link.
        """
        c_volume = self.compute_volume_confidence()
        c_identity = self.compute_identity_confidence()
        return min(c_volume, c_identity, self.density_conf)


class EffectiveOnHand(BaseModel):
    """
    Effective on-hand calculation for stockout prediction.
    When confidence < 1.0, treat inventory as distribution.
    
    EOH = normalized_qty * (0.50 + 0.50*confidence)
    """
    normalized_qty: Decimal
    confidence: Rate
    effective_qty: Decimal
    uncertainty_buffer: Decimal
    
    @classmethod
    def calculate(cls, qty: Decimal, conf: Rate) -> "EffectiveOnHand":
        """Calculate effective on-hand with confidence adjustment."""
        # Conservative EOH formula
        multiplier = Decimal("0.50") + Decimal("0.50") * conf
        effective = (qty * multiplier).quantize(Decimal("0.01"))
        
        # Uncertainty buffer
        buffer = qty - effective
        
        return cls(
            normalized_qty=qty,
            confidence=conf,
            effective_qty=effective,
            uncertainty_buffer=buffer,
        )


# =============================================================================
# FORCE WEIGH MODELS
# =============================================================================

class ForceWeighRequest(BaseModel):
    """
    Request to force a weigh-in.
    Generated when decision impact is high or uncertainty too large.
    """
    request_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    product_id: uuid.UUID
    product_name: str
    location_id: uuid.UUID
    
    # Trigger
    reason: ForceWeighReason
    reason_detail: str
    
    # Current state
    current_confidence: Optional[Rate] = None
    threshold_confidence: Optional[Rate] = None
    
    # Instructions
    instruction: str = "Weigh gross, subtract tare, enter net."
    tare_hint_g: Optional[int] = None
    
    # Priority
    priority: str = "normal"  # low, normal, high, critical
    blocks_execution: bool = True
    
    created_at: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# CONFIDENCE BUCKET RULES
# =============================================================================

class ConfidenceBucket(str, Enum):
    """Operational confidence buckets."""
    AUTO_USE = "auto_use"          # >= 0.85
    USABLE_PROMPT = "usable_prompt"  # 0.70-0.84
    PROVISIONAL = "provisional"    # 0.60-0.69
    REJECTED = "rejected"          # < 0.60


def get_confidence_bucket(confidence: Decimal) -> ConfidenceBucket:
    """Determine confidence bucket for operational decisions."""
    if confidence >= Decimal("0.85"):
        return ConfidenceBucket.AUTO_USE
    elif confidence >= Decimal("0.70"):
        return ConfidenceBucket.USABLE_PROMPT
    elif confidence >= Decimal("0.60"):
        return ConfidenceBucket.PROVISIONAL
    else:
        return ConfidenceBucket.REJECTED


CONFIDENCE_BUCKET_BEHAVIORS: dict[ConfidenceBucket, str] = {
    ConfidenceBucket.AUTO_USE: "Auto-usable for forecasting; no prompt needed",
    ConfidenceBucket.USABLE_PROMPT: "Usable but may prompt 'Weigh for precision?' on high-impact items",
    ConfidenceBucket.PROVISIONAL: "Allowed as provisional; triggers verification workflow",
    ConfidenceBucket.REJECTED: "Not accepted as inventory truth; force weigh-in or manual confirmation",
}

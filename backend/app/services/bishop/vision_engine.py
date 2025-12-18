"""
PROVENIQ Ops - Bishop Vision Estimation Engine
Vision pipeline for estimating container volume and fill ratio.

RULES:
- Vision is UPSTREAM-ONLY: produces observations with confidence, never actions
- No item identity → no mass conversion (volume-only)
- No container identity → no volume calculation (request selection)
- No density profile → no volume→mass conversion
- Every measurement carries confidence score and method code

CONFIDENCE MATH (Conservative):
- C_volume = 0.45*C_container + 0.55*C_fill
- C_identity = 0.60*C_ocr + 0.40*C_item
- C_mass = min(C_volume, C_identity, C_density)
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from app.models.vision import (
    BaseUoM,
    ConfidenceBucket,
    ConfidenceComponents,
    ContainerShape,
    ContainerTypeCreate,
    ContainerTypeOut,
    DensityProfileCreate,
    DensityProfileOut,
    DensitySourceType,
    EffectiveOnHand,
    ForceWeighReason,
    ForceWeighRequest,
    MeasurementMethodCode,
    VisionEstimateRequest,
    VisionEstimateResponse,
    VisionNextStep,
    VisionObservationOut,
    get_confidence_bucket,
)


# =============================================================================
# CONTAINER REFERENCE LIBRARY - Starter Dataset
# =============================================================================

CONTAINER_LIBRARY: list[dict] = [
    # Cambro CamSquare Series
    {"manufacturer": "Cambro", "model_family": "CamSquare", "display_name": "Cambro CamSquare 2 qt", 
     "shape": "RECT_PRISM", "nominal_volume_ml": 1893, "internal_height_mm": 152, 
     "internal_length_mm": 108, "internal_width_mm": 108, "has_graduation_marks": True},
    {"manufacturer": "Cambro", "model_family": "CamSquare", "display_name": "Cambro CamSquare 4 qt", 
     "shape": "RECT_PRISM", "nominal_volume_ml": 3785, "internal_height_mm": 178, 
     "internal_length_mm": 140, "internal_width_mm": 140, "has_graduation_marks": True},
    {"manufacturer": "Cambro", "model_family": "CamSquare", "display_name": "Cambro CamSquare 6 qt", 
     "shape": "RECT_PRISM", "nominal_volume_ml": 5678, "internal_height_mm": 203, 
     "internal_length_mm": 159, "internal_width_mm": 159, "has_graduation_marks": True},
    {"manufacturer": "Cambro", "model_family": "CamSquare", "display_name": "Cambro CamSquare 8 qt", 
     "shape": "RECT_PRISM", "nominal_volume_ml": 7571, "internal_height_mm": 229, 
     "internal_length_mm": 178, "internal_width_mm": 178, "has_graduation_marks": True},
    {"manufacturer": "Cambro", "model_family": "CamSquare", "display_name": "Cambro CamSquare 12 qt", 
     "shape": "RECT_PRISM", "nominal_volume_ml": 11356, "internal_height_mm": 254, 
     "internal_length_mm": 203, "internal_width_mm": 203, "has_graduation_marks": True},
    {"manufacturer": "Cambro", "model_family": "CamSquare", "display_name": "Cambro CamSquare 18 qt", 
     "shape": "RECT_PRISM", "nominal_volume_ml": 17034, "internal_height_mm": 305, 
     "internal_length_mm": 229, "internal_width_mm": 229, "has_graduation_marks": True},
    {"manufacturer": "Cambro", "model_family": "CamSquare", "display_name": "Cambro CamSquare 22 qt", 
     "shape": "RECT_PRISM", "nominal_volume_ml": 20820, "internal_height_mm": 330, 
     "internal_length_mm": 254, "internal_width_mm": 254, "has_graduation_marks": True},
    
    # Cambro CamRound Series (Cylinders)
    {"manufacturer": "Cambro", "model_family": "CamRound", "display_name": "Cambro CamRound 2 qt", 
     "shape": "CYLINDER", "nominal_volume_ml": 1893, "internal_height_mm": 140, 
     "internal_diameter_mm": 140, "has_graduation_marks": True},
    {"manufacturer": "Cambro", "model_family": "CamRound", "display_name": "Cambro CamRound 4 qt", 
     "shape": "CYLINDER", "nominal_volume_ml": 3785, "internal_height_mm": 178, 
     "internal_diameter_mm": 178, "has_graduation_marks": True},
    {"manufacturer": "Cambro", "model_family": "CamRound", "display_name": "Cambro CamRound 6 qt", 
     "shape": "CYLINDER", "nominal_volume_ml": 5678, "internal_height_mm": 203, 
     "internal_diameter_mm": 203, "has_graduation_marks": True},
    {"manufacturer": "Cambro", "model_family": "CamRound", "display_name": "Cambro CamRound 8 qt", 
     "shape": "CYLINDER", "nominal_volume_ml": 7571, "internal_height_mm": 229, 
     "internal_diameter_mm": 229, "has_graduation_marks": True},
    {"manufacturer": "Cambro", "model_family": "CamRound", "display_name": "Cambro CamRound 12 qt", 
     "shape": "CYLINDER", "nominal_volume_ml": 11356, "internal_height_mm": 254, 
     "internal_diameter_mm": 254, "has_graduation_marks": True},
    
    # Vollrath Lexan Series
    {"manufacturer": "Vollrath", "model_family": "Lexan", "display_name": "Vollrath Lexan 2 qt", 
     "shape": "RECT_PRISM", "nominal_volume_ml": 1893, "has_graduation_marks": True},
    {"manufacturer": "Vollrath", "model_family": "Lexan", "display_name": "Vollrath Lexan 4 qt", 
     "shape": "RECT_PRISM", "nominal_volume_ml": 3785, "has_graduation_marks": True},
    {"manufacturer": "Vollrath", "model_family": "Lexan", "display_name": "Vollrath Lexan 6 qt", 
     "shape": "RECT_PRISM", "nominal_volume_ml": 5678, "has_graduation_marks": True},
    {"manufacturer": "Vollrath", "model_family": "Lexan", "display_name": "Vollrath Lexan 8 qt", 
     "shape": "RECT_PRISM", "nominal_volume_ml": 7571, "has_graduation_marks": True},
    {"manufacturer": "Vollrath", "model_family": "Lexan", "display_name": "Vollrath Lexan 12 qt", 
     "shape": "RECT_PRISM", "nominal_volume_ml": 11356, "has_graduation_marks": True},
    
    # Hotel Pans (Full Size)
    {"manufacturer": "Generic", "model_family": "HotelPan", "display_name": "Full size hotel pan 2.5 in", 
     "shape": "HOTEL_PAN", "nominal_volume_ml": 8500, "internal_height_mm": 65,
     "internal_length_mm": 530, "internal_width_mm": 325, "has_graduation_marks": False},
    {"manufacturer": "Generic", "model_family": "HotelPan", "display_name": "Full size hotel pan 4 in", 
     "shape": "HOTEL_PAN", "nominal_volume_ml": 13000, "internal_height_mm": 100,
     "internal_length_mm": 530, "internal_width_mm": 325, "has_graduation_marks": False},
    {"manufacturer": "Generic", "model_family": "HotelPan", "display_name": "Full size hotel pan 6 in", 
     "shape": "HOTEL_PAN", "nominal_volume_ml": 20000, "internal_height_mm": 150,
     "internal_length_mm": 530, "internal_width_mm": 325, "has_graduation_marks": False},
    
    # Hotel Pans (Half Size)
    {"manufacturer": "Generic", "model_family": "HotelPan", "display_name": "Half size hotel pan 2.5 in", 
     "shape": "HOTEL_PAN", "nominal_volume_ml": 4200, "internal_height_mm": 65,
     "internal_length_mm": 325, "internal_width_mm": 265, "has_graduation_marks": False},
    {"manufacturer": "Generic", "model_family": "HotelPan", "display_name": "Half size hotel pan 4 in", 
     "shape": "HOTEL_PAN", "nominal_volume_ml": 6500, "internal_height_mm": 100,
     "internal_length_mm": 325, "internal_width_mm": 265, "has_graduation_marks": False},
    {"manufacturer": "Generic", "model_family": "HotelPan", "display_name": "Half size hotel pan 6 in", 
     "shape": "HOTEL_PAN", "nominal_volume_ml": 10000, "internal_height_mm": 150,
     "internal_length_mm": 325, "internal_width_mm": 265, "has_graduation_marks": False},
    
    # Hotel Pans (Third Size)
    {"manufacturer": "Generic", "model_family": "HotelPan", "display_name": "Third size hotel pan 4 in", 
     "shape": "HOTEL_PAN", "nominal_volume_ml": 4300, "internal_height_mm": 100,
     "internal_length_mm": 325, "internal_width_mm": 175, "has_graduation_marks": False},
    {"manufacturer": "Generic", "model_family": "HotelPan", "display_name": "Third size hotel pan 6 in", 
     "shape": "HOTEL_PAN", "nominal_volume_ml": 6700, "internal_height_mm": 150,
     "internal_length_mm": 325, "internal_width_mm": 175, "has_graduation_marks": False},
    
    # Hotel Pans (Sixth Size)
    {"manufacturer": "Generic", "model_family": "HotelPan", "display_name": "Sixth size hotel pan 4 in", 
     "shape": "HOTEL_PAN", "nominal_volume_ml": 2100, "internal_height_mm": 100,
     "internal_length_mm": 175, "internal_width_mm": 160, "has_graduation_marks": False},
    {"manufacturer": "Generic", "model_family": "HotelPan", "display_name": "Sixth size hotel pan 6 in", 
     "shape": "HOTEL_PAN", "nominal_volume_ml": 3200, "internal_height_mm": 150,
     "internal_length_mm": 175, "internal_width_mm": 160, "has_graduation_marks": False},
    
    # Rubbermaid Commercial
    {"manufacturer": "Rubbermaid", "model_family": "Commercial", "display_name": "Rubbermaid 2 qt", 
     "shape": "RECT_PRISM", "nominal_volume_ml": 1893, "has_graduation_marks": True},
    {"manufacturer": "Rubbermaid", "model_family": "Commercial", "display_name": "Rubbermaid 4 qt", 
     "shape": "RECT_PRISM", "nominal_volume_ml": 3785, "has_graduation_marks": True},
    {"manufacturer": "Rubbermaid", "model_family": "Commercial", "display_name": "Rubbermaid 6 qt", 
     "shape": "RECT_PRISM", "nominal_volume_ml": 5678, "has_graduation_marks": True},
    {"manufacturer": "Rubbermaid", "model_family": "Commercial", "display_name": "Rubbermaid 8 qt", 
     "shape": "RECT_PRISM", "nominal_volume_ml": 7571, "has_graduation_marks": True},
    {"manufacturer": "Rubbermaid", "model_family": "Commercial", "display_name": "Rubbermaid 12 qt", 
     "shape": "RECT_PRISM", "nominal_volume_ml": 11356, "has_graduation_marks": True},
]


# =============================================================================
# COMMON DENSITY PROFILES
# =============================================================================

COMMON_DENSITIES: dict[str, dict] = {
    # Liquids
    "water": {"density_g_per_ml": Decimal("1.000"), "source": "USDA", "variance": Decimal("0.001")},
    "milk_whole": {"density_g_per_ml": Decimal("1.030"), "source": "USDA", "variance": Decimal("0.010")},
    "cream_heavy": {"density_g_per_ml": Decimal("0.994"), "source": "USDA", "variance": Decimal("0.015")},
    "olive_oil": {"density_g_per_ml": Decimal("0.918"), "source": "USDA", "variance": Decimal("0.010")},
    "vegetable_oil": {"density_g_per_ml": Decimal("0.920"), "source": "USDA", "variance": Decimal("0.010")},
    "honey": {"density_g_per_ml": Decimal("1.420"), "source": "USDA", "variance": Decimal("0.020")},
    "maple_syrup": {"density_g_per_ml": Decimal("1.370"), "source": "USDA", "variance": Decimal("0.020")},
    
    # Granular (packed)
    "flour_ap": {"density_g_per_ml": Decimal("0.593"), "source": "USDA", "variance": Decimal("0.050")},
    "sugar_granulated": {"density_g_per_ml": Decimal("0.850"), "source": "USDA", "variance": Decimal("0.030")},
    "sugar_brown_packed": {"density_g_per_ml": Decimal("0.930"), "source": "USDA", "variance": Decimal("0.040")},
    "salt_table": {"density_g_per_ml": Decimal("1.217"), "source": "USDA", "variance": Decimal("0.020")},
    "rice_uncooked": {"density_g_per_ml": Decimal("0.850"), "source": "USDA", "variance": Decimal("0.030")},
    
    # Semi-solids
    "butter": {"density_g_per_ml": Decimal("0.911"), "source": "USDA", "variance": Decimal("0.015")},
    "sour_cream": {"density_g_per_ml": Decimal("0.960"), "source": "USDA", "variance": Decimal("0.020")},
    "mayonnaise": {"density_g_per_ml": Decimal("0.910"), "source": "USDA", "variance": Decimal("0.025")},
}


class VisionEstimationEngine:
    """
    Bishop Vision Estimation Engine
    
    Produces observations with confidence scores.
    NEVER makes decisions about ordering, waste, or blame.
    
    Hard Gates:
    - No item identity → no mass conversion (volume-only)
    - No container identity → no volume calculation
    - No density profile → no volume→mass conversion
    """
    
    def __init__(self) -> None:
        # Container library (in-memory for now, would be DB in production)
        self._container_types: dict[uuid.UUID, ContainerTypeOut] = {}
        self._density_profiles: dict[uuid.UUID, DensityProfileOut] = {}
        self._observations: list[VisionObservationOut] = []
        
        # Load starter data
        self._load_container_library()
    
    def _load_container_library(self) -> None:
        """Load the starter container library."""
        for data in CONTAINER_LIBRARY:
            container_id = uuid.uuid4()
            container = ContainerTypeOut(
                id=container_id,
                manufacturer=data["manufacturer"],
                model_family=data["model_family"],
                display_name=data["display_name"],
                shape=ContainerShape(data["shape"]),
                nominal_volume_ml=data["nominal_volume_ml"],
                internal_height_mm=data.get("internal_height_mm"),
                internal_length_mm=data.get("internal_length_mm"),
                internal_width_mm=data.get("internal_width_mm"),
                internal_diameter_mm=data.get("internal_diameter_mm"),
                has_graduation_marks=data.get("has_graduation_marks", False),
            )
            self._container_types[container_id] = container
    
    # =========================================================================
    # CONTAINER LIBRARY OPERATIONS
    # =========================================================================
    
    def get_container_types(
        self,
        manufacturer: Optional[str] = None,
        model_family: Optional[str] = None,
    ) -> list[ContainerTypeOut]:
        """Get container types from library."""
        containers = list(self._container_types.values())
        
        if manufacturer:
            containers = [c for c in containers if c.manufacturer.lower() == manufacturer.lower()]
        if model_family:
            containers = [c for c in containers if c.model_family.lower() == model_family.lower()]
        
        return sorted(containers, key=lambda c: (c.manufacturer, c.nominal_volume_ml))
    
    def get_container_type(self, container_id: uuid.UUID) -> Optional[ContainerTypeOut]:
        """Get a specific container type."""
        return self._container_types.get(container_id)
    
    def add_container_type(self, data: ContainerTypeCreate) -> ContainerTypeOut:
        """Add a new container type to library."""
        container_id = uuid.uuid4()
        container = ContainerTypeOut(
            id=container_id,
            **data.model_dump()
        )
        self._container_types[container_id] = container
        return container
    
    def find_container_by_volume(
        self,
        volume_ml: int,
        tolerance_pct: Decimal = Decimal("10"),
    ) -> list[ContainerTypeOut]:
        """Find containers matching approximate volume."""
        min_vol = int(volume_ml * (1 - float(tolerance_pct) / 100))
        max_vol = int(volume_ml * (1 + float(tolerance_pct) / 100))
        
        return [
            c for c in self._container_types.values()
            if min_vol <= c.nominal_volume_ml <= max_vol
        ]
    
    # =========================================================================
    # DENSITY PROFILE OPERATIONS
    # =========================================================================
    
    def register_density_profile(self, data: DensityProfileCreate) -> DensityProfileOut:
        """Register a density profile for a product."""
        profile_id = uuid.uuid4()
        profile = DensityProfileOut(
            id=profile_id,
            product_id=data.product_id,
            density_g_per_ml=data.density_g_per_ml,
            variance_pct=data.variance_pct,
            source_type=data.source_type,
            source_note=data.source_note,
        )
        self._density_profiles[profile_id] = profile
        return profile
    
    def get_density_profile(self, product_id: uuid.UUID) -> Optional[DensityProfileOut]:
        """Get density profile for a product."""
        for profile in self._density_profiles.values():
            if profile.product_id == product_id:
                return profile
        return None
    
    # =========================================================================
    # CONFIDENCE CALCULATIONS
    # =========================================================================
    
    def calculate_volume_from_fill(
        self,
        container: ContainerTypeOut,
        fill_ratio: Decimal,
    ) -> int:
        """Calculate volume from container + fill ratio."""
        # For containers with geometry, can be more accurate
        if container.shape == ContainerShape.CYLINDER and container.internal_height_mm and container.internal_diameter_mm:
            # V = π * r² * h * fill_ratio
            import math
            r = container.internal_diameter_mm / 2
            h = container.internal_height_mm * float(fill_ratio)
            volume_mm3 = math.pi * (r ** 2) * h
            return int(volume_mm3 / 1000)  # Convert to ml
        
        elif container.shape == ContainerShape.RECT_PRISM and container.internal_height_mm:
            if container.internal_length_mm and container.internal_width_mm:
                h = container.internal_height_mm * float(fill_ratio)
                volume_mm3 = container.internal_length_mm * container.internal_width_mm * h
                return int(volume_mm3 / 1000)
        
        # Fallback: use nominal volume × fill ratio
        return int(container.nominal_volume_ml * float(fill_ratio))
    
    def calculate_confidence(
        self,
        components: ConfidenceComponents,
    ) -> dict:
        """
        Calculate combined confidences using conservative rules.
        """
        c_volume = components.compute_volume_confidence()
        c_identity = components.compute_identity_confidence()
        c_mass = components.compute_mass_confidence()
        
        return {
            "volume_confidence": c_volume,
            "identity_confidence": c_identity,
            "mass_confidence": c_mass,
            "can_compute_volume": components.container_conf >= Decimal("0.70"),
            "can_convert_to_mass": c_identity >= Decimal("0.70") and components.density_conf >= Decimal("0.80"),
        }
    
    # =========================================================================
    # VISION ESTIMATION (OBSERVATION-ONLY)
    # =========================================================================
    
    def process_vision_estimate(
        self,
        request: VisionEstimateRequest,
        # Simulated vision outputs (would come from actual vision model)
        detected_container_id: Optional[uuid.UUID] = None,
        container_conf: Decimal = Decimal("0"),
        fill_ratio: Optional[Decimal] = None,
        fill_conf: Decimal = Decimal("0"),
        ocr_text: Optional[str] = None,
        ocr_conf: Decimal = Decimal("0"),
        item_hint: Optional[str] = None,
        item_hint_conf: Decimal = Decimal("0"),
    ) -> VisionEstimateResponse:
        """
        Process a vision estimate request.
        
        IMPORTANT: This produces OBSERVATIONS only.
        It does NOT make decisions.
        """
        observation = VisionObservationOut(
            id=uuid.uuid4(),
            image_asset_key=request.image_asset_key,
            captured_at=datetime.utcnow(),
            detected_container_type_id=detected_container_id,
            container_conf=container_conf,
            fill_ratio=fill_ratio,
            fill_conf=fill_conf,
            ocr_text=ocr_text,
            ocr_conf=ocr_conf,
            parsed_item_hint=item_hint,
            item_hint_conf=item_hint_conf,
        )
        
        self._observations.append(observation)
        
        # Determine next step
        warnings = []
        estimated_volume = None
        volume_confidence = None
        
        # Gate 1: Container identification
        if container_conf < Decimal("0.70"):
            next_step = VisionNextStep.SELECT_CONTAINER
            warnings.append("Container not confidently identified. Please select from list.")
        
        # Gate 2: Fill ratio visibility
        elif fill_conf < Decimal("0.50"):
            next_step = VisionNextStep.RETAKE_PHOTO
            warnings.append("Fill level not visible. Please retake photo with contents visible.")
        
        # Gate 3: Item identification for mass conversion
        elif item_hint_conf < Decimal("0.70"):
            # Can compute volume but not mass
            container = self._container_types.get(detected_container_id)
            if container and fill_ratio is not None:
                estimated_volume = self.calculate_volume_from_fill(container, fill_ratio)
                volume_confidence = (
                    Decimal("0.45") * container_conf +
                    Decimal("0.55") * fill_conf
                ).quantize(Decimal("0.01"))
            
            next_step = VisionNextStep.CONFIRM_ITEM
            warnings.append("Item not identified from label. Please confirm or select product.")
        
        # All gates passed
        else:
            container = self._container_types.get(detected_container_id)
            if container and fill_ratio is not None:
                estimated_volume = self.calculate_volume_from_fill(container, fill_ratio)
                volume_confidence = (
                    Decimal("0.45") * container_conf +
                    Decimal("0.55") * fill_conf
                ).quantize(Decimal("0.01"))
            
            # Check if confidence warrants acceptance or weigh
            combined_conf = min(container_conf, fill_conf, item_hint_conf)
            bucket = get_confidence_bucket(combined_conf)
            
            if bucket == ConfidenceBucket.AUTO_USE:
                next_step = VisionNextStep.ACCEPT_VOLUME
            elif bucket in (ConfidenceBucket.USABLE_PROMPT, ConfidenceBucket.PROVISIONAL):
                next_step = VisionNextStep.ACCEPT_VOLUME
                warnings.append(f"Confidence {combined_conf}: Consider weighing for high-value items.")
            else:
                next_step = VisionNextStep.WEIGH_REQUIRED
                warnings.append(f"Confidence {combined_conf} too low. Weigh-in required.")
        
        return VisionEstimateResponse(
            vision_observation=observation,
            recommended_next_step=next_step,
            estimated_volume_ml=estimated_volume,
            volume_confidence=volume_confidence,
            warnings=warnings,
        )
    
    # =========================================================================
    # EFFECTIVE ON-HAND CALCULATION
    # =========================================================================
    
    def calculate_effective_on_hand(
        self,
        normalized_qty: Decimal,
        confidence: Decimal,
    ) -> EffectiveOnHand:
        """
        Calculate effective on-hand for stockout prediction.
        
        When confidence < 1.0, treat inventory as distribution.
        EOH = normalized_qty * (0.50 + 0.50*confidence)
        """
        return EffectiveOnHand.calculate(normalized_qty, confidence)
    
    # =========================================================================
    # FORCE WEIGH DECISION
    # =========================================================================
    
    def should_force_weigh(
        self,
        product_id: uuid.UUID,
        current_confidence: Decimal,
        force_weigh_threshold: Decimal = Decimal("0.650"),
        is_high_value: bool = False,
        is_regulated: bool = False,
        is_stockout_critical: bool = False,
        has_shrinkage_flag: bool = False,
    ) -> Optional[ForceWeighRequest]:
        """
        Determine if a force-weigh is required.
        
        Returns ForceWeighRequest if weigh-in needed, None otherwise.
        """
        reason = None
        reason_detail = None
        priority = "normal"
        
        # Check triggers in priority order
        if is_regulated:
            reason = ForceWeighReason.REGULATED_ITEM
            reason_detail = "Regulated item requires accurate measurement"
            priority = "high"
        
        elif has_shrinkage_flag:
            reason = ForceWeighReason.SHRINKAGE_ESCALATION
            reason_detail = "Shrinkage flag + low confidence requires verification"
            priority = "high"
        
        elif is_stockout_critical and current_confidence < Decimal("0.80"):
            reason = ForceWeighReason.STOCKOUT_CRITICAL
            reason_detail = "Stockout projection depends on this measurement"
            priority = "critical"
        
        elif is_high_value and current_confidence < Decimal("0.85"):
            reason = ForceWeighReason.HIGH_VALUE_ITEM
            reason_detail = "High-value item with moderate uncertainty"
            priority = "normal"
        
        elif current_confidence < force_weigh_threshold:
            reason = ForceWeighReason.LOW_CONFIDENCE
            reason_detail = f"Confidence {current_confidence} below threshold {force_weigh_threshold}"
            priority = "normal"
        
        if reason:
            return ForceWeighRequest(
                product_id=product_id,
                product_name="",  # Would be filled from product lookup
                location_id=uuid.uuid4(),  # Would be filled from context
                reason=reason,
                reason_detail=reason_detail,
                current_confidence=current_confidence,
                threshold_confidence=force_weigh_threshold,
                priority=priority,
            )
        
        return None
    
    # =========================================================================
    # VOLUME TO MASS CONVERSION
    # =========================================================================
    
    def convert_volume_to_mass(
        self,
        volume_ml: int,
        density_profile: DensityProfileOut,
    ) -> tuple[int, Decimal]:
        """
        Convert volume to mass using density profile.
        
        Returns (mass_grams, confidence_adjustment)
        """
        mass_g = int(volume_ml * float(density_profile.density_g_per_ml))
        
        # Confidence adjustment based on variance
        conf_adj = max(
            Decimal("0.80"),
            Decimal("1") - density_profile.variance_pct
        )
        
        return mass_g, conf_adj
    
    def clear_data(self) -> None:
        """Clear all data except container library."""
        self._density_profiles.clear()
        self._observations.clear()


# Singleton instance
vision_engine = VisionEstimationEngine()

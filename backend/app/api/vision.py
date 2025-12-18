"""
PROVENIQ Ops - Vision Estimation API Routes
Bishop bulk inventory vision pipeline endpoints

RULES:
- Vision is UPSTREAM-ONLY: produces observations with confidence, never actions
- Hard gates enforce: no identity → no mass, no container → no volume
- Human-in-the-loop confirmation at every critical step

UX FLOWS:
- Flow A: Count Containers (fast)
- Flow B: Weigh Net (accurate)
- Flow C: Photo Estimate (vision)
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Query

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
    ForceWeighRequest,
    MeasurementMethodCode,
    VisionEstimateRequest,
    VisionEstimateResponse,
    VisionNextStep,
    get_confidence_bucket,
    CONFIDENCE_BUCKET_BEHAVIORS,
)
from app.services.bishop.vision_engine import vision_engine, COMMON_DENSITIES

router = APIRouter(prefix="/vision", tags=["Vision Estimation"])


# =============================================================================
# VISION ESTIMATION
# =============================================================================

@router.post("/estimate", response_model=VisionEstimateResponse)
async def estimate_from_image(
    org_id: uuid.UUID,
    image_asset_key: str,
    location_id: Optional[uuid.UUID] = None,
    hint_product_id: Optional[uuid.UUID] = None,
    # Simulated vision outputs (would come from actual vision model)
    detected_container_id: Optional[uuid.UUID] = None,
    container_conf: Decimal = Decimal("0.85"),
    fill_ratio: Optional[Decimal] = Decimal("0.65"),
    fill_conf: Decimal = Decimal("0.80"),
    ocr_text: Optional[str] = None,
    ocr_conf: Decimal = Decimal("0.75"),
    item_hint: Optional[str] = None,
    item_hint_conf: Decimal = Decimal("0.70"),
) -> VisionEstimateResponse:
    """
    Process a vision estimate from an image.
    
    IMPORTANT: Vision is UPSTREAM-ONLY.
    - Produces observations with confidence scores
    - NEVER makes decisions about ordering, waste, or blame
    
    Hard Gates:
    - No container identity → SELECT_CONTAINER
    - No fill visibility → RETAKE_PHOTO
    - No item identity → CONFIRM_ITEM (volume-only)
    - Low confidence → WEIGH_REQUIRED
    """
    request = VisionEstimateRequest(
        org_id=org_id,
        location_id=location_id,
        image_asset_key=image_asset_key,
        hint_product_id=hint_product_id,
    )
    
    return vision_engine.process_vision_estimate(
        request=request,
        detected_container_id=detected_container_id,
        container_conf=container_conf,
        fill_ratio=fill_ratio,
        fill_conf=fill_conf,
        ocr_text=ocr_text,
        ocr_conf=ocr_conf,
        item_hint=item_hint,
        item_hint_conf=item_hint_conf,
    )


# =============================================================================
# CONTAINER LIBRARY
# =============================================================================

@router.get("/containers", response_model=list[ContainerTypeOut])
async def get_container_types(
    manufacturer: Optional[str] = None,
    model_family: Optional[str] = None,
) -> list[ContainerTypeOut]:
    """
    Get container types from reference library.
    
    Includes Cambro, Vollrath, hotel pans, etc.
    """
    return vision_engine.get_container_types(
        manufacturer=manufacturer,
        model_family=model_family,
    )


@router.get("/containers/{container_id}", response_model=ContainerTypeOut)
async def get_container_type(container_id: uuid.UUID) -> dict:
    """Get a specific container type."""
    container = vision_engine.get_container_type(container_id)
    if not container:
        return {"error": "Container type not found"}
    return container.model_dump()


@router.get("/containers/search/volume")
async def find_containers_by_volume(
    volume_ml: int,
    tolerance_pct: Decimal = Decimal("10"),
) -> dict:
    """Find containers matching approximate volume."""
    containers = vision_engine.find_container_by_volume(volume_ml, tolerance_pct)
    return {
        "search_volume_ml": volume_ml,
        "tolerance_pct": str(tolerance_pct),
        "matches": len(containers),
        "containers": [c.model_dump() for c in containers],
    }


@router.post("/containers", response_model=ContainerTypeOut)
async def add_container_type(
    manufacturer: str,
    model_family: str,
    display_name: str,
    shape: ContainerShape,
    nominal_volume_ml: int,
    internal_height_mm: Optional[int] = None,
    internal_length_mm: Optional[int] = None,
    internal_width_mm: Optional[int] = None,
    internal_diameter_mm: Optional[int] = None,
    has_graduation_marks: bool = False,
) -> ContainerTypeOut:
    """Add a new container type to the library."""
    data = ContainerTypeCreate(
        manufacturer=manufacturer,
        model_family=model_family,
        display_name=display_name,
        shape=shape,
        nominal_volume_ml=nominal_volume_ml,
        internal_height_mm=internal_height_mm,
        internal_length_mm=internal_length_mm,
        internal_width_mm=internal_width_mm,
        internal_diameter_mm=internal_diameter_mm,
        has_graduation_marks=has_graduation_marks,
    )
    return vision_engine.add_container_type(data)


# =============================================================================
# DENSITY PROFILES
# =============================================================================

@router.post("/density")
async def register_density_profile(
    product_id: uuid.UUID,
    density_g_per_ml: Decimal,
    source_type: DensitySourceType,
    variance_pct: Decimal = Decimal("0.03"),
    source_note: Optional[str] = None,
) -> dict:
    """
    Register a density profile for volume→mass conversion.
    
    Required for converting vision-estimated volume to weight.
    """
    data = DensityProfileCreate(
        product_id=product_id,
        density_g_per_ml=density_g_per_ml,
        variance_pct=variance_pct,
        source_type=source_type,
        source_note=source_note,
    )
    profile = vision_engine.register_density_profile(data)
    return profile.model_dump()


@router.get("/density/{product_id}")
async def get_density_profile(product_id: uuid.UUID) -> dict:
    """Get density profile for a product."""
    profile = vision_engine.get_density_profile(product_id)
    if not profile:
        return {"error": "No density profile for product", "product_id": str(product_id)}
    return profile.model_dump()


@router.get("/density/common")
async def get_common_densities() -> dict:
    """Get common ingredient densities from USDA database."""
    return {
        "count": len(COMMON_DENSITIES),
        "note": "Use these as reference when creating density profiles",
        "densities": {
            name: {
                "density_g_per_ml": str(data["density_g_per_ml"]),
                "source": data["source"],
                "variance_pct": str(data["variance"]),
            }
            for name, data in COMMON_DENSITIES.items()
        },
    }


# =============================================================================
# CONFIDENCE CALCULATIONS
# =============================================================================

@router.post("/confidence/calculate")
async def calculate_confidence(
    container_conf: Decimal,
    fill_conf: Decimal,
    ocr_conf: Decimal = Decimal("0"),
    item_hint_conf: Decimal = Decimal("0"),
    density_conf: Decimal = Decimal("1"),
) -> dict:
    """
    Calculate combined confidences using conservative rules.
    
    Formulas:
    - C_volume = 0.45*C_container + 0.55*C_fill
    - C_identity = 0.60*C_ocr + 0.40*C_item
    - C_mass = min(C_volume, C_identity, C_density)
    """
    components = ConfidenceComponents(
        container_conf=container_conf,
        fill_conf=fill_conf,
        ocr_conf=ocr_conf,
        item_hint_conf=item_hint_conf,
        density_conf=density_conf,
    )
    
    result = vision_engine.calculate_confidence(components)
    
    # Add bucket classification
    volume_bucket = get_confidence_bucket(result["volume_confidence"])
    mass_bucket = get_confidence_bucket(result["mass_confidence"]) if result["can_convert_to_mass"] else None
    
    return {
        "components": {
            "container": str(container_conf),
            "fill": str(fill_conf),
            "ocr": str(ocr_conf),
            "item_hint": str(item_hint_conf),
            "density": str(density_conf),
        },
        "computed": {
            "volume_confidence": str(result["volume_confidence"]),
            "identity_confidence": str(result["identity_confidence"]),
            "mass_confidence": str(result["mass_confidence"]),
        },
        "gates": {
            "can_compute_volume": result["can_compute_volume"],
            "can_convert_to_mass": result["can_convert_to_mass"],
        },
        "volume_bucket": volume_bucket.value if volume_bucket else None,
        "volume_behavior": CONFIDENCE_BUCKET_BEHAVIORS.get(volume_bucket) if volume_bucket else None,
        "mass_bucket": mass_bucket.value if mass_bucket else None,
    }


@router.get("/confidence/buckets")
async def get_confidence_buckets() -> dict:
    """Get confidence bucket definitions and behaviors."""
    return {
        "buckets": [
            {
                "bucket": bucket.value,
                "range": ">= 0.85" if bucket == ConfidenceBucket.AUTO_USE else
                         "0.70-0.84" if bucket == ConfidenceBucket.USABLE_PROMPT else
                         "0.60-0.69" if bucket == ConfidenceBucket.PROVISIONAL else
                         "< 0.60",
                "behavior": behavior,
            }
            for bucket, behavior in CONFIDENCE_BUCKET_BEHAVIORS.items()
        ],
    }


# =============================================================================
# EFFECTIVE ON-HAND
# =============================================================================

@router.post("/effective-on-hand")
async def calculate_effective_on_hand(
    normalized_qty: Decimal,
    confidence: Decimal,
) -> dict:
    """
    Calculate effective on-hand for stockout prediction.
    
    When confidence < 1.0, treat inventory as distribution:
    EOH = normalized_qty * (0.50 + 0.50*confidence)
    
    Examples:
    - confidence 1.0 → EOH = 100% of qty
    - confidence 0.6 → EOH = 80% of qty
    - confidence 0.4 → EOH = 70% of qty
    """
    eoh = vision_engine.calculate_effective_on_hand(normalized_qty, confidence)
    
    return {
        "normalized_qty": str(eoh.normalized_qty),
        "confidence": str(eoh.confidence),
        "effective_qty": str(eoh.effective_qty),
        "uncertainty_buffer": str(eoh.uncertainty_buffer),
        "formula": "EOH = qty * (0.50 + 0.50*confidence)",
        "note": "Use effective_qty for stockout predictions when confidence < 0.85",
    }


# =============================================================================
# FORCE WEIGH
# =============================================================================

@router.post("/force-weigh/check")
async def check_force_weigh(
    product_id: uuid.UUID,
    current_confidence: Decimal,
    force_weigh_threshold: Decimal = Decimal("0.650"),
    is_high_value: bool = False,
    is_regulated: bool = False,
    is_stockout_critical: bool = False,
    has_shrinkage_flag: bool = False,
) -> dict:
    """
    Check if a force-weigh is required.
    
    Triggers:
    - Confidence below threshold
    - High-value item with moderate uncertainty
    - Stockout projection depends on this measurement
    - Regulated categories (alcohol, controlled goods)
    - Shrinkage escalation
    """
    request = vision_engine.should_force_weigh(
        product_id=product_id,
        current_confidence=current_confidence,
        force_weigh_threshold=force_weigh_threshold,
        is_high_value=is_high_value,
        is_regulated=is_regulated,
        is_stockout_critical=is_stockout_critical,
        has_shrinkage_flag=has_shrinkage_flag,
    )
    
    if request:
        return {
            "force_weigh_required": True,
            "request": request.model_dump(),
        }
    
    return {
        "force_weigh_required": False,
        "current_confidence": str(current_confidence),
        "threshold": str(force_weigh_threshold),
    }


# =============================================================================
# VOLUME TO MASS CONVERSION
# =============================================================================

@router.post("/convert/volume-to-mass")
async def convert_volume_to_mass(
    product_id: uuid.UUID,
    volume_ml: int,
) -> dict:
    """
    Convert volume to mass using density profile.
    
    REQUIRES verified density profile for the product.
    """
    profile = vision_engine.get_density_profile(product_id)
    if not profile:
        return {
            "error": "No density profile",
            "message": "Cannot convert volume to mass without verified density profile",
            "product_id": str(product_id),
        }
    
    mass_g, conf_adj = vision_engine.convert_volume_to_mass(volume_ml, profile)
    
    return {
        "volume_ml": volume_ml,
        "mass_g": mass_g,
        "mass_kg": round(mass_g / 1000, 3),
        "density_g_per_ml": str(profile.density_g_per_ml),
        "confidence_adjustment": str(conf_adj),
        "variance_pct": str(profile.variance_pct),
        "source_type": profile.source_type.value,
    }


# =============================================================================
# DEMO
# =============================================================================

@router.post("/demo/setup")
async def setup_demo() -> dict:
    """
    Set up demo data for vision estimation testing.
    """
    vision_engine.clear_data()
    
    # Get some container IDs for demo
    containers = vision_engine.get_container_types()
    cambro_12qt = next((c for c in containers if "12 qt" in c.display_name and "CamSquare" in c.model_family), None)
    hotel_pan_4in = next((c for c in containers if "Full size hotel pan 4 in" in c.display_name), None)
    
    # Register some density profiles
    flour_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    oil_id = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    
    flour_profile = vision_engine.register_density_profile(DensityProfileCreate(
        product_id=flour_id,
        density_g_per_ml=Decimal("0.593"),
        variance_pct=Decimal("0.05"),
        source_type=DensitySourceType.USDA,
        source_note="All-purpose flour, sifted",
    ))
    
    oil_profile = vision_engine.register_density_profile(DensityProfileCreate(
        product_id=oil_id,
        density_g_per_ml=Decimal("0.918"),
        variance_pct=Decimal("0.01"),
        source_type=DensitySourceType.USDA,
        source_note="Olive oil, extra virgin",
    ))
    
    return {
        "status": "demo_data_created",
        "container_library": {
            "total_containers": len(containers),
            "sample_cambro_12qt": cambro_12qt.model_dump() if cambro_12qt else None,
            "sample_hotel_pan": hotel_pan_4in.model_dump() if hotel_pan_4in else None,
        },
        "density_profiles": {
            "flour": flour_profile.model_dump(),
            "olive_oil": oil_profile.model_dump(),
        },
        "test_scenarios": [
            {
                "name": "High confidence vision estimate",
                "endpoint": "POST /vision/estimate",
                "params": {
                    "container_conf": "0.92",
                    "fill_conf": "0.88",
                    "ocr_conf": "0.85",
                    "item_hint_conf": "0.80",
                },
                "expected": "ACCEPT_VOLUME",
            },
            {
                "name": "Low confidence - force weigh",
                "endpoint": "POST /vision/estimate",
                "params": {
                    "container_conf": "0.55",
                    "fill_conf": "0.50",
                },
                "expected": "SELECT_CONTAINER (confidence too low)",
            },
            {
                "name": "Volume to mass conversion",
                "endpoint": "POST /vision/convert/volume-to-mass",
                "params": {
                    "product_id": str(flour_id),
                    "volume_ml": "5000",
                },
                "expected": "~2965g flour",
            },
        ],
    }


@router.delete("/data/clear")
async def clear_data() -> dict:
    """Clear vision estimation data (keeps container library)."""
    vision_engine.clear_data()
    return {"status": "cleared", "note": "Container library preserved"}

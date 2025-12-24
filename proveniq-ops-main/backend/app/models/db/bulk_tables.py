"""
PROVENIQ Ops - Bulk Inventory Database Models
SQLAlchemy models for bulk inventory, vision estimation, and container management.

Tables:
- bulk_item_configs: Per-item rules for bulk measurement
- density_profiles: Volume->mass conversion data
- container_types: Reference library (Cambro, Lexan, hotel pans)
- container_instances: Physical containers with QR/tare
- vision_observations: Raw vision outputs
- inventory_measurements: Authoritative quantities
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.db.base import Base


class BulkItemConfig(Base):
    """
    Per-item configuration for bulk inventory handling.
    Defines base UoM, preferred methods, thresholds.
    """
    __tablename__ = "bulk_item_configs"
    
    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = sa.Column(UUID(as_uuid=True), nullable=False, index=True)
    product_id = sa.Column(UUID(as_uuid=True), nullable=False, unique=True, index=True)
    
    # Unit strategy
    base_uom = sa.Column(sa.Text, nullable=False)  # 'g', 'ml', 'each'
    handling_uom = sa.Column(sa.Text, nullable=False)  # 'bag', 'cambro', 'hotel_pan', 'case'
    
    # Measurement preferences
    preferred_methods = sa.Column(sa.ARRAY(sa.Text), nullable=False)  # ['WEIGH_NET', 'VOLUME_GEOM']
    
    # Density requirements
    require_density_for_mass = sa.Column(sa.Boolean, nullable=False, default=True)
    default_density_profile_id = sa.Column(UUID(as_uuid=True), sa.ForeignKey("density_profiles.id"), nullable=True)
    
    # Container defaults
    default_container_type_id = sa.Column(UUID(as_uuid=True), sa.ForeignKey("container_types.id"), nullable=True)
    default_container_tare_g = sa.Column(sa.Integer, nullable=True)
    
    # Partial handling
    partial_allowed = sa.Column(sa.Boolean, nullable=False, default=True)
    partial_entry_mode = sa.Column(sa.Text, nullable=False, default='RATIO')  # 'RATIO', 'WEIGH', 'VOLUME'
    
    # Confidence thresholds
    min_confidence_to_autouse = sa.Column(sa.Numeric(4, 3), nullable=False, default=Decimal("0.700"))
    min_confidence_to_convert_mass = sa.Column(sa.Numeric(4, 3), nullable=False, default=Decimal("0.800"))
    force_weigh_below_confidence = sa.Column(sa.Numeric(4, 3), nullable=False, default=Decimal("0.650"))
    
    # Timestamps
    updated_at = sa.Column(sa.DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = sa.Column(sa.DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    
    # Relationships
    default_density_profile = relationship("DensityProfile", foreign_keys=[default_density_profile_id])
    default_container_type = relationship("ContainerType", foreign_keys=[default_container_type_id])


class DensityProfile(Base):
    """
    Verified volume->mass conversion data per ingredient/SKU.
    Required for converting vision-estimated volume to weight.
    """
    __tablename__ = "density_profiles"
    
    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = sa.Column(UUID(as_uuid=True), nullable=False, index=True)
    product_id = sa.Column(UUID(as_uuid=True), nullable=False, index=True)
    
    # Density data
    density_g_per_ml = sa.Column(sa.Numeric(10, 6), nullable=False)
    variance_pct = sa.Column(sa.Numeric(6, 3), nullable=False, default=Decimal("0.000"))  # e.g., 0.030 = 3%
    
    # Source tracking
    source_type = sa.Column(sa.Text, nullable=False)  # 'MANUFACTURER', 'USDA', 'CALIBRATED_WEIGH', 'OTHER'
    source_note = sa.Column(sa.Text, nullable=True)
    
    # Validity period
    valid_from = sa.Column(sa.Date, nullable=True)
    valid_to = sa.Column(sa.Date, nullable=True)
    
    # Timestamps
    created_at = sa.Column(sa.DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class ContainerType(Base):
    """
    Reference library of container types.
    Cambro, Vollrath Lexan, hotel pans, etc.
    """
    __tablename__ = "container_types"
    
    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Identification
    manufacturer = sa.Column(sa.Text, nullable=False)  # 'Cambro', 'Vollrath', etc.
    model_family = sa.Column(sa.Text, nullable=False)  # 'CamSquare', 'CamRound', 'Lexan', 'HotelPan'
    display_name = sa.Column(sa.Text, nullable=False)  # 'Cambro CamSquare 12 qt'
    
    # Geometry
    shape = sa.Column(sa.Text, nullable=False)  # 'RECT_PRISM', 'CYLINDER', 'HOTEL_PAN', 'OTHER'
    nominal_volume_ml = sa.Column(sa.Integer, nullable=False)
    
    # Internal dimensions (for fill ratio -> volume accuracy)
    internal_height_mm = sa.Column(sa.Integer, nullable=True)
    internal_length_mm = sa.Column(sa.Integer, nullable=True)
    internal_width_mm = sa.Column(sa.Integer, nullable=True)
    internal_diameter_mm = sa.Column(sa.Integer, nullable=True)
    
    # Features
    has_graduation_marks = sa.Column(sa.Boolean, nullable=False, default=False)
    image_ref = sa.Column(sa.Text, nullable=True)  # Asset key for UI
    
    # Timestamps
    created_at = sa.Column(sa.DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class ContainerInstance(Base):
    """
    Physical container instances (QR/NFC labeled).
    Optional but powerful for accurate tare tracking.
    """
    __tablename__ = "container_instances"
    
    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = sa.Column(UUID(as_uuid=True), nullable=False, index=True)
    
    # Type reference
    container_type_id = sa.Column(UUID(as_uuid=True), sa.ForeignKey("container_types.id"), nullable=False)
    
    # Instance data
    label_code = sa.Column(sa.Text, nullable=True)  # QR/NFC id
    tare_g = sa.Column(sa.Integer, nullable=True)
    notes = sa.Column(sa.Text, nullable=True)
    
    # Status
    active = sa.Column(sa.Boolean, nullable=False, default=True)
    
    # Timestamps
    created_at = sa.Column(sa.DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    
    # Relationships
    container_type = relationship("ContainerType")


class VisionObservation(Base):
    """
    Raw vision outputs (OCR, container class, fill ratio).
    Observation-only - does NOT make decisions.
    """
    __tablename__ = "vision_observations"
    
    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = sa.Column(UUID(as_uuid=True), nullable=False, index=True)
    location_id = sa.Column(UUID(as_uuid=True), nullable=True, index=True)
    
    # Image reference
    image_asset_key = sa.Column(sa.Text, nullable=False)
    captured_at = sa.Column(sa.DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    
    # Container detection
    detected_container_type_id = sa.Column(UUID(as_uuid=True), sa.ForeignKey("container_types.id"), nullable=True)
    container_conf = sa.Column(sa.Numeric(4, 3), nullable=False, default=Decimal("0.000"))
    
    # Fill estimation
    fill_ratio = sa.Column(sa.Numeric(6, 4), nullable=True)  # 0..1
    fill_conf = sa.Column(sa.Numeric(4, 3), nullable=False, default=Decimal("0.000"))
    
    # OCR extraction
    ocr_text = sa.Column(sa.Text, nullable=True)
    ocr_conf = sa.Column(sa.Numeric(4, 3), nullable=False, default=Decimal("0.000"))
    
    # Item identification
    parsed_item_hint = sa.Column(sa.Text, nullable=True)
    item_hint_conf = sa.Column(sa.Numeric(4, 3), nullable=False, default=Decimal("0.000"))
    
    # Additional data
    notes = sa.Column(JSONB, nullable=False, default=dict)
    
    # Timestamps
    created_at = sa.Column(sa.DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    
    # Relationships
    detected_container_type = relationship("ContainerType")


class InventoryMeasurement(Base):
    """
    Authoritative inventory quantities.
    The source of truth after normalization.
    """
    __tablename__ = "inventory_measurements"
    
    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = sa.Column(UUID(as_uuid=True), nullable=False, index=True)
    location_id = sa.Column(UUID(as_uuid=True), nullable=False, index=True)
    product_id = sa.Column(UUID(as_uuid=True), nullable=False, index=True)
    
    # Timing
    measured_at = sa.Column(sa.DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    
    # Method
    method_code = sa.Column(sa.Text, nullable=False)  # 'COUNT_STD', 'WEIGH_NET', etc.
    
    # Raw observation
    observed_value = sa.Column(sa.Numeric(14, 4), nullable=False)  # e.g., 3.5 bags, 6.96 qt
    observed_uom = sa.Column(sa.Text, nullable=False)  # 'bag', 'qt', 'lb_gross', 'ml', 'ratio'
    
    # Normalized result
    normalized_qty = sa.Column(sa.Numeric(18, 6), nullable=False)  # in base units
    base_uom = sa.Column(sa.Text, nullable=False)  # 'g', 'ml', 'each'
    
    # Confidence
    confidence = sa.Column(sa.Numeric(4, 3), nullable=False)
    
    # References
    density_profile_id = sa.Column(UUID(as_uuid=True), sa.ForeignKey("density_profiles.id"), nullable=True)
    container_instance_id = sa.Column(UUID(as_uuid=True), sa.ForeignKey("container_instances.id"), nullable=True)
    vision_observation_id = sa.Column(UUID(as_uuid=True), sa.ForeignKey("vision_observations.id"), nullable=True)
    decision_trace_id = sa.Column(UUID(as_uuid=True), nullable=True)
    
    # Audit
    created_by_user_id = sa.Column(UUID(as_uuid=True), nullable=True)
    created_at = sa.Column(sa.DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    
    # Relationships
    density_profile = relationship("DensityProfile")
    container_instance = relationship("ContainerInstance")
    vision_observation = relationship("VisionObservation")

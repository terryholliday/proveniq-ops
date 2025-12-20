"""BISHOP Module - SQLAlchemy Models

Back-of-House Inventory System for Hospitality Operations Protocol
"""
import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import String, DateTime, ForeignKey, Enum as SQLEnum, Text, Float, Integer, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class BishopLocationType(str, Enum):
    """Type of BISHOP-enabled location."""
    RESTAURANT = "RESTAURANT"
    RETAIL = "RETAIL"
    WAREHOUSE = "WAREHOUSE"
    KITCHEN = "KITCHEN"


class BishopScanStatus(str, Enum):
    """Status of a shelf scan operation."""
    IDLE = "IDLE"
    SCANNING = "SCANNING"
    ANALYZING_RISK = "ANALYZING_RISK"
    CHECKING_FUNDS = "CHECKING_FUNDS"
    ORDER_QUEUED = "ORDER_QUEUED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ShrinkageType(str, Enum):
    """Classification of shrinkage/loss."""
    THEFT = "THEFT"
    SPOILAGE = "SPOILAGE"
    DAMAGE = "DAMAGE"
    ADMIN_ERROR = "ADMIN_ERROR"
    VENDOR_ERROR = "VENDOR_ERROR"
    UNKNOWN = "UNKNOWN"


class BishopLocation(Base):
    """A BISHOP-enabled location (restaurant, retail store, warehouse)."""

    __tablename__ = "bishop_locations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    location_type: Mapped[BishopLocationType] = mapped_column(
        SQLEnum(BishopLocationType),
        default=BishopLocationType.RESTAURANT,
        nullable=False,
    )
    address: Mapped[str] = mapped_column(String(500), nullable=True)
    city: Mapped[str] = mapped_column(String(100), nullable=True)
    state: Mapped[str] = mapped_column(String(50), nullable=True)
    zip_code: Mapped[str] = mapped_column(String(20), nullable=True)
    
    # Vendor integration settings
    vendor_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=True, default=dict)
    
    # Budget/threshold settings
    daily_order_limit: Mapped[float] = mapped_column(Float, nullable=True)
    auto_order_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    owner: Mapped["User"] = relationship("User", back_populates="bishop_locations")
    shelves: Mapped[list["BishopShelf"]] = relationship("BishopShelf", back_populates="location", cascade="all, delete-orphan")
    scans: Mapped[list["BishopScan"]] = relationship("BishopScan", back_populates="location", cascade="all, delete-orphan")
    shrinkage_events: Mapped[list["ShrinkageEvent"]] = relationship("ShrinkageEvent", back_populates="location", cascade="all, delete-orphan")


class BishopShelf(Base):
    """A shelf/storage area within a BISHOP location."""

    __tablename__ = "bishop_shelves"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bishop_locations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    shelf_code: Mapped[str] = mapped_column(String(50), nullable=True)  # QR/barcode identifier
    zone: Mapped[str] = mapped_column(String(100), nullable=True)  # e.g., "Walk-in Cooler", "Dry Storage"
    
    # Expected inventory for this shelf (JSONB of SKU -> expected quantity)
    expected_inventory: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=True, default=dict)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    location: Mapped["BishopLocation"] = relationship("BishopLocation", back_populates="shelves")
    items: Mapped[list["BishopItem"]] = relationship("BishopItem", back_populates="shelf", cascade="all, delete-orphan")


class BishopItem(Base):
    """An inventory item tracked by BISHOP."""

    __tablename__ = "bishop_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    shelf_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bishop_shelves.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sku: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    
    # Quantity tracking
    quantity_on_hand: Mapped[int] = mapped_column(Integer, default=0)
    quantity_unit: Mapped[str] = mapped_column(String(50), nullable=True)  # "cases", "lbs", "each"
    par_level: Mapped[int] = mapped_column(Integer, nullable=True)  # Minimum stock level
    reorder_point: Mapped[int] = mapped_column(Integer, nullable=True)
    
    # Vendor info
    vendor_sku: Mapped[str] = mapped_column(String(100), nullable=True)
    vendor_name: Mapped[str] = mapped_column(String(255), nullable=True)  # SYSCO, US Foods, etc.
    unit_cost: Mapped[float] = mapped_column(Float, nullable=True)
    
    # Perishable tracking
    is_perishable: Mapped[bool] = mapped_column(Boolean, default=False)
    shelf_life_days: Mapped[int] = mapped_column(Integer, nullable=True)
    
    last_scanned_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    shelf: Mapped["BishopShelf"] = relationship("BishopShelf", back_populates="items")


class BishopScan(Base):
    """A shelf scan event - AI vision analysis of inventory."""

    __tablename__ = "bishop_scans"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bishop_locations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    shelf_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bishop_shelves.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    scanned_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    status: Mapped[BishopScanStatus] = mapped_column(
        SQLEnum(BishopScanStatus),
        default=BishopScanStatus.IDLE,
        nullable=False,
    )
    
    # Image/evidence
    image_url: Mapped[str] = mapped_column(String(500), nullable=True)
    image_hash: Mapped[str] = mapped_column(String(128), nullable=True)  # SHA-512
    
    # AI analysis results
    ai_detected_items: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=True, default=dict)
    discrepancies: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=True, default=dict)
    risk_score: Mapped[float] = mapped_column(Float, nullable=True)  # 0-100
    
    # Order generation
    suggested_order: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=True, default=dict)
    order_total: Mapped[float] = mapped_column(Float, nullable=True)
    order_approved: Mapped[bool] = mapped_column(Boolean, nullable=True)
    order_approved_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    # Relationships
    location: Mapped["BishopLocation"] = relationship("BishopLocation", back_populates="scans")


class ShrinkageEvent(Base):
    """A detected shrinkage/loss event."""

    __tablename__ = "shrinkage_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bishop_locations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bishop_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bishop_scans.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    shrinkage_type: Mapped[ShrinkageType] = mapped_column(
        SQLEnum(ShrinkageType),
        default=ShrinkageType.UNKNOWN,
        nullable=False,
    )
    
    sku: Mapped[str] = mapped_column(String(100), nullable=True)
    item_name: Mapped[str] = mapped_column(String(255), nullable=True)
    quantity_lost: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_cost: Mapped[float] = mapped_column(Float, nullable=True)
    total_loss_value: Mapped[float] = mapped_column(Float, nullable=True)
    
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    evidence_url: Mapped[str] = mapped_column(String(500), nullable=True)
    
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolved_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    # Relationships
    location: Mapped["BishopLocation"] = relationship("BishopLocation", back_populates="shrinkage_events")

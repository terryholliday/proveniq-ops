import uuid
from datetime import datetime
from enum import Enum
from typing import Optional
from sqlalchemy import String, DateTime, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class InspectionType(str, Enum):
    """Type of inspection."""
    MOVE_IN = "MOVE_IN"
    MOVE_OUT = "MOVE_OUT"
    PERIODIC = "PERIODIC"


class InspectionStatus(str, Enum):
    """Status of inspection per spec v1.1."""
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    REVIEWED = "REVIEWED"
    SIGNED = "SIGNED"
    ARCHIVED = "ARCHIVED"


class ItemCondition(str, Enum):
    """Condition of an inspected item."""
    GOOD = "GOOD"
    FAIR = "FAIR"
    DAMAGED = "DAMAGED"
    MISSING = "MISSING"


class Inspection(Base):
    """Inspection model - Move-In or Move-Out condition report."""
    
    __tablename__ = "inspections"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    lease_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[InspectionType] = mapped_column(
        SQLEnum(InspectionType),
        nullable=False,
    )
    status: Mapped[InspectionStatus] = mapped_column(
        SQLEnum(InspectionStatus),
        default=InspectionStatus.DRAFT,
        nullable=False,
    )
    
    # Spec v1.1: Schema versioning for hash compatibility
    schema_version: Mapped[int] = mapped_column(default=1, nullable=False)
    
    # Spec v1.1: Supplemental inspection support (corrections)
    supplemental_to_inspection_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inspections.id"),
        nullable=True,
    )
    
    # Spec v1.1: Content hash (SHA-256 of canonical JSON)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    # Signature/completion tracking
    signed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    signature_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Checklist items (JSONB)
    # Structure: [{"item": "Keys Returned", "value": true}, ...]
    checklists: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)
    
    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    lease: Mapped["Lease"] = relationship("Lease", back_populates="inspections")
    items: Mapped[list["InspectionItem"]] = relationship("InspectionItem", back_populates="inspection", cascade="all, delete-orphan")
    supplemental_inspections: Mapped[list["Inspection"]] = relationship("Inspection", back_populates="parent_inspection", remote_side="Inspection.id")
    parent_inspection: Mapped[Optional["Inspection"]] = relationship("Inspection", back_populates="supplemental_inspections", remote_side=[supplemental_to_inspection_id])


class InspectionItem(Base):
    """Individual item within an inspection report."""
    
    __tablename__ = "inspection_items"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    inspection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inspections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Optional link to a specific asset (e.g., fridge, HVAC)
    asset_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inventory_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    room_name: Mapped[str] = mapped_column(String(100), nullable=False)
    item_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    condition: Mapped[ItemCondition] = mapped_column(
        SQLEnum(ItemCondition),
        default=ItemCondition.GOOD,
        nullable=False,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Photo URLs stored as array
    photo_urls: Mapped[Optional[list]] = mapped_column(ARRAY(String), nullable=True, default=list)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    inspection: Mapped["Inspection"] = relationship("Inspection", back_populates="items")
    asset: Mapped[Optional["InventoryItem"]] = relationship("InventoryItem", back_populates="inspection_items")
    evidence: Mapped[list["InspectionEvidence"]] = relationship("InspectionEvidence", back_populates="inspection_item", cascade="all, delete-orphan")

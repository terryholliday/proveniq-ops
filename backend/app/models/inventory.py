import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional
from sqlalchemy import String, DateTime, Date, Text, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class InventoryItem(Base):
    """Inventory item - can be personal (Home) or property asset (Landlord)."""
    
    __tablename__ = "inventory_items"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    # Owner (user who owns the item - could be landlord for property assets)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Optional unit association (for property assets like appliances)
    unit_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("units.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    
    # Item details
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    brand: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    serial_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Valuation (stored as Decimal for precision)
    purchase_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    current_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    purchase_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    
    # Warranty info
    warranty_expiry: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    warranty_document_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Photos and documents (JSONB for flexibility)
    photo_urls: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)
    documents: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)
    
    # AI-extracted metadata
    ai_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    
    # Location within property
    room: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    owner: Mapped["User"] = relationship("User", back_populates="inventory_items")
    unit: Mapped[Optional["Unit"]] = relationship("Unit", back_populates="inventory_items")
    inspection_items: Mapped[list["InspectionItem"]] = relationship("InspectionItem", back_populates="asset")
    maintenance_requests: Mapped[list["MaintenanceRequest"]] = relationship("MaintenanceRequest", back_populates="asset")

import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import String, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from typing import Any
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class UnitStatus(str, Enum):
    """Unit occupancy status."""
    VACANT = "VACANT"
    OCCUPIED = "OCCUPIED"


class Property(Base):
    """Property model - a building/address owned by a Landlord."""
    
    __tablename__ = "properties"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    landlord_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=True)
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(50), nullable=False)
    zip_code: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Default checklist items for inspections (JSONB)
    default_checklist: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=True,
        default=list,
    )
    
    # Relationships
    landlord: Mapped["User"] = relationship("User", back_populates="properties")
    units: Mapped[list["Unit"]] = relationship("Unit", back_populates="property", cascade="all, delete-orphan")


class Unit(Base):
    """Unit model - an individual rentable unit within a Property."""
    
    __tablename__ = "units"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    property_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("properties.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    unit_number: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[UnitStatus] = mapped_column(
        SQLEnum(UnitStatus),
        default=UnitStatus.VACANT,
        nullable=False,
    )
    bedrooms: Mapped[int] = mapped_column(nullable=True)
    bathrooms: Mapped[float] = mapped_column(nullable=True)
    square_feet: Mapped[int] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    property: Mapped["Property"] = relationship("Property", back_populates="units")
    leases: Mapped[list["Lease"]] = relationship("Lease", back_populates="unit", cascade="all, delete-orphan")
    maintenance_requests: Mapped[list["MaintenanceRequest"]] = relationship("MaintenanceRequest", back_populates="unit")
    inventory_items: Mapped[list["InventoryItem"]] = relationship("InventoryItem", back_populates="unit")

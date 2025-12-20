import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    """User model - can be Landlord, Tenant, or both based on relationships."""
    
    __tablename__ = "users"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=True)
    phone: Mapped[str] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    properties: Mapped[list["Property"]] = relationship("Property", back_populates="landlord")
    leases: Mapped[list["Lease"]] = relationship("Lease", back_populates="tenant")
    maintenance_requests: Mapped[list["MaintenanceRequest"]] = relationship("MaintenanceRequest", back_populates="tenant")
    inventory_items: Mapped[list["InventoryItem"]] = relationship("InventoryItem", back_populates="owner")
    bishop_locations: Mapped[list["BishopLocation"]] = relationship("BishopLocation", back_populates="owner")

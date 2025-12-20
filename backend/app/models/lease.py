import uuid
from datetime import datetime, date
from sqlalchemy import Date, DateTime, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Lease(Base):
    """Lease model - links a Tenant to a Unit for a time period."""
    
    __tablename__ = "leases"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    unit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("units.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Security deposit tracking
    security_deposit_amount: Mapped[int] = mapped_column(nullable=True)  # Stored in cents
    security_deposit_status: Mapped[str] = mapped_column(nullable=True)  # HELD, RELEASED, DISPUTED
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    unit: Mapped["Unit"] = relationship("Unit", back_populates="leases")
    tenant: Mapped["User"] = relationship("User", back_populates="leases")
    inspections: Mapped[list["Inspection"]] = relationship("Inspection", back_populates="lease", cascade="all, delete-orphan")

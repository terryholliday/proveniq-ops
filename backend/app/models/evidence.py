"""Inspection Evidence model - tracks uploaded photos/documents for inspections."""

import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, BigInteger, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class InspectionEvidence(Base):
    """Evidence record for an inspection item (photo, video, document)."""
    
    __tablename__ = "inspection_evidence"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    inspection_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inspection_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Storage location
    storage_url: Mapped[str] = mapped_column(String(500), nullable=False)
    
    # File metadata
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    
    # Timestamps
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    inspection_item: Mapped["InspectionItem"] = relationship(
        "InspectionItem",
        back_populates="evidence",
    )

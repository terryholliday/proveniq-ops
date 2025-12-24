"""
PROVENIQ Ops - SQLAlchemy ORM Models
Authoritative database schema implementation
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


class Vendor(Base):
    """External suppliers with priority ranking."""
    
    __tablename__ = "vendors"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    api_endpoint: Mapped[Optional[str]] = mapped_column(String(512))
    priority_level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    
    # Relationships
    vendor_products: Mapped[list["VendorProduct"]] = relationship(
        back_populates="vendor", cascade="all, delete-orphan"
    )
    orders: Mapped[list["Order"]] = relationship(back_populates="vendor")
    
    __table_args__ = (
        CheckConstraint("priority_level > 0", name="vendors_priority_positive"),
        Index("idx_vendors_priority", "priority_level", postgresql_where="is_active = true"),
    )


class Product(Base):
    """Master product catalog with par levels."""
    
    __tablename__ = "products"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    barcode: Mapped[Optional[str]] = mapped_column(String(100), unique=True)
    par_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    risk_category: Mapped[str] = mapped_column(
        String(50), nullable=False, default="standard"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    
    # Relationships
    vendor_products: Mapped[list["VendorProduct"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    snapshots: Mapped[list["InventorySnapshot"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    
    __table_args__ = (
        CheckConstraint("par_level >= 0", name="products_par_non_negative"),
        CheckConstraint(
            "risk_category IN ('standard', 'perishable', 'hazardous', 'controlled')",
            name="products_risk_valid",
        ),
        Index("idx_products_barcode", "barcode", postgresql_where="barcode IS NOT NULL"),
        Index("idx_products_risk", "risk_category"),
    )


class VendorProduct(Base):
    """SKU mapping and pricing per vendor."""
    
    __tablename__ = "vendor_products"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    vendor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vendors.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    vendor_sku: Mapped[str] = mapped_column(String(100), nullable=False)
    current_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    stock_available: Mapped[Optional[int]] = mapped_column(Integer)
    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    
    # Relationships
    vendor: Mapped["Vendor"] = relationship(back_populates="vendor_products")
    product: Mapped["Product"] = relationship(back_populates="vendor_products")
    
    __table_args__ = (
        CheckConstraint("current_price > 0", name="vendor_products_price_positive"),
        CheckConstraint(
            "stock_available IS NULL OR stock_available >= 0",
            name="vendor_products_stock_non_negative",
        ),
        UniqueConstraint("vendor_id", "product_id"),
        UniqueConstraint("vendor_id", "vendor_sku"),
        Index("idx_vendor_products_vendor", "vendor_id"),
        Index("idx_vendor_products_product", "product_id"),
    )


class InventorySnapshot(Base):
    """Timestamped scan records with provenance."""
    
    __tablename__ = "inventory_snapshots"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4))
    scanned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    scanned_by: Mapped[str] = mapped_column(String(100), nullable=False, default="bishop")
    scan_method: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")
    location_tag: Mapped[Optional[str]] = mapped_column(String(255))
    
    # Relationships
    product: Mapped["Product"] = relationship(back_populates="snapshots")
    
    __table_args__ = (
        CheckConstraint("quantity >= 0", name="snapshots_quantity_non_negative"),
        CheckConstraint(
            "confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)",
            name="snapshots_confidence_range",
        ),
        CheckConstraint(
            "scan_method IN ('manual', 'barcode', 'silhouette', 'volumetric')",
            name="snapshots_method_valid",
        ),
        Index("idx_snapshots_product", "product_id"),
        Index("idx_snapshots_scanned_at", "scanned_at"),
        Index("idx_snapshots_scanned_by", "scanned_by"),
    )


class Order(Base):
    """Orders for Vendor Bridge tracking."""
    
    __tablename__ = "orders"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    vendor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vendors.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="queued")
    total_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4))
    blocked_reason: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Relationships
    vendor: Mapped["Vendor"] = relationship(back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
    
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'submitted', 'confirmed', 'delivered', 'cancelled', 'blocked')",
            name="orders_status_valid",
        ),
        Index("idx_orders_status", "status"),
        Index("idx_orders_vendor", "vendor_id"),
    )


class OrderItem(Base):
    """Individual line items within an order."""
    
    __tablename__ = "order_items"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id"), nullable=False
    )
    vendor_product_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vendor_products.id")
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    
    # Relationships
    order: Mapped["Order"] = relationship(back_populates="items")
    
    __table_args__ = (
        CheckConstraint("quantity > 0", name="order_items_quantity_positive"),
        Index("idx_order_items_order", "order_id"),
    )


class ConsumptionEvent(Base):
    """Inventory consumption/receiving events for burn rate calculation."""
    
    __tablename__ = "consumption_events"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    qty_delta: Mapped[int] = mapped_column(Integer, nullable=False)  # negative = consumption
    event_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="consumption"
    )
    location_id: Mapped[Optional[str]] = mapped_column(String(100))
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    recorded_by: Mapped[str] = mapped_column(String(100), nullable=False, default="bishop")
    
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('consumption', 'receiving', 'adjustment', 'transfer', 'spoilage')",
            name="consumption_event_type_valid",
        ),
        Index("idx_consumption_product", "product_id"),
        Index("idx_consumption_recorded", "recorded_at"),
        Index("idx_consumption_type", "event_type"),
    )


class UsageStatistics(Base):
    """Aggregated historical usage statistics per product."""
    
    __tablename__ = "usage_statistics"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    avg_daily_burn_7d: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False, default=0)
    avg_daily_burn_30d: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False, default=0)
    avg_daily_burn_90d: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False, default=0)
    variance_coefficient: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False, default=0)
    last_calculated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    
    __table_args__ = (
        Index("idx_usage_product", "product_id"),
    )


class VendorLeadTime(Base):
    """Vendor-specific lead times for products."""
    
    __tablename__ = "vendor_lead_times"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    vendor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vendors.id", ondelete="CASCADE"), nullable=False
    )
    avg_lead_time_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=48)
    reliability_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), nullable=False, default=1.0
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    
    __table_args__ = (
        UniqueConstraint("product_id", "vendor_id"),
        CheckConstraint("avg_lead_time_hours >= 0", name="lead_time_non_negative"),
        CheckConstraint(
            "reliability_score >= 0 AND reliability_score <= 1",
            name="reliability_score_range",
        ),
        Index("idx_lead_time_product", "product_id"),
        Index("idx_lead_time_vendor", "vendor_id"),
    )


class StockoutAlert(Base):
    """Persisted stockout alerts from Bishop prediction engine."""
    
    __tablename__ = "stockout_alerts"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    projected_hours_to_stockout: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    recommended_vendor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vendors.id")
    )
    recommended_qty: Mapped[Optional[int]] = mapped_column(Integer)
    estimated_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    resolved_by: Mapped[Optional[str]] = mapped_column(String(100))
    
    __table_args__ = (
        CheckConstraint(
            "alert_type IN ('PREDICTIVE_STOCKOUT', 'WARNING', 'CRITICAL')",
            name="alert_type_valid",
        ),
        CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')",
            name="alert_severity_valid",
        ),
        CheckConstraint(
            "status IN ('active', 'acknowledged', 'resolved', 'expired')",
            name="alert_status_valid",
        ),
        Index("idx_stockout_product", "product_id"),
        Index("idx_stockout_status", "status"),
        Index("idx_stockout_severity", "severity"),
        Index("idx_stockout_created", "created_at"),
    )


class BishopStateLog(Base):
    """FSM state transition audit trail."""
    
    __tablename__ = "bishop_state_log"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    previous_state: Mapped[Optional[str]] = mapped_column(String(50))
    current_state: Mapped[str] = mapped_column(String(50), nullable=False)
    trigger_event: Mapped[str] = mapped_column(String(100), nullable=False)
    context_data: Mapped[Optional[dict]] = mapped_column(JSONB)
    output_message: Mapped[Optional[str]] = mapped_column(Text)
    logged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    
    __table_args__ = (
        CheckConstraint(
            "current_state IN ('IDLE', 'SCANNING', 'ANALYZING_RISK', 'CHECKING_FUNDS', 'ORDER_QUEUED')",
            name="bishop_state_valid",
        ),
        Index("idx_bishop_log_state", "current_state"),
        Index("idx_bishop_log_time", "logged_at"),
    )

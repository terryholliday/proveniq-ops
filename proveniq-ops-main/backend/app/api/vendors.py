"""
PROVENIQ Ops - Vendor API Routes
Vendor Bridge and aggregation endpoints
"""

import uuid
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Vendor, VendorProduct, get_db
from app.models.schemas import (
    VendorCreate,
    VendorProductBase,
    VendorProductRead,
    VendorQueryResponse,
    VendorRead,
)
from app.services.vendor import vendor_bridge_instance
from app.services.vendor.bridge import ProductAvailability, VendorInfo

router = APIRouter(prefix="/vendors", tags=["Vendor Bridge"])


@router.get("/", response_model=list[VendorRead])
async def list_vendors(
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
) -> list[VendorRead]:
    """List all vendors, optionally filtered by active status."""
    query = select(Vendor)
    if active_only:
        query = query.where(Vendor.is_active == True)
    query = query.order_by(Vendor.priority_level)
    
    result = await db.execute(query)
    vendors = result.scalars().all()
    return [VendorRead.model_validate(v) for v in vendors]


@router.post("/", response_model=VendorRead, status_code=status.HTTP_201_CREATED)
async def create_vendor(
    vendor: VendorCreate,
    db: AsyncSession = Depends(get_db),
) -> VendorRead:
    """Create a new vendor."""
    db_vendor = Vendor(**vendor.model_dump())
    db.add(db_vendor)
    await db.flush()
    await db.refresh(db_vendor)
    
    # Register with Vendor Bridge
    vendor_bridge_instance.register_vendor(VendorInfo(
        id=db_vendor.id,
        name=db_vendor.name,
        priority_level=db_vendor.priority_level,
        api_endpoint=db_vendor.api_endpoint,
        is_active=db_vendor.is_active,
    ))
    
    return VendorRead.model_validate(db_vendor)


@router.get("/{vendor_id}", response_model=VendorRead)
async def get_vendor(
    vendor_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> VendorRead:
    """Get a specific vendor by ID."""
    result = await db.execute(select(Vendor).where(Vendor.id == vendor_id))
    vendor = result.scalar_one_or_none()
    
    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vendor {vendor_id} not found",
        )
    
    return VendorRead.model_validate(vendor)


@router.post("/query/availability")
async def query_vendor_availability(
    product_id: uuid.UUID,
    quantity_needed: int,
    prefer_price: bool = False,
) -> ProductAvailability:
    """
    Query all vendors for product availability.
    
    Returns best vendor recommendation with rationale.
    
    Args:
        product_id: Product to source
        quantity_needed: Required quantity
        prefer_price: If True, optimize for price over priority
    """
    return await vendor_bridge_instance.find_best_vendor(
        product_id=product_id,
        quantity_needed=quantity_needed,
        prefer_price=prefer_price,
    )


@router.post("/failover")
async def execute_vendor_failover(
    product_id: uuid.UUID,
    quantity_needed: int,
    primary_vendor_id: uuid.UUID,
) -> ProductAvailability:
    """
    Execute vendor failover when primary is out of stock.
    
    Failsafe Rule:
        IF primary_vendor.stock == 0
        → auto-query secondary vendors
        → recommend alternative
    
    All vendor switches are logged with rationale.
    """
    return await vendor_bridge_instance.execute_failover(
        product_id=product_id,
        quantity_needed=quantity_needed,
        primary_vendor_id=primary_vendor_id,
    )


@router.post("/compare-prices")
async def compare_vendor_prices(
    product_id: uuid.UUID,
    quantity_needed: int,
) -> ProductAvailability:
    """
    Execute price arbitrage comparison across vendors.
    
    Returns cheapest compliant option with rationale.
    Never auto-switches without logging.
    """
    return await vendor_bridge_instance.compare_prices(
        product_id=product_id,
        quantity_needed=quantity_needed,
    )


@router.get("/switch-log")
async def get_vendor_switch_log() -> list[dict]:
    """Get vendor switch audit log with rationale for each switch."""
    log = vendor_bridge_instance.get_switch_log()
    return [
        {
            "original_vendor_id": str(entry.original_vendor_id),
            "selected_vendor_id": str(entry.selected_vendor_id),
            "product_id": str(entry.product_id),
            "reason": entry.reason,
            "price_delta": str(entry.price_delta) if entry.price_delta else None,
            "logged_at": entry.logged_at.isoformat(),
        }
        for entry in log
    ]

"""
PROVENIQ Ops - Inventory API Routes
Inventory snapshots and product management
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import InventorySnapshot, Product, get_db
from app.models.schemas import (
    InventorySnapshotCreate,
    InventorySnapshotRead,
    ProductCreate,
    ProductRead,
)
from app.bridges.core_client import get_core_client

router = APIRouter(prefix="/inventory", tags=["Inventory"])


# =============================================================================
# PRODUCTS
# =============================================================================

@router.get("/products", response_model=list[ProductRead])
async def list_products(
    risk_category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> list[ProductRead]:
    """List all products, optionally filtered by risk category."""
    query = select(Product)
    if risk_category:
        query = query.where(Product.risk_category == risk_category)
    query = query.order_by(Product.name)
    
    result = await db.execute(query)
    products = result.scalars().all()
    return [ProductRead.model_validate(p) for p in products]


@router.post("/products", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
async def create_product(
    product: ProductCreate,
    db: AsyncSession = Depends(get_db),
) -> ProductRead:
    """Create a new product."""
    db_product = Product(**product.model_dump())
    db.add(db_product)
    await db.flush()
    await db.refresh(db_product)
    return ProductRead.model_validate(db_product)


@router.get("/products/{product_id}", response_model=ProductRead)
async def get_product(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ProductRead:
    """Get a specific product by ID."""
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product {product_id} not found",
        )
    
    return ProductRead.model_validate(product)


@router.get("/products/barcode/{barcode}", response_model=ProductRead)
async def get_product_by_barcode(
    barcode: str,
    db: AsyncSession = Depends(get_db),
) -> ProductRead:
    """Get a product by barcode (for scanner integration)."""
    result = await db.execute(select(Product).where(Product.barcode == barcode))
    product = result.scalar_one_or_none()
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with barcode {barcode} not found",
        )
    
    return ProductRead.model_validate(product)


# =============================================================================
# SNAPSHOTS
# =============================================================================

@router.get("/snapshots", response_model=list[InventorySnapshotRead])
async def list_snapshots(
    product_id: Optional[uuid.UUID] = None,
    scanned_by: Optional[str] = None,
    limit: int = Query(100, le=1000),
    db: AsyncSession = Depends(get_db),
) -> list[InventorySnapshotRead]:
    """
    List inventory snapshots with optional filters.
    
    Returns most recent snapshots first.
    """
    query = select(InventorySnapshot)
    
    if product_id:
        query = query.where(InventorySnapshot.product_id == product_id)
    if scanned_by:
        query = query.where(InventorySnapshot.scanned_by == scanned_by)
    
    query = query.order_by(InventorySnapshot.scanned_at.desc()).limit(limit)
    
    result = await db.execute(query)
    snapshots = result.scalars().all()
    return [InventorySnapshotRead.model_validate(s) for s in snapshots]


@router.post("/snapshots", response_model=InventorySnapshotRead, status_code=status.HTTP_201_CREATED)
async def create_snapshot(
    snapshot: InventorySnapshotCreate,
    db: AsyncSession = Depends(get_db),
) -> InventorySnapshotRead:
    """
    Record an inventory snapshot.
    
    Captures:
        - Product quantity at point in time
        - Confidence score (for AR/vision scans)
        - Scan method (manual, barcode, silhouette, volumetric)
        - Provenance (scanned_by: user or bishop)
    """
    # Verify product exists
    result = await db.execute(select(Product).where(Product.id == snapshot.product_id))
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product {snapshot.product_id} not found",
        )
    
    db_snapshot = InventorySnapshot(**snapshot.model_dump())
    db.add(db_snapshot)
    await db.flush()
    await db.refresh(db_snapshot)
    return InventorySnapshotRead.model_validate(db_snapshot)


@router.get("/snapshots/latest/{product_id}", response_model=InventorySnapshotRead)
async def get_latest_snapshot(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> InventorySnapshotRead:
    """Get the most recent inventory snapshot for a product."""
    query = (
        select(InventorySnapshot)
        .where(InventorySnapshot.product_id == product_id)
        .order_by(InventorySnapshot.scanned_at.desc())
        .limit(1)
    )
    
    result = await db.execute(query)
    snapshot = result.scalar_one_or_none()
    
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No snapshots found for product {product_id}",
        )
    
    return InventorySnapshotRead.model_validate(snapshot)


@router.get("/below-par", response_model=list[dict])
async def get_products_below_par(
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """
    Get products where latest inventory is below par level.
    
    Used for Smart Par Engine reorder recommendations.
    """
    # Get all products with their par levels
    products_result = await db.execute(select(Product))
    products = products_result.scalars().all()
    
    below_par = []
    
    for product in products:
        # Get latest snapshot for this product
        snapshot_query = (
            select(InventorySnapshot)
            .where(InventorySnapshot.product_id == product.id)
            .order_by(InventorySnapshot.scanned_at.desc())
            .limit(1)
        )
        snapshot_result = await db.execute(snapshot_query)
        latest = snapshot_result.scalar_one_or_none()
        
        current_qty = latest.quantity if latest else 0
        
        if current_qty < product.par_level:
            below_par.append({
                "product_id": str(product.id),
                "product_name": product.name,
                "barcode": product.barcode,
                "par_level": product.par_level,
                "current_quantity": current_qty,
                "shortage": product.par_level - current_qty,
                "last_scanned": latest.scanned_at.isoformat() if latest else None,
            })
    
    return sorted(below_par, key=lambda x: x["shortage"], reverse=True)


# =============================================================================
# P0: CORE BATCH VALUATION
# =============================================================================

@router.post("/valuate")
async def batch_valuate_inventory(
    location_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    P0: Batch valuate inventory using Core valuation engine.
    
    Returns total inventory value for insurance/accounting purposes.
    """
    # Get all products with latest snapshots
    products_result = await db.execute(select(Product))
    products = products_result.scalars().all()
    
    items_to_valuate = []
    
    for product in products:
        # Get latest snapshot
        snapshot_query = (
            select(InventorySnapshot)
            .where(InventorySnapshot.product_id == product.id)
            .order_by(InventorySnapshot.scanned_at.desc())
            .limit(1)
        )
        snapshot_result = await db.execute(snapshot_query)
        latest = snapshot_result.scalar_one_or_none()
        
        if latest and latest.quantity > 0:
            items_to_valuate.append({
                "id": str(product.id),
                "sku": product.barcode,
                "name": product.name,
                "category": product.risk_category or "inventory",
                "quantity": latest.quantity,
                "unit_cost": float(product.unit_cost_micros or 0) / 1_000_000,
            })
    
    # Call Core batch valuation
    core_client = get_core_client()
    valuation_result = await core_client.batch_valuate_inventory(items_to_valuate)
    
    print(f"[Core] Batch valuation complete: ${valuation_result.get('total_value', 0):.2f}")
    
    return {
        "location_id": str(location_id) if location_id else None,
        "items_valuated": valuation_result.get("successful", 0),
        "items_failed": valuation_result.get("failed", 0),
        "total_value": valuation_result.get("total_value", 0),
        "currency": "USD",
        "valuated_at": valuation_result.get("valuated_at"),
        "breakdown": valuation_result.get("results", []),
    }

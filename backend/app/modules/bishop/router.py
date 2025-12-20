"""BISHOP Module - API Router

Full implementation of restaurant/retail inventory management endpoints.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.firebase_auth import get_current_user_from_firebase
from app.models.user import User
from app.modules.bishop.models import (
    BishopLocation,
    BishopShelf,
    BishopItem,
    BishopScan,
    BishopScanStatus,
    ShrinkageEvent,
)
from app.modules.bishop.schemas import (
    BishopLocationCreate,
    BishopLocationUpdate,
    BishopLocationResponse,
    BishopShelfCreate,
    BishopShelfResponse,
    BishopItemCreate,
    BishopItemUpdate,
    BishopItemResponse,
    BishopScanCreate,
    BishopScanResponse,
    ShrinkageEventCreate,
    ShrinkageEventResponse,
    ShrinkageReport,
)
from app.modules.bishop.services import BishopFSM, ScanService, ShrinkageService, VendorService

router = APIRouter(prefix="/bishop", tags=["BISHOP"])


# ============ Location Endpoints ============

@router.post("/locations", response_model=BishopLocationResponse, status_code=status.HTTP_201_CREATED)
async def create_location(
    payload: BishopLocationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_from_firebase),
):
    """Create a new BISHOP-enabled location."""
    location = BishopLocation(
        owner_id=current_user.id,
        name=payload.name,
        location_type=payload.location_type,
        address=payload.address,
        city=payload.city,
        state=payload.state,
        zip_code=payload.zip_code,
        vendor_config=payload.vendor_config,
        daily_order_limit=payload.daily_order_limit,
        auto_order_enabled=payload.auto_order_enabled,
    )
    db.add(location)
    await db.flush()
    await db.refresh(location)
    return location


@router.get("/locations", response_model=list[BishopLocationResponse])
async def list_locations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_from_firebase),
):
    """List all BISHOP locations for the current user."""
    result = await db.execute(
        select(BishopLocation).where(BishopLocation.owner_id == current_user.id)
    )
    return result.scalars().all()


@router.get("/locations/{location_id}", response_model=BishopLocationResponse)
async def get_location(
    location_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_from_firebase),
):
    """Get a specific BISHOP location."""
    result = await db.execute(
        select(BishopLocation).where(
            BishopLocation.id == location_id,
            BishopLocation.owner_id == current_user.id,
        )
    )
    location = result.scalar_one_or_none()
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    return location


@router.patch("/locations/{location_id}", response_model=BishopLocationResponse)
async def update_location(
    location_id: UUID,
    payload: BishopLocationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_from_firebase),
):
    """Update a BISHOP location."""
    result = await db.execute(
        select(BishopLocation).where(
            BishopLocation.id == location_id,
            BishopLocation.owner_id == current_user.id,
        )
    )
    location = result.scalar_one_or_none()
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(location, field, value)
    
    await db.flush()
    await db.refresh(location)
    return location


@router.delete("/locations/{location_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_location(
    location_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_from_firebase),
):
    """Delete a BISHOP location."""
    result = await db.execute(
        select(BishopLocation).where(
            BishopLocation.id == location_id,
            BishopLocation.owner_id == current_user.id,
        )
    )
    location = result.scalar_one_or_none()
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    
    await db.delete(location)


# ============ Shelf Endpoints ============

@router.post("/shelves", response_model=BishopShelfResponse, status_code=status.HTTP_201_CREATED)
async def create_shelf(
    payload: BishopShelfCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_from_firebase),
):
    """Create a new shelf within a location."""
    result = await db.execute(
        select(BishopLocation).where(
            BishopLocation.id == payload.location_id,
            BishopLocation.owner_id == current_user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Location not found")
    
    shelf = BishopShelf(
        location_id=payload.location_id,
        name=payload.name,
        shelf_code=payload.shelf_code,
        zone=payload.zone,
        expected_inventory=payload.expected_inventory,
    )
    db.add(shelf)
    await db.flush()
    await db.refresh(shelf)
    return shelf


@router.get("/locations/{location_id}/shelves", response_model=list[BishopShelfResponse])
async def list_shelves(
    location_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_from_firebase),
):
    """List all shelves for a location."""
    loc_result = await db.execute(
        select(BishopLocation).where(
            BishopLocation.id == location_id,
            BishopLocation.owner_id == current_user.id,
        )
    )
    if not loc_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Location not found")
    
    result = await db.execute(
        select(BishopShelf).where(BishopShelf.location_id == location_id)
    )
    return result.scalars().all()


@router.get("/shelves/{shelf_id}", response_model=BishopShelfResponse)
async def get_shelf(
    shelf_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_from_firebase),
):
    """Get a specific shelf."""
    result = await db.execute(
        select(BishopShelf).join(BishopLocation).where(
            BishopShelf.id == shelf_id,
            BishopLocation.owner_id == current_user.id,
        )
    )
    shelf = result.scalar_one_or_none()
    if not shelf:
        raise HTTPException(status_code=404, detail="Shelf not found")
    return shelf


# ============ Item Endpoints ============

@router.post("/items", response_model=BishopItemResponse, status_code=status.HTTP_201_CREATED)
async def create_item(
    payload: BishopItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_from_firebase),
):
    """Create a new inventory item."""
    result = await db.execute(
        select(BishopShelf).join(BishopLocation).where(
            BishopShelf.id == payload.shelf_id,
            BishopLocation.owner_id == current_user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Shelf not found")
    
    item = BishopItem(
        shelf_id=payload.shelf_id,
        sku=payload.sku,
        name=payload.name,
        description=payload.description,
        quantity_on_hand=payload.quantity_on_hand,
        quantity_unit=payload.quantity_unit,
        par_level=payload.par_level,
        reorder_point=payload.reorder_point,
        vendor_sku=payload.vendor_sku,
        vendor_name=payload.vendor_name,
        unit_cost=payload.unit_cost,
        is_perishable=payload.is_perishable,
        shelf_life_days=payload.shelf_life_days,
    )
    db.add(item)
    await db.flush()
    await db.refresh(item)
    return item


@router.get("/shelves/{shelf_id}/items", response_model=list[BishopItemResponse])
async def list_items(
    shelf_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_from_firebase),
):
    """List all items on a shelf."""
    shelf_result = await db.execute(
        select(BishopShelf).join(BishopLocation).where(
            BishopShelf.id == shelf_id,
            BishopLocation.owner_id == current_user.id,
        )
    )
    if not shelf_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Shelf not found")
    
    result = await db.execute(
        select(BishopItem).where(BishopItem.shelf_id == shelf_id)
    )
    return result.scalars().all()


@router.get("/items/{item_id}", response_model=BishopItemResponse)
async def get_item(
    item_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_from_firebase),
):
    """Get a specific item."""
    result = await db.execute(
        select(BishopItem).join(BishopShelf).join(BishopLocation).where(
            BishopItem.id == item_id,
            BishopLocation.owner_id == current_user.id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.patch("/items/{item_id}", response_model=BishopItemResponse)
async def update_item(
    item_id: UUID,
    payload: BishopItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_from_firebase),
):
    """Update an inventory item."""
    result = await db.execute(
        select(BishopItem).join(BishopShelf).join(BishopLocation).where(
            BishopItem.id == item_id,
            BishopLocation.owner_id == current_user.id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(item, field, value)
    
    await db.flush()
    await db.refresh(item)
    return item


# ============ Scan Endpoints ============

@router.post("/scans", response_model=BishopScanResponse, status_code=status.HTTP_201_CREATED)
async def start_scan(
    payload: BishopScanCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_from_firebase),
):
    """Start a new shelf scan (triggers FSM: IDLE -> SCANNING -> ANALYZING_RISK)."""
    from app.modules.bishop.services.scan import ScanService
    from app.modules.bishop.services.vendor import VendorService
    from datetime import datetime
    import hashlib
    
    loc_result = await db.execute(
        select(BishopLocation).where(
            BishopLocation.id == payload.location_id,
            BishopLocation.owner_id == current_user.id,
        )
    )
    location = loc_result.scalar_one_or_none()
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    
    shelf = None
    if payload.shelf_id:
        shelf_result = await db.execute(
            select(BishopShelf).where(
                BishopShelf.id == payload.shelf_id,
                BishopShelf.location_id == payload.location_id,
            )
        )
        shelf = shelf_result.scalar_one_or_none()
        if not shelf:
            raise HTTPException(status_code=404, detail="Shelf not found")
    
    # Create scan record
    image_hash = None
    if payload.image_url:
        image_hash = hashlib.sha512(payload.image_url.encode()).hexdigest()
    
    scan = BishopScan(
        location_id=payload.location_id,
        shelf_id=payload.shelf_id,
        scanned_by_id=current_user.id,
        status=BishopScanStatus.SCANNING,
        image_url=payload.image_url,
        image_hash=image_hash,
        started_at=datetime.utcnow(),
    )
    db.add(scan)
    await db.flush()
    
    # AI Vision Analysis using OpenAI
    from app.modules.bishop.services.vision import VisionService
    vision_service = VisionService()
    
    ai_detected_items = {}
    if payload.image_url:
        ai_detected_items = await vision_service.analyze_image_url(payload.image_url)
    else:
        ai_detected_items = vision_service._mock_response()
    
    # Compare with expected inventory to find discrepancies
    discrepancies = vision_service.compare_with_expected(
        ai_detected_items,
        shelf.expected_inventory if shelf else None,
    )
    
    # Calculate risk score
    risk_score = vision_service.calculate_risk_score(discrepancies)
    
    scan.status = BishopScanStatus.COMPLETED
    scan.ai_detected_items = ai_detected_items
    scan.discrepancies = discrepancies
    scan.risk_score = risk_score
    scan.completed_at = datetime.utcnow()
    
    await db.flush()
    await db.refresh(scan)
    return scan


@router.get("/scans/{scan_id}", response_model=BishopScanResponse)
async def get_scan(
    scan_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_from_firebase),
):
    """Get scan status and results."""
    result = await db.execute(
        select(BishopScan).join(BishopLocation).where(
            BishopScan.id == scan_id,
            BishopLocation.owner_id == current_user.id,
        )
    )
    scan = result.scalar_one_or_none()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    return scan


@router.get("/locations/{location_id}/scans", response_model=list[BishopScanResponse])
async def list_scans(
    location_id: UUID,
    limit: int = Query(default=20, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_from_firebase),
):
    """List recent scans for a location."""
    loc_result = await db.execute(
        select(BishopLocation).where(
            BishopLocation.id == location_id,
            BishopLocation.owner_id == current_user.id,
        )
    )
    if not loc_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Location not found")
    
    result = await db.execute(
        select(BishopScan)
        .where(BishopScan.location_id == location_id)
        .order_by(BishopScan.started_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


@router.post("/scans/{scan_id}/approve-order")
async def approve_order(
    scan_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_from_firebase),
):
    """Approve a suggested order from a scan."""
    from datetime import datetime
    
    result = await db.execute(
        select(BishopScan).join(BishopLocation).where(
            BishopScan.id == scan_id,
            BishopLocation.owner_id == current_user.id,
        )
    )
    scan = result.scalar_one_or_none()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    if scan.status not in (BishopScanStatus.ORDER_QUEUED, BishopScanStatus.CHECKING_FUNDS):
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot approve order in status: {scan.status.value}"
        )
    
    if not scan.suggested_order:
        raise HTTPException(status_code=400, detail="No order to approve")
    
    scan.order_approved = True
    scan.order_approved_by_id = current_user.id
    scan.status = BishopScanStatus.COMPLETED
    scan.completed_at = datetime.utcnow()
    
    await db.flush()
    
    return {"status": "approved", "scan_id": str(scan.id), "order_total": scan.order_total}


# ============ Shrinkage Endpoints ============

@router.post("/shrinkage", response_model=ShrinkageEventResponse, status_code=status.HTTP_201_CREATED)
async def create_shrinkage_event(
    payload: ShrinkageEventCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_from_firebase),
):
    """Manually report a shrinkage event."""
    from datetime import datetime
    
    loc_result = await db.execute(
        select(BishopLocation).where(
            BishopLocation.id == payload.location_id,
            BishopLocation.owner_id == current_user.id,
        )
    )
    if not loc_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Location not found")
    
    total_loss_value = None
    if payload.unit_cost:
        total_loss_value = payload.quantity_lost * payload.unit_cost
    
    event = ShrinkageEvent(
        location_id=payload.location_id,
        item_id=payload.item_id,
        scan_id=payload.scan_id,
        shrinkage_type=payload.shrinkage_type,
        sku=payload.sku,
        item_name=payload.item_name,
        quantity_lost=payload.quantity_lost,
        unit_cost=payload.unit_cost,
        total_loss_value=total_loss_value,
        notes=payload.notes,
        evidence_url=payload.evidence_url,
        detected_at=datetime.utcnow(),
    )
    db.add(event)
    await db.flush()
    await db.refresh(event)
    return event


@router.get("/locations/{location_id}/shrinkage", response_model=list[ShrinkageEventResponse])
async def list_shrinkage_events(
    location_id: UUID,
    resolved: bool | None = None,
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_from_firebase),
):
    """List shrinkage events for a location."""
    loc_result = await db.execute(
        select(BishopLocation).where(
            BishopLocation.id == location_id,
            BishopLocation.owner_id == current_user.id,
        )
    )
    if not loc_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Location not found")
    
    query = select(ShrinkageEvent).where(ShrinkageEvent.location_id == location_id)
    
    if resolved is not None:
        query = query.where(ShrinkageEvent.resolved == resolved)
    
    query = query.order_by(ShrinkageEvent.detected_at.desc()).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/locations/{location_id}/shrinkage/report", response_model=ShrinkageReport)
async def get_shrinkage_report(
    location_id: UUID,
    days: int = Query(default=30, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_from_firebase),
):
    """Get aggregated shrinkage report for a location."""
    from datetime import datetime, timedelta
    
    loc_result = await db.execute(
        select(BishopLocation).where(
            BishopLocation.id == location_id,
            BishopLocation.owner_id == current_user.id,
        )
    )
    if not loc_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Location not found")
    
    period_start = datetime.utcnow() - timedelta(days=days)
    period_end = datetime.utcnow()
    
    result = await db.execute(
        select(ShrinkageEvent).where(
            ShrinkageEvent.location_id == location_id,
            ShrinkageEvent.detected_at >= period_start,
        )
    )
    events = result.scalars().all()
    
    by_type: dict[str, float] = {}
    for event in events:
        type_key = event.shrinkage_type.value
        by_type[type_key] = by_type.get(type_key, 0) + (event.total_loss_value or 0)
    
    return ShrinkageReport(
        location_id=location_id,
        period_start=period_start,
        period_end=period_end,
        total_events=len(events),
        total_loss_value=sum(e.total_loss_value or 0 for e in events),
        by_type=by_type,
        top_items=[],
    )


@router.post("/shrinkage/{event_id}/resolve")
async def resolve_shrinkage_event(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_from_firebase),
):
    """Mark a shrinkage event as resolved."""
    from datetime import datetime
    
    result = await db.execute(
        select(ShrinkageEvent).join(BishopLocation).where(
            ShrinkageEvent.id == event_id,
            BishopLocation.owner_id == current_user.id,
        )
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Shrinkage event not found")
    
    event.resolved = True
    event.resolved_at = datetime.utcnow()
    await db.flush()
    
    return {"status": "resolved", "event_id": str(event.id)}

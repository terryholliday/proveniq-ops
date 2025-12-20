"""Tenant router - Inspections, Maintenance submissions."""

from typing import List, Optional
from uuid import UUID
from datetime import datetime
import hashlib

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.user import User
from app.models.lease import Lease
from app.models.property import Unit
from app.models.inspection import Inspection, InspectionItem, InspectionType, InspectionStatus, ItemCondition
from app.models.maintenance import MaintenanceRequest, MaintenancePriority, MaintenanceStatus
from app.models.inventory import InventoryItem
from app.schemas.inspection import (
    InspectionCreate,
    InspectionResponse,
    InspectionSubmit,
    InspectionItemCreate,
)
from app.schemas.maintenance import (
    MaintenanceRequestCreate,
    MaintenanceRequestResponse,
)
from app.dependencies import get_current_user, get_current_active_lease, require_active_lease

router = APIRouter(prefix="/tenant", tags=["tenant"])


# ============================================================================
# INSPECTIONS
# ============================================================================

@router.get("/inspections", response_model=List[InspectionResponse])
async def list_my_inspections(
    db: AsyncSession = Depends(get_db),
    lease: Lease = Depends(require_active_lease),
):
    """List all inspections for the current tenant's active lease."""
    result = await db.execute(
        select(Inspection)
        .where(Inspection.lease_id == lease.id)
        .options(selectinload(Inspection.items))
        .order_by(Inspection.created_at.desc())
    )
    return result.scalars().all()


@router.post("/inspections", response_model=InspectionResponse, status_code=status.HTTP_201_CREATED)
async def create_inspection(
    inspection_data: InspectionCreate,
    db: AsyncSession = Depends(get_db),
    lease: Lease = Depends(require_active_lease),
):
    """
    Create a new inspection (Move-In or Move-Out).
    
    The tenant starts the inspection in DRAFT status, then submits it.
    """
    # Verify lease matches
    if inspection_data.lease_id != lease.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only create inspections for your own lease",
        )
    
    # Check if inspection of this type already exists and is submitted
    existing = await db.execute(
        select(Inspection)
        .where(Inspection.lease_id == lease.id)
        .where(Inspection.type == inspection_data.type)
        .where(Inspection.status != InspectionStatus.DRAFT)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A {inspection_data.type.value} inspection has already been submitted",
        )
    
    # Get property's default checklist
    unit_result = await db.execute(
        select(Unit)
        .where(Unit.id == lease.unit_id)
        .options(selectinload(Unit.property))
    )
    unit = unit_result.scalar_one()
    default_checklist = unit.property.default_checklist or []
    
    # Create inspection
    inspection = Inspection(
        lease_id=lease.id,
        type=inspection_data.type,
        status=InspectionStatus.DRAFT,
        notes=inspection_data.notes,
        checklists=inspection_data.checklists or default_checklist,
    )
    db.add(inspection)
    await db.flush()
    
    # Add items if provided
    if inspection_data.items:
        for item_data in inspection_data.items:
            item = InspectionItem(
                inspection_id=inspection.id,
                asset_id=item_data.asset_id,
                room_name=item_data.room_name,
                item_name=item_data.item_name,
                condition=item_data.condition,
                notes=item_data.notes,
                photo_urls=item_data.photo_urls,
            )
            db.add(item)
    
    await db.commit()
    
    # Reload with items
    result = await db.execute(
        select(Inspection)
        .where(Inspection.id == inspection.id)
        .options(selectinload(Inspection.items))
    )
    return result.scalar_one()


@router.post("/inspections/submit", response_model=InspectionResponse)
async def submit_inspection(
    submit_data: InspectionSubmit,
    db: AsyncSession = Depends(get_db),
    lease: Lease = Depends(require_active_lease),
):
    """
    Submit/sign an inspection.
    
    This locks the inspection and creates a timestamped, signed record.
    """
    # Get inspection
    result = await db.execute(
        select(Inspection)
        .where(Inspection.id == submit_data.inspection_id)
        .options(selectinload(Inspection.items))
    )
    inspection = result.scalar_one_or_none()
    
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")
    
    if inspection.lease_id != lease.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    if inspection.status != InspectionStatus.DRAFT:
        raise HTTPException(
            status_code=400,
            detail="Inspection has already been submitted",
        )
    
    # Update checklist if provided
    if submit_data.checklists:
        inspection.checklists = [c.model_dump() for c in submit_data.checklists]
    
    # Clear existing items and add new ones
    for item in inspection.items:
        await db.delete(item)
    
    for item_data in submit_data.items:
        item = InspectionItem(
            inspection_id=inspection.id,
            asset_id=item_data.asset_id,
            room_name=item_data.room_name,
            item_name=item_data.item_name,
            condition=item_data.condition,
            notes=item_data.notes,
            photo_urls=item_data.photo_urls,
        )
        db.add(item)
    
    # Sign and submit
    inspection.status = InspectionStatus.SUBMITTED
    inspection.signed_at = datetime.utcnow()
    inspection.signature_hash = submit_data.signature_hash
    
    await db.commit()
    
    # Reload
    result = await db.execute(
        select(Inspection)
        .where(Inspection.id == inspection.id)
        .options(selectinload(Inspection.items))
    )
    return result.scalar_one()


@router.get("/inspections/{inspection_id}", response_model=InspectionResponse)
async def get_inspection(
    inspection_id: UUID,
    db: AsyncSession = Depends(get_db),
    lease: Lease = Depends(require_active_lease),
):
    """Get a specific inspection."""
    result = await db.execute(
        select(Inspection)
        .where(Inspection.id == inspection_id)
        .options(selectinload(Inspection.items))
    )
    inspection = result.scalar_one_or_none()
    
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")
    
    if inspection.lease_id != lease.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return inspection


# ============================================================================
# MAINTENANCE REQUESTS (The "Lite" Work Order)
# ============================================================================

@router.get("/maintenance", response_model=List[MaintenanceRequestResponse])
async def list_my_maintenance_requests(
    db: AsyncSession = Depends(get_db),
    lease: Lease = Depends(require_active_lease),
):
    """List all maintenance requests for the current tenant."""
    result = await db.execute(
        select(MaintenanceRequest)
        .where(MaintenanceRequest.unit_id == lease.unit_id)
        .where(MaintenanceRequest.tenant_id == lease.tenant_id)
        .order_by(MaintenanceRequest.created_at.desc())
    )
    requests = result.scalars().all()
    
    # Enrich with asset details
    response = []
    for req in requests:
        resp = MaintenanceRequestResponse.model_validate(req)
        
        if req.asset_id:
            asset_result = await db.execute(
                select(InventoryItem).where(InventoryItem.id == req.asset_id)
            )
            asset = asset_result.scalar_one_or_none()
            if asset:
                resp.asset_name = asset.name
                resp.asset_model = asset.model
                resp.asset_serial = asset.serial_number
                resp.asset_warranty_expiry = asset.warranty_expiry
        
        response.append(resp)
    
    return response


@router.post("/maintenance", response_model=MaintenanceRequestResponse, status_code=status.HTTP_201_CREATED)
async def create_maintenance_request(
    request_data: MaintenanceRequestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    lease: Lease = Depends(require_active_lease),
):
    """
    Create a maintenance request.
    
    Context Awareness:
    - If tenant selects an Asset (e.g., "Samsung Fridge"), attach asset_id
      so Landlord sees model/serial/warranty info automatically.
    - Routes to Landlord, NOT public marketplace.
    """
    # Verify asset belongs to the unit (if provided)
    if request_data.asset_id:
        asset_result = await db.execute(
            select(InventoryItem)
            .where(InventoryItem.id == request_data.asset_id)
            .where(InventoryItem.unit_id == lease.unit_id)
        )
        asset = asset_result.scalar_one_or_none()
        if not asset:
            raise HTTPException(
                status_code=400,
                detail="Asset not found or doesn't belong to your unit",
            )
    
    # Create maintenance request
    maintenance = MaintenanceRequest(
        unit_id=lease.unit_id,
        tenant_id=current_user.id,
        asset_id=request_data.asset_id,
        title=request_data.title,
        description=request_data.description,
        priority=request_data.priority,
        status=MaintenanceStatus.OPEN,
    )
    db.add(maintenance)
    await db.commit()
    await db.refresh(maintenance)
    
    # TODO: Trigger notification to Landlord
    # await notify_landlord_maintenance_request(lease.unit.property.landlord_id, maintenance)
    
    # Build response with asset details
    resp = MaintenanceRequestResponse.model_validate(maintenance)
    
    if maintenance.asset_id:
        asset_result = await db.execute(
            select(InventoryItem).where(InventoryItem.id == maintenance.asset_id)
        )
        asset = asset_result.scalar_one_or_none()
        if asset:
            resp.asset_name = asset.name
            resp.asset_model = asset.model
            resp.asset_serial = asset.serial_number
            resp.asset_warranty_expiry = asset.warranty_expiry
    
    return resp


# ============================================================================
# DEPOSIT SHIELD (Tenant's Evidence Locker)
# ============================================================================

@router.get("/deposit-shield")
async def get_deposit_shield(
    db: AsyncSession = Depends(get_db),
    lease: Lease = Depends(require_active_lease),
):
    """
    Get the tenant's "Deposit Shield" status.
    
    Shows:
    - Security deposit amount
    - Move-in inspection status
    - Evidence locker (timestamped photos)
    """
    # Get inspections
    result = await db.execute(
        select(Inspection)
        .where(Inspection.lease_id == lease.id)
        .options(selectinload(Inspection.items))
    )
    inspections = result.scalars().all()
    
    move_in = None
    move_out = None
    
    for insp in inspections:
        if insp.type == InspectionType.MOVE_IN:
            move_in = insp
        elif insp.type == InspectionType.MOVE_OUT:
            move_out = insp
    
    # Calculate protection score
    protection_score = 0
    if move_in and move_in.status == InspectionStatus.SUBMITTED:
        protection_score += 50
        # Add points for photos
        photo_count = sum(len(item.photo_urls or []) for item in move_in.items)
        protection_score += min(photo_count * 2, 30)  # Up to 30 points for photos
        # Add points for checklist completion
        if move_in.checklists:
            completed = sum(1 for c in move_in.checklists if c.get('value', False))
            protection_score += min(completed * 2, 20)  # Up to 20 points
    
    return {
        "lease_id": lease.id,
        "security_deposit_amount": lease.security_deposit_amount,
        "security_deposit_status": lease.security_deposit_status,
        "protection_score": min(protection_score, 100),
        "move_in_inspection": {
            "status": move_in.status.value if move_in else "NOT_STARTED",
            "signed_at": move_in.signed_at if move_in else None,
            "signature_hash": move_in.signature_hash if move_in else None,
            "item_count": len(move_in.items) if move_in else 0,
            "photo_count": sum(len(item.photo_urls or []) for item in move_in.items) if move_in else 0,
        } if move_in else None,
        "move_out_inspection": {
            "status": move_out.status.value if move_out else "NOT_STARTED",
            "signed_at": move_out.signed_at if move_out else None,
        } if move_out else None,
        "tips": [
            "Take photos of every room, including close-ups of any existing damage",
            "Document all appliances with their serial numbers",
            "Complete the move-in checklist thoroughly",
            "Keep the app installed - your evidence is blockchain-hashed via Ledger",
        ] if not move_in or move_in.status == InspectionStatus.DRAFT else [],
    }


# ============================================================================
# UNIT ASSETS (For maintenance context)
# ============================================================================

@router.get("/unit-assets")
async def list_unit_assets(
    db: AsyncSession = Depends(get_db),
    lease: Lease = Depends(require_active_lease),
):
    """
    List all assets in the tenant's unit.
    
    Used for selecting an asset when creating a maintenance request.
    """
    result = await db.execute(
        select(InventoryItem)
        .where(InventoryItem.unit_id == lease.unit_id)
    )
    assets = result.scalars().all()
    
    return [
        {
            "id": asset.id,
            "name": asset.name,
            "category": asset.category,
            "brand": asset.brand,
            "model": asset.model,
            "room": asset.room,
            "warranty_expiry": asset.warranty_expiry,
        }
        for asset in assets
    ]

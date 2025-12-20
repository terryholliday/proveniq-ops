"""Landlord router - Property/Unit management, CSV upload."""

import csv
import io
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.user import User
from app.models.property import Property, Unit, UnitStatus
from app.models.lease import Lease
from app.models.inspection import Inspection, InspectionType
from app.schemas.property import (
    PropertyCreate, 
    PropertyResponse, 
    PropertyWithStats,
    UnitCreate, 
    UnitResponse,
    ChecklistItem,
)
from app.schemas.lease import LeaseCreate, LeaseResponse, TenantCSVRow, TenantUploadResult
from app.schemas.inspection import InspectionDiff, DiffItem
from app.dependencies import get_current_user, get_landlord_properties, require_landlord_access

router = APIRouter(prefix="/landlord", tags=["landlord"])


# ============================================================================
# PROPERTY MANAGEMENT
# ============================================================================

@router.get("/properties", response_model=List[PropertyWithStats])
async def list_properties(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all properties owned by the current landlord with occupancy stats."""
    result = await db.execute(
        select(Property)
        .where(Property.landlord_id == current_user.id)
        .options(selectinload(Property.units))
    )
    properties = result.scalars().all()
    
    response = []
    for prop in properties:
        total = len(prop.units)
        occupied = sum(1 for u in prop.units if u.status == UnitStatus.OCCUPIED)
        
        response.append(PropertyWithStats(
            **PropertyResponse.model_validate(prop).model_dump(),
            total_units=total,
            occupied_units=occupied,
            vacant_units=total - occupied,
        ))
    
    return response


@router.post("/properties", response_model=PropertyResponse, status_code=status.HTTP_201_CREATED)
async def create_property(
    property_data: PropertyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new property with optional units."""
    # Create property
    property = Property(
        landlord_id=current_user.id,
        name=property_data.name,
        address=property_data.address,
        city=property_data.city,
        state=property_data.state,
        zip_code=property_data.zip_code,
        default_checklist=[c.model_dump() for c in property_data.default_checklist] if property_data.default_checklist else None,
    )
    db.add(property)
    await db.flush()
    
    # Create units if provided
    if property_data.units:
        for unit_data in property_data.units:
            unit = Unit(
                property_id=property.id,
                unit_number=unit_data.unit_number,
                status=unit_data.status,
                bedrooms=unit_data.bedrooms,
                bathrooms=unit_data.bathrooms,
                square_feet=unit_data.square_feet,
            )
            db.add(unit)
    
    await db.commit()
    await db.refresh(property)
    
    # Reload with units
    result = await db.execute(
        select(Property)
        .where(Property.id == property.id)
        .options(selectinload(Property.units))
    )
    return result.scalar_one()


@router.get("/properties/{property_id}", response_model=PropertyResponse)
async def get_property(
    property_id: UUID,
    property: Property = Depends(require_landlord_access),
):
    """Get a specific property (with RLS check)."""
    return property


@router.post("/properties/{property_id}/units", response_model=UnitResponse, status_code=status.HTTP_201_CREATED)
async def add_unit(
    property_id: UUID,
    unit_data: UnitCreate,
    db: AsyncSession = Depends(get_db),
    property: Property = Depends(require_landlord_access),
):
    """Add a unit to a property."""
    unit = Unit(
        property_id=property_id,
        unit_number=unit_data.unit_number,
        status=unit_data.status,
        bedrooms=unit_data.bedrooms,
        bathrooms=unit_data.bathrooms,
        square_feet=unit_data.square_feet,
    )
    db.add(unit)
    await db.commit()
    await db.refresh(unit)
    return unit


@router.put("/properties/{property_id}/checklist", response_model=PropertyResponse)
async def update_default_checklist(
    property_id: UUID,
    checklist: List[ChecklistItem],
    db: AsyncSession = Depends(get_db),
    property: Property = Depends(require_landlord_access),
):
    """Update the default inspection checklist for a property."""
    property.default_checklist = [c.model_dump() for c in checklist]
    await db.commit()
    await db.refresh(property)
    return property


# ============================================================================
# TENANT CSV UPLOAD (The "Trojan Horse" Onboarding)
# ============================================================================

@router.post("/upload-tenants", response_model=TenantUploadResult)
async def upload_tenants_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Bulk upload tenants via CSV.
    
    CSV Format:
    Property,Unit,TenantEmail,TenantName,LeaseStart,LeaseEnd,SecurityDeposit
    
    Logic:
    - Creates Properties/Units if they don't exist
    - Creates User account for Tenant (if new) -> sends Invite Email (mock)
    - Creates Lease entry linking Tenant to Unit
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV",
        )
    
    content = await file.read()
    decoded = content.decode('utf-8')
    reader = csv.DictReader(io.StringIO(decoded))
    
    result = TenantUploadResult(
        total_rows=0,
        properties_created=0,
        units_created=0,
        tenants_created=0,
        leases_created=0,
        errors=[],
    )
    
    # Cache for properties/units we've seen
    property_cache: dict[str, Property] = {}
    unit_cache: dict[str, Unit] = {}
    
    for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
        result.total_rows += 1
        
        try:
            # Parse row
            property_address = row.get('Property', '').strip()
            unit_number = row.get('Unit', '').strip()
            tenant_email = row.get('TenantEmail', '').strip().lower()
            tenant_name = row.get('TenantName', '').strip() or None
            lease_start = row.get('LeaseStart', '').strip()
            lease_end = row.get('LeaseEnd', '').strip()
            security_deposit = row.get('SecurityDeposit', '').strip()
            
            if not all([property_address, unit_number, tenant_email, lease_start, lease_end]):
                result.errors.append(f"Row {row_num}: Missing required fields")
                continue
            
            # Get or create Property
            cache_key = property_address.lower()
            if cache_key in property_cache:
                property = property_cache[cache_key]
            else:
                # Check if exists
                prop_result = await db.execute(
                    select(Property)
                    .where(Property.landlord_id == current_user.id)
                    .where(func.lower(Property.address) == cache_key)
                )
                property = prop_result.scalar_one_or_none()
                
                if not property:
                    # Create new property
                    property = Property(
                        landlord_id=current_user.id,
                        address=property_address,
                        city="",  # Would need to parse or require in CSV
                        state="",
                        zip_code="",
                    )
                    db.add(property)
                    await db.flush()
                    result.properties_created += 1
                
                property_cache[cache_key] = property
            
            # Get or create Unit
            unit_cache_key = f"{property.id}:{unit_number.lower()}"
            if unit_cache_key in unit_cache:
                unit = unit_cache[unit_cache_key]
            else:
                unit_result = await db.execute(
                    select(Unit)
                    .where(Unit.property_id == property.id)
                    .where(func.lower(Unit.unit_number) == unit_number.lower())
                )
                unit = unit_result.scalar_one_or_none()
                
                if not unit:
                    unit = Unit(
                        property_id=property.id,
                        unit_number=unit_number,
                        status=UnitStatus.VACANT,
                    )
                    db.add(unit)
                    await db.flush()
                    result.units_created += 1
                
                unit_cache[unit_cache_key] = unit
            
            # Get or create Tenant User
            tenant_result = await db.execute(
                select(User).where(func.lower(User.email) == tenant_email)
            )
            tenant = tenant_result.scalar_one_or_none()
            
            if not tenant:
                tenant = User(
                    email=tenant_email,
                    full_name=tenant_name,
                    is_verified=False,  # Will need to verify via email
                )
                db.add(tenant)
                await db.flush()
                result.tenants_created += 1
                
                # TODO: Send invite email
                # await send_tenant_invite_email(tenant.email, property.address, unit.unit_number)
            
            # Create Lease
            from datetime import datetime
            lease = Lease(
                unit_id=unit.id,
                tenant_id=tenant.id,
                start_date=datetime.strptime(lease_start, '%Y-%m-%d').date(),
                end_date=datetime.strptime(lease_end, '%Y-%m-%d').date(),
                active=True,
                security_deposit_amount=int(security_deposit) if security_deposit else None,
                security_deposit_status="HELD" if security_deposit else None,
            )
            db.add(lease)
            result.leases_created += 1
            
            # Update unit status
            unit.status = UnitStatus.OCCUPIED
            
        except Exception as e:
            result.errors.append(f"Row {row_num}: {str(e)}")
            continue
    
    await db.commit()
    return result


# ============================================================================
# INSPECTION DIFF ENGINE
# ============================================================================

@router.get("/leases/{lease_id}/inspection-diff", response_model=InspectionDiff)
async def get_inspection_diff(
    lease_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the "Delta" report comparing Move-In vs Move-Out inspections.
    
    Returns side-by-side comparison with damage detection.
    """
    # Verify landlord owns this lease's property
    lease_result = await db.execute(
        select(Lease)
        .where(Lease.id == lease_id)
        .options(
            selectinload(Lease.unit).selectinload(Unit.property),
            selectinload(Lease.inspections).selectinload(Inspection.items),
        )
    )
    lease = lease_result.scalar_one_or_none()
    
    if not lease:
        raise HTTPException(status_code=404, detail="Lease not found")
    
    if lease.unit.property.landlord_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Find move-in and move-out inspections
    move_in = None
    move_out = None
    
    for insp in lease.inspections:
        if insp.type == InspectionType.MOVE_IN and insp.status.value in ["SUBMITTED", "REVIEWED"]:
            move_in = insp
        elif insp.type == InspectionType.MOVE_OUT and insp.status.value in ["SUBMITTED", "REVIEWED"]:
            move_out = insp
    
    if not move_in:
        raise HTTPException(status_code=400, detail="No submitted move-in inspection found")
    if not move_out:
        raise HTTPException(status_code=400, detail="No submitted move-out inspection found")
    
    # Build diff
    diff_items = []
    
    # Index move-in items by room+item_name or asset_id
    move_in_index = {}
    for item in move_in.items:
        key = f"{item.room_name}:{item.item_name or ''}" if not item.asset_id else str(item.asset_id)
        move_in_index[key] = item
    
    # Compare with move-out items
    for out_item in move_out.items:
        key = f"{out_item.room_name}:{out_item.item_name or ''}" if not out_item.asset_id else str(out_item.asset_id)
        in_item = move_in_index.get(key)
        
        if in_item:
            # Compare conditions
            damage_detected = (
                out_item.condition.value in ["DAMAGED", "MISSING"] and 
                in_item.condition.value == "GOOD"
            )
            
            diff_items.append(DiffItem(
                room_name=out_item.room_name,
                item_name=out_item.item_name,
                asset_id=out_item.asset_id,
                move_in_condition=in_item.condition,
                move_out_condition=out_item.condition,
                move_in_notes=in_item.notes,
                move_out_notes=out_item.notes,
                move_in_photos=in_item.photo_urls or [],
                move_out_photos=out_item.photo_urls or [],
                damage_detected=damage_detected,
            ))
            
            # Remove from index (to track missing items)
            del move_in_index[key]
        else:
            # New item in move-out (shouldn't happen normally)
            diff_items.append(DiffItem(
                room_name=out_item.room_name,
                item_name=out_item.item_name,
                asset_id=out_item.asset_id,
                move_in_condition=ItemCondition.GOOD,  # Assume was good
                move_out_condition=out_item.condition,
                move_out_notes=out_item.notes,
                move_out_photos=out_item.photo_urls or [],
                damage_detected=out_item.condition.value in ["DAMAGED", "MISSING"],
            ))
    
    # Items in move-in but not move-out = MISSING
    from app.models.inspection import ItemCondition
    for key, in_item in move_in_index.items():
        diff_items.append(DiffItem(
            room_name=in_item.room_name,
            item_name=in_item.item_name,
            asset_id=in_item.asset_id,
            move_in_condition=in_item.condition,
            move_out_condition=ItemCondition.MISSING,
            move_in_notes=in_item.notes,
            move_in_photos=in_item.photo_urls or [],
            damage_detected=True,
        ))
    
    # Calculate stats
    damaged = sum(1 for d in diff_items if d.move_out_condition.value == "DAMAGED")
    missing = sum(1 for d in diff_items if d.move_out_condition.value == "MISSING")
    no_change = sum(1 for d in diff_items if not d.damage_detected)
    
    return InspectionDiff(
        lease_id=lease_id,
        move_in_inspection_id=move_in.id,
        move_out_inspection_id=move_out.id,
        diff_items=diff_items,
        total_items=len(diff_items),
        damaged_items=damaged,
        missing_items=missing,
        no_change_items=no_change,
    )

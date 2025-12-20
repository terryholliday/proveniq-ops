from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel

from app.models.property import UnitStatus


class ChecklistItem(BaseModel):
    """Single checklist item."""
    item: str
    value: bool = False


class UnitBase(BaseModel):
    """Base unit schema."""
    unit_number: str
    status: UnitStatus = UnitStatus.VACANT
    bedrooms: Optional[int] = None
    bathrooms: Optional[float] = None
    square_feet: Optional[int] = None


class UnitCreate(UnitBase):
    """Schema for creating a unit."""
    pass


class UnitResponse(UnitBase):
    """Schema for unit response."""
    id: UUID
    property_id: UUID
    created_at: datetime
    
    class Config:
        from_attributes = True


class PropertyBase(BaseModel):
    """Base property schema."""
    name: Optional[str] = None
    address: str
    city: str
    state: str
    zip_code: str
    default_checklist: Optional[List[ChecklistItem]] = None


class PropertyCreate(PropertyBase):
    """Schema for creating a property."""
    units: Optional[List[UnitCreate]] = None


class PropertyResponse(PropertyBase):
    """Schema for property response."""
    id: UUID
    landlord_id: UUID
    created_at: datetime
    updated_at: datetime
    units: List[UnitResponse] = []
    
    class Config:
        from_attributes = True


class PropertyWithStats(PropertyResponse):
    """Property response with occupancy stats."""
    total_units: int = 0
    occupied_units: int = 0
    vacant_units: int = 0

from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel

from app.models.inspection import InspectionType, InspectionStatus, ItemCondition


class ChecklistValue(BaseModel):
    """Single checklist item with value."""
    item: str
    value: bool


class InspectionItemBase(BaseModel):
    """Base inspection item schema."""
    room_name: str
    item_name: Optional[str] = None
    condition: ItemCondition = ItemCondition.GOOD
    notes: Optional[str] = None
    photo_urls: Optional[List[str]] = []
    asset_id: Optional[UUID] = None


class InspectionItemCreate(InspectionItemBase):
    """Schema for creating an inspection item."""
    pass


class InspectionItemResponse(InspectionItemBase):
    """Schema for inspection item response."""
    id: UUID
    inspection_id: UUID
    created_at: datetime
    
    class Config:
        from_attributes = True


class InspectionBase(BaseModel):
    """Base inspection schema."""
    type: InspectionType
    notes: Optional[str] = None
    checklists: Optional[List[ChecklistValue]] = []


class InspectionCreate(InspectionBase):
    """Schema for creating an inspection."""
    lease_id: UUID
    items: Optional[List[InspectionItemCreate]] = []


class InspectionSubmit(BaseModel):
    """Schema for submitting/signing an inspection."""
    inspection_id: UUID
    signature_hash: str
    checklists: Optional[List[ChecklistValue]] = None
    items: List[InspectionItemCreate]


class InspectionResponse(InspectionBase):
    """Schema for inspection response."""
    id: UUID
    lease_id: UUID
    status: InspectionStatus
    signed_at: Optional[datetime] = None
    signature_hash: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    items: List[InspectionItemResponse] = []
    
    class Config:
        from_attributes = True


class DiffItem(BaseModel):
    """Single item showing difference between move-in and move-out."""
    room_name: str
    item_name: Optional[str] = None
    asset_id: Optional[UUID] = None
    move_in_condition: ItemCondition
    move_out_condition: ItemCondition
    move_in_notes: Optional[str] = None
    move_out_notes: Optional[str] = None
    move_in_photos: List[str] = []
    move_out_photos: List[str] = []
    damage_detected: bool = False


class InspectionDiff(BaseModel):
    """Diff report comparing move-in vs move-out inspections."""
    lease_id: UUID
    move_in_inspection_id: UUID
    move_out_inspection_id: UUID
    diff_items: List[DiffItem]
    total_items: int
    damaged_items: int
    missing_items: int
    no_change_items: int

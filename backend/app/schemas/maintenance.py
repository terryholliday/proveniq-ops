from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel

from app.models.maintenance import MaintenancePriority, MaintenanceStatus


class MaintenanceRequestBase(BaseModel):
    """Base maintenance request schema."""
    title: str
    description: str
    priority: MaintenancePriority = MaintenancePriority.MEDIUM
    asset_id: Optional[UUID] = None


class MaintenanceRequestCreate(MaintenanceRequestBase):
    """Schema for creating a maintenance request."""
    pass  # unit_id and tenant_id derived from current user's lease


class MaintenanceRequestResponse(MaintenanceRequestBase):
    """Schema for maintenance request response."""
    id: UUID
    unit_id: UUID
    tenant_id: UUID
    status: MaintenanceStatus
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    # Include asset details if linked
    asset_name: Optional[str] = None
    asset_model: Optional[str] = None
    asset_serial: Optional[str] = None
    asset_warranty_expiry: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class MaintenanceRequestUpdate(BaseModel):
    """Schema for updating a maintenance request."""
    status: Optional[MaintenanceStatus] = None
    priority: Optional[MaintenancePriority] = None
    resolution_notes: Optional[str] = None

from datetime import datetime, date
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr


class LeaseBase(BaseModel):
    """Base lease schema."""
    start_date: date
    end_date: date
    security_deposit_amount: Optional[int] = None  # In cents


class LeaseCreate(LeaseBase):
    """Schema for creating a lease."""
    unit_id: UUID
    tenant_id: UUID


class LeaseResponse(LeaseBase):
    """Schema for lease response."""
    id: UUID
    unit_id: UUID
    tenant_id: UUID
    active: bool
    security_deposit_status: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class TenantCSVRow(BaseModel):
    """Schema for a row in the tenant upload CSV."""
    property_address: str
    unit_number: str
    tenant_email: EmailStr
    tenant_name: Optional[str] = None
    lease_start: date
    lease_end: date
    security_deposit: Optional[int] = None  # In cents


class TenantUploadResult(BaseModel):
    """Result of tenant CSV upload."""
    total_rows: int
    properties_created: int
    units_created: int
    tenants_created: int
    leases_created: int
    errors: list[str] = []

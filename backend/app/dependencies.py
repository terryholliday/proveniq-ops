"""Dependency injection helpers for FastAPI."""

from typing import Optional
from uuid import UUID
from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.user import User
from app.models.lease import Lease
from app.models.property import Property


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    # In production, this would come from JWT token
    user_id: Optional[UUID] = None,
) -> User:
    """Get the current authenticated user.
    
    TODO: Implement proper JWT authentication.
    For now, accepts user_id as a header/query param for testing.
    """
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive",
        )
    
    return user


async def get_current_active_lease(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Optional[Lease]:
    """Get the current user's active lease (if they are a tenant).
    
    Returns None if user has no active lease.
    Used to determine if user is acting as a Tenant.
    """
    result = await db.execute(
        select(Lease)
        .where(Lease.tenant_id == current_user.id)
        .where(Lease.active == True)
        .options(selectinload(Lease.unit))
    )
    return result.scalar_one_or_none()


async def require_active_lease(
    lease: Optional[Lease] = Depends(get_current_active_lease),
) -> Lease:
    """Require that the current user has an active lease.
    
    Raises 403 if user is not a tenant with an active lease.
    """
    if not lease:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must have an active lease to perform this action",
        )
    return lease


async def get_landlord_properties(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Property]:
    """Get all properties owned by the current user (as landlord).
    
    Used for RLS - landlords only see their own properties.
    """
    result = await db.execute(
        select(Property)
        .where(Property.landlord_id == current_user.id)
        .options(selectinload(Property.units))
    )
    return result.scalars().all()


async def require_landlord_access(
    property_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Property:
    """Require that the current user owns the specified property.
    
    Raises 403 if user doesn't own the property.
    """
    result = await db.execute(
        select(Property)
        .where(Property.id == property_id)
        .where(Property.landlord_id == current_user.id)
        .options(selectinload(Property.units))
    )
    property = result.scalar_one_or_none()
    
    if not property:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this property",
        )
    
    return property

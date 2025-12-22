"""Authentication router for PROVENIQ Ops.

Restaurant/Retail staff authentication via Firebase.
The API verifies Firebase JWTs - it never mints them.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.firebase_auth import get_current_user_from_firebase as get_current_user, require_role
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


# ============================================================================
# SCHEMAS
# ============================================================================

class UserProfile(BaseModel):
    """User profile response."""
    id: UUID
    email: str
    full_name: Optional[str] = None
    role: Optional[str] = None
    organization_id: Optional[UUID] = None
    is_active: bool


class UpdateProfileRequest(BaseModel):
    """Request to update user profile."""
    full_name: Optional[str] = None
    phone: Optional[str] = None


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/me", response_model=UserProfile)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
):
    """
    Get current user's profile.
    
    Requires valid Firebase JWT in Authorization header.
    """
    return UserProfile(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        organization_id=current_user.organization_id,
        is_active=current_user.is_active,
    )


@router.patch("/me", response_model=UserProfile)
async def update_my_profile(
    request: UpdateProfileRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update current user's profile.
    """
    if request.full_name is not None:
        current_user.full_name = request.full_name
    if request.phone is not None:
        current_user.phone = request.phone
    
    current_user.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(current_user)
    
    return UserProfile(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        organization_id=current_user.organization_id,
        is_active=current_user.is_active,
    )


@router.get("/verify")
async def verify_token(
    current_user: User = Depends(get_current_user),
):
    """
    Verify that the current token is valid.
    
    Returns minimal user info for token validation.
    """
    return {
        "valid": True,
        "user_id": str(current_user.id),
        "role": current_user.role,
    }

"""Authentication router - Magic Link exchange and Firebase Custom Tokens.

Per spec v1.1:
- The API never mints JWTs
- It verifies Magic Links/Credentials and issues Firebase Custom Tokens
- The Client SDK exchanges these for JWTs
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.firebase_auth import (
    create_firebase_custom_token,
    generate_magic_token,
    hash_magic_token,
    get_magic_token_expiry,
)
from app.models.user import User
from app.models.lease import Lease

router = APIRouter(prefix="/auth", tags=["auth"])


# ============================================================================
# SCHEMAS
# ============================================================================

class MagicTokenExchangeRequest(BaseModel):
    """Request to exchange a magic token for a Firebase Custom Token."""
    magic_token: str


class MagicTokenExchangeResponse(BaseModel):
    """Response containing Firebase Custom Token."""
    firebase_custom_token: str
    lease_id: UUID
    tenant_id: UUID
    tenant_email: str


class InviteRequest(BaseModel):
    """Request to generate and send a tenant invite."""
    lease_id: UUID


class InviteResponse(BaseModel):
    """Response containing the magic link."""
    magic_link: str
    expires_at: datetime


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/exchange-token", response_model=MagicTokenExchangeResponse)
async def exchange_magic_token(
    request: MagicTokenExchangeRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Exchange a magic link token for a Firebase Custom Token.
    
    Flow:
    1. Verify magic token is valid and not expired
    2. Get the associated lease and tenant
    3. Create Firebase Custom Token with claims
    4. Mark token as used
    5. Update lease status to PENDING -> ACTIVE if first login
    
    The client then uses the Firebase Custom Token to sign in with Firebase,
    which returns a JWT for subsequent API calls.
    """
    # Find the lease by magic token
    result = await db.execute(
        select(Lease)
        .where(Lease.magic_token == request.magic_token)
    )
    lease = result.scalar_one_or_none()
    
    if not lease:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired magic link",
        )
    
    # Check expiry
    if lease.magic_token_expires_at and lease.magic_token_expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Magic link has expired. Request a new invite from your landlord.",
        )
    
    # Get the tenant
    tenant_result = await db.execute(
        select(User).where(User.id == lease.tenant_id)
    )
    tenant = tenant_result.scalar_one_or_none()
    
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant account not found",
        )
    
    # Ensure tenant has a Firebase UID (create if needed)
    if not tenant.firebase_uid:
        # Generate a Firebase UID based on our user ID
        tenant.firebase_uid = f"tenant_{tenant.id}"
    
    # Create Firebase Custom Token with claims
    claims = {
        "role": "TENANT",
        "lease_id": str(lease.id),
        "tenant_id": str(tenant.id),
    }
    
    firebase_custom_token = create_firebase_custom_token(
        uid=tenant.firebase_uid,
        claims=claims,
    )
    
    # Mark magic token as used (but keep it for audit)
    # In production, you might want to invalidate it after first use
    # lease.magic_token = None
    
    # Update lease status if this is the first login
    if lease.status == "pending":
        lease.status = "active"
    
    # Update tenant role if not set
    if not tenant.role:
        tenant.role = "TENANT"
    
    await db.commit()
    
    return MagicTokenExchangeResponse(
        firebase_custom_token=firebase_custom_token,
        lease_id=lease.id,
        tenant_id=tenant.id,
        tenant_email=tenant.email,
    )


@router.post("/generate-invite", response_model=InviteResponse)
async def generate_tenant_invite(
    request: InviteRequest,
    db: AsyncSession = Depends(get_db),
    # In production, add: current_user: User = Depends(require_role("LANDLORD_ADMIN"))
):
    """
    Generate a magic link invite for a tenant.
    
    Called by landlord to invite a tenant to complete their move-in inspection.
    """
    # Get the lease
    result = await db.execute(
        select(Lease).where(Lease.id == request.lease_id)
    )
    lease = result.scalar_one_or_none()
    
    if not lease:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lease not found",
        )
    
    # Generate magic token
    magic_token = generate_magic_token()
    expires_at = get_magic_token_expiry(hours=72)
    
    # Store on lease
    lease.magic_token = magic_token
    lease.magic_token_expires_at = expires_at
    
    # Update status to pending (invite sent)
    if lease.status == "draft":
        lease.status = "pending"
    
    await db.commit()
    
    # Build magic link
    # In production, use proper domain
    base_url = "https://ops.proveniq.io"
    magic_link = f"{base_url}/auth?token={magic_token}"
    
    # Alternative: Deep link for mobile app
    # magic_link = f"proveniq://auth?token={magic_token}"
    
    return InviteResponse(
        magic_link=magic_link,
        expires_at=expires_at,
    )


@router.post("/refresh-invite", response_model=InviteResponse)
async def refresh_tenant_invite(
    request: InviteRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Refresh an expired magic link for a tenant.
    
    Generates a new token and extends expiry.
    """
    result = await db.execute(
        select(Lease).where(Lease.id == request.lease_id)
    )
    lease = result.scalar_one_or_none()
    
    if not lease:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lease not found",
        )
    
    # Generate new magic token
    magic_token = generate_magic_token()
    expires_at = get_magic_token_expiry(hours=72)
    
    lease.magic_token = magic_token
    lease.magic_token_expires_at = expires_at
    
    await db.commit()
    
    base_url = "https://ops.proveniq.io"
    magic_link = f"{base_url}/auth?token={magic_token}"
    
    return InviteResponse(
        magic_link=magic_link,
        expires_at=expires_at,
    )

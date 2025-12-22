from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User

router = APIRouter(prefix="/admin", tags=["admin"])


class BootstrapUserRequest(BaseModel):
    firebase_uid: str
    email: str
    full_name: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = None
    organization_id: Optional[UUID] = None
    is_active: bool = True


@router.post("/bootstrap-user")
async def bootstrap_user(
    request: Request,
    payload: BootstrapUserRequest,
    db: AsyncSession = Depends(get_db),
    x_bootstrap_key: Optional[str] = Header(default=None, alias="X-Bootstrap-Key"),
):
    if not settings.DEBUG:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    if not settings.ADMIN_BOOTSTRAP_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ADMIN_BOOTSTRAP_KEY not configured",
        )

    if not x_bootstrap_key or x_bootstrap_key != settings.ADMIN_BOOTSTRAP_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bootstrap key")

    client_host = request.client.host if request.client else None
    if client_host not in {"127.0.0.1", "localhost"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Localhost only")

    result = await db.execute(select(User).where(User.firebase_uid == payload.firebase_uid))
    user = result.scalar_one_or_none()

    if not user:
        email_result = await db.execute(select(User).where(User.email == payload.email))
        user = email_result.scalar_one_or_none()

    if user:
        user.firebase_uid = payload.firebase_uid
        user.email = payload.email
        user.full_name = payload.full_name
        user.phone = payload.phone
        user.role = payload.role
        user.organization_id = payload.organization_id
        user.is_active = payload.is_active
        await db.flush()
        return {"status": "updated", "user_id": str(user.id)}

    user = User(
        firebase_uid=payload.firebase_uid,
        email=payload.email,
        full_name=payload.full_name,
        phone=payload.phone,
        role=payload.role,
        organization_id=payload.organization_id,
        is_active=payload.is_active,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    return {"status": "created", "user_id": str(user.id)}

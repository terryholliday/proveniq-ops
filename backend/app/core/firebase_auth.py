"""Firebase Authentication Middleware

Implements Firebase Custom Token exchange and JWT verification.
Per spec v1.1: The API never mints JWTs. It verifies Magic Links/Credentials 
and issues Firebase Custom Tokens. The Client SDK exchanges these for JWTs.
"""

import os
from typing import Optional
from datetime import datetime, timedelta
import secrets
import hashlib

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# Firebase Admin SDK
try:
    import firebase_admin
    from firebase_admin import credentials, auth as firebase_auth
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    firebase_admin = None
    firebase_auth = None

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import settings as app_settings
from app.models.user import User


# Initialize Firebase Admin SDK
def init_firebase():
    """Initialize Firebase Admin SDK if not already initialized."""
    if not FIREBASE_AVAILABLE:
        return False
    
    try:
        existing_app = firebase_admin.get_app()
        desired_project_id = app_settings.FIREBASE_PROJECT_ID
        existing_project_id = getattr(existing_app, "project_id", None)
        if desired_project_id and existing_project_id and existing_project_id != desired_project_id:
            firebase_admin.delete_app(existing_app)
            raise ValueError("Firebase app initialized for different project")
        return True
    except ValueError:
        # Not initialized yet
        desired_project_id = app_settings.FIREBASE_PROJECT_ID
        cred_path = app_settings.GOOGLE_APPLICATION_CREDENTIALS or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if cred_path:
            cred_path = cred_path.strip('"')
        if cred_path and os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
            options = {"projectId": desired_project_id} if desired_project_id else None
            firebase_admin.initialize_app(cred, options=options)
            return True
        else:
            # Try default credentials (for Cloud Run/Cloud Functions)
            try:
                options = {"projectId": desired_project_id} if desired_project_id else None
                firebase_admin.initialize_app(options=options)
                return True
            except Exception:
                return False


# Security scheme
security = HTTPBearer(auto_error=False)


class FirebaseUser:
    """Represents a verified Firebase user."""
    
    def __init__(
        self,
        uid: str,
        email: Optional[str] = None,
        email_verified: bool = False,
        claims: Optional[dict] = None,
    ):
        self.uid = uid
        self.email = email
        self.email_verified = email_verified
        self.claims = claims or {}
    
    @property
    def role(self) -> Optional[str]:
        return self.claims.get("role")
    
    @property
    def organization_id(self) -> Optional[str]:
        return self.claims.get("organization_id")


async def verify_firebase_token(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[FirebaseUser]:
    """
    Verify Firebase JWT token from Authorization header.
    
    Returns FirebaseUser if valid, None if no token provided.
    Raises HTTPException if token is invalid.
    """
    if not credentials:
        return None
    
    if not FIREBASE_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Firebase authentication not available",
        )
    
    if not init_firebase():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Firebase authentication not configured",
        )
    
    try:
        # Verify the Firebase ID token
        decoded_token = firebase_auth.verify_id_token(credentials.credentials)
        
        return FirebaseUser(
            uid=decoded_token["uid"],
            email=decoded_token.get("email"),
            email_verified=decoded_token.get("email_verified", False),
            claims=decoded_token,
        )
    except firebase_auth.InvalidIdTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication token: {str(e)}",
        )
    except firebase_auth.ExpiredIdTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication token expired: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}",
        )


async def require_firebase_auth(
    firebase_user: Optional[FirebaseUser] = Depends(verify_firebase_token),
) -> FirebaseUser:
    """Require valid Firebase authentication."""
    if not firebase_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return firebase_user


async def get_current_user_from_firebase(
    db: AsyncSession = Depends(get_db),
    firebase_user: FirebaseUser = Depends(require_firebase_auth),
) -> User:
    """
    Get the database User record for the authenticated Firebase user.
    Creates user if they don't exist yet.
    """
    result = await db.execute(
        select(User).where(User.firebase_uid == firebase_user.uid)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        # Check if user exists by email
        if firebase_user.email:
            result = await db.execute(
                select(User).where(User.email == firebase_user.email)
            )
            user = result.scalar_one_or_none()
            
            if user:
                # Link existing user to Firebase
                user.firebase_uid = firebase_user.uid
                await db.commit()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found. Complete onboarding first.",
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )
    
    return user


def create_firebase_custom_token(uid: str, claims: Optional[dict] = None) -> str:
    """
    Create a Firebase Custom Token for a user.
    
    Per spec: The API issues Firebase Custom Tokens.
    The Client SDK exchanges these for JWTs.
    """
    if not FIREBASE_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Firebase authentication not available",
        )
    
    init_firebase()
    
    try:
        custom_token = firebase_auth.create_custom_token(uid, claims)
        return custom_token.decode("utf-8") if isinstance(custom_token, bytes) else custom_token
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create authentication token: {str(e)}",
        )


def generate_magic_token() -> str:
    """Generate a secure magic link token."""
    return secrets.token_urlsafe(32)


def hash_magic_token(token: str) -> str:
    """Hash a magic token for storage."""
    return hashlib.sha256(token.encode()).hexdigest()


def get_magic_token_expiry(hours: int = 72) -> datetime:
    """Get expiry time for a magic token (default 72 hours)."""
    return datetime.utcnow() + timedelta(hours=hours)


# Role-based access control
def require_role(*allowed_roles: str):
    """
    Dependency that requires the user to have one of the specified roles.
    
    Usage:
        @router.get("/admin-only")
        async def admin_endpoint(user: User = Depends(require_role("LANDLORD_ADMIN"))):
            ...
    """
    async def role_checker(
        user: User = Depends(get_current_user_from_firebase),
    ) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {', '.join(allowed_roles)}",
            )
        return user
    
    return role_checker

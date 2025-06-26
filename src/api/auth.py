"""
Authentication API endpoints for Scintilla

Handles Google OAuth login flow and user session management.
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from src.auth.google_oauth import (
    get_current_user, 
    verify_google_token, 
    create_or_update_user_from_google,
    create_jwt_token,
    AuthenticationError
)
from src.config import settings
from src.db.base import get_db_session
from src.db.models import User

logger = structlog.get_logger()

router = APIRouter(prefix="/auth", tags=["authentication"])


class LoginRequest(BaseModel):
    """Request model for Google OAuth login"""
    google_token: str = Field(..., description="Google ID token from frontend OAuth flow")


class LoginResponse(BaseModel):
    """Response model for successful login"""
    success: bool
    user: dict
    token: str
    message: str


class UserInfoResponse(BaseModel):
    """Response model for user information"""
    user_id: str
    email: str
    name: str
    picture_url: Optional[str] = None
    is_admin: bool
    last_login: Optional[datetime] = None


@router.post("/login", response_model=LoginResponse)
async def login(
    login_request: LoginRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Authenticate user with Google OAuth token
    
    Frontend should:
    1. Use Google OAuth to get ID token
    2. Send ID token to this endpoint
    3. Receive JWT token for subsequent requests
    """
    try:
        # Verify Google token
        token_info = await verify_google_token(login_request.google_token)
        
        # Create or update user
        user = await create_or_update_user_from_google(db, token_info)
        
        # Create JWT token for frontend
        jwt_token = create_jwt_token(str(user.user_id), user.email)
        
        logger.info("User logged in successfully", user_id=user.user_id, email=user.email)
        
        return LoginResponse(
            success=True,
            user={
                "user_id": str(user.user_id),
                "email": user.email,
                "name": user.name,
                "picture_url": user.picture_url,
                "is_admin": user.is_admin
            },
            token=jwt_token,
            message="Login successful"
        )
        
    except AuthenticationError as e:
        logger.warning("Login failed", error=str(e))
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error("Login error", error=str(e))
        raise HTTPException(status_code=500, detail="Login failed")


@router.get("/me", response_model=UserInfoResponse)
async def get_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    Get current user information
    
    Requires authentication via Bearer token in Authorization header.
    """
    return UserInfoResponse(
        user_id=str(current_user.user_id),
        email=current_user.email,
        name=current_user.name,
        picture_url=current_user.picture_url,
        is_admin=current_user.is_admin,
        last_login=getattr(current_user, 'last_login', None)
    )


@router.post("/logout")
async def logout():
    """
    Logout user
    
    Frontend should:
    1. Call this endpoint
    2. Clear stored JWT token
    3. Redirect to login page
    """
    return {"success": True, "message": "Logged out successfully"}


@router.get("/config")
async def get_auth_config():
    """
    Get authentication configuration for frontend
    
    Returns information needed for frontend OAuth setup.
    """
    return {
        "google_oauth_client_id": settings.google_oauth_client_id,
        "allowed_domains": settings.allowed_domains_list,
        "auth_enabled": bool(settings.google_oauth_client_id and settings.google_oauth_client_secret)
    }


@router.get("/health")
async def auth_health():
    """
    Check authentication system health
    """
    return {
        "status": "healthy",
        "oauth_configured": bool(settings.google_oauth_client_id and settings.google_oauth_client_secret),
        "allowed_domains": settings.allowed_domains_list
    } 
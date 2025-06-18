"""
Mock authentication system for development

Provides a simple mock user for testing purposes.
Replace with Google OAuth in production.
"""

import uuid
from datetime import datetime
from typing import Optional

from fastapi import Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog

from src.db.base import get_db_session
from src.db.models import User

logger = structlog.get_logger()

# Mock user for development
MOCK_USER_EMAIL = "developer@ignitetech.com"
MOCK_USER_NAME = "Mock Developer"
MOCK_USER_PICTURE = "https://via.placeholder.com/150"


async def ensure_mock_user_exists(db: AsyncSession) -> User:
    """Ensure the mock user exists in the database"""
    
    # Check if mock user exists
    query = select(User).where(User.email == MOCK_USER_EMAIL)
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if not user:
        # Create mock user
        user = User(
            user_id=uuid.uuid4(),
            email=MOCK_USER_EMAIL,
            name=MOCK_USER_NAME,
            picture_url=MOCK_USER_PICTURE,
            is_admin=True  # Make mock user admin for testing
        )
        
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        logger.info("Created mock user", user_id=user.user_id, email=user.email)
    
    return user


async def get_current_user(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db_session)
) -> User:
    """
    Mock authentication dependency
    
    In production, this would:
    1. Validate Google OAuth token from Authorization header
    2. Extract user info from token
    3. Create/update user in database
    
    For development, returns a mock user.
    """
    
    # In development mode, always return mock user
    try:
        mock_user = await ensure_mock_user_exists(db)
        
        # Create a fresh user object with just the needed data to avoid session issues
        detached_user = User(
            user_id=mock_user.user_id,
            email=mock_user.email,
            name=mock_user.name,
            picture_url=mock_user.picture_url,
            is_admin=mock_user.is_admin
        )
        
        logger.debug("Using mock authentication", user_id=mock_user.user_id)
        return detached_user
        
    except Exception as e:
        logger.error("Mock authentication failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Authentication system error"
        )


async def validate_google_token(token: str) -> dict:
    """
    Placeholder for Google OAuth token validation
    
    In production, this would:
    1. Verify token signature
    2. Check token expiration
    3. Validate issuer and audience
    4. Return user claims
    """
    raise NotImplementedError("Google OAuth not implemented yet")


async def create_or_update_user_from_token(db: AsyncSession, token_claims: dict) -> User:
    """
    Create or update user from Google OAuth token claims
    
    In production, this would:
    1. Extract user info from token claims
    2. Check if user exists by google_sub
    3. Create new user or update existing
    4. Validate domain restrictions
    """
    raise NotImplementedError("Google OAuth not implemented yet") 
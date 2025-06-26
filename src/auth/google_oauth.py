"""
Google OAuth authentication for Scintilla

Implements Google OAuth 2.0 flow for user authentication.
Only allows users from specified domains (ignitetech.com, ignitetech.ai).
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import jwt
import httpx
from fastapi import Depends, HTTPException, Header, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog

from src.config import settings
from src.db.base import get_db_session
from src.db.models import User

logger = structlog.get_logger()

security = HTTPBearer()

# Google OAuth endpoints
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
GOOGLE_CERTS_URL = "https://www.googleapis.com/oauth2/v1/certs"


class AuthenticationError(Exception):
    """Custom authentication error"""
    pass


async def verify_google_token(token: str) -> Dict[str, Any]:
    """
    Verify Google ID token and return user claims
    """
    try:
        # For development, we can use Google's tokeninfo endpoint
        # In production, you should verify the JWT signature properly
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://oauth2.googleapis.com/tokeninfo?id_token={token}"
            )
            
            if response.status_code != 200:
                raise AuthenticationError("Invalid token")
            
            token_info = response.json()
            
            # Verify token claims
            if token_info.get("aud") != settings.google_oauth_client_id:
                raise AuthenticationError("Invalid audience")
            
            if token_info.get("iss") not in ["accounts.google.com", "https://accounts.google.com"]:
                raise AuthenticationError("Invalid issuer")
            
            # Check if token is expired
            exp = token_info.get("exp")
            if exp and int(exp) < datetime.utcnow().timestamp():
                raise AuthenticationError("Token expired")
            
            # Verify domain restriction
            email = token_info.get("email")
            if not email:
                raise AuthenticationError("Email not found in token")
            
            domain = email.split("@")[1] if "@" in email else ""
            if domain not in settings.allowed_domains_list:
                raise AuthenticationError(f"Domain {domain} not allowed")
            
            return token_info
            
    except httpx.RequestError as e:
        logger.error("Failed to verify token", error=str(e))
        raise AuthenticationError("Token verification failed")
    except Exception as e:
        logger.error("Token verification error", error=str(e))
        raise AuthenticationError("Invalid token")


async def create_or_update_user_from_google(db: AsyncSession, token_info: Dict[str, Any]) -> User:
    """
    Create or update user from Google token information
    """
    email = token_info.get("email")
    google_sub = token_info.get("sub")
    name = token_info.get("name", email)
    picture_url = token_info.get("picture", "")
    
    if not email or not google_sub:
        raise AuthenticationError("Missing required user information")
    
    # Check if user exists by email (primary identifier)
    query = select(User).where(User.email == email)
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if user:
        # Update existing user
        user.name = name
        user.picture_url = picture_url
        user.last_login = datetime.utcnow()
        
        # Update google_sub if it changed (shouldn't happen, but just in case)
        if hasattr(user, 'google_sub'):
            user.google_sub = google_sub
            
        logger.info("Updated existing user", user_id=user.user_id, email=email)
    else:
        # Create new user
        user = User(
            user_id=uuid.uuid4(),
            email=email,
            name=name,
            picture_url=picture_url,
            is_admin=email in ["admin@ignitetech.com", "your-admin@ignitetech.com"],  # Configure admin emails
            created_at=datetime.utcnow(),
            last_login=datetime.utcnow()
        )
        
        # Add google_sub if the User model supports it
        if hasattr(user, 'google_sub'):
            user.google_sub = google_sub
        
        db.add(user)
        logger.info("Created new user", user_id=user.user_id, email=email)
    
    await db.commit()
    await db.refresh(user)
    
    # Return detached user object to avoid session issues
    detached_user = User(
        user_id=user.user_id,
        email=user.email,
        name=user.name,
        picture_url=user.picture_url,
        is_admin=user.is_admin
    )
    
    return detached_user


async def get_current_user_production(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db_session)
) -> User:
    """
    Production authentication dependency using Google OAuth
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    try:
        # Verify Google token
        token_info = await verify_google_token(credentials.credentials)
        
        # Create or update user
        user = await create_or_update_user_from_google(db, token_info)
        
        logger.debug("Authenticated user", user_id=user.user_id, email=user.email)
        return user
        
    except AuthenticationError as e:
        logger.warning("Authentication failed", error=str(e))
        raise HTTPException(
            status_code=401,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"}
        )
    except Exception as e:
        logger.error("Authentication error", error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Authentication system error"
        )


# For development compatibility
async def get_current_user_development(
    db: AsyncSession = Depends(get_db_session)
) -> User:
    """
    Development authentication (mock user)
    """
    from src.auth.mock import ensure_mock_user_exists
    
    mock_user = await ensure_mock_user_exists(db)
    
    detached_user = User(
        user_id=mock_user.user_id,
        email=mock_user.email,
        name=mock_user.name,
        picture_url=mock_user.picture_url,
        is_admin=mock_user.is_admin
    )
    
    logger.debug("Using development authentication", user_id=mock_user.user_id)
    return detached_user


# Main authentication dependency - switches based on environment
async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db_session)
) -> User:
    """
    Main authentication dependency
    
    Uses production OAuth in production, mock in development
    """
    # Use production auth if Google OAuth is configured
    if settings.google_oauth_client_id and settings.google_oauth_client_secret:
        # Extract authorization header manually for production auth
        authorization = request.headers.get("authorization")
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=401,
                detail="Bearer token required",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        token = authorization.split(" ")[1]
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        return await get_current_user_production(credentials, db)
    else:
        # Fall back to development mock
        logger.debug("Using development authentication (Google OAuth not configured)")
        return await get_current_user_development(db)


def create_jwt_token(user_id: str, email: str) -> str:
    """
    Create a JWT token for frontend session management
    """
    payload = {
        "user_id": user_id,
        "email": email,
        "exp": datetime.utcnow() + timedelta(days=1),
        "iat": datetime.utcnow()
    }
    
    return jwt.encode(payload, settings.jwt_secret_key, algorithm="HS256")


def verify_jwt_token(token: str) -> Dict[str, Any]:
    """
    Verify a JWT token and return payload
    """
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Token expired")
    except jwt.InvalidTokenError:
        raise AuthenticationError("Invalid token") 
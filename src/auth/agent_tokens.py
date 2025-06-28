"""
Agent Token Authentication Service

Handles creation, validation, and management of user agent tokens
for local agent authentication.
"""

import hashlib
import secrets
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
import structlog

from src.db.models import User, UserAgentToken

logger = structlog.get_logger()


class AgentTokenService:
    """Service for managing user agent tokens"""
    
    @staticmethod
    def generate_token() -> str:
        """
        Generate a secure random token
        
        Format: scat_<32 random hex chars>
        Example: scat_a1b2c3d4e5f6789...
        """
        random_part = secrets.token_hex(32)  # 64 chars
        return f"scat_{random_part}"
    
    @staticmethod
    def hash_token(token: str) -> str:
        """Hash a token for database storage"""
        return hashlib.sha256(token.encode()).hexdigest()
    
    @staticmethod
    def get_token_prefix(token: str) -> str:
        """Get the first 8 characters for display purposes"""
        return token[:8]
    
    @classmethod
    async def create_token(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        name: Optional[str] = None,
        expires_days: Optional[int] = None
    ) -> tuple[UserAgentToken, str]:
        """
        Create a new agent token for a user
        
        Returns:
            Tuple of (token_record, plain_token)
        """
        # Generate the token
        plain_token = cls.generate_token()
        token_hash = cls.hash_token(plain_token)
        token_prefix = cls.get_token_prefix(plain_token)
        
        # Calculate expiration if specified
        expires_at = None
        if expires_days:
            expires_at = datetime.now(timezone.utc) + timedelta(days=expires_days)
        
        # Create the token record
        token_record = UserAgentToken(
            user_id=user_id,
            token_hash=token_hash,
            token_prefix=token_prefix,
            name=name,
            expires_at=expires_at
        )
        
        db.add(token_record)
        await db.flush()  # Get the token_id
        
        logger.info(
            "Agent token created",
            user_id=user_id,
            token_id=token_record.token_id,
            token_prefix=token_prefix,
            name=name,
            expires_at=expires_at
        )
        
        return token_record, plain_token
    
    @classmethod
    async def validate_token(
        cls,
        db: AsyncSession,
        token: str
    ) -> Optional[User]:
        """
        Validate a token and return the associated user
        
        Also updates the last_used_at timestamp
        
        Returns:
            User if token is valid, None otherwise
        """
        if not token or not token.startswith("scat_"):
            return None
        
        token_hash = cls.hash_token(token)
        
        # Find the token record
        result = await db.execute(
            select(UserAgentToken, User)
            .join(User)
            .where(UserAgentToken.token_hash == token_hash)
            .where(UserAgentToken.is_active == True)
        )
        
        row = result.first()
        if not row:
            logger.warning("Invalid agent token used", token_prefix=cls.get_token_prefix(token))
            return None
        
        token_record, user = row
        
        # Check expiration
        if token_record.expires_at and token_record.expires_at < datetime.now(timezone.utc):
            logger.warning(
                "Expired agent token used",
                token_id=token_record.token_id,
                token_prefix=token_record.token_prefix,
                expired_at=token_record.expires_at
            )
            return None
        
        # Update last used timestamp
        await db.execute(
            update(UserAgentToken)
            .where(UserAgentToken.token_id == token_record.token_id)
            .values(last_used_at=datetime.now(timezone.utc))
        )
        
        logger.debug(
            "Agent token validated",
            user_id=user.user_id,
            token_id=token_record.token_id,
            token_prefix=token_record.token_prefix
        )
        
        return user
    
    @classmethod
    async def list_user_tokens(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID
    ) -> List[UserAgentToken]:
        """List all active tokens for a user"""
        result = await db.execute(
            select(UserAgentToken)
            .where(UserAgentToken.user_id == user_id)
            .where(UserAgentToken.is_active == True)
            .order_by(UserAgentToken.created_at.desc())
        )
        
        return result.scalars().all()
    
    @classmethod
    async def revoke_token(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        token_id: uuid.UUID
    ) -> bool:
        """
        Revoke (deactivate) a token
        
        Returns:
            True if token was revoked, False if not found
        """
        result = await db.execute(
            update(UserAgentToken)
            .where(UserAgentToken.token_id == token_id)
            .where(UserAgentToken.user_id == user_id)
            .values(is_active=False, updated_at=datetime.now(timezone.utc))
        )
        
        if result.rowcount > 0:
            logger.info(
                "Agent token revoked",
                user_id=user_id,
                token_id=token_id
            )
            return True
        
        return False
    
    @classmethod
    async def revoke_all_tokens(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID
    ) -> int:
        """
        Revoke all tokens for a user
        
        Returns:
            Number of tokens revoked
        """
        result = await db.execute(
            update(UserAgentToken)
            .where(UserAgentToken.user_id == user_id)
            .where(UserAgentToken.is_active == True)
            .values(is_active=False, updated_at=datetime.now(timezone.utc))
        )
        
        revoked_count = result.rowcount
        
        if revoked_count > 0:
            logger.info(
                "All agent tokens revoked for user",
                user_id=user_id,
                revoked_count=revoked_count
            )
        
        return revoked_count 
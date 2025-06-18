"""
Bot management API endpoints

Handles CRUD operations for bots (collections of sources with access control).
"""

import uuid
from typing import List, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import structlog

from src.db.base import get_db_session
from src.db.models import User, Bot, Source, UserBotAccess
from src.db.mcp_credentials import get_bot_sources_with_credentials
from src.auth.mock import get_current_user

logger = structlog.get_logger()
router = APIRouter()


# Request/Response Models
class BotCreate(BaseModel):
    """Request to create a new bot"""
    name: str = Field(..., description="Display name for the bot")
    description: Optional[str] = None
    source_ids: List[uuid.UUID] = Field(..., description="List of source IDs to include in this bot")
    is_public: bool = Field(default=False, description="Whether the bot is publicly accessible")
    allowed_user_ids: Optional[List[uuid.UUID]] = Field(default=None, description="User IDs allowed to access this bot (if not public)")

class BotUpdate(BaseModel):
    """Request to update a bot"""
    name: Optional[str] = None
    description: Optional[str] = None
    source_ids: Optional[List[uuid.UUID]] = None
    is_public: Optional[bool] = None
    allowed_user_ids: Optional[List[uuid.UUID]] = None

class BotResponse(BaseModel):
    """Bot information response"""
    bot_id: uuid.UUID
    name: str
    description: Optional[str]
    source_ids: List[uuid.UUID]
    created_by_admin_id: uuid.UUID
    is_public: bool
    allowed_user_ids: List[uuid.UUID]
    created_at: datetime
    updated_at: Optional[datetime]

class BotWithSourcesResponse(BotResponse):
    """Bot response with source details"""
    sources: List[dict]  # Will contain source information
    tool_count: Optional[int]
    user_has_access: bool

class UserBotAccessResponse(BaseModel):
    """User bot access information"""
    user_id: uuid.UUID
    bot_id: uuid.UUID
    granted_at: datetime
    granted_by_admin_id: uuid.UUID


@router.post("/bots", response_model=BotResponse)
async def create_bot(
    bot_data: BotCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Create a new bot (admin-only functionality)"""
    
    # TODO: Add admin permission check
    # For now, any user can create bots
    
    # Verify all source IDs exist and are accessible
    if bot_data.source_ids:
        source_query = select(Source).where(
            Source.source_id.in_(bot_data.source_ids),
            Source.is_active == True
        )
        result = await db.execute(source_query)
        found_sources = result.scalars().all()
        
        if len(found_sources) != len(bot_data.source_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more source IDs are invalid or inactive"
            )
    
    # Create bot with timezone-aware datetime
    bot_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    
    bot = Bot(
        bot_id=bot_id,
        name=bot_data.name,
        description=bot_data.description,
        source_ids=bot_data.source_ids or [],
        created_by_admin_id=user.user_id,
        is_public=bot_data.is_public,
        allowed_user_ids=bot_data.allowed_user_ids or [],
        created_at=now,
        updated_at=now
    )
    
    db.add(bot)
    await db.flush()
    
    # Pre-capture values for response before commit
    response_data = {
        "bot_id": bot_id,
        "name": bot_data.name,
        "description": bot_data.description,
        "source_ids": bot_data.source_ids or [],
        "created_by_admin_id": user.user_id,
        "is_public": bot_data.is_public,
        "allowed_user_ids": bot_data.allowed_user_ids or [],
        "created_at": now,
        "updated_at": now
    }
    
    # Create user access records for allowed users
    if not bot_data.is_public and bot_data.allowed_user_ids:
        for user_id in bot_data.allowed_user_ids:
            access = UserBotAccess(
                user_id=user_id,
                bot_id=bot_id,
                granted_at=now,
                granted_by_admin_id=user.user_id
            )
            db.add(access)
    
    await db.commit()
    
    logger.info(
        "Bot created",
        bot_id=bot_id,
        name=bot_data.name,
        created_by=user.user_id,
        source_count=len(bot_data.source_ids or [])
    )
    
    return BotResponse(**response_data)


@router.get("/bots", response_model=List[BotResponse])
async def list_bots(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """List bots accessible to the user"""
    
    # Get public bots + bots user has explicit access to
    from sqlalchemy import or_
    
    # First get user's explicit access
    access_query = select(UserBotAccess.bot_id).where(
        UserBotAccess.user_id == user.user_id
    )
    access_result = await db.execute(access_query)
    accessible_bot_ids = [row[0] for row in access_result.fetchall()]
    
    # Query for accessible bots
    conditions = [Bot.is_public == True]
    if accessible_bot_ids:
        conditions.append(Bot.bot_id.in_(accessible_bot_ids))
    
    query = select(Bot).where(or_(*conditions))
    result = await db.execute(query)
    bots = result.scalars().all()
    
    return [
        BotResponse(
            bot_id=bot.bot_id,
            name=bot.name,
            description=bot.description,
            source_ids=bot.source_ids,
            created_by_admin_id=bot.created_by_admin_id,
            is_public=bot.is_public,
            allowed_user_ids=bot.allowed_user_ids,
            created_at=bot.created_at,
            updated_at=bot.updated_at
        )
        for bot in bots
    ]


@router.get("/bots/{bot_id}", response_model=BotWithSourcesResponse)
async def get_bot(
    bot_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get a specific bot with source details"""
    
    # Check if user has access to this bot
    bot_query = select(Bot).where(Bot.bot_id == bot_id)
    bot_result = await db.execute(bot_query)
    bot = bot_result.scalar_one_or_none()
    
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found"
        )
    
    # Check access permissions
    user_has_access = False
    if bot.is_public:
        user_has_access = True
    else:
        # Check explicit access
        access_query = select(UserBotAccess).where(
            UserBotAccess.user_id == user.user_id,
            UserBotAccess.bot_id == bot_id
        )
        access_result = await db.execute(access_query)
        user_has_access = access_result.scalar_one_or_none() is not None
    
    if not user_has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this bot"
        )
    
    # Get source details
    sources = []
    if bot.source_ids:
        source_query = select(Source).where(
            Source.source_id.in_(bot.source_ids),
            Source.is_active == True
        )
        source_result = await db.execute(source_query)
        source_objects = source_result.scalars().all()
        
        sources = [
            {
                "source_id": str(source.source_id),
                "name": source.name,
                "description": source.description,
                "server_type": source.server_type.value,
                "server_url": source.server_url
            }
            for source in source_objects
        ]
    
    # TODO: Get tool count from MCP client
    tool_count = len(bot.source_ids) * 8 if bot.source_ids else 0  # Estimate
    
    return BotWithSourcesResponse(
        bot_id=bot.bot_id,
        name=bot.name,
        description=bot.description,
        source_ids=bot.source_ids,
        created_by_admin_id=bot.created_by_admin_id,
        is_public=bot.is_public,
        allowed_user_ids=bot.allowed_user_ids,
        created_at=bot.created_at,
        updated_at=bot.updated_at,
        sources=sources,
        tool_count=tool_count,
        user_has_access=user_has_access
    )


@router.put("/bots/{bot_id}", response_model=BotResponse)
async def update_bot(
    bot_id: uuid.UUID,
    bot_data: BotUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Update a bot (admin-only functionality)"""
    
    # Get bot
    bot_query = select(Bot).where(Bot.bot_id == bot_id)
    bot_result = await db.execute(bot_query)
    bot = bot_result.scalar_one_or_none()
    
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found"
        )
    
    # TODO: Add admin permission check
    # For now, only allow the creator to update
    if bot.created_by_admin_id != user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this bot"
        )
    
    # Verify source IDs if provided
    if bot_data.source_ids is not None:
        if bot_data.source_ids:
            source_query = select(Source).where(
                Source.source_id.in_(bot_data.source_ids),
                Source.is_active == True
            )
            result = await db.execute(source_query)
            found_sources = result.scalars().all()
            
            if len(found_sources) != len(bot_data.source_ids):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="One or more source IDs are invalid or inactive"
                )
    
    # Update fields
    if bot_data.name is not None:
        bot.name = bot_data.name
    if bot_data.description is not None:
        bot.description = bot_data.description
    if bot_data.source_ids is not None:
        bot.source_ids = bot_data.source_ids
    if bot_data.is_public is not None:
        bot.is_public = bot_data.is_public
    if bot_data.allowed_user_ids is not None:
        bot.allowed_user_ids = bot_data.allowed_user_ids
        
        # Update user access records
        # First, remove existing access
        delete_query = select(UserBotAccess).where(UserBotAccess.bot_id == bot_id)
        delete_result = await db.execute(delete_query)
        for access in delete_result.scalars().all():
            await db.delete(access)
        
        # Add new access records if not public
        if not bot.is_public and bot_data.allowed_user_ids:
            for user_id in bot_data.allowed_user_ids:
                access = UserBotAccess(
                    user_id=user_id,
                    bot_id=bot.bot_id,
                    granted_at=datetime.now(timezone.utc),
                    granted_by_admin_id=user.user_id
                )
                db.add(access)
    
    bot.updated_at = datetime.now(timezone.utc)
    await db.commit()
    
    logger.info(
        "Bot updated",
        bot_id=bot.bot_id,
        name=bot.name,
        updated_by=user.user_id
    )
    
    return BotResponse(
        bot_id=bot.bot_id,
        name=bot.name,
        description=bot.description,
        source_ids=bot.source_ids,
        created_by_admin_id=bot.created_by_admin_id,
        is_public=bot.is_public,
        allowed_user_ids=bot.allowed_user_ids,
        created_at=bot.created_at,
        updated_at=bot.updated_at
    )


@router.delete("/bots/{bot_id}")
async def delete_bot(
    bot_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Delete a bot (admin-only functionality)"""
    
    # Get bot
    bot_query = select(Bot).where(Bot.bot_id == bot_id)
    bot_result = await db.execute(bot_query)
    bot = bot_result.scalar_one_or_none()
    
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found"
        )
    
    # TODO: Add admin permission check
    # For now, only allow the creator to delete
    if bot.created_by_admin_id != user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this bot"
        )
    
    # Delete user access records
    access_query = select(UserBotAccess).where(UserBotAccess.bot_id == bot_id)
    access_result = await db.execute(access_query)
    for access in access_result.scalars().all():
        await db.delete(access)
    
    # Delete bot
    await db.delete(bot)
    await db.commit()
    
    logger.info(
        "Bot deleted",
        bot_id=bot_id,
        name=bot.name,
        deleted_by=user.user_id
    )
    
    return {"message": "Bot deleted successfully"}


@router.post("/bots/{bot_id}/access", response_model=UserBotAccessResponse)
async def grant_bot_access(
    bot_id: uuid.UUID,
    user_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Grant a user access to a bot (admin-only functionality)"""
    
    # Get bot
    bot_query = select(Bot).where(Bot.bot_id == bot_id)
    bot_result = await db.execute(bot_query)
    bot = bot_result.scalar_one_or_none()
    
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found"
        )
    
    # TODO: Add admin permission check
    # For now, only allow the creator to grant access
    if bot.created_by_admin_id != user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify bot access"
        )
    
    # Check if access already exists
    existing_query = select(UserBotAccess).where(
        UserBotAccess.user_id == user_id,
        UserBotAccess.bot_id == bot_id
    )
    existing_result = await db.execute(existing_query)
    if existing_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has access to this bot"
        )
    
    # Create access record
    access = UserBotAccess(
        user_id=user_id,
        bot_id=bot_id,
        granted_at=datetime.now(timezone.utc),
        granted_by_admin_id=user.user_id
    )
    
    db.add(access)
    await db.commit()
    
    logger.info(
        "Bot access granted",
        bot_id=bot_id,
        user_id=user_id,
        granted_by=user.user_id
    )
    
    return UserBotAccessResponse(
        user_id=access.user_id,
        bot_id=access.bot_id,
        granted_at=access.granted_at,
        granted_by_admin_id=access.granted_by_admin_id
    )


@router.delete("/bots/{bot_id}/access/{user_id}")
async def revoke_bot_access(
    bot_id: uuid.UUID,
    user_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Revoke a user's access to a bot (admin-only functionality)"""
    
    # Get bot
    bot_query = select(Bot).where(Bot.bot_id == bot_id)
    bot_result = await db.execute(bot_query)
    bot = bot_result.scalar_one_or_none()
    
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found"
        )
    
    # TODO: Add admin permission check
    # For now, only allow the creator to revoke access
    if bot.created_by_admin_id != user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify bot access"
        )
    
    # Find and delete access record
    access_query = select(UserBotAccess).where(
        UserBotAccess.user_id == user_id,
        UserBotAccess.bot_id == bot_id
    )
    access_result = await db.execute(access_query)
    access = access_result.scalar_one_or_none()
    
    if not access:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User access not found"
        )
    
    await db.delete(access)
    await db.commit()
    
    logger.info(
        "Bot access revoked",
        bot_id=bot_id,
        user_id=user_id,
        revoked_by=user.user_id
    )
    
    return {"message": "Bot access revoked successfully"} 
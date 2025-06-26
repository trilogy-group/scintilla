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
from src.db.mcp_credentials import get_bot_sources_with_credentials, store_source_credentials
from src.auth.google_oauth import get_current_user
from src.api.models import BotCreate, BotUpdate, BotResponse, BotWithSourcesResponse, BotSourceCreate, BotSourceUpdate, SourceResponse, UserBotAccessResponse

logger = structlog.get_logger()
router = APIRouter()


# All models now imported from src.api.models


@router.post("/bots", response_model=BotResponse)
async def create_bot(
    bot_data: BotCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Create a new bot with dedicated sources (admin-only functionality)"""
    
    # TODO: Add admin permission check
    # For now, any user can create bots
    
    # Create bot with timezone-aware datetime
    bot_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    
    bot = Bot(
        bot_id=bot_id,
        name=bot_data.name,
        description=bot_data.description,
        source_ids=[],  # Will be populated after sources are created
        created_by_admin_id=user.user_id,
        is_public=bot_data.is_public,
        allowed_user_ids=bot_data.allowed_user_ids or [],
        created_at=now,
        updated_at=now
    )
    
    db.add(bot)
    await db.flush()  # Get the bot ID without committing
    
    # Create dedicated sources for this bot
    created_source_ids = []
    for source_data in bot_data.sources:
        # Create source owned by the bot (no server_type validation needed)
        source_id = uuid.uuid4()
        source = Source(
            source_id=source_id,
            name=source_data.name,
            description=source_data.description,
            instructions=source_data.instructions,
            server_url=source_data.server_url,
            auth_headers={},  # Will be populated by credentials
            owner_user_id=None,  # Bot-owned, not user-owned
            owner_bot_id=bot_id,
            is_active=True,
            created_at=now,
            updated_at=now
        )
        
        db.add(source)
        await db.flush()  # Get the source ID
        
        # Store credentials for the source
        try:
            await store_source_credentials(
                db=db,
                source_id=source_id,
                credentials=source_data.credentials
            )
            created_source_ids.append(source_id)
            
        except Exception as e:
            await db.rollback()
            logger.error("Failed to store source credentials for bot", 
                        bot_id=bot_id, source_id=source_id, error=str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to store credentials for source: {source_data.name}"
            )
    
    # Update bot with created source IDs
    bot.source_ids = created_source_ids
    
    # Create user access records for allowed users
    if not bot_data.is_public and bot_data.allowed_user_ids:
        for user_id in bot_data.allowed_user_ids:
            access = UserBotAccess(
                user_id=user_id,
                bot_id=bot_id,
                granted_at=now
            )
            db.add(access)
    
    await db.commit()
    
    logger.info(
        "Bot created with dedicated sources",
        bot_id=bot_id,
        name=bot_data.name,
        created_by=user.user_id,
        source_count=len(created_source_ids)
    )
    
    return BotResponse(
        bot_id=bot_id,
        name=bot_data.name,
        description=bot_data.description,
        source_ids=created_source_ids,
        created_by_admin_id=user.user_id,
        is_public=bot_data.is_public,
        allowed_user_ids=bot_data.allowed_user_ids or [],
        created_at=now,
        updated_at=now
    )


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
    conditions = [Bot.is_public.is_(True)]
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
    
    # Get bot-owned sources
    sources = []
    source_query = select(Source).where(
        Source.owner_bot_id == bot_id,
        Source.is_active.is_(True)
    )
    source_result = await db.execute(source_query)
    source_objects = source_result.scalars().all()
    
    # Build sources with tool cache information
    sources = []
    for source in source_objects:
        # Extract ALL source attributes early to avoid greenlet issues
        source_id = source.source_id
        source_name = source.name
        source_description = source.description
        source_instructions = source.instructions
        source_server_url = source.server_url
        source_owner_user_id = source.owner_user_id
        source_owner_bot_id = source.owner_bot_id
        source_is_active = source.is_active
        source_created_at = source.created_at
        source_updated_at = source.updated_at
        source_tools_cache_status = source.tools_cache_status
        source_tools_last_cached_at = source.tools_last_cached_at
        source_tools_cache_error = source.tools_cache_error
        
        # Get cached tools for this source
        cached_tools = []
        cached_tool_count = 0
        
        try:
            from src.db.tool_cache import ToolCacheService
            tools_data = await ToolCacheService.get_cached_tools_for_sources(db, [source_id])
            if tools_data:
                cached_tools = [tool["name"] for tool in tools_data]
                cached_tool_count = len(cached_tools)
        except Exception as e:
            logger.warning("Failed to get cached tools for bot source", 
                          source_id=source_id, error=str(e))
        
        sources.append(SourceResponse(
            source_id=source_id,
            name=source_name,
            description=source_description,
            instructions=source_instructions,
            server_url=source_server_url,
            owner_user_id=source_owner_user_id,
            owner_bot_id=source_owner_bot_id,
            is_active=source_is_active,
            created_at=source_created_at,
            updated_at=source_updated_at,
            tools_cache_status=source_tools_cache_status,
            tools_last_cached_at=source_tools_last_cached_at,
            tools_cache_error=source_tools_cache_error,
            cached_tool_count=cached_tool_count,
            cached_tools=cached_tools
        ))
    
    # TODO: Get tool count from MCP client
    tool_count = len(sources) * 8 if sources else 0  # Estimate
    
    return BotWithSourcesResponse(
        bot_id=bot.bot_id,
        name=bot.name,
        description=bot.description,
        source_ids=bot.source_ids,  # Keep for backward compatibility
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
    
    # Extract ALL bot attributes early to avoid greenlet issues
    bot_id_value = bot.bot_id
    bot_name = bot.name
    bot_description = bot.description
    bot_source_ids = bot.source_ids
    bot_created_by_admin_id = bot.created_by_admin_id
    bot_is_public = bot.is_public
    bot_allowed_user_ids = bot.allowed_user_ids
    bot_created_at = bot.created_at
    bot_updated_at = bot.updated_at
    
    # Update basic bot fields and track changes
    updated_name = bot_data.name if bot_data.name is not None else bot_name
    updated_description = bot_data.description if bot_data.description is not None else bot_description
    updated_is_public = bot_data.is_public if bot_data.is_public is not None else bot_is_public
    updated_allowed_user_ids = bot_data.allowed_user_ids if bot_data.allowed_user_ids is not None else bot_allowed_user_ids
    
    if bot_data.name is not None:
        bot.name = bot_data.name
    if bot_data.description is not None:
        bot.description = bot_data.description
    if bot_data.is_public is not None:
        bot.is_public = bot_data.is_public
    if bot_data.allowed_user_ids is not None:
        bot.allowed_user_ids = bot_data.allowed_user_ids
        
        # Update user access records
        # First, remove existing access
        delete_query = select(UserBotAccess).where(UserBotAccess.bot_id == bot_id)
        delete_result = await db.execute(delete_query)
        existing_access = delete_result.scalars().all()
        for access in existing_access:
            await db.delete(access)
        
        # Add new access records if not public
        if not bot.is_public and bot_data.allowed_user_ids:
            for user_id in bot_data.allowed_user_ids:
                access = UserBotAccess(
                    user_id=user_id,
                    bot_id=bot_id_value,  # Use extracted value instead of bot.bot_id
                    granted_at=datetime.now(timezone.utc)
                )
                db.add(access)
    
    # Handle source updates
    if bot_data.sources is not None:
        # Get current bot sources
        current_sources_query = select(Source).where(
            Source.owner_bot_id == bot_id,
            Source.is_active.is_(True)
        )
        current_sources_result = await db.execute(current_sources_query)
        current_sources_list = current_sources_result.scalars().all()
        
        # Extract ALL source data early to avoid greenlet issues
        current_sources_data = {}
        for source in current_sources_list:
            source_id_str = str(source.source_id)
            current_sources_data[source_id_str] = {
                'object': source,
                'source_id': source.source_id,
                'name': source.name,
                'description': source.description,
                'instructions': source.instructions,
                'server_url': source.server_url,
                'created_at': source.created_at,
                'updated_at': source.updated_at
            }
        
        updated_source_ids = []
        
        for source_update in bot_data.sources:
            if source_update.source_id:
                # Update existing source
                source_id_str = str(source_update.source_id)
                if source_id_str in current_sources_data:
                    source_data = current_sources_data[source_id_str]
                    source = source_data['object']
                    source_id_value = source_data['source_id']  # Use extracted value
                    
                    source.name = source_update.name
                    source.description = source_update.description
                    source.instructions = source_update.instructions
                    source.server_url = source_update.server_url
                    source.updated_at = datetime.now(timezone.utc)
                    
                    # Update credentials if provided
                    if source_update.credentials and source_update.credentials.get("api_key"):
                        try:
                            await store_source_credentials(
                                db=db,
                                source_id=source_id_value,  # Use extracted value
                                credentials=source_update.credentials
                            )
                        except Exception as e:
                            logger.error("Failed to update source credentials", 
                                       source_id=source_id_value, error=str(e))  # Use extracted value
                    
                    updated_source_ids.append(source_id_value)  # Use extracted value
            else:
                # Create new source
                source_id = uuid.uuid4()
                new_source = Source(
                    source_id=source_id,
                    name=source_update.name,
                    description=source_update.description,
                    instructions=source_update.instructions,
                    server_url=source_update.server_url,
                    auth_headers={},
                    owner_user_id=None,
                    owner_bot_id=bot_id,
                    is_active=True,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )
                
                db.add(new_source)
                await db.flush()  # Get the source ID
                
                # Store credentials for new source
                if source_update.credentials:
                    try:
                        await store_source_credentials(
                            db=db,
                            source_id=source_id,
                            credentials=source_update.credentials
                        )
                    except Exception as e:
                        logger.error("Failed to store new source credentials", 
                                   source_id=source_id, error=str(e))
                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Failed to store credentials for new source: {source_update.name}"
                        )
                
                updated_source_ids.append(source_id)
        
        # Deactivate sources not in the update list
        for source_id_str, source_data in current_sources_data.items():
            source_id_value = source_data['source_id']  # Use extracted value
            if source_id_value not in updated_source_ids:
                source = source_data['object']
                source.is_active = False
                source.updated_at = datetime.now(timezone.utc)
        
        # Update bot's source_ids list
        bot.source_ids = updated_source_ids
        final_source_ids = updated_source_ids
    else:
        final_source_ids = bot_source_ids
    
    final_updated_at = datetime.now(timezone.utc)
    bot.updated_at = final_updated_at
    await db.commit()
    
    logger.info(
        "Bot updated",
        bot_id=bot_id_value,   # Use extracted value
        name=updated_name,     # Use tracked value
        updated_by=user.user_id
    )
    
    return BotResponse(
        bot_id=bot_id_value,                    # Use extracted value
        name=updated_name,                      # Use tracked value
        description=updated_description,        # Use tracked value
        source_ids=final_source_ids,           # Use tracked value
        created_by_admin_id=bot_created_by_admin_id,  # Use extracted value
        is_public=updated_is_public,           # Use tracked value
        allowed_user_ids=updated_allowed_user_ids,    # Use tracked value
        created_at=bot_created_at,             # Use extracted value
        updated_at=final_updated_at            # Use tracked value
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
    
    # Extract values early to avoid greenlet issues
    bot_name = bot.name
    
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
        name=bot_name,  # Use extracted value
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
    now = datetime.now(timezone.utc)
    access = UserBotAccess(
        user_id=user_id,
        bot_id=bot_id,
        granted_at=now,
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
        user_id=user_id,  # Use parameter instead of access.user_id
        bot_id=bot_id,    # Use parameter instead of access.bot_id
        granted_at=now,   # Use extracted value
        granted_by_admin_id=user.user_id  # Use direct value
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
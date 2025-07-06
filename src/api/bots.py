"""
Bots API endpoints

Handles bot creation, retrieval, update, and deletion with source management.
Updated to support user ownership and bot-source associations.
"""

import uuid
from typing import List, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
import structlog

from src.db.base import get_db_session
from src.db.models import User, Bot, Source, UserBotAccess, BotSourceAssociation, SourceShare
from src.auth.google_oauth import get_current_user
from src.api.models import (
    BotCreate, BotUpdate, BotResponse, BotWithSourcesResponse, 
    BotSourceCreate, BotSourceUpdate, SourceResponse, UserBotAccessResponse,
    BotSourceConfig, BotSourceAssociationResponse, UserResponse
)

logger = structlog.get_logger()
router = APIRouter()


async def get_accessible_bot_ids(db: AsyncSession, user_id: uuid.UUID) -> List[uuid.UUID]:
    """Get bot IDs user can access: owned + shared + public"""
    
    # User's own bots
    owned_bots = await db.execute(
        select(Bot.bot_id).where(Bot.created_by_user_id == user_id)
    )
    
    # Public bots
    public_bots = await db.execute(
        select(Bot.bot_id).where(Bot.is_public == True)
    )
    
    # Explicitly shared bots
    shared_bots = await db.execute(
        select(UserBotAccess.bot_id).where(UserBotAccess.user_id == user_id)
    )
    
    all_bot_ids = set()
    all_bot_ids.update(owned_bots.scalars())
    all_bot_ids.update(public_bots.scalars())
    all_bot_ids.update(shared_bots.scalars())
    
    return list(all_bot_ids)


async def get_accessible_sources(db: AsyncSession, user_id: uuid.UUID) -> List[Source]:
    """Get all sources user can access: owned + shared + bot-owned from accessible bots"""
    
    # User's own sources
    user_sources_query = select(Source).where(Source.owner_user_id == user_id, Source.is_active == True)
    user_sources_result = await db.execute(user_sources_query)
    user_sources = user_sources_result.scalars().all()
    
    # Sources shared with user
    shared_sources_query = (
        select(Source)
        .join(SourceShare, Source.source_id == SourceShare.source_id)
        .where(SourceShare.shared_with_user_id == user_id, Source.is_active == True)
    )
    shared_sources_result = await db.execute(shared_sources_query)
    shared_sources = shared_sources_result.scalars().all()
    
    # Bot-owned sources from bots user has access to
    accessible_bot_ids = await get_accessible_bot_ids(db, user_id)
    if accessible_bot_ids:
        bot_sources_query = select(Source).where(
            Source.owner_bot_id.in_(accessible_bot_ids),
            Source.is_active == True
        )
        bot_sources_result = await db.execute(bot_sources_query)
        bot_sources = bot_sources_result.scalars().all()
    else:
        bot_sources = []
    
    # Combine and deduplicate
    all_sources = {}
    for source in list(user_sources) + list(shared_sources) + list(bot_sources):
        all_sources[source.source_id] = source
    
    return list(all_sources.values())


async def get_sources_for_bot_config(db: AsyncSession, user_id: uuid.UUID) -> List[Source]:
    """Get sources available for bot configuration: user's own sources + sources shared with user (NO bot-owned sources)"""
    
    # User's own sources
    user_sources_query = select(Source).where(Source.owner_user_id == user_id, Source.is_active == True)
    user_sources_result = await db.execute(user_sources_query)
    user_sources = user_sources_result.scalars().all()
    
    # Sources shared with user
    shared_sources_query = (
        select(Source)
        .join(SourceShare, Source.source_id == SourceShare.source_id)
        .where(SourceShare.shared_with_user_id == user_id, Source.is_active == True)
    )
    shared_sources_result = await db.execute(shared_sources_query)
    shared_sources = shared_sources_result.scalars().all()
    
    # NOTE: We intentionally exclude bot-owned sources from being available for other bots
    # to prevent circular dependencies and keep bot source ownership clear
    
    # Combine and deduplicate (only user sources + shared sources)
    all_sources = {}
    for source in list(user_sources) + list(shared_sources):
        all_sources[source.source_id] = source
    
    return list(all_sources.values())


async def create_bot_source_associations(
    db: AsyncSession, 
    bot_id: uuid.UUID, 
    source_configs: List[BotSourceConfig],
    user_id: uuid.UUID
) -> List[uuid.UUID]:
    """Create bot-source associations based on configuration"""
    
    created_source_ids = []
    
    for config in source_configs:
        if config.type == "create" and config.create_data:
            # Create new bot-owned source
            source_data = config.create_data
            
            # Prepare credentials
            credentials = source_data.credentials or {}
            auth_headers = credentials.get("auth_headers", {})
            
            new_source = Source(
                source_id=uuid.uuid4(),
                name=source_data.name,
                description=source_data.description,
                instructions=source_data.instructions,
                server_url=source_data.server_url,
                auth_headers=auth_headers,
                owner_bot_id=bot_id,
                is_active=True
            )
            
            db.add(new_source)
            await db.flush()  # Get the source_id
            
            # Create association
            association = BotSourceAssociation(
                bot_id=bot_id,
                source_id=new_source.source_id,
                custom_instructions=source_data.instructions  # Use source instructions as custom instructions
            )
            db.add(association)
            created_source_ids.append(new_source.source_id)
            
            logger.info("Created new bot-owned source", source_id=new_source.source_id, bot_id=bot_id)
            
        elif config.type == "reference" and config.reference_data:
            # Reference existing source
            ref_data = config.reference_data
            
            # Verify user has access to the source
            accessible_sources = await get_accessible_sources(db, user_id)
            accessible_source_ids = [s.source_id for s in accessible_sources]
            
            if ref_data.source_id not in accessible_source_ids:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"You don't have access to source {ref_data.source_id}"
                )
            
            # Create association
            association = BotSourceAssociation(
                bot_id=bot_id,
                source_id=ref_data.source_id,
                custom_instructions=ref_data.custom_instructions
            )
            db.add(association)
            created_source_ids.append(ref_data.source_id)
            
            logger.info("Created bot-source association", source_id=ref_data.source_id, bot_id=bot_id)
    
    return created_source_ids


@router.post("/bots", response_model=BotResponse)
async def create_bot(
    bot_data: BotCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Create a new bot (any user can create bots)"""
    
    try:
        bot_id = uuid.uuid4()
        
        # Handle legacy sources format for backward compatibility
        source_configs = bot_data.source_configs
        if bot_data.sources and not source_configs:
            # Convert legacy sources to new format
            source_configs = [
                BotSourceConfig(
                    type="create",
                    create_data=source
                ) for source in bot_data.sources
            ]
        
        # Create bot
        new_bot = Bot(
            bot_id=bot_id,
            name=bot_data.name,
            description=bot_data.description,
            created_by_user_id=user.user_id,  # User ownership, not admin
            is_public=bot_data.is_public,
            source_ids=[]  # Keep empty for backward compatibility
        )
        
        db.add(new_bot)
        await db.flush()  # Get the bot in the session
        
        # Create source associations
        if source_configs:
            created_source_ids = await create_bot_source_associations(
                db, bot_id, source_configs, user.user_id
            )
            
            # Update source_ids for backward compatibility
            new_bot.source_ids = created_source_ids
        
        # Handle bot sharing
        if bot_data.shared_with_users:
            for shared_user_id in bot_data.shared_with_users:
                access = UserBotAccess(
                    user_id=shared_user_id,
                    bot_id=bot_id
                )
                db.add(access)
        
        await db.commit()
        await db.refresh(new_bot)
        
        logger.info("Bot created successfully", bot_id=bot_id, user_id=user.user_id)
        
        return BotResponse(
            bot_id=new_bot.bot_id,
            name=new_bot.name,
            description=new_bot.description,
            source_ids=new_bot.source_ids,
            created_by_user_id=new_bot.created_by_user_id,
            is_public=new_bot.is_public,
            shared_with_users=bot_data.shared_with_users or [],
            created_at=new_bot.created_at,
            updated_at=new_bot.updated_at
        )
        
    except Exception as e:
        await db.rollback()
        logger.error("Bot creation failed", error=str(e), user_id=user.user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create bot: {str(e)}"
        )


@router.get("/bots", response_model=List[BotResponse])
async def get_bots(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get all bots accessible to the user"""
    
    try:
        accessible_bot_ids = await get_accessible_bot_ids(db, user.user_id)
        
        if not accessible_bot_ids:
            return []
        
        result = await db.execute(
            select(Bot)
            .where(Bot.bot_id.in_(accessible_bot_ids))
            .order_by(Bot.created_at.desc())
        )
        bots = result.scalars().all()
        
        bot_responses = []
        for bot in bots:
            # Get shared user IDs for this bot
            shared_users_result = await db.execute(
                select(UserBotAccess.user_id).where(UserBotAccess.bot_id == bot.bot_id)
            )
            shared_user_ids = list(shared_users_result.scalars())
            
            bot_responses.append(BotResponse(
                bot_id=bot.bot_id,
                name=bot.name,
                description=bot.description,
                source_ids=bot.source_ids,
                created_by_user_id=bot.created_by_user_id,
                is_public=bot.is_public,
                shared_with_users=shared_user_ids,
                created_at=bot.created_at,
                updated_at=bot.updated_at
            ))
        
        return bot_responses
        
    except Exception as e:
        logger.error("Failed to fetch bots", error=str(e), user_id=user.user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch bots: {str(e)}"
        )


# Add endpoint to get available sources for bot configuration (MUST come before /bots/{bot_id})
@router.get("/bots/available-sources", response_model=List[SourceResponse])
async def get_available_sources(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get all sources accessible to the user for bot configuration"""
    
    try:
        accessible_sources = await get_sources_for_bot_config(db, user.user_id)
        
        source_responses = []
        for source in accessible_sources:
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
            
            # Determine ownership type and sharing status
            if source_owner_user_id == user.user_id:
                owner_type = "user"
                is_shared = False
            elif source_owner_bot_id:
                owner_type = "bot"
                is_shared = False  # User has access via bot ownership
            else:
                owner_type = "user"  # Shared by another user
                is_shared = True
            
            # Get cached tools using proper service to avoid greenlet issues
            cached_tool_count = 0
            try:
                from src.db.tool_cache import ToolCacheService
                tools_data = await ToolCacheService.get_cached_tools_for_sources(db, [source_id])
                if tools_data:
                    cached_tool_count = len(tools_data)
            except Exception as tools_error:
                logger.warning("Failed to get cached tools for source", 
                              source_id=source_id, error=str(tools_error))
            
            source_responses.append(SourceResponse(
                source_id=source_id,
                name=source_name,
                description=source_description,
                instructions=source_instructions,
                server_url=source_server_url,
                owner_user_id=source_owner_user_id,
                owner_bot_id=source_owner_bot_id,
                owner_type=owner_type,
                is_shared_with_user=is_shared,
                is_active=source_is_active,
                created_at=source_created_at,
                updated_at=source_updated_at,
                tools_cache_status=source_tools_cache_status,
                tools_last_cached_at=source_tools_last_cached_at,
                tools_cache_error=source_tools_cache_error,
                cached_tool_count=cached_tool_count
            ))
        
        return source_responses
        
    except Exception as e:
        logger.error("Failed to fetch available sources", error=str(e), user_id=user.user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch available sources: {str(e)}"
        )


@router.get("/bots/{bot_id}", response_model=BotWithSourcesResponse)
async def get_bot(
    bot_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get detailed bot information with sources"""
    
    try:
        # Check if user has access to this bot
        accessible_bot_ids = await get_accessible_bot_ids(db, user.user_id)
        
        if bot_id not in accessible_bot_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bot not found or access denied"
            )
        
        # Get bot with associations
        bot_result = await db.execute(
            select(Bot)
            .options(selectinload(Bot.source_associations))
            .where(Bot.bot_id == bot_id)
        )
        bot = bot_result.scalar_one_or_none()
        
        if not bot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bot not found"
            )
        
        # Get source details for associations
        source_associations = []
        legacy_sources = []
        total_tools = 0
        
        for assoc in bot.source_associations:
            # Get source details
            source_result = await db.execute(
                select(Source).where(Source.source_id == assoc.source_id)
            )
            source = source_result.scalar_one_or_none()
            
            if source:
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
                
                # Determine source type
                if source_owner_user_id == user.user_id:
                    source_type = "owned"
                elif source_owner_bot_id == bot_id:
                    source_type = "bot_owned"
                else:
                    source_type = "shared"
                
                # Get cached tools using proper service to avoid greenlet issues
                cached_tool_count = 0
                try:
                    from src.db.tool_cache import ToolCacheService
                    tools_data = await ToolCacheService.get_cached_tools_for_sources(db, [source_id])
                    if tools_data:
                        cached_tool_count = len(tools_data)
                except Exception as tools_error:
                    logger.warning("Failed to get cached tools for source", 
                                  source_id=source_id, error=str(tools_error))
                
                # Create association response
                source_associations.append(BotSourceAssociationResponse(
                    source_id=source_id,
                    source_name=source_name,
                    custom_instructions=assoc.custom_instructions,
                    source_type=source_type,
                    created_at=assoc.created_at,
                    cached_tool_count=cached_tool_count,
                    tools_cache_status=source_tools_cache_status,
                    tools_last_cached_at=source_tools_last_cached_at
                ))
                
                # Legacy source response for backward compatibility
                legacy_sources.append(SourceResponse(
                    source_id=source_id,
                    name=source_name,
                    description=source_description,
                    instructions=source_instructions,
                    server_url=source_server_url,
                    owner_user_id=source_owner_user_id,
                    owner_bot_id=source_owner_bot_id,
                    owner_type="user" if source_owner_user_id else "bot" if source_owner_bot_id else None,
                    is_active=source_is_active,
                    created_at=source_created_at,
                    updated_at=source_updated_at,
                    tools_cache_status=source_tools_cache_status,
                    tools_last_cached_at=source_tools_last_cached_at,
                    tools_cache_error=source_tools_cache_error,
                    cached_tool_count=cached_tool_count
                ))
                
                total_tools += cached_tool_count
        
        # Get shared user IDs
        shared_users_result = await db.execute(
            select(UserBotAccess.user_id).where(UserBotAccess.bot_id == bot_id)
        )
        shared_user_ids = list(shared_users_result.scalars())
        
        return BotWithSourcesResponse(
            bot_id=bot.bot_id,
            name=bot.name,
            description=bot.description,
            source_ids=bot.source_ids,  # Legacy
            created_by_user_id=bot.created_by_user_id,
            is_public=bot.is_public,
            shared_with_users=shared_user_ids,
            created_at=bot.created_at,
            updated_at=bot.updated_at,
            sources=legacy_sources,  # Legacy
            source_associations=source_associations,  # New
            tool_count=total_tools,
            user_has_access=True
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to fetch bot details", error=str(e), bot_id=bot_id, user_id=user.user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch bot details: {str(e)}"
        )


# Add endpoint to get all users for sharing
@router.get("/users", response_model=List[UserResponse])
async def get_users(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get all users for sharing purposes"""
    
    try:
        result = await db.execute(
            select(User)
            .where(User.user_id != user.user_id)  # Exclude current user
            .order_by(User.name)
        )
        users = result.scalars().all()
        
        return [
            UserResponse(
                user_id=u.user_id,
                email=u.email,
                name=u.name,
                picture_url=u.picture_url,
                created_at=u.created_at
            )
            for u in users
        ]
        
    except Exception as e:
        logger.error("Failed to fetch users", error=str(e), user_id=user.user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch users: {str(e)}"
        )


@router.delete("/bots/{bot_id}")
async def delete_bot(
    bot_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Delete a bot (only owner can delete)"""
    
    try:
        # Get bot
        result = await db.execute(select(Bot).where(Bot.bot_id == bot_id))
        bot = result.scalar_one_or_none()
        
        if not bot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bot not found"
            )
        
        # Check ownership
        if bot.created_by_user_id != user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the bot owner can delete it"
            )
        
        # Delete bot using ORM method to trigger cascade deletes
        await db.delete(bot)
        await db.commit()
        
        logger.info("Bot deleted successfully", bot_id=bot_id, user_id=user.user_id)
        
        return {"message": "Bot deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("Bot deletion failed", error=str(e), bot_id=bot_id, user_id=user.user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete bot: {str(e)}"
        )


@router.put("/bots/{bot_id}", response_model=BotResponse)
async def update_bot(
    bot_id: uuid.UUID,
    bot_data: BotUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Update an existing bot (only owner can update)"""
    
    try:
        # Get bot
        result = await db.execute(select(Bot).where(Bot.bot_id == bot_id))
        bot = result.scalar_one_or_none()
        
        if not bot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bot not found"
            )
        
        # Check ownership
        if bot.created_by_user_id != user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the bot owner can update it"
            )
        
        # Extract ALL bot attributes early to avoid greenlet issues
        bot_id_value = bot.bot_id
        original_name = bot.name
        original_description = bot.description
        original_is_public = bot.is_public
        original_source_ids = bot.source_ids
        original_created_by_user_id = bot.created_by_user_id
        original_created_at = bot.created_at
        original_updated_at = bot.updated_at
        
        # Track changes for response
        updated_name = bot_data.name if bot_data.name is not None else original_name
        updated_description = bot_data.description if bot_data.description is not None else original_description
        updated_is_public = bot_data.is_public if bot_data.is_public is not None else original_is_public
        updated_source_ids = original_source_ids  # Will be updated if source_configs provided
        updated_shared_with_users = bot_data.shared_with_users if bot_data.shared_with_users is not None else []
        
        # Update basic fields
        if bot_data.name is not None:
            bot.name = bot_data.name
        if bot_data.description is not None:
            bot.description = bot_data.description
        if bot_data.is_public is not None:
            bot.is_public = bot_data.is_public
        
        # Handle source configuration updates
        if bot_data.source_configs:
            # Remove existing associations
            await db.execute(
                delete(BotSourceAssociation).where(BotSourceAssociation.bot_id == bot_id_value)
            )
            
            # Create new associations
            created_source_ids = await create_bot_source_associations(
                db, bot_id_value, bot_data.source_configs, user.user_id
            )
            
            # Update source_ids for backward compatibility
            bot.source_ids = created_source_ids
            updated_source_ids = created_source_ids  # Track the updated value
        
        # Handle sharing updates
        if bot_data.shared_with_users is not None:
            # Remove existing access records
            await db.execute(
                delete(UserBotAccess).where(UserBotAccess.bot_id == bot_id_value)
            )
            
            # Add new access records
            for shared_user_id in bot_data.shared_with_users:
                access = UserBotAccess(
                    user_id=shared_user_id,
                    bot_id=bot_id_value
                )
                db.add(access)
        
        await db.commit()
        
        logger.info("Bot updated successfully", bot_id=bot_id_value, user_id=user.user_id)
        
        # Use tracked values instead of accessing model attributes after commit
        return BotResponse(
            bot_id=bot_id_value,
            name=updated_name,
            description=updated_description,
            source_ids=updated_source_ids,
            created_by_user_id=original_created_by_user_id,
            is_public=updated_is_public,
            shared_with_users=updated_shared_with_users,
            created_at=original_created_at,
            updated_at=original_updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("Bot update failed", error=str(e), bot_id=bot_id, user_id=user.user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update bot: {str(e)}"
        ) 
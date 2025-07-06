"""
Sources management API endpoints

Handles CRUD operations for sources (individual MCP server connections owned by users).
"""

import uuid
from uuid import UUID
from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, or_, func
from sqlalchemy.orm import selectinload
import structlog

from src.db.base import get_db_session
from src.db.models import User, Source, SourceTool, Bot, UserBotAccess, BotSourceAssociation, SourceShare
from src.auth.google_oauth import get_current_user
from src.api.models import SourceCreate, SourceUpdate, SourceResponse, RefreshResponse, ErrorResponse
from src.db.mcp_credentials import store_source_credentials, get_user_sources_with_credentials, MCPCredentialManager
from src.db.tool_cache import ToolCacheService
from src.agents.fast_mcp import FastMCPService

logger = structlog.get_logger()
router = APIRouter()


# Request/Response Models

class SourceWithStatusResponse(SourceResponse):
    """Source response with connection status"""
    is_connected: bool
    last_connection_check: Optional[datetime]
    connection_error: Optional[str]
    tool_count: Optional[int]


class BotUsingSource(BaseModel):
    """Bot that is using a source"""
    bot_id: uuid.UUID
    bot_name: str
    custom_instructions: Optional[str]


class SourceDeletionWarning(BaseModel):
    """Warning response when source is used by bots"""
    warning: bool = True
    message: str
    source_name: str
    bots_using_source: List[BotUsingSource]


@router.post("", response_model=SourceResponse)
async def create_source(
    source_data: SourceCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Create a new MCP source for the user"""
    
    try:
        # Create source with simplified structure (no server_type validation needed)
        source_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        
        source = Source(
            source_id=source_id,
            name=source_data.name,
            description=source_data.description,
            instructions=source_data.instructions,
            server_url=source_data.server_url,
            auth_headers={},  # Will be populated by credentials
            owner_user_id=user.user_id,
            is_active=True,
            is_public=source_data.is_public or False,
            created_at=now,
            updated_at=now
        )
        
        db.add(source)
        await db.flush()  # Get the source ID without committing
        
        # Store credentials using simplified system
        from src.db.mcp_credentials import SimplifiedCredentialManager
        
        auth_headers = source_data.credentials.get("auth_headers", {})
        success = await SimplifiedCredentialManager.store_source_auth(
            db=db,
            source_id=source_id,
            server_url=source_data.server_url,
            auth_headers=auth_headers
        )
        
        if not success:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to store source credentials"
            )
        
        await db.commit()
        
        # Get cached tools for response
        cached_tools = []
        cached_tool_count = 0
        
        logger.info(
            "Source created",
            source_id=source_id,
            name=source_data.name,
            user_id=user.user_id
        )
        
        return SourceResponse(
            source_id=source_id,
            name=source_data.name,
            description=source_data.description,
            instructions=source_data.instructions,
            server_url=source_data.server_url,
            owner_user_id=user.user_id,
            owner_bot_id=None,
            is_public=source_data.is_public or False,
            is_active=True,
            created_at=now,
            updated_at=now,
            tools_cache_status="pending",
            tools_last_cached_at=None,
            tools_cache_error=None,
            cached_tool_count=cached_tool_count,
            cached_tools=cached_tools
        )
        
    except Exception as e:
        await db.rollback()
        logger.error("Failed to create source", error=str(e), user_id=user.user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create source: {str(e)}"
        )


@router.get("", response_model=List[SourceResponse])
async def list_user_sources(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """List sources owned by the current user with tool information"""
    
    query = select(Source).where(
        Source.owner_user_id == user.user_id,
        Source.is_active.is_(True)
    )
    
    result = await db.execute(query)
    sources = result.scalars().all()
    
    source_responses = []
    
    for source in sources:
        # Extract ALL source attributes early to avoid greenlet issues
        source_id = source.source_id
        source_name = source.name
        source_description = source.description
        source_instructions = source.instructions
        source_server_url = source.server_url
        source_owner_user_id = source.owner_user_id
        source_owner_bot_id = source.owner_bot_id
        source_is_active = source.is_active
        source_is_public = source.is_public
        source_created_at = source.created_at
        source_updated_at = source.updated_at
        source_tools_cache_status = source.tools_cache_status
        source_tools_last_cached_at = source.tools_last_cached_at
        source_tools_cache_error = source.tools_cache_error
        
        # Get cached tools for this source
        cached_tools = []
        cached_tool_count = 0
        
        try:
            tools_data = await ToolCacheService.get_cached_tools_for_sources(db, [source_id])
            if tools_data:
                cached_tools = [tool["name"] for tool in tools_data]
                cached_tool_count = len(cached_tools)
        except Exception as e:
            logger.warning("Failed to get cached tools for source", 
                          source_id=source_id, error=str(e))
        
        source_responses.append(SourceResponse(
            source_id=source_id,
            name=source_name,
            description=source_description,
            instructions=source_instructions,
            server_url=source_server_url,
            owner_user_id=source_owner_user_id,
            owner_bot_id=source_owner_bot_id,
            is_public=source_is_public,
            is_active=source_is_active,
            created_at=source_created_at,
            updated_at=source_updated_at,
            tools_cache_status=source_tools_cache_status,
            tools_last_cached_at=source_tools_last_cached_at,
            tools_cache_error=source_tools_cache_error,
            cached_tool_count=cached_tool_count,
            cached_tools=cached_tools
        ))
    
    return source_responses


@router.get("/available-for-query", response_model=List[SourceResponse])
async def get_available_sources_for_query(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get all sources available for query selection (owned + shared + public)"""
    
    # Get user's own sources
    user_sources_query = select(Source).where(
        Source.owner_user_id == user.user_id,
        Source.is_active.is_(True)
    )
    
    # Get public sources (not owned by current user)
    public_sources_query = select(Source).where(
        Source.is_public.is_(True),
        Source.is_active.is_(True),
        Source.owner_user_id != user.user_id  # Exclude user's own public sources (already included above)
    )
    
    # Get sources shared with user
    shared_sources_query = (
        select(Source)
        .join(SourceShare, Source.source_id == SourceShare.source_id)
        .where(
            SourceShare.shared_with_user_id == user.user_id,
            Source.is_active.is_(True)
        )
    )
    
    # Execute all queries
    user_sources_result = await db.execute(user_sources_query)
    public_sources_result = await db.execute(public_sources_query)
    shared_sources_result = await db.execute(shared_sources_query)
    
    user_sources = user_sources_result.scalars().all()
    public_sources = public_sources_result.scalars().all()
    shared_sources = shared_sources_result.scalars().all()
    
    # Combine and deduplicate sources
    all_sources = {}
    for source in list(user_sources) + list(public_sources) + list(shared_sources):
        all_sources[source.source_id] = source
    
    source_responses = []
    
    for source in all_sources.values():
        # Extract ALL source attributes early to avoid greenlet issues
        source_id = source.source_id
        source_name = source.name
        source_description = source.description
        source_instructions = source.instructions
        source_server_url = source.server_url
        source_owner_user_id = source.owner_user_id
        source_owner_bot_id = source.owner_bot_id
        source_is_active = source.is_active
        source_is_public = source.is_public
        source_created_at = source.created_at
        source_updated_at = source.updated_at
        source_tools_cache_status = source.tools_cache_status
        source_tools_last_cached_at = source.tools_last_cached_at
        source_tools_cache_error = source.tools_cache_error
        
        # Determine owner type and sharing status
        owner_type = None
        is_shared_with_user = False
        
        if source_owner_user_id == user.user_id:
            owner_type = "user"
            is_shared_with_user = False
        elif source_owner_bot_id:
            owner_type = "bot"
            is_shared_with_user = False
        elif source_is_public:
            owner_type = "user"  # Public sources are still owned by users
            is_shared_with_user = False  # Public access, not personal sharing
        else:
            owner_type = "user"  # Shared by another user
            is_shared_with_user = True
        
        # Get cached tools for this source
        cached_tools = []
        cached_tool_count = 0
        
        try:
            tools_data = await ToolCacheService.get_cached_tools_for_sources(db, [source_id])
            if tools_data:
                cached_tools = [tool["name"] for tool in tools_data]
                cached_tool_count = len(cached_tools)
        except Exception as e:
            logger.warning("Failed to get cached tools for source", 
                          source_id=source_id, error=str(e))
        
        source_responses.append(SourceResponse(
            source_id=source_id,
            name=source_name,
            description=source_description,
            instructions=source_instructions,
            server_url=source_server_url,
            owner_user_id=source_owner_user_id,
            owner_bot_id=source_owner_bot_id,
            owner_type=owner_type,
            is_shared_with_user=is_shared_with_user,
            is_public=source_is_public,
            is_active=source_is_active,
            created_at=source_created_at,
            updated_at=source_updated_at,
            tools_cache_status=source_tools_cache_status,
            tools_last_cached_at=source_tools_last_cached_at,
            tools_cache_error=source_tools_cache_error,
            cached_tool_count=cached_tool_count,
            cached_tools=cached_tools
        ))
    
    # Sort by name for consistent ordering
    source_responses.sort(key=lambda s: s.name.lower())
    
    return source_responses


@router.get("/{source_id}", response_model=SourceResponse)
async def get_source(
    source_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get a specific source owned by the current user with tool information"""
    
    query = select(Source).where(
        Source.source_id == source_id,
        Source.owner_user_id == user.user_id
    )
    
    result = await db.execute(query)
    source = result.scalar_one_or_none()
    
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found"
        )
    
    # Extract ALL source attributes early to avoid greenlet issues
    source_source_id = source.source_id
    source_name = source.name
    source_description = source.description
    source_instructions = source.instructions
    source_server_url = source.server_url
    source_owner_user_id = source.owner_user_id
    source_owner_bot_id = source.owner_bot_id
    source_is_active = source.is_active
    source_is_public = source.is_public
    source_created_at = source.created_at
    source_updated_at = source.updated_at
    source_tools_cache_status = source.tools_cache_status
    source_tools_last_cached_at = source.tools_last_cached_at
    source_tools_cache_error = source.tools_cache_error
    
    # Get cached tools for this source
    cached_tools = []
    cached_tool_count = 0
    
    try:
        tools_data = await ToolCacheService.get_cached_tools_for_sources(db, [source_source_id])
        if tools_data:
            cached_tools = [tool["name"] for tool in tools_data]
            cached_tool_count = len(cached_tools)
    except Exception as e:
        logger.warning("Failed to get cached tools for source", 
                      source_id=source_source_id, error=str(e))
    
    return SourceResponse(
        source_id=source_source_id,
        name=source_name,
        description=source_description,
        instructions=source_instructions,
        server_url=source_server_url,
        owner_user_id=source_owner_user_id,
        owner_bot_id=source_owner_bot_id,
        is_public=source_is_public,
        is_active=source_is_active,
        created_at=source_created_at,
        updated_at=source_updated_at,
        tools_cache_status=source_tools_cache_status,
        tools_last_cached_at=source_tools_last_cached_at,
        tools_cache_error=source_tools_cache_error,
        cached_tool_count=cached_tool_count,
        cached_tools=cached_tools
    )


@router.put("/{source_id}", response_model=SourceResponse)
async def update_source(
    source_id: uuid.UUID,
    source_data: SourceUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Update a source owned by the current user (comprehensive update with sharing support)"""
    
    try:
        # Get source
        result = await db.execute(
            select(Source).where(
                Source.source_id == source_id,
                Source.owner_user_id == user.user_id
            )
        )
        source = result.scalar_one_or_none()
        
        if not source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Source not found or access denied"
            )
        
        # Extract ALL source attributes early to avoid greenlet issues
        source_id_value = source.source_id
        original_name = source.name
        original_description = source.description
        original_instructions = source.instructions
        original_server_url = source.server_url
        original_is_public = source.is_public
        original_owner_user_id = source.owner_user_id
        original_owner_bot_id = source.owner_bot_id
        original_is_active = source.is_active
        original_created_at = source.created_at
        original_updated_at = source.updated_at
        original_tools_cache_status = source.tools_cache_status
        original_tools_last_cached_at = source.tools_last_cached_at
        original_tools_cache_error = source.tools_cache_error
        
        # Track changes for response
        updated_name = source_data.name if source_data.name is not None else original_name
        updated_description = source_data.description if source_data.description is not None else original_description
        updated_instructions = source_data.instructions if source_data.instructions is not None else original_instructions
        updated_server_url = source_data.server_url if source_data.server_url is not None else original_server_url
        updated_is_public = source_data.is_public if source_data.is_public is not None else original_is_public
        
        # Update basic fields
        updated_at = datetime.now(timezone.utc)
        if source_data.name is not None:
            source.name = source_data.name
        if source_data.description is not None:
            source.description = source_data.description
        if source_data.instructions is not None:
            source.instructions = source_data.instructions
        if source_data.server_url is not None:
            source.server_url = source_data.server_url
        if source_data.is_public is not None:
            source.is_public = source_data.is_public
        
        source.updated_at = updated_at
        
        # Update credentials if provided
        credentials_updated = False
        if source_data.credentials is not None:
            try:
                from src.db.mcp_credentials import SimplifiedCredentialManager
                
                auth_headers = source_data.credentials.get("auth_headers", {})
                success = await SimplifiedCredentialManager.store_source_auth(
                    db=db,
                    source_id=source_id_value,
                    server_url=updated_server_url,
                    auth_headers=auth_headers
                )
                credentials_updated = success
                
                if not success:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to update source credentials"
                    )
            except Exception as e:
                logger.error("Failed to update source credentials", error=str(e))
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to update source credentials: {str(e)}"
                )
        
        # Handle sharing updates
        if source_data.shared_with_users is not None:
            # Remove existing shares
            await db.execute(
                delete(SourceShare).where(SourceShare.source_id == source_id_value)
            )
            
            # Add new shares
            for shared_user_id in source_data.shared_with_users:
                share = SourceShare(
                    source_id=source_id_value,
                    shared_with_user_id=shared_user_id,
                    granted_by_user_id=user.user_id
                )
                db.add(share)
        
        # If credentials or server URL were updated, mark tools for refresh
        if credentials_updated or source_data.server_url is not None:
            logger.info("Source credentials or URL updated - tools will be refreshed on next use", 
                       source_id=source_id_value)
            source.tools_cache_status = "pending"
            source.tools_cache_error = None
        
        await db.commit()
        
        # Get current tool information after update
        cached_tools = []
        cached_tool_count = 0
        
        try:
            tools_data = await ToolCacheService.get_cached_tools_for_sources(db, [source_id_value])
            if tools_data:
                cached_tools = [tool["name"] for tool in tools_data]
                cached_tool_count = len(cached_tools)
        except Exception as e:
            logger.warning("Failed to get cached tools for updated source", 
                          source_id=source_id_value, error=str(e))
        
        logger.info("Source updated successfully", 
                   source_id=source_id_value, 
                   user_id=user.user_id,
                   credentials_updated=credentials_updated)
        
        # Use tracked values instead of accessing model attributes after commit
        return SourceResponse(
            source_id=source_id_value,
            name=updated_name,
            description=updated_description,
            instructions=updated_instructions,
            server_url=updated_server_url,
            owner_user_id=original_owner_user_id,
            owner_bot_id=original_owner_bot_id,
            is_public=updated_is_public,
            is_active=original_is_active,
            created_at=original_created_at,
            updated_at=updated_at,
            tools_cache_status=source.tools_cache_status if credentials_updated or source_data.server_url is not None else original_tools_cache_status,
            tools_last_cached_at=original_tools_last_cached_at,
            tools_cache_error=None if credentials_updated or source_data.server_url is not None else original_tools_cache_error,
            cached_tool_count=cached_tool_count,
            cached_tools=cached_tools
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("Source update failed", error=str(e), source_id=source_id, user_id=user.user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update source: {str(e)}"
        )


@router.delete("/{source_id}")
async def delete_source(
    source_id: uuid.UUID,
    force: bool = False,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
) -> Union[SourceDeletionWarning, Dict[str, str]]:
    """Delete a source owned by the current user with bot association warnings"""
    
    query = select(Source).where(
        Source.source_id == source_id,
        Source.owner_user_id == user.user_id
    )
    
    result = await db.execute(query)
    source = result.scalar_one_or_none()
    
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found"
        )
    
    # Capture values before modifying
    source_name = source.name
    owner_user_id = source.owner_user_id
    
    # Check if source is used by any bots
    associations_query = select(BotSourceAssociation, Bot).join(
        Bot, BotSourceAssociation.bot_id == Bot.bot_id
    ).where(BotSourceAssociation.source_id == source_id)
    
    associations_result = await db.execute(associations_query)
    associations = associations_result.fetchall()
    
    # If source is used by bots and user hasn't confirmed deletion
    if associations and not force:
        bots_using_source = []
        for assoc, bot in associations:
            bots_using_source.append(BotUsingSource(
                bot_id=bot.bot_id,
                bot_name=bot.name,
                custom_instructions=assoc.custom_instructions
            ))
        
        return SourceDeletionWarning(
            message=f"Source '{source_name}' is currently used by {len(bots_using_source)} bot(s). Deleting it will remove it from these bots but keep the bots themselves.",
            source_name=source_name,
            bots_using_source=bots_using_source
        )
    
    # If force=True or no associations, proceed with deletion
    if associations:
        # Remove bot-source associations
        await db.execute(
            delete(BotSourceAssociation).where(BotSourceAssociation.source_id == source_id)
        )
        logger.info(
            "Removed source from bots",
            source_id=source_id,
            bot_count=len(associations)
        )
    
    # Soft delete the source
    source.is_active = False
    source.updated_at = datetime.utcnow()
    
    await db.commit()
    
    logger.info(
        "Source deleted",
        source_id=source_id,
        name=source_name,
        owner_user_id=owner_user_id,
        had_bot_associations=len(associations) > 0
    )
    
    return {"message": "Source deleted successfully"}


@router.get("/{source_id}/status", response_model=SourceWithStatusResponse)
async def get_source_status(
    source_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get source connection status and tool information"""
    
    # Get source with credentials
    sources_with_creds = await get_user_sources_with_credentials(db, user.user_id)
    source_config = next(
        (s for s in sources_with_creds if s['source_id'] == source_id),
        None
    )
    
    if not source_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found"
        )
    
    # Return basic status
    return SourceWithStatusResponse(
        source_id=source_config['source_id'],
        name=source_config['name'],
        description=None,  # Not included in config
        instructions=None,  # Not included in config
        server_url=source_config['server_url'],
        owner_user_id=user.user_id,
        owner_bot_id=None,  # Not available in config
        is_active=True,  # Assumed active since it's returned
        created_at=datetime.utcnow(),  # Not available in config
        updated_at=datetime.utcnow(),  # Not available in config
        is_connected=True,
        last_connection_check=datetime.utcnow(),
        connection_error=None,
        tool_count=None
    )


@router.post("/{source_id}/refresh")
async def refresh_source_tools(
    source_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Refresh tools from any source (remote MCP or local agent) and update the database cache.
    
    For local sources, this automatically discovers tools from agents first if needed,
    then validates them. For remote sources, it directly connects to the MCP server.
    """
    
    # Get source and extract all needed attributes early
    source = await db.get(Source, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    # Extract source attributes immediately to avoid greenlet errors
    source_id_value = source.source_id
    source_name = source.name
    source_url = source.server_url
    source_owner_user_id = source.owner_user_id
    source_owner_bot_id = source.owner_bot_id
    
    # Check ownership - handle both user-owned and bot-owned sources
    user_can_refresh = False
    
    if source_owner_user_id:
        # User-owned source: check direct ownership
        user_can_refresh = (source_owner_user_id == current_user.user_id)
    elif source_owner_bot_id:
        # Bot-owned source: check if user has access to the bot
        from sqlalchemy import or_
        
        # Get the bot and check access
        bot_query = select(Bot).where(Bot.bot_id == source_owner_bot_id)
        bot_result = await db.execute(bot_query)
        bot = bot_result.scalar_one_or_none()
        
        if bot:
            # Check if bot is public or user has explicit access
            if bot.is_public:
                user_can_refresh = True
            else:
                # Check explicit access
                access_query = select(UserBotAccess).where(
                    UserBotAccess.user_id == current_user.user_id,
                    UserBotAccess.bot_id == source_owner_bot_id
                )
                access_result = await db.execute(access_query)
                user_can_refresh = access_result.scalar_one_or_none() is not None
    
    if not user_can_refresh:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Check if this is a local source (starts with local://)
    is_local_source = source_url.startswith('local://')
    
    if is_local_source:
        # For local sources, handle agent tool discovery first
        return await _refresh_local_source_tools(
            source_id_value, source_name, source_url, db
        )
    else:
        # For remote sources, use FastMCP directly
        return await _refresh_remote_source_tools(
            source_id_value, source_name, db
        )


async def _refresh_local_source_tools(
    source_id: uuid.UUID,
    source_name: str, 
    source_url: str,
    db: AsyncSession
):
    """Handle tool refresh for local sources with automatic agent discovery"""
    
    try:
        # Extract capability from local URL (e.g., local://jira_operations -> jira_operations)
        capability = source_url.replace('local://', '')
        
        logger.info(f"Refreshing local source tools", 
                   source_name=source_name, 
                   capability=capability)
        
        # Import local agent manager
        from src.api.local_agents import local_agent_manager
        
        # Find an agent that can handle this capability
        capable_agent_id = None
        for agent_id, agent in local_agent_manager.agents.items():
            if capability in agent.capabilities:
                capable_agent_id = agent_id
                break
        
        if not capable_agent_id:
            raise HTTPException(
                status_code=400, 
                detail=f"No active local agent found with capability '{capability}'. Please ensure a local agent with this capability is running and registered."
            )
        
        logger.info(f"Found capable agent for local source refresh",
                   agent_id=capable_agent_id,
                   capability=capability)
        
        # Check if we already have cached tools
        from src.db.tool_cache import ToolCacheService
        existing_tools = await ToolCacheService.get_cached_tools_for_sources(db, [source_id])
        
        if not existing_tools:
            # No cached tools - need to discover them first
            logger.info(f"No cached tools found - discovering from agent {capable_agent_id}")
            
            # Submit a tool discovery task to the agent
            discovery_task_id = local_agent_manager.submit_task(
                tool_name="__discovery__",  # Special internal task
                arguments={"capability": capability},
                timeout_seconds=30
            )
            
            # Wait for the agent to provide its tools
            result = await local_agent_manager.wait_for_task_result(discovery_task_id, timeout_seconds=30)
            
            if not result or not result.success:
                error_msg = result.error if result else "Tool discovery timed out"
                
                # Update source with error
                from sqlalchemy import update
                await db.execute(
                    update(Source)
                    .where(Source.source_id == source_id)
                    .values(
                        tools_cache_status="error",
                        tools_cache_error=error_msg
                    )
                )
                await db.commit()
                
                raise HTTPException(
                    status_code=400,
                    detail=f"Agent tool discovery failed: {error_msg}"
                )
            
            # Parse tools from agent response
            tools_data = result.result
            if isinstance(tools_data, str):
                import json
                try:
                    tools_data = json.loads(tools_data)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse tools JSON: {e}, raw data: {tools_data}")
                    raise HTTPException(
                        status_code=400,
                        detail=f"Failed to parse agent response: {str(e)}"
                    )
            
            if not isinstance(tools_data, dict):
                logger.error(f"Expected dict from agent, got {type(tools_data)}: {tools_data}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid response format from agent: expected dict, got {type(tools_data)}"
                )
            
            tools = tools_data.get("tools", [])
            
            # Cache the discovered tools
            from src.db.models import SourceTool
            from sqlalchemy import delete
            
            # Clear existing cached tools for this source
            await db.execute(
                delete(SourceTool).where(SourceTool.source_id == source_id)
            )
            
            # Cache the discovered tools
            tools_count = 0
            for tool in tools:
                if isinstance(tool, dict) and tool.get("name"):
                    source_tool = SourceTool(
                        source_id=source_id,
                        tool_name=tool["name"],
                        tool_description=tool.get("description", ""),
                        tool_schema=tool.get("inputSchema", {}),
                        last_refreshed_at=datetime.now(timezone.utc),
                        is_active=True
                    )
                    db.add(source_tool)
                    tools_count += 1
            
            # Update source status
            from sqlalchemy import update
            await db.execute(
                update(Source)
                .where(Source.source_id == source_id)
                .values(
                    tools_cache_status="cached",
                    tools_last_cached_at=datetime.now(timezone.utc),
                    tools_cache_error=None
                )
            )
            
            await db.commit()
            
            logger.info(f"Successfully discovered and cached {tools_count} tools for local source {source_name}")
            
            return RefreshResponse(
                message=f"Successfully discovered and cached {tools_count} tools from local agent {capable_agent_id}",
                tools_count=tools_count,
                timestamp=datetime.utcnow()
            )
        else:
            # Tools already cached - validate them
            logger.info(f"Found {len(existing_tools)} cached tools - validating with FastMCP")
            
            # Use FastMCP to validate the cached tools
            success, message, tool_count = await FastMCPService.discover_and_cache_tools(
                db=db,
                source_id=source_id
            )
            
            if not success:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Tool validation failed: {message}"
                )
            
            return RefreshResponse(
                message=f"Successfully validated {tool_count} cached tools for local source",
                tools_count=tool_count,
                timestamp=datetime.utcnow()
            )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Failed to refresh local source tools for {source_name}: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to refresh local source tools: {str(e)}"
        )


async def _refresh_remote_source_tools(
    source_id: uuid.UUID,
    source_name: str,
    db: AsyncSession
):
    """Handle tool refresh for remote MCP sources"""
    
    try:
        logger.info(f"Refreshing remote source tools using FastMCP: {source_name}")
        
        # Use FastMCP service to discover and cache tools (simplified interface)
        success, message, tool_count = await FastMCPService.discover_and_cache_tools(
            db=db,
            source_id=source_id
        )
        
        if not success:
            raise HTTPException(
                status_code=400, 
                detail=f"Tool refresh failed: {message}"
            )
        
        logger.info(f"Successfully refreshed and cached {tool_count} tools for remote source: {source_name}")
        
        return RefreshResponse(
            message=f"Successfully refreshed {tool_count} tools using FastMCP",
            tools_count=tool_count,
            timestamp=datetime.utcnow()
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Failed to refresh remote source tools for {source_name}: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to refresh remote source tools: {str(e)}"
        )


# Removed duplicate test endpoint - using the FastMCP-based one above 
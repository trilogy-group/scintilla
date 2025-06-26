"""
Sources management API endpoints

Handles CRUD operations for sources (individual MCP server connections owned by users).
"""

import uuid
from uuid import UUID
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, or_, func
from sqlalchemy.orm import selectinload
import structlog

from src.db.base import get_db_session
from src.db.models import User, Source, SourceTool, Bot, UserBotAccess
from src.auth.google_oauth import get_current_user
from src.api.models import SourceCreate, SourceResponse, RefreshResponse, ErrorResponse
from src.db.mcp_credentials import store_source_credentials, get_user_sources_with_credentials, MCPCredentialManager
from src.db.tool_cache import ToolCacheService
from src.agents.fast_mcp import FastMCPService

logger = structlog.get_logger()
router = APIRouter()


# Request/Response Models
class SourceUpdate(BaseModel):
    """Request to update a source"""
    name: Optional[str] = None
    description: Optional[str] = None
    instructions: Optional[str] = None
    credentials: Optional[Dict[str, str]] = None

class SourceWithStatusResponse(SourceResponse):
    """Source response with connection status"""
    is_connected: bool
    last_connection_check: Optional[datetime]
    connection_error: Optional[str]
    tool_count: Optional[int]


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
    """Update a source owned by the current user"""
    
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
    
    # Capture original values
    original_name = source.name
    original_description = source.description
    original_instructions = source.instructions
    original_server_url = source.server_url
    original_owner_user_id = source.owner_user_id
    original_owner_bot_id = source.owner_bot_id
    original_is_active = source.is_active
    original_created_at = source.created_at
    original_tools_cache_status = source.tools_cache_status
    original_tools_last_cached_at = source.tools_last_cached_at
    original_tools_cache_error = source.tools_cache_error
    
    # Update fields
    updated_at = datetime.utcnow()
    if source_data.name is not None:
        source.name = source_data.name
    if source_data.description is not None:
        source.description = source_data.description
    if source_data.instructions is not None:
        source.instructions = source_data.instructions
    
    source.updated_at = updated_at
    
    # Update credentials if provided
    credentials_updated = False
    if source_data.credentials is not None:
        try:
            success = await store_source_credentials(
                db=db,
                source_id=source_id,
                credentials=source_data.credentials
            )
            credentials_updated = success
        except Exception as e:
            logger.error("Failed to update source credentials", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update source credentials"
            )
    
    # If credentials were updated, mark tools for lazy refresh
    if credentials_updated:
        logger.info("Source credentials updated - tools will be refreshed on next use", 
                   source_id=source_id)
        # Update source to mark tools as pending refresh
        source.tools_cache_status = "pending"
        source.tools_cache_error = None
    
    await db.commit()
    
    # Use captured or updated values
    final_name = source_data.name if source_data.name is not None else original_name
    final_description = source_data.description if source_data.description is not None else original_description
    final_instructions = source_data.instructions if source_data.instructions is not None else original_instructions
    
    # Get current tool information after update
    cached_tools = []
    cached_tool_count = 0
    
    try:
        tools_data = await ToolCacheService.get_cached_tools_for_sources(db, [source_id])
        if tools_data:
            cached_tools = [tool["name"] for tool in tools_data]
            cached_tool_count = len(cached_tools)
    except Exception as e:
        logger.warning("Failed to get cached tools for updated source", 
                      source_id=source_id, error=str(e))
    
    logger.info(
        "Source updated",
        source_id=source_id,
        name=final_name,
        owner_user_id=user.user_id
    )
    
    return SourceResponse(
        source_id=source_id,
        name=final_name,
        description=final_description,
        instructions=final_instructions,
        server_url=original_server_url,
        owner_user_id=original_owner_user_id,
        owner_bot_id=original_owner_bot_id,
        is_active=original_is_active,
        created_at=original_created_at,
        updated_at=updated_at,
        tools_cache_status=source_tools_cache_status,
        tools_last_cached_at=source_tools_last_cached_at,
        tools_cache_error=source_tools_cache_error,
        cached_tool_count=cached_tool_count,
        cached_tools=cached_tools
    )


@router.delete("/{source_id}")
async def delete_source(
    source_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Delete a source owned by the current user"""
    
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
    
    # Soft delete
    source.is_active = False
    source.updated_at = datetime.utcnow()
    
    await db.commit()
    
    logger.info(
        "Source deleted",
        source_id=source_id,
        name=source_name,
        owner_user_id=owner_user_id
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
    
    # TODO: Implement actual connection testing
    # For now, return basic status
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
        is_connected=True,  # TODO: Implement real check
        last_connection_check=datetime.utcnow(),
        connection_error=None,
        tool_count=None  # TODO: Get from MCP client
    )


@router.post("/{source_id}/test")
async def test_source_connection(
    source_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Test connection to an MCP server using FastMCP."""
    
    # Get source and extract attributes early
    source = await db.get(Source, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    # Extract attributes immediately
    source_owner_user_id = source.owner_user_id
    source_owner_bot_id = source.owner_bot_id
    source_url = source.server_url
    source_name = source.name
    
    # Check ownership - handle both user-owned and bot-owned sources
    user_can_test = False
    
    if source_owner_user_id:
        # User-owned source: check direct ownership
        user_can_test = (source_owner_user_id == current_user.user_id)
    elif source_owner_bot_id:
        # Bot-owned source: check if user has access to the bot
        # Get the bot and check access
        bot_query = select(Bot).where(Bot.bot_id == source_owner_bot_id)
        bot_result = await db.execute(bot_query)
        bot = bot_result.scalar_one_or_none()
        
        if bot:
            # Check if bot is public or user has explicit access
            if bot.is_public:
                user_can_test = True
            else:
                # Check explicit access
                access_query = select(UserBotAccess).where(
                    UserBotAccess.user_id == current_user.user_id,
                    UserBotAccess.bot_id == source_owner_bot_id
                )
                access_result = await db.execute(access_query)
                user_can_test = access_result.scalar_one_or_none() is not None
    
    if not user_can_test:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Test connection using FastMCP service with simplified interface
    # Get auth configuration from database
    from src.db.mcp_credentials import SimplifiedCredentialManager
    auth_config = await SimplifiedCredentialManager.get_source_auth(db, source_id)
    if not auth_config:
        raise HTTPException(status_code=400, detail="Source authentication not configured")
    
    result = await FastMCPService.test_connection(
        auth_config["server_url"], 
        auth_config["auth_headers"]
    )
    
    return {
        "source_id": source_id,
        "source_name": source_name,
        "connection_test": result
    }


@router.post("/refresh-cache")
async def refresh_tool_cache(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Refresh cached tools for all sources the user has access to (user-owned + accessible bot sources) using FastMCP
    """
    try:
        from sqlalchemy import or_
        
        # Get user's directly owned sources
        user_sources_query = select(Source).where(
            Source.owner_user_id == user.user_id,
            Source.is_active.is_(True)
        )
        user_sources_result = await db.execute(user_sources_query)
        user_sources = user_sources_result.scalars().all()
        
        # Get bot sources user has access to
        # First get user's accessible bot IDs
        access_query = select(UserBotAccess.bot_id).where(
            UserBotAccess.user_id == user.user_id
        )
        access_result = await db.execute(access_query)
        accessible_bot_ids = [row[0] for row in access_result.fetchall()]
        
        # Get public bots + explicitly accessible bots
        bot_conditions = [Bot.is_public.is_(True)]
        if accessible_bot_ids:
            bot_conditions.append(Bot.bot_id.in_(accessible_bot_ids))
        
        accessible_bots_query = select(Bot.bot_id).where(or_(*bot_conditions))
        accessible_bots_result = await db.execute(accessible_bots_query)
        all_accessible_bot_ids = [row[0] for row in accessible_bots_result.fetchall()]
        
        # Get sources owned by accessible bots
        bot_sources = []
        if all_accessible_bot_ids:
            bot_sources_query = select(Source).where(
                Source.owner_bot_id.in_(all_accessible_bot_ids),
                Source.is_active.is_(True)
            )
            bot_sources_result = await db.execute(bot_sources_query)
            bot_sources = bot_sources_result.scalars().all()
        
        # Combine all sources
        all_sources = list(user_sources) + list(bot_sources)
        
        if not all_sources:
            return {
                "success": True,
                "message": "No sources found for user",
                "refreshed_sources": 0,
                "total_tools": 0
            }
        
        refreshed_count = 0
        total_tools = 0
        errors = []
        
        for source in all_sources:
            # Extract source attributes early
            source_id = source.source_id
            source_name = source.name
            source_url = source.server_url
            
            try:
                # Use FastMCP service to discover and cache tools (simplified interface)
                success, message, tool_count = await FastMCPService.discover_and_cache_tools(
                    db=db,
                    source_id=source_id
                )
                
                if success:
                    refreshed_count += 1
                    total_tools += tool_count
                    logger.info("Refreshed tools for source",
                               source_id=source_id,
                               source_name=source_name,
                               tool_count=tool_count)
                else:
                    errors.append({
                        "source_id": str(source_id),
                        "source_name": source_name,
                        "error": message
                    })
                    
            except Exception as e:
                errors.append({
                    "source_id": str(source_id),
                    "source_name": source_name,
                    "error": str(e)
                })
        
        return {
            "success": True,
            "message": f"Refreshed tools for {refreshed_count}/{len(all_sources)} sources (user-owned: {len(user_sources)}, bot sources: {len(bot_sources)})",
            "refreshed_sources": refreshed_count,
            "total_sources": len(all_sources),
            "user_sources": len(user_sources),
            "bot_sources": len(bot_sources),
            "total_tools": total_tools,
            "errors": errors if errors else None
        }
        
    except Exception as e:
        logger.error("Failed to refresh tool cache", user_id=user.user_id, error=str(e))
        return {
            "success": False,
            "message": f"Failed to refresh tool cache: {str(e)}",
            "refreshed_sources": 0,
            "total_tools": 0
        }


@router.post("/{source_id}/refresh")
async def refresh_source_tools(
    source_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Refresh tools from an MCP server using FastMCP and update the database cache."""
    
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
    
    try:
        logger.info(f"Refreshing tools using FastMCP for source: {source_name}")
        
        # Use FastMCP service to discover and cache tools (simplified interface)
        success, message, tool_count = await FastMCPService.discover_and_cache_tools(
            db=db,
            source_id=source_id_value
        )
        
        if not success:
            raise HTTPException(
                status_code=400, 
                detail=f"Tool refresh failed: {message}"
            )
        
        logger.info(f"Successfully refreshed and cached {tool_count} tools for source: {source_name}")
        
        return RefreshResponse(
            message=f"Successfully refreshed {tool_count} tools using FastMCP",
            tools_count=tool_count,
            timestamp=datetime.utcnow()
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Failed to refresh tools for source {source_name}: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to refresh tools: {str(e)}"
        )


# Removed duplicate test endpoint - using the FastMCP-based one above 
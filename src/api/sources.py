"""
Sources management API endpoints

Handles CRUD operations for sources (individual MCP server connections owned by users).
"""

import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import structlog

from src.db.base import get_db_session
from src.db.models import User, Source, MCPServerType, CredentialType
from src.db.mcp_credentials import get_user_sources_with_credentials, store_source_credentials
from src.auth.mock import get_current_user
from src.db.tool_cache import ToolCacheService
from src.api.models import SourceCreate, SourceResponse

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


@router.post("/sources", response_model=SourceResponse)
async def create_source(
    source_data: SourceCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Create a new source for the current user"""
    
    # Validate server type
    try:
        server_type = MCPServerType(source_data.server_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid server type: {source_data.server_type}"
        )
    
    # Create source with pre-generated ID
    source_id = uuid.uuid4()
    created_at = datetime.utcnow()
    
    source = Source(
        source_id=source_id,
        name=source_data.name,
        description=source_data.description,
        instructions=source_data.instructions,
        server_type=server_type,
        server_url=source_data.server_url,
        owner_user_id=user.user_id,
        owner_bot_id=None,  # User-owned source
        is_active=True,
        created_at=created_at,
        updated_at=created_at
    )
    
    db.add(source)
    await db.flush()  # Get the ID without committing
    
    # Store credentials
    try:
        await store_source_credentials(
            db=db,
            source_id=source_id,
            credentials=source_data.credentials
        )
        await db.commit()
        
    except Exception as e:
        await db.rollback()
        logger.error("Failed to store source credentials", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store source credentials"
        )
    
    logger.info(
        "Source created",
        source_id=source_id,
        name=source_data.name,
        owner_user_id=user.user_id
    )
    
    # Asynchronously cache tools for this source (don't block the response)
    try:
        cache_result = await ToolCacheService.cache_tools_for_source(db, source_id)
        if cache_result["success"]:
            logger.info("Tools cached for new source", 
                       source_id=source_id, 
                       tool_count=cache_result["cached_tools"],
                       cache_time_ms=cache_result["cache_time_ms"])
        else:
            logger.warning("Failed to cache tools for new source",
                          source_id=source_id,
                          error=cache_result["error"])
    except Exception as e:
        logger.warning("Tool caching failed for new source",
                      source_id=source_id,
                      error=str(e))
    
    return SourceResponse(
        source_id=source_id,
        name=source_data.name,
        description=source_data.description,
        instructions=source_data.instructions,
        server_type=server_type.value,
        server_url=source_data.server_url,
        owner_user_id=user.user_id,
        owner_bot_id=None,
        is_active=True,
        created_at=created_at,
        updated_at=created_at
    )


@router.get("/sources", response_model=List[SourceResponse])
async def list_user_sources(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """List sources owned by the current user"""
    
    query = select(Source).where(
        Source.owner_user_id == user.user_id,
        Source.is_active == True
    )
    
    result = await db.execute(query)
    sources = result.scalars().all()
    
    return [
        SourceResponse(
            source_id=source.source_id,
            name=source.name,
            description=source.description,
            instructions=source.instructions,
            server_type=source.server_type.value,
            server_url=source.server_url,
            owner_user_id=source.owner_user_id,
            owner_bot_id=source.owner_bot_id,
            is_active=source.is_active,
            created_at=source.created_at,
            updated_at=source.updated_at
        )
        for source in sources
    ]


@router.get("/sources/{source_id}", response_model=SourceResponse)
async def get_source(
    source_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get a specific source owned by the current user"""
    
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
    
    return SourceResponse(
        source_id=source.source_id,
        name=source.name,
        description=source.description,
        instructions=source.instructions,
        server_type=source.server_type.value,
        server_url=source.server_url,
        owner_user_id=source.owner_user_id,
        owner_bot_id=source.owner_bot_id,
        is_active=source.is_active,
        created_at=source.created_at,
        updated_at=source.updated_at
    )


@router.put("/sources/{source_id}", response_model=SourceResponse)
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
    original_server_type = source.server_type
    original_server_url = source.server_url
    original_owner_user_id = source.owner_user_id
    original_owner_bot_id = source.owner_bot_id
    original_is_active = source.is_active
    original_created_at = source.created_at
    
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
            await store_source_credentials(
                db=db,
                source_id=source_id,
                credentials=source_data.credentials
            )
            credentials_updated = True
        except Exception as e:
            logger.error("Failed to update source credentials", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update source credentials"
            )
    
    await db.commit()
    
    # If credentials were updated, refresh the tool cache
    if credentials_updated:
        try:
            cache_result = await ToolCacheService.cache_tools_for_source(db, source_id, force_refresh=True)
            if cache_result["success"]:
                logger.info("Tools refreshed for updated source", 
                           source_id=source_id, 
                           tool_count=cache_result["cached_tools"],
                           cache_time_ms=cache_result["cache_time_ms"])
            else:
                logger.warning("Failed to refresh tools for updated source",
                              source_id=source_id,
                              error=cache_result["error"])
        except Exception as e:
            logger.warning("Tool refresh failed for updated source",
                          source_id=source_id,
                          error=str(e))
    
    # Use captured or updated values
    final_name = source_data.name if source_data.name is not None else original_name
    final_description = source_data.description if source_data.description is not None else original_description
    final_instructions = source_data.instructions if source_data.instructions is not None else original_instructions
    
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
        server_type=original_server_type.value,
        server_url=original_server_url,
        owner_user_id=original_owner_user_id,
        owner_bot_id=original_owner_bot_id,
        is_active=original_is_active,
        created_at=original_created_at,
        updated_at=updated_at
    )


@router.delete("/sources/{source_id}")
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


@router.get("/sources/{source_id}/status", response_model=SourceWithStatusResponse)
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
        server_type=source_config['server_type'].value if hasattr(source_config['server_type'], 'value') else str(source_config['server_type']),
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


@router.post("/sources/{source_id}/test")
async def test_source_connection(
    source_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Test connection to a source"""
    
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
    
    # Actually test the connection using MCP agent
    try:
        from src.agents.langchain_mcp import MCPAgent
        
        agent = MCPAgent()
        # Create a temporary configuration list with just this source
        temp_configs = [source_config]
        
        # Build server configs for testing
        server_configs = {}
        config = source_config
        source_name = f"{config['name'].lower().replace(' ', '_')}_test"
        
        server_type_str = config["server_type"].value if hasattr(config["server_type"], 'value') else str(config["server_type"])
        if server_type_str == "CUSTOM_SSE":
            mcp_config = {
                "command": "uvx",
                "args": [
                    "mcp-proxy",
                    "--headers",
                    "x-api-key",
                    config["credentials"].get("api_key", ""),
                    config["server_url"]
                ],
                "transport": "stdio"
            }
            server_configs[source_name] = mcp_config
        
        if server_configs:
            from langchain_mcp_adapters.client import MultiServerMCPClient
            import time
            
            start_time = time.time()
            test_client = MultiServerMCPClient(server_configs)
            tools = await test_client.get_tools()
            end_time = time.time()
            
            response_time = int((end_time - start_time) * 1000)
            
            return {
                "success": True,
                "message": "Connection test successful",
                "tool_count": len(tools),
                "response_time_ms": response_time,
                "tools": [tool.name for tool in tools] if tools else []
            }
        else:
            return {
                "success": False,
                "message": f"Unsupported server type: {server_type_str}",
                "tool_count": 0,
                "response_time_ms": 0
            }
            
    except Exception as e:
        logger.error("Connection test failed", source_id=source_id, error=str(e))
        return {
            "success": False,
            "message": f"Connection test failed: {str(e)}",
            "tool_count": 0,
            "response_time_ms": 0
        }


@router.post("/refresh-cache")
async def refresh_tool_cache(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Refresh cached tools for all user sources
    """
    try:
        # Get user's sources
        query = select(Source).where(
            Source.owner_user_id == user.user_id,
            Source.is_active == True
        )
        result = await db.execute(query)
        user_sources = result.scalars().all()
        
        if not user_sources:
            return {
                "success": True,
                "message": "No sources found for user",
                "refreshed_sources": 0,
                "total_tools": 0
            }
        
        refreshed_count = 0
        total_tools = 0
        errors = []
        
        for source in user_sources:
            try:
                cache_result = await ToolCacheService.cache_tools_for_source(
                    db, source.source_id, force_refresh=True
                )
                
                if cache_result["success"]:
                    refreshed_count += 1
                    total_tools += cache_result["cached_tools"]
                    logger.info("Refreshed tools for source",
                               source_id=source.source_id,
                               source_name=source.name,
                               tool_count=cache_result["cached_tools"])
                else:
                    errors.append({
                        "source_id": str(source.source_id),
                        "source_name": source.name,
                        "error": cache_result["error"]
                    })
                    
            except Exception as e:
                errors.append({
                    "source_id": str(source.source_id),
                    "source_name": source.name,
                    "error": str(e)
                })
        
        return {
            "success": True,
            "message": f"Refreshed tools for {refreshed_count}/{len(user_sources)} sources",
            "refreshed_sources": refreshed_count,
            "total_sources": len(user_sources),
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


@router.post("/sources/{source_id}/refresh-tools")
async def refresh_source_tools(
    source_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Refresh cached tools for a specific source (user-owned or bot-owned if user has access)
    """
    # Get the source
    query = select(Source).where(Source.source_id == source_id)
    result = await db.execute(query)
    source = result.scalar_one_or_none()
    
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found"
        )
    
    # Extract ALL source attributes early to avoid greenlet issues
    source_name = source.name
    source_owner_user_id = source.owner_user_id
    source_owner_bot_id = source.owner_bot_id
    
    # Check access permissions
    has_access = False
    
    if source_owner_user_id == user.user_id:
        # User owns the source directly
        has_access = True
    elif source_owner_bot_id:
        # Check if user has access to the bot that owns this source
        from src.db.models import Bot, UserBotAccess
        from sqlalchemy import or_
        
        bot_query = select(Bot).where(Bot.bot_id == source_owner_bot_id)
        bot_result = await db.execute(bot_query)
        bot = bot_result.scalar_one_or_none()
        
        if bot:
            # Extract bot attributes early too
            bot_is_public = bot.is_public
            bot_bot_id = bot.bot_id
            
            if bot_is_public:
                has_access = True
            else:
                # Check explicit access
                access_query = select(UserBotAccess).where(
                    UserBotAccess.user_id == user.user_id,
                    UserBotAccess.bot_id == bot_bot_id
                )
                access_result = await db.execute(access_query)
                has_access = access_result.scalar_one_or_none() is not None
    
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to refresh tools for this source"
        )
    
    try:
        cache_result = await ToolCacheService.cache_tools_for_source(
            db, source_id, force_refresh=True
        )
        
        if cache_result["success"]:
            return {
                "success": True,
                "message": f"Tools refreshed for source '{source_name}'",  # Use extracted value
                "cached_tools": cache_result["cached_tools"],
                "cache_time_ms": cache_result["cache_time_ms"],
                "status": cache_result["status"]
            }
        else:
            return {
                "success": False,
                "message": f"Failed to refresh tools: {cache_result['error']}",
                "cached_tools": 0
            }
            
    except Exception as e:
        logger.error("Failed to refresh source tools", 
                    source_id=source_id, error=str(e))
        return {
            "success": False,
            "message": f"Failed to refresh tools: {str(e)}",
            "cached_tools": 0
        } 
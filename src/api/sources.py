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
from src.db.mcp_tool_cache import MCPToolCacheManager

logger = structlog.get_logger()
router = APIRouter()


# Request/Response Models
class SourceCreate(BaseModel):
    """Request to create a new source"""
    name: str = Field(..., description="Display name for the source")
    server_type: str = Field(..., description="Type of MCP server (CUSTOM_SSE)")
    server_url: str = Field(..., description="Base URL of the MCP server")
    credentials: Dict[str, str] = Field(..., description="Credential fields")
    description: Optional[str] = None

class SourceUpdate(BaseModel):
    """Request to update a source"""
    name: Optional[str] = None
    description: Optional[str] = None
    credentials: Optional[Dict[str, str]] = None

class SourceResponse(BaseModel):
    """Source information response"""
    source_id: uuid.UUID
    name: str
    description: Optional[str]
    server_type: str
    server_url: str
    owner_user_id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]
    # Note: credentials are not included in response for security

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
        server_type=server_type,
        server_url=source_data.server_url,
        owner_user_id=user.user_id,
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
    
    return SourceResponse(
        source_id=source_id,
        name=source_data.name,
        description=source_data.description,
        server_type=server_type.value,
        server_url=source_data.server_url,
        owner_user_id=user.user_id,
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
            server_type=source.server_type.value,
            server_url=source.server_url,
            owner_user_id=source.owner_user_id,
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
        server_type=source.server_type.value,
        server_url=source.server_url,
        owner_user_id=source.owner_user_id,
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
    original_server_type = source.server_type
    original_server_url = source.server_url
    original_owner_user_id = source.owner_user_id
    original_is_active = source.is_active
    original_created_at = source.created_at
    
    # Update fields
    updated_at = datetime.utcnow()
    if source_data.name is not None:
        source.name = source_data.name
    if source_data.description is not None:
        source.description = source_data.description
    
    source.updated_at = updated_at
    
    # Update credentials if provided
    if source_data.credentials is not None:
        try:
            await store_source_credentials(
                db=db,
                source_id=source_id,
                credentials=source_data.credentials
            )
        except Exception as e:
            logger.error("Failed to update source credentials", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update source credentials"
            )
    
    await db.commit()
    
    # Use captured or updated values
    final_name = source_data.name if source_data.name is not None else original_name
    final_description = source_data.description if source_data.description is not None else original_description
    
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
        server_type=original_server_type.value,
        server_url=original_server_url,
        owner_user_id=original_owner_user_id,
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
        server_type=source_config['server_type'].value if hasattr(source_config['server_type'], 'value') else str(source_config['server_type']),
        server_url=source_config['server_url'],
        owner_user_id=user.user_id,
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
    user: User = Depends(get_current_user)
):
    """
    Refresh the MCP tool cache for the current user
    
    This will invalidate the current cache and force a fresh
    load of tools on the next query.
    """
    async with get_db_session() as db:
        try:
            # Invalidate all cache entries for this user
            entries_removed = await MCPToolCacheManager.invalidate_user_cache(db, user.user_id)
            
            logger.info(
                "Refreshed MCP tool cache for user",
                user_id=user.user_id,
                entries_removed=entries_removed
            )
            
            return {
                "success": True,
                "message": f"Tool cache refreshed. {entries_removed} cache entries cleared.",
                "entries_removed": entries_removed
            }
            
        except Exception as e:
            logger.error(
                "Failed to refresh tool cache",
                user_id=user.user_id,
                error=str(e)
            )
            raise HTTPException(
                status_code=500,
                detail=f"Failed to refresh tool cache: {str(e)}"
            ) 
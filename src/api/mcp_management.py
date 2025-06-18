"""
MCP Management API

Endpoints for managing MCP server configurations and credentials.
"""

import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from src.db.base import get_db_session
from src.db.models import User, MCPServerType, CredentialType
from src.db.mcp_credentials import MCPCredentialManager
from src.auth.mock import get_current_user

logger = structlog.get_logger()
router = APIRouter()


# Request/Response Models
class MCPServerResponse(BaseModel):
    """MCP Server information response"""
    server_id: uuid.UUID
    name: str
    description: Optional[str]
    server_type: str
    credential_type: str
    required_fields: List[str]
    base_url: Optional[str]
    is_public: bool
    created_at: datetime

class CredentialRequest(BaseModel):
    """Request to store MCP credentials"""
    server_id: uuid.UUID
    bot_id: uuid.UUID
    credentials: Dict[str, str] = Field(..., description="Credential fields (e.g., {'api_key': 'sk-...', 'base_url': 'https://...'})")
    expires_at: Optional[datetime] = None

class CredentialResponse(BaseModel):
    """MCP credential response (without actual credential values)"""
    credential_id: uuid.UUID
    server_id: uuid.UUID
    bot_id: uuid.UUID
    server_name: str
    is_active: bool
    last_used: Optional[datetime]
    expires_at: Optional[datetime]
    created_at: datetime

class BotMCPStatusResponse(BaseModel):
    """Bot MCP configuration status"""
    bot_id: uuid.UUID
    bot_name: str
    server_count: int
    tool_count: Optional[int]
    last_sync: Optional[datetime]
    servers: List[CredentialResponse]


@router.get("/servers", response_model=List[MCPServerResponse])
async def list_mcp_servers(
    include_public_only: bool = False,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """List available MCP servers"""
    
    # TODO: Update this endpoint for the new Sources/Bots architecture
    # For now, return empty list since we use Sources instead of predefined servers
    servers = []
    
    return [
        MCPServerResponse(
            server_id=server.server_id,
            name=server.name,
            description=server.description,
            server_type=server.server_type.value,
            credential_type=server.credential_type.value,
            required_fields=server.required_fields,
            base_url=server.base_url,
            is_public=server.is_public,
            created_at=server.created_at
        )
        for server in servers
    ]

@router.post("/credentials", response_model=CredentialResponse)
async def store_mcp_credentials(
    request: CredentialRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Store encrypted MCP credentials for a bot"""
    
    # TODO: Add permission check - user should own the bot or have access
    
    logger.info(
        "Storing MCP credentials",
        user_id=user.user_id,
        bot_id=request.bot_id,
        server_id=request.server_id
    )
    
    try:
        credential = await MCPCredentialManager.store_bot_credentials(
            db=db,
            bot_id=request.bot_id,
            server_id=request.server_id,
            credentials=request.credentials,
            expires_at=request.expires_at
        )
        
        # Get server name for response
        from sqlalchemy import select
        from src.db.models import MCPServer
        server_query = select(MCPServer).where(MCPServer.server_id == request.server_id)
        server_result = await db.execute(server_query)
        server = server_result.scalar_one_or_none()
        
        return CredentialResponse(
            credential_id=credential.credential_id,
            server_id=credential.server_id,
            bot_id=credential.bot_id,
            server_name=server.name if server else "Unknown",
            is_active=credential.is_active,
            last_used=credential.last_used,
            expires_at=credential.expires_at,
            created_at=credential.created_at
        )
        
    except Exception as e:
        logger.error(
            "Failed to store MCP credentials",
            error=str(e),
            user_id=user.user_id,
            bot_id=request.bot_id,
            server_id=request.server_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store credentials"
        )

@router.get("/credentials/bot/{bot_id}", response_model=List[CredentialResponse])
async def list_bot_mcp_credentials(
    bot_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """List MCP credentials for a specific bot"""
    
    # TODO: Add permission check - user should own the bot or have access
    
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from src.db.models import BotMCPCredential
    
    query = (
        select(BotMCPCredential)
        .options(selectinload(BotMCPCredential.mcp_server))
        .where(BotMCPCredential.bot_id == bot_id)
    )
    
    result = await db.execute(query)
    credentials = result.scalars().all()
    
    return [
        CredentialResponse(
            credential_id=cred.credential_id,
            server_id=cred.server_id,
            bot_id=cred.bot_id,
            server_name=cred.mcp_server.name,
            is_active=cred.is_active,
            last_used=cred.last_used,
            expires_at=cred.expires_at,
            created_at=cred.created_at
        )
        for cred in credentials
    ]

@router.delete("/credentials/{credential_id}")
async def delete_mcp_credentials(
    credential_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Delete MCP credentials"""
    
    # TODO: Add permission check - user should own the bot or have access
    
    from sqlalchemy import select
    from src.db.models import BotMCPCredential
    
    query = select(BotMCPCredential).where(BotMCPCredential.credential_id == credential_id)
    result = await db.execute(query)
    credential = result.scalar_one_or_none()
    
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credential not found"
        )
    
    success = await MCPCredentialManager.delete_bot_credentials(
        db=db,
        bot_id=credential.bot_id,
        server_id=credential.server_id
    )
    
    if success:
        logger.info(
            "Deleted MCP credentials",
            user_id=user.user_id,
            credential_id=credential_id,
            bot_id=credential.bot_id
        )
        return {"message": "Credentials deleted successfully"}
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete credentials"
        )

@router.get("/bot/{bot_id}/status", response_model=BotMCPStatusResponse)
async def get_bot_mcp_status(
    bot_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get MCP configuration status for a bot"""
    
    # TODO: Add permission check - user should own the bot or have access
    
    from sqlalchemy import select
    from src.db.models import Bot
    from src.agents.langchain_mcp import MCPAgent
    
    # Get bot info
    bot_query = select(Bot).where(Bot.bot_id == bot_id)
    bot_result = await db.execute(bot_query)
    bot = bot_result.scalar_one_or_none()
    
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found"
        )
    
    # Get credentials
    credentials = await list_bot_mcp_credentials(bot_id, user, db)
    
    # Try to load MCP tools to get tool count
    tool_count = None
    try:
        agent = MCPAgent()
        tool_count = await agent.load_mcp_endpoints_from_bot(db, bot_id)
    except Exception as e:
        logger.warning(
            "Failed to load MCP tools for status check",
            bot_id=bot_id,
            error=str(e)
        )
    
    return BotMCPStatusResponse(
        bot_id=bot_id,
        bot_name=bot.display_name,
        server_count=len(credentials),
        tool_count=tool_count,
        last_sync=datetime.utcnow(),  # TODO: Track actual last sync time
        servers=credentials
    )

@router.post("/test/{bot_id}")
async def test_bot_mcp_connection(
    bot_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Test MCP connections for a bot"""
    
    # TODO: Add permission check - user should own the bot or have access
    
    from src.agents.langchain_mcp import MCPAgent
    
    logger.info(
        "Testing MCP connections for bot",
        user_id=user.user_id,
        bot_id=bot_id
    )
    
    try:
        agent = MCPAgent()
        tool_count = await agent.load_mcp_endpoints_from_bot(db, bot_id)
        
        return {
            "success": True,
            "tool_count": tool_count,
            "loaded_servers": agent.get_loaded_servers(),
            "available_tools": [
                {"name": tool["name"], "description": tool["description"]}
                for tool in agent.get_available_tools()
            ]
        }
        
    except Exception as e:
        logger.error(
            "MCP connection test failed",
            bot_id=bot_id,
            error=str(e)
        )
        return {
            "success": False,
            "error": str(e),
            "tool_count": 0,
            "loaded_servers": [],
            "available_tools": []
        } 
"""
MCP Management API

Simplified management endpoints after the MCP authentication refactor.
Most functionality has been moved to the sources and bots endpoints.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog

from src.db.base import get_db_session
from src.db.models import User
from src.auth.google_oauth import get_current_user

logger = structlog.get_logger()
router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check endpoint for MCP management"""
    return {
        "status": "healthy",
        "service": "mcp_management",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get("/status")
async def get_mcp_status(user: User = Depends(get_current_user)):
    """Get MCP system status"""
    return {
        "success": True,
        "status": {
            "system_ready": True,
            "architecture": "simplified_sources_based",
            "authentication": "header_based_and_url_embedded",
            "description": "MCP servers configured as Sources with simplified authentication"
        },
        "user_id": user.user_id,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.post("/refresh")
async def trigger_global_refresh(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Trigger a refresh of all user's sources"""
    
    # Count user's active sources
    from src.db.models import Source
    
    user_sources_query = select(Source).where(
        Source.owner_user_id == user.user_id,
        Source.is_active.is_(True)
    )
    user_sources_result = await db.execute(user_sources_query)
    user_sources = user_sources_result.scalars().all()
    
    return {
        "success": True,
        "message": f"Found {len(user_sources)} active sources for user",
        "user_sources_count": len(user_sources),
        "note": "Use individual source refresh endpoints for tool cache refresh",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get("/info")
async def get_mcp_info():
    """Get information about the MCP system"""
    return {
        "system": "Scintilla MCP Management",
        "version": "simplified",
        "architecture": {
            "sources": "MCP servers configured as Sources",
            "authentication": "header-based (auth_headers) or URL-embedded credentials",
            "caching": "Tools cached in source_tools table",
            "agents": "FastMCP service with database integration"
        },
        "endpoints": {
            "sources": "/sources/* - Create, list, update, delete MCP sources",
            "bots": "/bots/* - Create bots with dedicated MCP sources",  
            "management": "/mcp/* - System status and management"
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    } 
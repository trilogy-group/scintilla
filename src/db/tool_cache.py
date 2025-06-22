"""
Tool Caching Service

Manages caching of MCP tool metadata in the database to avoid
expensive list_tools calls during query time.
"""

import uuid
import json
import asyncio
import time
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
import structlog

from src.db.models import Source, SourceTool
from src.agents.fast_mcp import FastMCPService

logger = structlog.get_logger()


class ToolCacheService:
    """Service for managing tool caching in the database"""
    
    @staticmethod
    async def cache_tools_for_source(
        db: AsyncSession, 
        source_id: uuid.UUID,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Cache tools for a specific source by calling list_tools and storing results in DB
        
        Args:
            db: Database session
            source_id: Source ID to cache tools for
            force_refresh: Force refresh even if already cached
            
        Returns:
            Dict with caching results and metadata
        """
        cache_start = time.time()
        
        try:
            # Get source configuration
            source_query = select(Source).where(Source.source_id == source_id)
            result = await db.execute(source_query)
            source = result.scalar_one_or_none()
            
            if not source:
                return {
                    "success": False,
                    "error": f"Source {source_id} not found",
                    "cached_tools": 0
                }
            
            # Extract ALL source attributes early to avoid greenlet issues
            source_name = source.name
            source_tools_cache_status = source.tools_cache_status
            source_tools_last_cached_at = source.tools_last_cached_at
            
            # Check if already cached and not forcing refresh
            if not force_refresh and source_tools_cache_status == "cached":
                # Return existing cached tools count
                tools_query = select(SourceTool).where(
                    SourceTool.source_id == source_id,
                    SourceTool.is_active.is_(True)
                )
                tools_result = await db.execute(tools_query)
                existing_tools = tools_result.scalars().all()
                
                return {
                    "success": True,
                    "cached_tools": len(existing_tools),
                    "cache_time_ms": 0,
                    "status": "already_cached",
                    "last_cached": source_tools_last_cached_at
                }
            
            logger.info("Starting tool caching for source", 
                       source_id=source_id, source_name=source_name, force_refresh=force_refresh)
            
            # Update status to indicate caching in progress
            source.tools_cache_status = "caching"
            source.tools_cache_error = None
            await db.commit()
            
            # Use FastMCP service for tool discovery (simplified - no separate API key needed)
            mcp_load_start = time.time()
            
            try:
                # Use FastMCP service to discover and cache tools
                success, message, tool_count = await asyncio.wait_for(
                    FastMCPService.discover_and_cache_tools(
                        db=db,
                        source_id=source_id
                    ),
                    timeout=30  # 30 second timeout for tool discovery
                )
                
                if not success:
                    raise Exception(f"Failed to discover tools: {message}")
                
                # FastMCP service already cached the tools, so we just need to get them
                tools_query = select(SourceTool).where(
                    SourceTool.source_id == source_id,
                    SourceTool.is_active.is_(True)
                )
                tools_result = await db.execute(tools_query)
                cached_tools = tools_result.scalars().all()
                
                available_tools = [
                    {
                        "name": tool.tool_name,
                        "description": tool.tool_description,
                        "inputSchema": tool.tool_schema
                    }
                    for tool in cached_tools
                ]
                
            except asyncio.TimeoutError:
                raise Exception(f"FastMCP tool discovery timed out after 30 seconds for source {source_id}")
            except Exception as e:
                raise Exception(f"Failed to discover tools via FastMCP: {str(e)}")
            
            mcp_load_time = (time.time() - mcp_load_start) * 1000
            
            logger.info("Retrieved tools using FastMCP service", 
                       source_id=source_id, 
                       tool_count=len(available_tools),
                       method="fastmcp_simplified",
                       load_time_ms=int(mcp_load_time))
            
            # FastMCP service already handled caching and updating source status
            # Just format the tools for response
            db_insert_start = time.time()
            cached_tools = [
                {
                    "name": tool["name"],
                    "description": tool["description"], 
                    "schema": tool["inputSchema"]
                }
                for tool in available_tools
            ]
            
            db_insert_time = (time.time() - db_insert_start) * 1000
            total_cache_time = (time.time() - cache_start) * 1000
            
            logger.info("Successfully cached tools for source",
                       source_id=source_id, 
                       source_name=source_name,
                       cached_tools=len(cached_tools),
                       timing={
                           "total_cache_time_ms": int(total_cache_time),
                           "mcp_load_time_ms": int(mcp_load_time),
                           "db_insert_time_ms": int(db_insert_time)
                       })
            
            return {
                "success": True,
                "cached_tools": len(cached_tools),
                "cache_time_ms": int(total_cache_time),
                "mcp_load_time_ms": int(mcp_load_time),
                "db_insert_time_ms": int(db_insert_time),
                "tools": cached_tools,
                "status": "newly_cached"
            }
            
        except Exception as e:
            # Update source with error status
            try:
                source.tools_cache_status = "error"
                source.tools_cache_error = str(e)
                await db.commit()
            except Exception as commit_error:
                logger.error("Failed to update source error status", 
                           source_id=source_id, error=str(commit_error))
            
            cache_time = (time.time() - cache_start) * 1000
            
            logger.error("Failed to cache tools for source",
                        source_id=source_id, 
                        error=str(e),
                        cache_time_ms=int(cache_time))
            
            return {
                "success": False,
                "error": str(e),
                "cached_tools": 0,
                "cache_time_ms": int(cache_time)
            }
    
    @staticmethod
    async def get_cached_tools_for_sources(
        db: AsyncSession, 
        source_ids: List[uuid.UUID]
    ) -> List[Dict[str, Any]]:
        """
        Get cached tools for multiple sources from database
        
        Args:
            db: Database session
            source_ids: List of source IDs to get tools for
            
        Returns:
            List of tool metadata dictionaries
        """
        if not source_ids:
            return []
        
        # Query cached tools
        tools_query = select(SourceTool, Source.name.label('source_name')).join(
            Source, SourceTool.source_id == Source.source_id
        ).where(
            SourceTool.source_id.in_(source_ids),
            SourceTool.is_active.is_(True),
            Source.is_active.is_(True)
        )
        
        result = await db.execute(tools_query)
        tools_data = result.all()
        
        cached_tools = []
        for tool_row, source_name in tools_data:
            cached_tools.append({
                "name": tool_row.tool_name,
                "description": tool_row.tool_description,
                "source_id": tool_row.source_id,
                "source_name": source_name,
                "schema": tool_row.tool_schema,
                "last_refreshed": tool_row.last_refreshed_at
            })
        
        logger.debug("Retrieved cached tools from database",
                    source_ids=source_ids,
                    tool_count=len(cached_tools))
        
        return cached_tools
    
    @staticmethod
    async def get_cache_status_for_sources(
        db: AsyncSession, 
        source_ids: List[uuid.UUID]
    ) -> Dict[uuid.UUID, Dict[str, Any]]:
        """
        Get cache status for multiple sources
        
        Args:
            db: Database session
            source_ids: List of source IDs to check
            
        Returns:
            Dict mapping source_id to cache status info
        """
        if not source_ids:
            return {}
        
        sources_query = select(Source).where(Source.source_id.in_(source_ids))
        result = await db.execute(sources_query)
        sources = result.scalars().all()
        
        status_map = {}
        for source in sources:
            status_map[source.source_id] = {
                "status": source.tools_cache_status,
                "last_cached": source.tools_last_cached_at,
                "error": source.tools_cache_error,
                "source_name": source.name
            }
        
        return status_map
    
    @staticmethod
    async def refresh_all_source_tools(db: AsyncSession) -> Dict[str, Any]:
        """
        Refresh tools for all active sources (background task)
        
        Args:
            db: Database session
            
        Returns:
            Summary of refresh results
        """
        logger.info("Starting refresh of all source tools")
        
        # Get all active sources
        sources_query = select(Source).where(Source.is_active.is_(True))
        result = await db.execute(sources_query)
        sources = result.scalars().all()
        
        refresh_results = {
            "total_sources": len(sources),
            "successful": 0,
            "failed": 0,
            "errors": []
        }
        
        for source in sources:
            try:
                result = await ToolCacheService.cache_tools_for_source(
                    db, source.source_id, force_refresh=True
                )
                
                if result["success"]:
                    refresh_results["successful"] += 1
                    logger.info("Refreshed tools for source", 
                               source_id=source.source_id, 
                               source_name=source.name,
                               tool_count=result["cached_tools"])
                else:
                    refresh_results["failed"] += 1
                    refresh_results["errors"].append({
                        "source_id": str(source.source_id),
                        "source_name": source.name,
                        "error": result["error"]
                    })
                    
            except Exception as e:
                refresh_results["failed"] += 1
                refresh_results["errors"].append({
                    "source_id": str(source.source_id),
                    "source_name": source.name,
                    "error": str(e)
                })
                logger.error("Failed to refresh source tools", 
                           source_id=source.source_id, error=str(e))
        
        logger.info("Completed refresh of all source tools", 
                   total=refresh_results["total_sources"],
                   successful=refresh_results["successful"],
                   failed=refresh_results["failed"])
        
        return refresh_results 
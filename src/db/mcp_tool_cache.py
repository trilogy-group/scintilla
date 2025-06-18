"""
Database-backed MCP Tool Cache Manager

Provides persistent caching of MCP tool information to avoid
repeated tool listing operations.
"""

import uuid
import json
import hashlib
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from langchain_core.tools import BaseTool
import structlog

from src.db.models import MCPToolCache as MCPToolCacheModel

logger = structlog.get_logger()


class MCPToolCacheManager:
    """Database-backed cache manager for MCP tools"""
    
    @staticmethod
    def _get_utc_now() -> datetime:
        """Get current UTC time with timezone awareness"""
        return datetime.now(timezone.utc)
    
    @staticmethod
    def _generate_cache_key(user_id: uuid.UUID, bot_source_ids: Optional[List[uuid.UUID]] = None) -> str:
        """Generate a unique cache key for the given configuration"""
        key_parts = [str(user_id)]
        if bot_source_ids:
            key_parts.extend(sorted(str(sid) for sid in bot_source_ids))
        
        # Create a hash of the key for consistent length
        key_string = "|".join(key_parts)
        return hashlib.sha256(key_string.encode()).hexdigest()[:32]
    
    @staticmethod
    def _serialize_tools(tools: List[BaseTool]) -> List[Dict[str, Any]]:
        """Serialize tools to JSON-compatible format"""
        logger.debug("Starting tool serialization", tool_count=len(tools))
        serialized_tools = []
        for i, tool in enumerate(tools):
            try:
                logger.debug("Serializing tool", tool_index=i, tool_name=getattr(tool, "name", "unknown"))
                
                # Simplified serialization - just capture essential info
                tool_data = {
                    "name": tool.name,
                    "description": tool.description,
                }
                
                # Try to add args_schema but don't fail if it doesn't work
                try:
                    if hasattr(tool, 'args_schema') and tool.args_schema:
                        tool_data["args_schema"] = tool.args_schema.model_json_schema()
                except Exception as schema_error:
                    logger.debug("Could not serialize args_schema", tool_name=tool.name, error=str(schema_error))
                    tool_data["args_schema"] = None
                
                # Try to add metadata but don't fail if it doesn't work
                try:
                    tool_data["metadata"] = getattr(tool, "metadata", {})
                except Exception as metadata_error:
                    logger.debug("Could not serialize metadata", tool_name=tool.name, error=str(metadata_error))
                    tool_data["metadata"] = {}
                
                serialized_tools.append(tool_data)
                logger.debug("Successfully serialized tool", tool_name=tool.name)
            except Exception as e:
                logger.warning(
                    "Failed to serialize tool",
                    tool_index=i,
                    tool_name=getattr(tool, "name", "unknown"),
                    error=str(e)
                )
                continue
        
        logger.debug("Tool serialization completed", serialized_count=len(serialized_tools))
        return serialized_tools
    
    @staticmethod
    async def get_cached_tools(
        db: AsyncSession,
        user_id: uuid.UUID,
        bot_source_ids: Optional[List[uuid.UUID]] = None,
        max_age_hours: int = 24
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached tools if available and not expired
        
        Args:
            db: Database session
            user_id: User ID
            bot_source_ids: Optional bot source IDs
            max_age_hours: Maximum age of cache in hours
            
        Returns:
            Cached tool data or None if not found/expired
        """
        cache_key = MCPToolCacheManager._generate_cache_key(user_id, bot_source_ids)
        
        # Query for cached data
        query = select(MCPToolCacheModel).where(
            MCPToolCacheModel.cache_key == cache_key
        )
        result = await db.execute(query)
        cache_entry = result.scalar_one_or_none()
        
        if not cache_entry:
            logger.debug("No cached tools found", cache_key=cache_key)
            return None
        
        # Check if cache is expired - use timezone-aware datetime
        now_utc = MCPToolCacheManager._get_utc_now()
        cutoff_time = now_utc - timedelta(hours=max_age_hours)
        
        # Ensure cache timestamp is timezone-aware
        cache_time = cache_entry.last_refreshed_at
        if cache_time.tzinfo is None:
            cache_time = cache_time.replace(tzinfo=timezone.utc)
        
        if cache_time < cutoff_time:
            logger.info(
                "Cached tools expired, removing",
                cache_key=cache_key,
                age_hours=(now_utc - cache_time).total_seconds() / 3600
            )
            await db.delete(cache_entry)
            await db.commit()
            return None
        
        # Return cached data
        age_seconds = (now_utc - cache_time).total_seconds()
        logger.info(
            "Using cached MCP tools",
            cache_key=cache_key,
            tool_count=cache_entry.tool_count,
            age_seconds=int(age_seconds),
            loaded_servers=cache_entry.loaded_servers
        )
        
        return {
            "tools_data": cache_entry.tools_data,
            "loaded_servers": cache_entry.loaded_servers,
            "tool_count": int(cache_entry.tool_count),
            "cached_at": cache_entry.last_refreshed_at,
            "age_seconds": int(age_seconds)
        }
    
    @staticmethod
    async def cache_tools(
        db: AsyncSession,
        user_id: uuid.UUID,
        tools: List[BaseTool],
        loaded_servers: List[str],
        bot_source_ids: Optional[List[uuid.UUID]] = None
    ) -> None:
        """
        Cache tools in the database
        
        Args:
            db: Database session
            user_id: User ID
            tools: List of tools to cache
            loaded_servers: List of server names
            bot_source_ids: Optional bot source IDs
        """
        cache_key = MCPToolCacheManager._generate_cache_key(user_id, bot_source_ids)
        
        # Serialize tools
        tools_data = MCPToolCacheManager._serialize_tools(tools)
        
        # Check if cache entry already exists
        query = select(MCPToolCacheModel).where(
            MCPToolCacheModel.cache_key == cache_key
        )
        result = await db.execute(query)
        existing_entry = result.scalar_one_or_none()
        
        now = MCPToolCacheManager._get_utc_now()
        
        if existing_entry:
            # Update existing entry
            existing_entry.tools_data = tools_data
            existing_entry.loaded_servers = loaded_servers
            existing_entry.tool_count = str(len(tools))
            existing_entry.last_refreshed_at = now
            
            logger.info(
                "Updated cached MCP tools",
                cache_key=cache_key,
                tool_count=len(tools),
                servers=loaded_servers
            )
        else:
            # Create new cache entry
            cache_entry = MCPToolCacheModel(
                user_id=user_id,
                bot_source_ids=bot_source_ids or [],
                tools_data=tools_data,
                loaded_servers=loaded_servers,
                tool_count=str(len(tools)),
                cache_key=cache_key,
                last_refreshed_at=now
            )
            db.add(cache_entry)
            
            logger.info(
                "Cached new MCP tools",
                cache_key=cache_key,
                tool_count=len(tools),
                servers=loaded_servers
            )
        
        await db.commit()
    
    @staticmethod
    async def invalidate_cache(
        db: AsyncSession,
        user_id: uuid.UUID,
        bot_source_ids: Optional[List[uuid.UUID]] = None
    ) -> bool:
        """
        Invalidate cached tools for the given configuration
        
        Args:
            db: Database session
            user_id: User ID
            bot_source_ids: Optional bot source IDs
            
        Returns:
            True if cache was invalidated, False if no cache found
        """
        cache_key = MCPToolCacheManager._generate_cache_key(user_id, bot_source_ids)
        
        # Delete cache entry
        query = delete(MCPToolCacheModel).where(
            MCPToolCacheModel.cache_key == cache_key
        )
        result = await db.execute(query)
        await db.commit()
        
        if result.rowcount > 0:
            logger.info("Invalidated MCP tool cache", cache_key=cache_key)
            return True
        else:
            logger.debug("No cache to invalidate", cache_key=cache_key)
            return False
    
    @staticmethod
    async def invalidate_user_cache(db: AsyncSession, user_id: uuid.UUID) -> int:
        """
        Invalidate all cached tools for a user
        
        Args:
            db: Database session
            user_id: User ID
            
        Returns:
            Number of cache entries invalidated
        """
        query = delete(MCPToolCacheModel).where(
            MCPToolCacheModel.user_id == user_id
        )
        result = await db.execute(query)
        await db.commit()
        
        logger.info(
            "Invalidated all MCP tool cache for user",
            user_id=user_id,
            entries_removed=result.rowcount
        )
        
        return result.rowcount
    
    @staticmethod
    async def clear_expired_cache(db: AsyncSession, max_age_hours: int = 24) -> int:
        """
        Clear all expired cache entries
        
        Args:
            db: Database session
            max_age_hours: Maximum age in hours
            
        Returns:
            Number of entries cleared
        """
        cutoff_time = MCPToolCacheManager._get_utc_now() - timedelta(hours=max_age_hours)
        
        query = delete(MCPToolCacheModel).where(
            MCPToolCacheModel.last_refreshed_at < cutoff_time
        )
        result = await db.execute(query)
        await db.commit()
        
        if result.rowcount > 0:
            logger.info(
                "Cleared expired MCP tool cache entries",
                entries_removed=result.rowcount,
                max_age_hours=max_age_hours
            )
        
        return result.rowcount 
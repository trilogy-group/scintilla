"""
FastMCP Integration Module

Centralized FastMCP client for all MCP operations in Scintilla.
Replaces legacy MCP SDK with modern FastMCP implementation.

Key Features:
- Tool discovery and caching via database
- Tool execution for conversations
- Connection testing and validation
- Proper Hive server authentication (x-api-key)
- Clean error handling and logging
"""

import uuid
import json
import asyncio
import time
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse, urlencode, urlunparse, parse_qs

import structlog
from fastmcp import Client as FastMCPClient
from mcp import ClientSession
from mcp.client.sse import sse_client
import httpx
from langchain_core.tools import BaseTool, Tool
from langchain.tools import StructuredTool
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from src.db.models import Source, SourceTool, BotSourceAssociation
from src.db.mcp_credentials import SimplifiedCredentialManager

logger = structlog.get_logger()


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server connection"""
    source_id: uuid.UUID
    name: str
    server_url: str
    auth_headers: Optional[Dict[str, str]] = None


class FastMCPService:
    """
    Centralized service for all FastMCP operations using simplified authentication
    
    Handles:
    - Tool discovery and caching
    - Tool execution during conversations  
    - Connection testing
    - Unified authentication (headers or URL-embedded)
    """
    
    @staticmethod
    def _prepare_auth_for_fastmcp(
        server_url: str, 
        auth_headers: Optional[Dict[str, str]] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Prepare authentication for FastMCP client
        
        Args:
            server_url: Server URL (may already contain embedded auth)
            auth_headers: Optional authentication headers
            
        Returns:
            Tuple of (final_url, fastmcp_config)
        """
        if not auth_headers or len(auth_headers) == 0:
            # No headers provided or empty dict - use URL as-is (may have embedded auth)
            return server_url, {}
        
        # Handle different auth methods for FastMCP
        fastmcp_config = {}
        
        if "Authorization" in auth_headers:
            auth_value = auth_headers["Authorization"]
            if auth_value.startswith("Bearer "):
                # For Bearer tokens, pass the full Authorization header value
                # Some servers (like MCP Atlassian) expect the full "Bearer <token>" format
                fastmcp_config["headers"] = {"Authorization": auth_value}
            else:
                # For other auth types, try passing as auth parameter
                fastmcp_config["auth"] = auth_value
        elif "x-api-key" in auth_headers:
            # For x-api-key, try embedding in URL as FastMCP might expect it there
            from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
            parsed = urlparse(server_url)
            query_params = parse_qs(parsed.query)
            query_params["x-api-key"] = [auth_headers["x-api-key"]]
            new_query = urlencode(query_params, doseq=True)
            server_url = urlunparse(parsed._replace(query=new_query))
        else:
            # For any other headers, pass them directly
            fastmcp_config["headers"] = auth_headers
        
        return server_url, fastmcp_config
    
    @staticmethod
    async def test_connection(
        server_url: str, 
        auth_headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Test connection to MCP server using official MCP client (consistent with tool calls)
        
        Args:
            server_url: MCP server URL 
            auth_headers: Optional authentication headers
            
        Returns:
            Dictionary with test results
        """
        start_time = time.time()
        
        try:
            # Use the same authentication method as tool calls and discovery
            headers = {}
            sse_url = server_url
            
            # Handle URL-embedded authentication (Hive style)
            if "x-api-key=" in server_url:
                from urllib.parse import urlparse, parse_qs
                parsed = urlparse(server_url)
                query_params = parse_qs(parsed.query)
                if "x-api-key" in query_params:
                    api_key = query_params["x-api-key"][0]
                    headers["x-api-key"] = api_key
                    # Remove auth from URL for clean SSE connection
                    sse_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                    if not sse_url.endswith('/sse'):
                        sse_url += '/sse'
            else:
                # Handle header-based authentication (Atlassian style)
                if auth_headers and len(auth_headers) > 0:
                    headers.update(auth_headers)
                # Ensure URL ends with /sse
                if not sse_url.endswith('/sse'):
                    sse_url += '/sse'
            
            # Test connection using official MCP client
            async with sse_client(sse_url, headers=headers) as (transport_read, transport_write):
                async with ClientSession(transport_read, transport_write) as session:
                    await session.initialize()
                    tools_response = await asyncio.wait_for(session.list_tools(), timeout=15.0)
                    tools = tools_response.tools
                    
                    end_time = time.time()
                    response_time = int((end_time - start_time) * 1000)
                    
                    return {
                        "success": True,
                        "message": "Connection successful",
                        "tool_count": len(tools),
                        "response_time_ms": response_time,
                        "tools": [tool.name for tool in tools[:10]]  # First 10 tools
                    }
                
        except asyncio.TimeoutError:
            return {
                "success": False,
                "message": "Connection timed out after 15 seconds",
                "tool_count": 0,
                "response_time_ms": 15000
            }
        except Exception as e:
            end_time = time.time()
            response_time = int((end_time - start_time) * 1000)
            
            return {
                "success": False,
                "message": f"Connection failed: {str(e)}",
                "tool_count": 0,
                "response_time_ms": response_time
            }
    
    @staticmethod
    async def discover_and_cache_tools(
        db: AsyncSession,
        source_id: uuid.UUID
    ) -> Tuple[bool, str, int]:
        """
        Discover tools from MCP server and cache them in database
        
        Args:
            db: Database session
            source_id: Source ID to cache tools for
            
        Returns:
            Tuple of (success, message, tool_count)
        """
        try:
            # Get source authentication configuration
            auth_config = await SimplifiedCredentialManager.get_source_auth(db, source_id)
            if not auth_config:
                return False, "Source authentication not found", 0
            
            server_url = auth_config["server_url"]
            auth_headers = auth_config["auth_headers"]
            
            # Update source status to indicate caching in progress
            await db.execute(
                update(Source)
                .where(Source.source_id == source_id)
                .values(
                    tools_cache_status="caching",
                    tools_cache_error=None
                )
            )
            await db.commit()
            
            # Check if this is a local:// URL scheme that should route to local agents
            if server_url.startswith(("local://", "stdio://", "agent://")):
                return await FastMCPService._discover_tools_from_local_agent(
                    db, source_id, server_url
                )
            
            # Use the same authentication method as tool calls (official MCP client)
            # This ensures consistency and works with servers that need specific header formats
            headers = {}
            sse_url = server_url
            
            # Handle URL-embedded authentication (Hive style)
            if "x-api-key=" in server_url:
                from urllib.parse import urlparse, parse_qs
                parsed = urlparse(server_url)
                query_params = parse_qs(parsed.query)
                if "x-api-key" in query_params:
                    api_key = query_params["x-api-key"][0]
                    headers["x-api-key"] = api_key
                    # Remove auth from URL for clean SSE connection
                    sse_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                    if not sse_url.endswith('/sse'):
                        sse_url += '/sse'
            else:
                # Handle header-based authentication (Atlassian style)
                if auth_headers and len(auth_headers) > 0:
                    headers.update(auth_headers)
                # Ensure URL ends with /sse
                if not sse_url.endswith('/sse'):
                    sse_url += '/sse'
            
            # Discover tools using official MCP client (same as tool calls)
            async with sse_client(sse_url, headers=headers) as (transport_read, transport_write):
                async with ClientSession(transport_read, transport_write) as session:
                    await session.initialize()
                    tools_response = await asyncio.wait_for(session.list_tools(), timeout=30.0)
                    tools = tools_response.tools
            
            # Clear existing cached tools for this source
            await db.execute(
                SourceTool.__table__.delete().where(SourceTool.source_id == source_id)
            )
            
            # Cache new tools
            for tool in tools:
                # Handle various schema formats
                tool_schema = {}
                if hasattr(tool, 'inputSchema'):
                    # Some tools might have inputSchema = None
                    tool_schema = tool.inputSchema if tool.inputSchema is not None else {}
                
                source_tool = SourceTool(
                    source_id=source_id,
                    tool_name=tool.name,
                    tool_description=tool.description,
                    tool_schema=tool_schema,
                    last_refreshed_at=datetime.now(timezone.utc),
                    is_active=True
                )
                db.add(source_tool)
            
            # Update source status to indicate successful caching
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
            
            logger.info(
                "Tools discovered and cached successfully",
                source_id=source_id,
                tool_count=len(tools)
            )
            
            return True, f"Successfully cached {len(tools)} tools", len(tools)
            
        except asyncio.TimeoutError:
            error_msg = "Tool discovery timed out after 30 seconds"
            await FastMCPService._update_cache_error(db, source_id, error_msg)
            return False, error_msg, 0
            
        except Exception as e:
            error_msg = f"Tool discovery failed: {str(e)}"
            await FastMCPService._update_cache_error(db, source_id, error_msg)
            return False, error_msg, 0
    
    @staticmethod
    async def _discover_tools_from_local_agent(
        db: AsyncSession,
        source_id: uuid.UUID,
        server_url: str
    ) -> Tuple[bool, str, int]:
        """
        Check if tools are already cached for this local source.
        
        Local agent tools should be refreshed using the /agents/refresh-tools endpoint,
        not discovered on-demand. This method just checks if tools are cached.
        
        Args:
            db: Database session
            source_id: Source ID to check for cached tools
            server_url: Local URL scheme (e.g., local://khoros-atlassian)
            
        Returns:
            Tuple of (success, message, tool_count)
        """
        try:
            # Check if we already have cached tools for this source
            from sqlalchemy import select, func
            result = await db.execute(
                select(func.count(SourceTool.tool_name))
                .where(SourceTool.source_id == source_id)
                .where(SourceTool.is_active == True)
            )
            tool_count = result.scalar_one()
            
            if tool_count > 0:
                logger.info(
                    "Found cached tools for local source",
                    source_id=source_id,
                    server_url=server_url,
                    tool_count=tool_count
                )
                return True, f"Using {tool_count} cached tools", tool_count
            
            # No cached tools found - tools need to be refreshed first
            error_msg = (
                f"No cached tools found for {server_url}. "
                f"Please use POST /api/agents/refresh-tools with appropriate agent_id and capability "
                f"to discover and cache tools for this local source."
            )
            
            await FastMCPService._update_cache_error(db, source_id, error_msg)
            
            logger.warning(
                "No cached tools for local source",
                source_id=source_id,
                server_url=server_url,
                message=error_msg
            )
            
            return False, error_msg, 0
            
        except Exception as e:
            error_msg = f"Local agent tool check failed: {str(e)}"
            await FastMCPService._update_cache_error(db, source_id, error_msg)
            logger.error("Local agent tool check error", error=str(e), source_id=source_id)
            return False, error_msg, 0
    
    @staticmethod
    async def _update_cache_error(db: AsyncSession, source_id: uuid.UUID, error_msg: str):
        """Update source with caching error"""
        try:
            await db.execute(
                update(Source)
                .where(Source.source_id == source_id)
                .values(
                    tools_cache_status="error",
                    tools_cache_error=error_msg
                )
            )
            await db.commit()
            logger.error("Updated source with cache error", source_id=source_id, error=error_msg)
        except Exception as e:
            logger.error("Failed to update source cache error", source_id=source_id, error=str(e))
    
    @staticmethod
    async def call_tool(
        server_url: str,
        auth_headers: Optional[Dict[str, str]],
        tool_name: str,
        arguments: Dict[str, Any],
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Call a specific tool on an MCP server using official MCP client with retry logic
        or route to local agents for local:// URLs
        
        Args:
            server_url: MCP server URL or local:// scheme
            auth_headers: Optional authentication headers
            tool_name: Name of the tool to call
            arguments: Tool arguments
            max_retries: Maximum number of retry attempts
            
        Returns:
            Tool result dictionary
        """
        
        # Check if this is a local:// URL scheme that should route to local agents
        if server_url.startswith(("local://", "stdio://", "agent://")):
            return await FastMCPService._call_tool_via_local_agent(
                server_url, tool_name, arguments
            )
        
        # Handle remote MCP servers with retry logic
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                # Debug logging
                if attempt == 0:
                    logger.info(
                        "FastMCPService.call_tool called with official MCP client",
                        tool_name=tool_name,
                        arguments=arguments,
                        server_url=server_url,
                        has_auth_headers=bool(auth_headers)
                    )
                else:
                    logger.info(
                        "Retrying tool call",
                        tool_name=tool_name,
                        attempt=attempt,
                        max_retries=max_retries
                    )
                
                # Prepare headers for official MCP client (extract auth from URL if needed)
                headers = {}
                sse_url = server_url
                
                # Handle URL-embedded authentication (Hive style)
                if "x-api-key=" in server_url:
                    from urllib.parse import urlparse, parse_qs
                    parsed = urlparse(server_url)
                    query_params = parse_qs(parsed.query)
                    if "x-api-key" in query_params:
                        api_key = query_params["x-api-key"][0]
                        headers["x-api-key"] = api_key
                        # Remove auth from URL for clean SSE connection
                        sse_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                        if not sse_url.endswith('/sse'):
                            sse_url += '/sse'
                    logger.info(f"Extracted Hive auth from URL: x-api-key present, clean URL: {sse_url}")
                else:
                    # Handle header-based authentication (Atlassian style)
                    if auth_headers and len(auth_headers) > 0:
                        headers.update(auth_headers)
                    # Ensure URL ends with /sse
                    if not sse_url.endswith('/sse'):
                        sse_url += '/sse'
                
                # Add small delay between retries to avoid overwhelming server
                if attempt > 0:
                    await asyncio.sleep(min(attempt * 0.5, 2.0))  # 0.5s, 1s, 2s max
                
                async with sse_client(sse_url, headers=headers) as (transport_read, transport_write):
                    async with ClientSession(transport_read, transport_write) as session:
                        # Initialize the session
                        await session.initialize()
                        
                        # List available tools for debugging (only on first attempt)
                        if attempt == 0:
                            try:
                                tools_response = await session.list_tools()
                                tool_names = [tool.name for tool in tools_response.tools]
                                logger.info(
                                    "Available tools on server (official MCP client)",
                                    tool_count=len(tool_names),
                                    has_search_emails='search_emails' in tool_names,
                                    has_jira_search='jira_search' in tool_names,
                                    first_few_tools=tool_names[:5]
                                )
                            except Exception as e:
                                logger.warning("Failed to list tools with official client", error=str(e))
                        
                        # Call the tool
                        result = await asyncio.wait_for(
                            session.call_tool(tool_name, arguments), 
                            timeout=60.0
                        )
                        
                        logger.info(
                            "Official MCP client tool call succeeded",
                            tool_name=tool_name,
                            attempt=attempt,
                            result_type=type(result).__name__
                        )
                        
                        # Extract result content
                        tool_result = ""
                        if hasattr(result, 'content') and result.content:
                            for content_item in result.content:
                                if hasattr(content_item, 'text'):
                                    tool_result += content_item.text
                                else:
                                    tool_result += str(content_item)
                        else:
                            tool_result = str(result)
                        
                        return {
                            "success": True,
                            "result": tool_result,
                            "tool_name": tool_name,
                            "arguments": arguments
                        }
                    
            except asyncio.TimeoutError as e:
                last_error = e
                if attempt == max_retries:
                    logger.error(
                        "Official MCP tool call timed out after all retries",
                        tool_name=tool_name,
                        timeout=60.0,
                        attempts=attempt + 1
                    )
                    return {
                        "success": False,
                        "error": f"Tool call timed out after 60 seconds (tried {attempt + 1} times)",
                        "tool_name": tool_name,
                        "arguments": arguments
                    }
                else:
                    logger.warning(
                        "Tool call timed out, retrying",
                        tool_name=tool_name,
                        attempt=attempt
                    )
                    
            except Exception as e:
                last_error = e
                if attempt == max_retries:
                    logger.error(
                        "Official MCP tool call failed after all retries",
                        tool_name=tool_name,
                        error=str(e),
                        exception_type=type(e).__name__,
                        attempts=attempt + 1
                    )
                    return {
                        "success": False,
                        "error": f"Tool call failed: {str(e)} (tried {attempt + 1} times)",
                        "tool_name": tool_name,
                        "arguments": arguments
                    }
                else:
                    logger.warning(
                        "Tool call failed, retrying",
                        tool_name=tool_name,
                        error=str(e),
                        attempt=attempt
                    )
        
        # Should never reach here, but just in case
        return {
            "success": False,
            "error": f"Tool call failed after {max_retries + 1} attempts: {str(last_error)}",
            "tool_name": tool_name,
            "arguments": arguments
        }
    
    @staticmethod
    async def _call_tool_via_local_agent(
        server_url: str,
        tool_name: str,
        arguments: Dict[str, Any],
        timeout_seconds: int = 60
    ) -> Dict[str, Any]:
        """
        Execute a tool via local agents using the local agent API
        
        Args:
            server_url: Local URL scheme (e.g., local://khoros-atlassian)
            tool_name: Name of the tool to call
            arguments: Tool arguments
            timeout_seconds: Timeout for tool execution
            
        Returns:
            Tool result dictionary
        """
        try:
            # Import here to avoid circular imports
            from src.api.local_agents import execute_local_tool
            
            logger.info(
                "🏠 Routing tool call to local agent",
                tool_name=tool_name,
                arguments=arguments,
                server_url=server_url
            )
            
            # Execute via local agent system
            result = await execute_local_tool(tool_name, arguments, timeout_seconds)
            
            logger.info(
                "🏠 Local agent tool call completed",
                tool_name=tool_name,
                success=result.get("success", False)
            )
            
            return result
            
        except Exception as e:
            logger.error(
                "🏠 Local agent tool call failed",
                tool_name=tool_name,
                error=str(e)
            )
            return {
                "success": False,
                "error": f"Local agent execution failed: {str(e)}",
                "tool_name": tool_name,
                "arguments": arguments
            }


class FastMCPToolManager:
    """
    Manager for loading and binding FastMCP tools for LangChain
    
    Loads tools from database cache and creates LangChain-compatible tools
    that use FastMCP for execution.
    """
    
    def __init__(self):
        self.server_configs: List[MCPServerConfig] = []
        self.tools: List[BaseTool] = []
        self.sources: List[Source] = []
        
    async def load_tools_for_user(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        bot_source_ids: Optional[List[uuid.UUID]] = None
    ) -> int:
        """
        Load tools from database cache for user and optional bot sources
        
        Args:
            db: Database session
            user_id: User ID
            bot_source_ids: Optional bot source IDs to include
            
        Returns:
            Number of tools loaded
        """
        # Get user sources
        user_sources_query = select(Source).where(
            Source.owner_user_id == user_id,
            Source.is_active.is_(True),
            Source.tools_cache_status == "cached"
        )
        
        # Get bot sources if specified and non-empty
        bot_sources_query = None
        if bot_source_ids and len(bot_source_ids) > 0:
            bot_sources_query = select(Source).where(
                Source.source_id.in_(bot_source_ids),
                Source.is_active.is_(True),
                Source.tools_cache_status == "cached"
            )
        
        # Execute queries
        user_sources_result = await db.execute(user_sources_query)
        user_sources = user_sources_result.scalars().all()
        
        bot_sources = []
        if bot_sources_query is not None:
            bot_sources_result = await db.execute(bot_sources_query)
            bot_sources = bot_sources_result.scalars().all()
        
        all_sources = list(user_sources) + list(bot_sources)
        
        if not all_sources:
            logger.warning("No cached sources found for tool loading")
            return 0
        
        return await self._load_tools_from_sources(db, all_sources)
    
    async def load_tools_for_specific_sources(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        source_ids: List[uuid.UUID]
    ) -> int:
        """
        Load tools from database cache for specific source IDs only
        
        Args:
            db: Database session
            user_id: User ID (for access control)
            source_ids: Specific source IDs to load tools from
            
        Returns:
            Number of tools loaded
        """
        if not source_ids:
            logger.info("No source IDs provided - loading no tools")
            return 0
        
        # Get sources by IDs with access control - user must have access to these sources
        sources_query = select(Source).where(
            Source.source_id.in_(source_ids),
            Source.is_active.is_(True),
            Source.tools_cache_status == "cached"
        ).where(
            # User has access if they own it, it's public, it's shared with them, or it's a bot source
            (Source.owner_user_id == user_id) |  # User owns it
            (Source.is_public == True) |  # Public source
            (Source.owner_bot_id != None)  # Bot-owned source (accessible to all users)
            # TODO: Add proper sharing check via SourceShare table if needed
        )
        
        sources_result = await db.execute(sources_query)
        filtered_sources = sources_result.scalars().all()
        
        logger.info(
            "Filtered sources for specific source loading",
            requested_sources=len(source_ids),
            accessible_sources=len(filtered_sources),
            accessible_source_ids=[s.source_id for s in filtered_sources],
            user_id=user_id
        )
        
        if not filtered_sources:
            logger.warning(
                "No accessible sources found for requested IDs",
                requested_source_ids=source_ids,
                user_id=user_id
            )
            return 0
        
        return await self._load_tools_from_sources(db, filtered_sources)
    
    async def _load_tools_from_sources(
        self,
        db: AsyncSession,
        sources: List[Source]
    ) -> int:
        """
        Common method to load tools from a list of source objects
        
        Args:
            db: Database session
            sources: List of Source objects to load tools from
            
        Returns:
            Number of tools loaded
        """
        if not sources:
            logger.warning("No sources provided for tool loading")
            return 0
        
        # Store sources for instruction retrieval
        self.sources = sources
        
        # Build server configs 
        self.server_configs = []
        
        for source in sources:
            # Extract source attributes
            source_id = source.source_id
            source_name = source.name
            source_url = source.server_url
            source_auth_headers = source.auth_headers or {}
            
            config = MCPServerConfig(
                source_id=source_id,
                name=source_name,
                server_url=source_url,
                auth_headers=source_auth_headers
            )
            self.server_configs.append(config)
        
        # Get cached tools for all sources
        source_ids = [config.source_id for config in self.server_configs]
        
        # Only query for cached tools if we have source IDs
        cached_tools = []
        if source_ids:
            cached_tools_query = select(SourceTool).where(
                SourceTool.source_id.in_(source_ids),
                SourceTool.is_active.is_(True)
            )
            
            cached_tools_result = await db.execute(cached_tools_query)
            cached_tools = cached_tools_result.scalars().all()
        
        # Create LangChain tools from cached data
        self.tools = []
        
        for cached_tool in cached_tools:
            # Find server config for this tool
            server_config = next(
                (config for config in self.server_configs if config.source_id == cached_tool.source_id),
                None
            )
            
            if not server_config:
                continue
            
            # Create LangChain tool that uses FastMCP
            langchain_tool = self._create_langchain_tool(cached_tool, server_config)
            self.tools.append(langchain_tool)
        
        logger.info(
            "FastMCP tools loaded from sources",
            total_tools=len(self.tools),
            cached_tools_found=len(cached_tools),
            tools_skipped=len(cached_tools) - len(self.tools),
            source_count=len(self.server_configs),
            sources_used=len(sources)
        )
        
        return len(self.tools)
    
    def _create_langchain_tool(self, cached_tool: SourceTool, server_config: MCPServerConfig) -> BaseTool:
        """Create a LangChain tool that uses FastMCP for execution"""
        from pydantic import BaseModel, create_model, Field
        from typing import Optional, Any
        
        # Extract tool metadata
        original_tool_name = cached_tool.tool_name
        tool_description = cached_tool.tool_description or f"Tool {original_tool_name} from {server_config.name}"
        tool_schema = cached_tool.tool_schema or {}
        
        # Create namespaced tool name to avoid conflicts between sources
        # Convert source name to safe identifier (replace spaces/special chars with underscores)
        safe_source_name = "".join(c if c.isalnum() else "_" for c in server_config.name.lower())
        safe_source_name = safe_source_name.strip("_")  # Remove leading/trailing underscores
        
        # Create namespaced tool name: source_toolname
        namespaced_tool_name = f"{safe_source_name}_{original_tool_name}"
        
        # Update description to indicate source
        enhanced_description = f"[{server_config.name}] {tool_description}"
        
        # Get schema properties
        properties = tool_schema.get("properties", {})
        required_params = tool_schema.get("required", [])
        
        # Create Pydantic model from MCP schema for LangChain
        pydantic_fields = {}
        
        for param_name, param_def in properties.items():
            param_type = param_def.get("type", "string")
            param_description = param_def.get("description", "")
            param_default = param_def.get("default")
            
            # Map JSON Schema types to Python types
            if param_type == "string":
                python_type = str
            elif param_type == "integer":
                python_type = int
            elif param_type == "number":
                python_type = float
            elif param_type == "boolean":
                python_type = bool
            else:
                python_type = Any
            
            # Make optional if not in required params
            if param_name not in required_params:
                python_type = Optional[python_type]
                if param_default is not None:
                    pydantic_fields[param_name] = (python_type, Field(default=param_default, description=param_description))
                else:
                    pydantic_fields[param_name] = (python_type, Field(default=None, description=param_description))
            else:
                pydantic_fields[param_name] = (python_type, Field(description=param_description))
        
        # Create dynamic Pydantic model
        if pydantic_fields:
            args_schema = create_model(f"{namespaced_tool_name}Args", **pydantic_fields)
        else:
            # Handle tools with missing/empty schemas - assume they take no parameters
            args_schema = create_model(f"{namespaced_tool_name}Args")  # Empty model = no parameters
            
            if tool_schema is None:
                logger.info(f"🔧 Tool {namespaced_tool_name} has no schema (None) - creating no-parameter tool")
            elif tool_schema == {}:
                logger.info(f"🔧 Tool {namespaced_tool_name} has empty schema ({{}}) - creating no-parameter tool")
            else:
                logger.info(f"🔧 Tool {namespaced_tool_name} has schema with no properties - creating no-parameter tool")
        
        # Create dynamic tool function
        async def tool_func(**kwargs) -> str:
            """Dynamic tool function that calls FastMCP"""
            logger.info(f"🔧 NAMESPACED TOOL CALL: {namespaced_tool_name} -> {original_tool_name} with {kwargs}")
            
            # Call the original tool name on the MCP server
            result = await FastMCPService.call_tool(
                server_url=server_config.server_url,
                auth_headers=server_config.auth_headers,
                tool_name=original_tool_name,  # Use original name for MCP server
                arguments=kwargs
            )
            
            if result.get("success"):
                return result["result"]
            else:
                return f"Error: {result.get('error', 'Unknown error')}"
        
        # Use StructuredTool for proper schema handling
        from langchain.tools import StructuredTool
        
        return StructuredTool(
            name=namespaced_tool_name,  # Use namespaced name for LangChain
            description=enhanced_description,  # Enhanced description with source info
            func=tool_func,
            coroutine=tool_func,  # For async execution
            args_schema=args_schema,  # Properly handles empty schemas
            metadata={
                'source_id': server_config.source_id,
                'source_name': server_config.name,
                'server_url': server_config.server_url,
                'original_tool_name': original_tool_name  # Store original name for reference
            }
        )
    
    def get_tools(self) -> List[BaseTool]:
        """Get loaded LangChain tools"""
        return self.tools.copy()
    
    def get_server_names(self) -> List[str]:
        """Get names of loaded servers"""
        return [config.name for config in self.server_configs]
    
    def filter_search_tools(self) -> List[BaseTool]:
        """Filter tools to search/read-only tools (excludes destructive operations)"""
        search_keywords = [
            'search', 'get', 'list', 'find', 'read', 'fetch', 'query', 'lookup',
            'retrieve', 'browse', 'view', 'show', 'describe', 'info'
        ]
        
        destructive_keywords = [
            'delete', 'remove', 'create', 'update', 'modify', 'write', 'post',
            'put', 'patch', 'edit', 'change', 'set', 'insert', 'add'
        ]
        
        search_tools = []
        
        for tool in self.tools:
            tool_name_lower = tool.name.lower()
            tool_desc_lower = (tool.description or "").lower()
            
            # Check if it's a search tool
            is_search = any(keyword in tool_name_lower or keyword in tool_desc_lower 
                          for keyword in search_keywords)
            
            # Check if it's destructive
            is_destructive = any(keyword in tool_name_lower or keyword in tool_desc_lower 
                               for keyword in destructive_keywords)
            
            # Include if it's a search tool and not destructive
            if is_search and not is_destructive:
                search_tools.append(tool)
        
        return search_tools
    
    async def get_source_instructions(self, db: AsyncSession) -> Dict[str, str]:
        """Get instructions for all loaded sources, including bot-specific instructions"""
        instructions_map = {}
        
        if hasattr(self, 'sources'):
            for source in self.sources:
                # Extract attributes early to avoid greenlet issues
                source_name = source.name
                source_instructions = source.instructions
                source_id = source.source_id
                
                # First check for bot-specific instructions in BotSourceAssociation
                bot_instructions_query = select(BotSourceAssociation.custom_instructions).where(
                    BotSourceAssociation.source_id == source_id,
                    BotSourceAssociation.custom_instructions.isnot(None),
                    BotSourceAssociation.custom_instructions != ""
                )
                
                bot_instructions_result = await db.execute(bot_instructions_query)
                bot_instructions = bot_instructions_result.scalar()
                
                # Use bot-specific instructions if available, otherwise fall back to source instructions
                if bot_instructions:
                    instructions_map[source_name] = bot_instructions
                    logger.info(f"📋 Found BOT-SPECIFIC instructions for source: {source_name} -> {bot_instructions}")
                elif source_instructions:
                    instructions_map[source_name] = source_instructions
                    logger.info(f"📋 Found general instructions for source: {source_name} -> {source_instructions}")
        
        logger.info(f"📋 Loaded instructions for {len(instructions_map)} sources")
        return instructions_map 
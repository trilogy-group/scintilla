"""
LangChain MCP Agent using official langchain-mcp-adapters

This module provides MCP agent integration using the official
LangChain MCP adapters with robust credential management.
"""

import uuid
import os
import json
import re
import time
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Ensure environment variables are loaded
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

from typing import List, Dict, Any, AsyncGenerator, Optional, Tuple
import structlog

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.tools import BaseTool
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from langchain_mcp_adapters.client import MultiServerMCPClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.mcp_credentials import MCPCredentialManager
# MCPToolCacheManager removed - using simple source-based loading
from src.agents.citations import SourceExtractor, CitationManager, Source

logger = structlog.get_logger()


class MCPConnectionPool:
    """Connection pool for MCP clients to improve performance"""
    
    def __init__(self, max_connections: int = 10):
        self._pool: Dict[str, MultiServerMCPClient] = {}
        self._pool_lock = asyncio.Lock()
        self._max_connections = max_connections
        self._connection_count = 0
        
    async def get_client(self, server_configs: Dict) -> MultiServerMCPClient:
        """Get or create MCP client from pool"""
        # Create a hash key from server configs
        config_key = self._hash_configs(server_configs)
        
        async with self._pool_lock:
            if config_key in self._pool:
                logger.debug("Reusing MCP client from pool", config_key=config_key[:16])
                return self._pool[config_key]
            
            if self._connection_count >= self._max_connections:
                # Simple LRU eviction - remove oldest
                oldest_key = next(iter(self._pool))
                old_client = self._pool.pop(oldest_key)
                await self._close_client(old_client)
                self._connection_count -= 1
                logger.debug("Evicted old MCP client from pool", evicted_key=oldest_key[:16])
            
            # Create new client
            logger.debug("Creating new MCP client for pool", config_key=config_key[:16])
            client = MultiServerMCPClient(server_configs)
            self._pool[config_key] = client
            self._connection_count += 1
            
            return client
    
    def _hash_configs(self, server_configs: Dict) -> str:
        """Create a hash key from server configurations"""
        # Sort configs for consistent hashing
        sorted_configs = json.dumps(server_configs, sort_keys=True)
        import hashlib
        return hashlib.md5(sorted_configs.encode()).hexdigest()
    
    async def _close_client(self, client: MultiServerMCPClient):
        """Close MCP client gracefully"""
        try:
            # Add any cleanup logic here if needed
            pass
        except Exception as e:
            logger.warning("Error closing MCP client", error=str(e))
    
    async def close_all(self):
        """Close all connections in pool"""
        async with self._pool_lock:
            for client in self._pool.values():
                await self._close_client(client)
            self._pool.clear()
            self._connection_count = 0


# Global connection pool
_mcp_pool = MCPConnectionPool()


class ContentProcessor:
    """Handles intelligent content truncation and summarization"""
    
    # Token limits for different content types
    MAX_TOKENS_PER_TOOL = 15000  # Max tokens per tool result
    MAX_TOKENS_SEARCH_RESULT = 8000  # Max tokens for search results
    MAX_TOKENS_FILE_CONTENT = 12000  # Max tokens for file content
    
    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Rough token estimation (1 token ≈ 4 characters for most text)"""
        return len(str(text)) // 4
    
    @staticmethod
    async def truncate_with_context_async(content: str, max_tokens: int, query_context: str = "") -> Dict[str, Any]:
        """
        Async version of intelligent content truncation
        
        Args:
            content: Original content
            max_tokens: Maximum tokens allowed
            query_context: User query for context-aware truncation
            
        Returns:
            Dict with truncated content and metadata
        """
        if not content:
            return {"content": "", "truncated": False, "original_tokens": 0}
        
        content_str = str(content)
        original_tokens = ContentProcessor.estimate_tokens(content_str)
        
        if original_tokens <= max_tokens:
            return {
                "content": content_str,
                "truncated": False,
                "original_tokens": original_tokens
            }
        
        # Calculate target length
        target_length = max_tokens * 4  # Convert tokens back to characters
        
        # Try to find relevant sections based on query context
        if query_context:
            relevant_sections = await ContentProcessor._extract_relevant_sections_async(
                content_str, query_context, target_length
            )
            if relevant_sections:
                return {
                    "content": relevant_sections,
                    "truncated": True,
                    "original_tokens": original_tokens,
                    "truncated_tokens": ContentProcessor.estimate_tokens(relevant_sections),
                    "truncation_method": "context_aware"
                }
        
        # Fallback: Smart truncation with beginning and end
        truncated = ContentProcessor._smart_truncate(content_str, target_length)
        
        return {
            "content": truncated,
            "truncated": True,
            "original_tokens": original_tokens,
            "truncated_tokens": ContentProcessor.estimate_tokens(truncated),
            "truncation_method": "smart_truncate"
        }
    
    @staticmethod
    def truncate_with_context(content: str, max_tokens: int, query_context: str = "") -> Dict[str, Any]:
        """
        Intelligently truncate content while preserving relevant sections
        
        Args:
            content: Original content
            max_tokens: Maximum tokens allowed
            query_context: User query for context-aware truncation
            
        Returns:
            Dict with truncated content and metadata
        """
        if not content:
            return {"content": "", "truncated": False, "original_tokens": 0}
        
        content_str = str(content)
        original_tokens = ContentProcessor.estimate_tokens(content_str)
        
        if original_tokens <= max_tokens:
            return {
                "content": content_str,
                "truncated": False,
                "original_tokens": original_tokens
            }
        
        # Calculate target length
        target_length = max_tokens * 4  # Convert tokens back to characters
        
        # Try to find relevant sections based on query context
        if query_context:
            relevant_sections = ContentProcessor._extract_relevant_sections(
                content_str, query_context, target_length
            )
            if relevant_sections:
                return {
                    "content": relevant_sections,
                    "truncated": True,
                    "original_tokens": original_tokens,
                    "truncated_tokens": ContentProcessor.estimate_tokens(relevant_sections),
                    "truncation_method": "context_aware"
                }
        
        # Fallback: Smart truncation with beginning and end
        truncated = ContentProcessor._smart_truncate(content_str, target_length)
        
        return {
            "content": truncated,
            "truncated": True,
            "original_tokens": original_tokens,
            "truncated_tokens": ContentProcessor.estimate_tokens(truncated),
            "truncation_method": "smart_truncate"
        }
    
    @staticmethod
    async def _extract_relevant_sections_async(content: str, query: str, target_length: int) -> str:
        """Async version of extract relevant sections"""
        # Run CPU-intensive work in thread pool
        return await asyncio.get_event_loop().run_in_executor(
            None, ContentProcessor._extract_relevant_sections, content, query, target_length
        )
    
    @staticmethod
    def _extract_relevant_sections(content: str, query: str, target_length: int) -> str:
        """Extract sections most relevant to the query"""
        query_lower = query.lower()
        query_keywords = re.findall(r'\b\w+\b', query_lower)
        
        # Split content into sections (paragraphs, code blocks, etc.)
        sections = []
        
        # Split by double newlines (paragraphs)
        paragraphs = content.split('\n\n')
        for para in paragraphs:
            if len(para.strip()) > 50:  # Skip very short sections
                sections.append(para.strip())
        
        # If no good paragraph splits, split by single newlines
        if len(sections) < 3:
            sections = [line.strip() for line in content.split('\n') if len(line.strip()) > 30]
        
        # Score sections based on keyword relevance
        scored_sections = []
        for section in sections:
            section_lower = section.lower()
            score = 0
            
            # Count keyword matches
            for keyword in query_keywords:
                if len(keyword) > 2:  # Skip very short words
                    score += section_lower.count(keyword) * len(keyword)
            
            # Bonus for configuration-related content
            config_keywords = ['config', 'configuration', 'setting', 'parameter', 'option', 'samba', 'smb']
            for keyword in config_keywords:
                if keyword in section_lower:
                    score += 10
            
            if score > 0:
                scored_sections.append((score, section))
        
        # Sort by relevance and take top sections
        scored_sections.sort(reverse=True, key=lambda x: x[0])
        
        # Build result within target length
        result_sections = []
        current_length = 0
        
        for score, section in scored_sections:
            if current_length + len(section) < target_length:
                result_sections.append(section)
                current_length += len(section) + 2  # +2 for joining
            else:
                # Add partial section if there's room
                remaining = target_length - current_length - 100  # Leave room for truncation note
                if remaining > 100:
                    result_sections.append(section[:remaining] + "...")
                break
        
        if result_sections:
            return "\n\n".join(result_sections)
        
        return ""
    
    @staticmethod
    def _smart_truncate(content: str, target_length: int) -> str:
        """Smart truncation keeping beginning and end with summary in middle"""
        if len(content) <= target_length:
            return content
        
        # Keep first 40% and last 20% of target length
        start_length = int(target_length * 0.4)
        end_length = int(target_length * 0.2)
        
        start_part = content[:start_length]
        end_part = content[-end_length:] if end_length > 0 else ""
        
        # Create truncation summary
        total_chars = len(content)
        truncated_chars = total_chars - start_length - end_length
        
        summary = f"\n\n[... CONTENT TRUNCATED: {truncated_chars:,} characters removed from middle section ...]\n\n"
        
        return start_part + summary + end_part
    
    @staticmethod
    async def process_tool_result_async(tool_name: str, result: Any, query_context: str = "", citation_manager: CitationManager = None) -> Dict[str, Any]:
        """
        Async version of process tool result with appropriate truncation strategy and source extraction
        
        Args:
            tool_name: Name of the tool that generated the result
            result: Raw tool result
            query_context: User query for context
            citation_manager: Citation manager for source tracking
            
        Returns:
            Processed result with truncation metadata and citations
        """
        if not result:
            return {"success": True, "result": result, "processing": {"truncated": False}, "sources": []}
        
        # Extract sources from tool result
        sources = []
        citation_numbers = []
        if citation_manager:
            # Create proper tool result structure for source extraction
            if isinstance(result, dict) and "result" in result:
                # Already in proper format
                tool_result_for_extraction = result
            else:
                # Raw result - wrap it in proper format
                tool_result_for_extraction = {
                    "success": True,
                    "result": result
                }
            
            extracted_sources = SourceExtractor.extract_from_tool_result(tool_name, tool_result_for_extraction)
            if extracted_sources:
                citation_numbers = citation_manager.add_sources(extracted_sources)
                sources = [source.to_dict() for source in extracted_sources]
                logger.info(
                    "Extracted sources from tool result",
                    tool_name=tool_name,
                    source_count=len(extracted_sources),
                    citation_numbers=citation_numbers
                )
        
        # Determine max tokens based on tool type
        max_tokens = ContentProcessor.MAX_TOKENS_PER_TOOL
        
        if "search" in tool_name.lower():
            max_tokens = ContentProcessor.MAX_TOKENS_SEARCH_RESULT
        elif "read" in tool_name.lower() or "file" in tool_name.lower():
            max_tokens = ContentProcessor.MAX_TOKENS_FILE_CONTENT
        
        # Handle different result formats
        if isinstance(result, dict):
            if "result" in result:
                # Standard tool result format
                processed = await ContentProcessor.truncate_with_context_async(
                    result["result"], max_tokens, query_context
                )
                
                return {
                    "success": result.get("success", True),
                    "result": processed["content"],
                    "processing": {
                        "truncated": processed["truncated"],
                        "original_tokens": processed["original_tokens"],
                        "final_tokens": processed.get("truncated_tokens", processed["original_tokens"]),
                        "truncation_method": processed.get("truncation_method", "none")
                    },
                    "sources": sources,
                    "citation_numbers": citation_numbers
                }
            else:
                # Process the entire dict as content
                content_str = json.dumps(result, indent=2)
                processed = await ContentProcessor.truncate_with_context_async(
                    content_str, max_tokens, query_context
                )
                
                return {
                    "success": True,
                    "result": processed["content"],
                    "processing": {
                        "truncated": processed["truncated"],
                        "original_tokens": processed["original_tokens"],
                        "final_tokens": processed.get("truncated_tokens", processed["original_tokens"]),
                        "truncation_method": processed.get("truncation_method", "none")
                    },
                    "sources": sources,
                    "citation_numbers": citation_numbers
                }
        else:
            # Handle string or other types
            processed = await ContentProcessor.truncate_with_context_async(
                str(result), max_tokens, query_context
            )
            
            return {
                "success": True,
                "result": processed["content"],
                "processing": {
                    "truncated": processed["truncated"],
                    "original_tokens": processed["original_tokens"],
                    "final_tokens": processed.get("truncated_tokens", processed["original_tokens"]),
                    "truncation_method": processed.get("truncation_method", "none")
                },
                "sources": sources,
                "citation_numbers": citation_numbers
            }
    
    @staticmethod
    def process_tool_result(tool_name: str, result: Any, query_context: str = "", citation_manager: CitationManager = None) -> Dict[str, Any]:
        """
        Process tool result with appropriate truncation strategy and source extraction
        
        Args:
            tool_name: Name of the tool that generated the result
            result: Raw tool result
            query_context: User query for context
            citation_manager: Citation manager for source tracking
            
        Returns:
            Processed result with truncation metadata and citations
        """
        if not result:
            return {"success": True, "result": result, "processing": {"truncated": False}, "sources": []}
        
        # Extract sources from tool result
        sources = []
        citation_numbers = []
        if citation_manager:
            # Create proper tool result structure for source extraction
            if isinstance(result, dict) and "result" in result:
                # Already in proper format
                tool_result_for_extraction = result
            else:
                # Raw result - wrap it in proper format
                tool_result_for_extraction = {
                    "success": True,
                    "result": result
                }
            
            extracted_sources = SourceExtractor.extract_from_tool_result(tool_name, tool_result_for_extraction)
            if extracted_sources:
                citation_numbers = citation_manager.add_sources(extracted_sources)
                sources = [source.to_dict() for source in extracted_sources]
                logger.info(
                    "Extracted sources from tool result",
                    tool_name=tool_name,
                    source_count=len(extracted_sources),
                    citation_numbers=citation_numbers
                )
        
        # Determine max tokens based on tool type
        max_tokens = ContentProcessor.MAX_TOKENS_PER_TOOL
        
        if "search" in tool_name.lower():
            max_tokens = ContentProcessor.MAX_TOKENS_SEARCH_RESULT
        elif "read" in tool_name.lower() or "file" in tool_name.lower():
            max_tokens = ContentProcessor.MAX_TOKENS_FILE_CONTENT
        
        # Handle different result formats
        if isinstance(result, dict):
            if "result" in result:
                # Standard tool result format
                processed = ContentProcessor.truncate_with_context(
                    result["result"], max_tokens, query_context
                )
                
                return {
                    "success": result.get("success", True),
                    "result": processed["content"],
                    "processing": {
                        "truncated": processed["truncated"],
                        "original_tokens": processed["original_tokens"],
                        "final_tokens": processed.get("truncated_tokens", processed["original_tokens"]),
                        "truncation_method": processed.get("truncation_method", "none")
                    },
                    "sources": sources,
                    "citation_numbers": citation_numbers
                }
            else:
                # Process the entire dict as content
                content_str = json.dumps(result, indent=2)
                processed = ContentProcessor.truncate_with_context(
                    content_str, max_tokens, query_context
                )
                
                return {
                    "success": True,
                    "result": processed["content"],
                    "processing": {
                        "truncated": processed["truncated"],
                        "original_tokens": processed["original_tokens"],
                        "final_tokens": processed.get("truncated_tokens", processed["original_tokens"]),
                        "truncation_method": processed.get("truncation_method", "none")
                    },
                    "sources": sources,
                    "citation_numbers": citation_numbers
                }
        else:
            # Handle string or other types
            processed = ContentProcessor.truncate_with_context(
                str(result), max_tokens, query_context
            )
            
            return {
                "success": True,
                "result": processed["content"],
                "processing": {
                    "truncated": processed["truncated"],
                    "original_tokens": processed["original_tokens"],
                    "final_tokens": processed.get("truncated_tokens", processed["original_tokens"]),
                    "truncation_method": processed.get("truncation_method", "none")
                },
                "sources": sources,
                "citation_numbers": citation_numbers
            }





class MCPAgent:
    """
    Simple MCP agent with direct Claude integration and tool calling
    """
    
    def __init__(self):
        self.mcp_client: Optional[MultiServerMCPClient] = None
        self.tools: List[BaseTool] = []
        self.loaded_servers: List[str] = []
        self.citation_manager: CitationManager = CitationManager()
        self._server_configs: Optional[Dict] = None  # Store configs for connection pooling
        self._cached_tools_metadata: Optional[Dict] = None  # Cache tool metadata for fast loading
    
    def _build_mcp_config(self, config: dict, source_name: str) -> Optional[dict]:
        """
        Build MCP client configuration for different server types
        
        Args:
            config: Source configuration with credentials
            source_name: Unique name for this source
            
        Returns:
            MCP configuration dict or None if unsupported
        """
        server_type_str = config["server_type"].value if hasattr(config["server_type"], 'value') else str(config["server_type"])
        
        if server_type_str == "CUSTOM_SSE":
            # Legacy: Uses mcp-proxy with command line args (current Hive setup)
            return {
                "command": "mcp-proxy",
                "args": [
                    "--headers",
                    "x-api-key",
                    config["credentials"].get("api_key", ""),
                    config["server_url"]
                ],
                "transport": "stdio"
            }
            
        elif server_type_str == "DIRECT_SSE":
            # New: Direct URL connection with headers (like Atlassian MCP)
            headers = {}
            
            # Handle Bearer token (most common for external APIs)
            if "bearer_token" in config["credentials"]:
                headers["Authorization"] = f"Bearer {config['credentials']['bearer_token']}"
            
            # Handle API key header (alternative)
            elif "api_key" in config["credentials"]:
                headers["x-api-key"] = config["credentials"]["api_key"]
            
            # Handle custom headers JSON (most flexible)
            elif "custom_headers" in config["credentials"]:
                try:
                    import json
                    custom_headers = json.loads(config["credentials"]["custom_headers"])
                    headers.update(custom_headers)
                except (json.JSONDecodeError, TypeError):
                    logger.warning(f"Invalid custom headers JSON for {source_name}", 
                                 headers=config["credentials"].get("custom_headers"))
            
            return {
                "url": config["server_url"],
                "headers": headers,
                "transport": "sse"
            }
            
        elif server_type_str == "WEBSOCKET":
            # Future: WebSocket connections
            logger.warning(f"WebSocket support not implemented yet for {source_name}")
            return None
            
        else:
            logger.warning(f"Unsupported server type: {server_type_str} for {source_name}")
            return None
        
    async def _create_mcp_client_from_configs(self, server_configs: Dict) -> MultiServerMCPClient:
        """Create MCP client from server configurations with connection pooling and timeout"""
        try:
            logger.info("Creating MCP client with connection pooling", server_count=len(server_configs))
            
            # Add timeout to prevent hanging on mcp-proxy dependency resolution
            try:
                client = await asyncio.wait_for(
                    _mcp_pool.get_client(server_configs),
                    timeout=45  # 45 second timeout for client creation
                )
                return client
            except asyncio.TimeoutError:
                logger.error(
                    "MCP client creation timed out - likely mcp-proxy dependency resolution issue",
                    server_count=len(server_configs),
                    timeout_seconds=45
                )
                raise Exception("MCP client creation timed out after 45 seconds")
                
        except Exception as e:
            logger.error("Failed to create MCP client", error=str(e))
            raise
    
    async def load_mcp_endpoints_from_user_sources(
        self, 
        db: AsyncSession, 
        user_id: uuid.UUID,
        force_refresh: bool = False
    ) -> int:
        """
        Load MCP endpoints from user's personal sources with database caching
        
        Args:
            db: Database session
            user_id: User ID to load sources for
            force_refresh: Force refresh of cache
            
        Returns:
            Number of tools loaded
        """
        load_start = time.time()
        logger.info("Loading MCP endpoints from user sources", user_id=user_id, force_refresh=force_refresh)
        
        # Store for lazy loading
        self._cached_tools_metadata = {
            "user_id": user_id,
            "db_session": db
        }
        
        # Simple approach: always load from MCP servers
        logger.info("Loading tools from user sources", user_id=user_id)
        
        # Get all source configurations for this user
        config_load_start = time.time()
        configurations = await MCPCredentialManager.get_user_sources_with_credentials(db, user_id)
        config_load_time = (time.time() - config_load_start) * 1000
        
        if not configurations:
            logger.warning("No source configurations found for user", user_id=user_id)
            return 0
        
        # Build server configs for MultiServerMCPClient
        config_build_start = time.time()
        server_configs = {}
        
        for i, config in enumerate(configurations):
            source_name = f"{config['name'].lower().replace(' ', '_')}_{i}"
            
            try:
                # Build MCP client configuration using centralized method
                mcp_config = self._build_mcp_config(config, source_name)
                
                if mcp_config:
                    server_configs[source_name] = mcp_config
                    server_type_str = config["server_type"].value if hasattr(config["server_type"], 'value') else str(config["server_type"])
                    self.loaded_servers.append(f"{config['name']} ({server_type_str})")
                    
                    logger.debug(
                        "Built MCP client config",
                        source_name=source_name,
                        server_type=server_type_str,
                        transport=mcp_config.get("transport", "unknown")
                    )
                else:
                    continue
                
            except Exception as e:
                logger.error(
                    "Failed to build config for MCP source",
                    source_id=config.get("source_id"),
                    source_name=config.get("name"),
                    error=str(e)
                )
                continue
        
        config_build_time = (time.time() - config_build_start) * 1000
        
        if not server_configs:
            logger.warning("No valid MCP server configurations built")
            return 0
        
        # Store configs for potential lazy loading
        self._server_configs = server_configs
        
        logger.info(
            "Setting up MCP client with credential management",
            server_count=len(server_configs),
            servers=list(server_configs.keys()),
            config_load_time_ms=int(config_load_time),
            config_build_time_ms=int(config_build_time)
        )
        
        try:
            # Create MultiServerMCPClient immediately (cache miss)
            mcp_client_start = time.time()
            self.mcp_client = await self._create_mcp_client_from_configs(server_configs)
            mcp_client_time = (time.time() - mcp_client_start) * 1000
            
            # Load all tools from all servers using standard LangChain approach
            tools_load_start = time.time()
            self.tools = await self.mcp_client.get_tools()
            tools_load_time = (time.time() - tools_load_start) * 1000
            
            total_load_time = (time.time() - load_start) * 1000
            
            logger.info(
                "Successfully loaded MCP tools from user sources",
                tool_count=len(self.tools),
                tool_names=[tool.name for tool in self.tools],
                loaded_servers=self.loaded_servers,
                timing_breakdown={
                    "total_time_ms": int(total_load_time),
                    "config_load_time_ms": int(config_load_time),
                    "config_build_time_ms": int(config_build_time),
                    "mcp_client_creation_ms": int(mcp_client_time),
                    "tools_load_time_ms": int(tools_load_time)
                }
            )
            
            return len(self.tools)
            
        except Exception as e:
            error_time = (time.time() - load_start) * 1000
            logger.error(
                "Failed to load MCP endpoints via credential management",
                error=str(e),
                server_configs=list(server_configs.keys()),
                time_to_error_ms=int(error_time)
            )
            self.tools = []
            return 0
    
    async def load_mcp_endpoints_from_bot_sources(
        self, 
        db: AsyncSession, 
        source_ids: List[uuid.UUID]
    ) -> int:
        """
        Load MCP endpoints from bot sources
        
        Args:
            db: Database session
            source_ids: List of source IDs to load
            
        Returns:
            Number of tools loaded
        """
        logger.info("Loading MCP endpoints from bot sources", source_ids=source_ids)
        
        # Get all source configurations for these sources
        configurations = await MCPCredentialManager.get_bot_sources_with_credentials(db, source_ids)
        
        if not configurations:
            logger.warning("No source configurations found for bot sources", source_ids=source_ids)
            return 0
        
        # Build server configs for MultiServerMCPClient
        server_configs = {}
        
        for i, config in enumerate(configurations):
            source_name = f"{config['name'].lower().replace(' ', '_')}_{i}"
            
            try:
                # Build MCP client configuration using centralized method
                mcp_config = self._build_mcp_config(config, source_name)
                
                if mcp_config:
                    server_configs[source_name] = mcp_config
                    server_type_str = config["server_type"].value if hasattr(config["server_type"], 'value') else str(config["server_type"])
                    self.loaded_servers.append(f"{config['name']} ({server_type_str})")
                    
                    logger.debug(
                        "Built MCP client config for bot source",
                        source_name=source_name,
                        server_type=server_type_str,
                        transport=mcp_config.get("transport", "unknown")
                    )
                else:
                    continue
                
            except Exception as e:
                logger.error(
                    "Failed to build config for bot MCP source",
                    source_id=config.get("source_id"),
                    source_name=config.get("name"),
                    error=str(e)
                )
                continue
        
        if not server_configs:
            logger.warning("No valid MCP server configurations built for bot sources")
            return 0
        
        logger.info(
            "Setting up MCP client with bot sources",
            server_count=len(server_configs),
            servers=list(server_configs.keys())
        )
        
        try:
            # Create MultiServerMCPClient using standard approach
            self.mcp_client = await self._create_mcp_client_from_configs(server_configs)
            
            # Load all tools from all servers using standard LangChain approach
            self.tools = await self.mcp_client.get_tools()
            
            logger.info(
                "Successfully loaded MCP tools from bot sources",
                tool_count=len(self.tools),
                tool_names=[tool.name for tool in self.tools],
                loaded_servers=self.loaded_servers
            )
            
            return len(self.tools)
            
        except Exception as e:
            logger.error(
                "Failed to load MCP endpoints from bot sources",
                error=str(e),
                server_configs=list(server_configs.keys())
            )
            self.tools = []
            return 0
    
    async def load_mcp_endpoints_merged(
        self, 
        db: AsyncSession, 
        user_id: uuid.UUID,
        bot_source_ids: List[uuid.UUID] = None
    ) -> int:
        """
        Load MCP endpoints from both user sources and bot sources (merged)
        
        Args:
            db: Database session
            user_id: User ID to load personal sources for
            bot_source_ids: Optional list of bot source IDs to merge
            
        Returns:
            Number of tools loaded
        """
        logger.info("Loading merged MCP endpoints", user_id=user_id, bot_source_ids=bot_source_ids)
        
        # Get user sources
        user_configurations = await MCPCredentialManager.get_user_sources_with_credentials(db, user_id)
        
        # Get bot sources if provided
        bot_configurations = []
        if bot_source_ids:
            bot_configurations = await MCPCredentialManager.get_bot_sources_with_credentials(db, bot_source_ids)
        
        # Merge configurations
        all_configurations = user_configurations + bot_configurations
        
        if not all_configurations:
            logger.warning("No source configurations found for merged loading", 
                         user_id=user_id, bot_source_ids=bot_source_ids)
            return 0
        
        # Build server configs for MultiServerMCPClient
        server_configs = {}
        
        for i, config in enumerate(all_configurations):
            source_name = f"{config['name'].lower().replace(' ', '_')}_{i}"
            
            try:
                # Build MCP client configuration using centralized method
                mcp_config = self._build_mcp_config(config, source_name)
                
                if mcp_config:
                    server_configs[source_name] = mcp_config
                    server_type_str = config["server_type"].value if hasattr(config["server_type"], 'value') else str(config["server_type"])
                    self.loaded_servers.append(f"{config['name']} ({server_type_str})")
                    
                    logger.debug(
                        "Built MCP client config for merged source",
                        source_name=source_name,
                        server_type=server_type_str,
                        transport=mcp_config.get("transport", "unknown")
                    )
                else:
                    continue
                
            except Exception as e:
                logger.error(
                    "Failed to build config for merged MCP source",
                    source_id=config.get("source_id"),
                    source_name=config.get("name"),
                    error=str(e)
                )
                continue
        
        if not server_configs:
            logger.warning("No valid MCP server configurations built for merged sources")
            return 0
        
        logger.info(
            "Setting up MCP client with merged sources",
            server_count=len(server_configs),
            user_sources=len(user_configurations),
            bot_sources=len(bot_configurations),
            servers=list(server_configs.keys())
        )
        
        try:
            # Create MultiServerMCPClient using standard approach
            self.mcp_client = await self._create_mcp_client_from_configs(server_configs)
            
            # Load all tools from all servers using standard LangChain approach
            self.tools = await self.mcp_client.get_tools()
            
            logger.info(
                "Successfully loaded merged MCP tools",
                tool_count=len(self.tools),
                tool_names=[tool.name for tool in self.tools],
                loaded_servers=self.loaded_servers
            )
            
            return len(self.tools)
            
        except Exception as e:
            logger.error(
                "Failed to load merged MCP endpoints",
                error=str(e),
                server_configs=list(server_configs.keys())
            )
            self.tools = []
            return 0

    def filter_search_tools(self) -> List[BaseTool]:
        """Filter tools to only include search/read-only operations"""
        
        # Keywords that indicate read-only/search operations
        search_keywords = [
            'search', 'get', 'list', 'find', 'retrieve', 'fetch', 'read', 
            'query', 'browse', 'view', 'show', 'check', 'status', 'info',
            'contents', 'repositories', 'issues', 'commits', 'files'
        ]
        
        # Keywords that indicate action/write operations (to exclude)
        action_keywords = [
            'create', 'update', 'delete', 'submit', 'add', 'remove', 'modify',
            'edit', 'write', 'post', 'put', 'patch', 'fork', 'push', 'implement',
            'ticket', 'jira', 'enhancement', 'deploy'
        ]
        
        filtered_tools = []
        
        for tool in self.tools:
            tool_name_lower = tool.name.lower()
            tool_desc_lower = tool.description.lower()
            
            # Check if tool contains action keywords (exclude if it does)
            has_action_keywords = any(
                keyword in tool_name_lower or keyword in tool_desc_lower 
                for keyword in action_keywords
            )
            
            # Check if tool contains search keywords (include if it does)
            has_search_keywords = any(
                keyword in tool_name_lower or keyword in tool_desc_lower 
                for keyword in search_keywords
            )
            
            # Include tool if it has search keywords and no action keywords
            if has_search_keywords and not has_action_keywords:
                filtered_tools.append(tool)
                logger.debug("Including search tool", tool_name=tool.name)
            else:
                logger.debug("Excluding action tool", tool_name=tool.name, reason="not read-only")
        
        logger.info(
            "Filtered tools for search-only operations",
            original_count=len(self.tools),
            filtered_count=len(filtered_tools),
            excluded_count=len(self.tools) - len(filtered_tools)
        )
        
        return filtered_tools

    async def query(
        self,
        message: str,
        llm_provider: str = "anthropic",
        llm_model: str = "claude-sonnet-4-20250514",
        mode: str = "conversational",
        require_sources: bool = True,
        min_sources: int = 2,
        search_depth: str = "thorough",
        conversation_id: Optional[uuid.UUID] = None,
        db_session: Optional[AsyncSession] = None,
        custom_system_prompt: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Execute query using direct Claude integration with MCP tools
        
        Args:
            message: User query
            llm_provider: LLM provider (anthropic, openai)
            llm_model: Model name
            mode: Query mode (conversational, search)
            require_sources: Whether to require sources
            min_sources: Minimum number of sources required
            search_depth: Search depth
            conversation_id: Optional conversation ID
            db_session: Optional database session
            
        Yields:
            Streaming response chunks
        """
        if not self.tools:
            yield {
                "type": "error",
                "error": "No MCP tools available"
            }
            return
        
        # Filter to search-only tools for knowledge base focus
        search_tools = self.filter_search_tools()
        
        if not search_tools:
            yield {
                "type": "error", 
                "error": "No search tools available after filtering"
            }
            return

        try:
            # Initialize LLM
            if llm_provider == "anthropic":
                api_key = os.getenv("ANTHROPIC_API_KEY")
                logger.debug("Anthropic API key status", 
                           has_key=bool(api_key), 
                           key_length=len(api_key) if api_key else 0)
                
                if not api_key:
                    raise ValueError("ANTHROPIC_API_KEY environment variable is not set")
                
                llm = ChatAnthropic(
                    model=llm_model,
                    temperature=0.1,
                    api_key=api_key
                )
            elif llm_provider == "openai":
                api_key = os.getenv("OPENAI_API_KEY")
                if not api_key:
                    raise ValueError("OPENAI_API_KEY environment variable is not set")
                    
                llm = ChatOpenAI(
                    model=llm_model,
                    temperature=0.1,
                    api_key=api_key
                )
            else:
                raise ValueError(f"Unsupported LLM provider: {llm_provider}")
            
            # Get tool information for context
            tools_info = []
            for tool in search_tools:
                tool_info = f"- {tool.name}: {tool.description}"
                
                # Only add schema info if the tool actually has a proper schema
                if hasattr(tool, 'args_schema') and tool.args_schema:
                    try:
                        schema = tool.args_schema.model_json_schema()
                        properties = schema.get('properties', {})
                        required = schema.get('required', [])
                        
                        if properties:
                            params_info = []
                            for param_name, param_data in properties.items():
                                param_type = param_data.get('type', 'string')
                                param_desc = param_data.get('description', '')
                                is_required = param_name in required
                                req_marker = " (required)" if is_required else " (optional)"
                                params_info.append(f"{param_name} ({param_type}){req_marker}: {param_desc}")
                            
                            tool_info += f"\n  Parameters: {', '.join(params_info)}"
                    except Exception:
                        pass
                # Don't add hints for tools without schemas - let LLM figure it out
                
                tools_info.append(tool_info)
            
            tools_context = "\n".join(tools_info)
            server_context = ", ".join(self.loaded_servers)
            
            # Debug: Log what tool context is being sent to LLM
            logger.info("Tool context being sent to LLM", 
                       tool_count=len(search_tools),
                       tool_types=[type(tool).__name__ for tool in search_tools],
                       tool_names=[tool.name for tool in search_tools])
            
            # Use custom system prompt if provided, otherwise create default based on mode
            if custom_system_prompt:
                system_prompt = custom_system_prompt
                logger.info("Using custom system prompt with bot source instructions")
            elif mode == "search":
                system_prompt = f"""You are Scintilla, IgniteTech's comprehensive knowledge search agent. Your primary mission is to provide thorough, well-researched answers by searching deep into our knowledge bases.

CRITICAL SEARCH REQUIREMENTS:
- You MUST use AT LEAST {min_sources} different search tools for comprehensive coverage
- Search across different types of sources: repositories, code files, issues, documentation
- Do not stop after the first tool - continue searching until you have comprehensive information
- Cross-reference information between sources for accuracy and completeness

CRITICAL CITATION REQUIREMENTS:
- ALWAYS cite sources using [1], [2], [3] format when referencing information
- Each unique source gets ONE citation number
- Place citations immediately after the relevant information
- I will provide you with source information for each tool result

Available search tools ({len(search_tools)} tools):
{tools_context}

Connected knowledge sources: {server_context}

MANDATORY SEARCH STRATEGY:
1. Start with repository search to understand the codebase structure
2. Use code search to find specific implementations and patterns
3. Search issues and discussions for context and problems
4. Look for documentation and examples
5. Cross-reference findings across all sources

CITATION EXAMPLES:
- "The configuration file shows that samba is enabled [1]."
- "According to the documentation, the default port is 445 [2]."
- "Multiple repositories indicate this pattern [1][3]."

When answering:
- Always cite which specific tools/sources provided each piece of information using [1], [2], [3] format
- Indicate confidence level based on source consistency
- Provide relevant repository links, issue numbers, or file paths
- If information conflicts between sources, mention the discrepancy with proper citations

You MUST use multiple search tools - single-source answers are inadequate.
You MUST include citations in your response using the [1], [2], [3] format."""
            else:
                system_prompt = f"""You are Scintilla, IgniteTech's intelligent knowledge assistant. You help users find information across our comprehensive knowledge bases using search tools.

CITATION REQUIREMENTS:
- ALWAYS cite sources using [1], [2], [3] format when referencing information
- You will receive tool results that contain raw data - extract relevant URLs, file IDs, and links from this data
- Each unique source gets ONE citation number
- Place citations immediately after the relevant information
- At the end of your response, include a Sources section with proper URLs

You have access to {len(search_tools)} search tools from: {server_context}

Available search tools:
{tools_context}

IMPORTANT: When you receive tool results, look for:
- File IDs (for Google Drive: docs.google.com/document/d/FILE_ID/edit)
- Repository names (for GitHub URLs)  
- Any URLs or links mentioned in the content
- Document titles and names

Your approach:
1. Use relevant search tools to find information about the user's query
2. Extract URLs, file IDs, and links from the tool results
3. Create proper citations with [1], [2], [3] format in your text
4. Provide comprehensive answers with proper source citations
5. Include a Sources section at the end with this EXACT format:

<SOURCES>
[1] [Document Title](https://docs.google.com/document/d/FILE_ID/edit)
[2] [Repository Name](https://github.com/user/repo)
[3] [Another Document](https://example.com/doc)
</SOURCES>

Example of good response:
"The configuration shows that the API key is required [1]. According to the documentation, the default timeout is 30 seconds [2]. The latest updates can be found in the repository [3]."

<SOURCES>
[1] [Configuration Guide](https://docs.google.com/document/d/abc123/edit)
[2] [API Documentation](https://docs.google.com/document/d/def456/edit)
[3] [GitHub Repository](https://github.com/company/repo)
</SOURCES>

Always use the search tools to provide accurate, up-to-date information from our knowledge bases.
Always cite your sources using the [1], [2], [3] format and include the <SOURCES> section."""
            
            # Encapsulate the user query with search instructions
            if require_sources:
                encapsulated_query = f"""User Query: "{message}"

SEARCH REQUIREMENTS - YOU MUST FOLLOW THESE:
- Use AT LEAST {min_sources} different search tools to gather comprehensive information
- Search in multiple areas: repositories, code files, issues, documentation
- Do NOT stop after finding basic information - search thoroughly
- Look for: code examples, implementation patterns, configuration details, best practices
- Cross-reference findings from different sources
- Provide specific examples, code snippets, or links where relevant

SEARCH STRATEGY:
1. First: Search repositories to understand the overall structure
2. Then: Search code files for specific implementations  
3. Also: Search issues for context and common problems
4. Finally: Look for any documentation or examples

Please provide a thorough response based on searching our knowledge bases with multiple tools."""
            else:
                encapsulated_query = message

            system_message = SystemMessage(content=system_prompt)
            
            # Clear previous citations for new query
            self.citation_manager.clear()
            
            # Send initial thinking message
            yield {
                "type": "thinking", 
                "content": f"Starting {search_depth} search across {len(search_tools)} tools from {len(self.loaded_servers)} knowledge sources..."
            }
            
            # Create LLM with search tools bound to it
            llm_with_tools = llm.bind_tools(search_tools)
            
            # Debug: Log tool schemas that are being bound to LLM
            logger.info("Binding tools to LLM", tool_count=len(search_tools))
            for tool in search_tools:
                if hasattr(tool, 'args_schema') and tool.args_schema:
                    try:
                        schema = tool.args_schema.model_json_schema()
                        logger.debug(
                            "Tool schema for LLM binding",
                            tool_name=tool.name,
                            description=tool.description,
                            required_params=schema.get('required', []),
                            properties=list(schema.get('properties', {}).keys())
                        )
                    except Exception as e:
                        logger.debug("Could not get tool schema", tool_name=tool.name, error=str(e))
                else:
                    logger.warning("Tool has no schema", tool_name=tool.name)
            
            # Create user message with encapsulated query
            user_message = HumanMessage(content=encapsulated_query)
            
            # Initialize conversation history
            messages = [system_message]
            
            # Load conversation history if conversation_id is provided
            if conversation_id and db_session:
                logger.info(
                    "Attempting to load conversation history",
                    conversation_id=conversation_id,
                    has_db_session=bool(db_session)
                )
                try:
                    from src.db.models import Message as DBMessage
                    from sqlalchemy import select
                    
                    # Get previous messages from database
                    query = (
                        select(DBMessage)
                        .where(DBMessage.conversation_id == conversation_id)
                        .order_by(DBMessage.created_at)
                    )
                    
                    result = await db_session.execute(query)
                    previous_messages = result.scalars().all()
                    
                    logger.info(
                        "Database query completed",
                        conversation_id=conversation_id,
                        found_messages=len(previous_messages)
                    )
                    
                    # Convert database messages to LangChain format
                    for db_msg in previous_messages:
                        logger.debug(
                            "Processing message from database",
                            message_id=db_msg.message_id,
                            role=db_msg.role,
                            content_length=len(db_msg.content) if db_msg.content else 0,
                            content_preview=db_msg.content[:100] if db_msg.content else ""
                        )
                        if db_msg.role == "user":
                            messages.append(HumanMessage(content=db_msg.content))
                        elif db_msg.role == "assistant":
                            messages.append(AIMessage(content=db_msg.content))
                    
                    logger.info(
                        "Loaded conversation history",
                        conversation_id=conversation_id,
                        previous_messages=len(previous_messages),
                        total_messages=len(messages),
                        messages_summary=[f"{msg.role}: {msg.content[:50]}..." for msg in previous_messages]
                    )
                    
                except Exception as e:
                    logger.warning(
                        "Failed to load conversation history",
                        conversation_id=conversation_id,
                        error=str(e),
                        error_type=type(e).__name__
                    )
            else:
                logger.info(
                    "No conversation history to load",
                    conversation_id=conversation_id,
                    has_db_session=bool(db_session)
                )
            
            # Add current user message
            messages.append(user_message)
            tool_calls_made = []
            max_iterations = 10  # Prevent infinite loops
            iteration = 0
            total_conversation_tokens = 0
            max_conversation_tokens = 150000  # Leave room for final response
            
            while iteration < max_iterations:
                iteration += 1
                
                # Check conversation token limit
                # Ensure all message content is converted to strings before joining
                message_contents = []
                for msg in messages:
                    if hasattr(msg, 'content'):
                        content = msg.content
                        if isinstance(content, list):
                            # If content is a list, convert to string
                            content = str(content)
                        elif not isinstance(content, str):
                            # If content is not a string, convert to string
                            content = str(content)
                        message_contents.append(content)
                
                conversation_content = " ".join(message_contents)
                total_conversation_tokens = ContentProcessor.estimate_tokens(conversation_content)
                
                if total_conversation_tokens > max_conversation_tokens:
                    logger.warning(
                        "Conversation approaching token limit, stopping tool calls",
                        total_tokens=total_conversation_tokens,
                        max_tokens=max_conversation_tokens
                    )
                    break
                
                # Get response from LLM
                response = await llm_with_tools.ainvoke(messages)
                
                # Add LLM response to conversation
                messages.append(response)
                
                # Check if LLM wants to call any tools
                if hasattr(response, 'tool_calls') and response.tool_calls:
                    tool_results = []
                    
                    for tool_call in response.tool_calls:
                        tool_name = tool_call['name']
                        tool_args = tool_call['args']
                        
                        yield {
                            "type": "tool_call",
                            "tool_name": tool_name,
                            "tool_args": tool_args,
                            "status": "starting"
                        }
                        
                        # Execute the tool call with query context
                        try:
                            # Debug: Log what the LLM is actually calling
                            logger.info(
                                "LLM tool call details",
                                tool_name=tool_name,
                                tool_args=tool_args,
                                tool_args_type=type(tool_args),
                                tool_args_empty=len(tool_args) == 0 if isinstance(tool_args, dict) else "not a dict"
                            )
                            
                            # Handle case where LLM might wrap args in a 'kwargs' key
                            actual_args = tool_args
                            if isinstance(tool_args, dict) and len(tool_args) == 1 and 'kwargs' in tool_args:
                                logger.debug("Unwrapping kwargs from LLM tool call", tool_name=tool_name)
                                actual_args = tool_args['kwargs'] if isinstance(tool_args['kwargs'], dict) else tool_args
                            
                            logger.info(
                                "Final args being passed to tool",
                                tool_name=tool_name,
                                actual_args=actual_args,
                                actual_args_type=type(actual_args),
                                actual_args_empty=len(actual_args) == 0 if isinstance(actual_args, dict) else "not a dict"
                            )
                            
                            tool_result = await self.call_tool(
                                tool_name, 
                                query_context=message,  # Pass original query for context
                                citation_manager=self.citation_manager,  # Pass citation manager
                                **actual_args
                            )
                            
                            # Include processing info in the yield
                            result_to_yield = dict(tool_result)
                            if "processing" in tool_result:
                                processing_info = tool_result["processing"]
                                if processing_info.get("truncated", False):
                                    result_to_yield["truncation_info"] = {
                                        "truncated": True,
                                        "original_tokens": processing_info["original_tokens"],
                                        "final_tokens": processing_info["final_tokens"],
                                        "method": processing_info["truncation_method"]
                                    }
                            
                            yield {
                                "type": "tool_result",
                                "tool_name": tool_name,
                                "result": result_to_yield
                            }
                            
                            tool_calls_made.append({
                                "tool_name": tool_name,
                                "parameters": tool_args,
                                "result": tool_result,
                                "processing": tool_result.get("processing", {})
                            })
                            
                            # Create tool message for conversation (use processed content + citation context)
                            tool_content = {
                                "success": tool_result.get("success", True),
                                "result": tool_result.get("result", "")
                            }
                            
                            # Add citation context if sources were found
                            if tool_result.get("sources"):
                                citation_context = self.citation_manager.get_citation_context_for_llm()
                                if citation_context:
                                    tool_content["citation_context"] = citation_context
                            
                            tool_message = ToolMessage(
                                content=json.dumps(tool_content),
                                tool_call_id=tool_call['id']
                            )
                            tool_results.append(tool_message)
                            
                        except Exception as e:
                            error_result = {"error": str(e), "success": False}
                            yield {
                                "type": "tool_result",
                                "tool_name": tool_name,
                                "result": error_result
                            }
                            
                            tool_calls_made.append({
                                "tool_name": tool_name,
                                "parameters": tool_args,
                                "result": error_result
                            })
                            
                            # Create error tool message
                            tool_message = ToolMessage(
                                content=json.dumps(error_result),
                                tool_call_id=tool_call['id']
                            )
                            tool_results.append(tool_message)
                    
                    # Add tool results to conversation
                    messages.extend(tool_results)
                    
                    # Continue the loop to let LLM process tool results
                    continue
                else:
                    # No more tool calls, we have the final response
                    final_content = response.content
                    break
            
            # If we hit max iterations, use the last response
            if iteration >= max_iterations:
                final_content = response.content if hasattr(response, 'content') else "Maximum iterations reached"
            
            # Calculate processing statistics
            total_tools_called = len(tool_calls_made)
            truncated_tools = sum(1 for call in tool_calls_made 
                                if call.get("processing", {}).get("truncated", False))
            total_original_tokens = sum(call.get("processing", {}).get("original_tokens", 0) 
                                      for call in tool_calls_made)
            total_final_tokens = sum(call.get("processing", {}).get("final_tokens", 0) 
                                   for call in tool_calls_made)
            
            # Generate reference list
            reference_list = self.citation_manager.generate_reference_list()
            if reference_list:
                final_content += f"\n\n{reference_list}"
            
            # Extract URLs from LLM response and enhance source metadata
            enhanced_sources = self._enhance_sources_with_llm_urls(final_content, self.citation_manager.get_sources_metadata())
            
            yield {
                "type": "final_response",
                "content": final_content,
                "tool_calls": tool_calls_made,
                "tools_available": len(self.tools),
                "servers_connected": len(self.loaded_servers),
                "sources": enhanced_sources,
                "processing_stats": {
                    "total_tools_called": total_tools_called,
                    "tools_truncated": truncated_tools,
                    "total_original_tokens": total_original_tokens,
                    "total_final_tokens": total_final_tokens,
                    "conversation_tokens": total_conversation_tokens,
                    "tokens_saved": total_original_tokens - total_final_tokens,
                    "sources_found": len(self.citation_manager.sources)
                }
            }
            
        except Exception as e:
            logger.error(
                "Agent query failed",
                error=str(e),
                message=message,
                provider=llm_provider,
                model=llm_model
            )
            yield {
                "type": "error",
                "error": str(e)
            }
    
    async def call_tool(self, tool_name: str, query_context: str = "", citation_manager: CitationManager = None, **kwargs) -> Dict[str, Any]:
        """
        Call a specific MCP tool by name with intelligent content processing
        
        Args:
            tool_name: Name of the tool to call
            query_context: User query for context-aware processing
            citation_manager: Citation manager for source tracking
            **kwargs: Tool arguments
            
        Returns:
            Processed tool result with truncation metadata and timing info
        """
        tool_start_time = time.time()
        
        try:
            # Find the tool
            tool_lookup_start = time.time()
            tool = next((t for t in self.tools if t.name == tool_name), None)
            tool_lookup_time = (time.time() - tool_lookup_start) * 1000
            
            if not tool:
                return {"error": f"Tool '{tool_name}' not found"}
            
            # Log tool schema for debugging
            tool_schema = {}
            if hasattr(tool, 'args_schema') and tool.args_schema:
                try:
                    tool_schema = tool.args_schema.model_json_schema()
                    logger.debug("Tool schema", tool_name=tool_name, schema=tool_schema)
                except Exception as e:
                    logger.debug("Could not get tool schema", tool_name=tool_name, error=str(e))
            
            # Call the tool directly (no lazy loading needed)
            tool_execution_start = time.time()
            logger.info("Executing tool", tool_name=tool_name, args=kwargs)
            
            # Try different methods to call the tool based on LangChain version
            try:
                # First try with config parameter (newer LangChain versions)
                logger.debug("Attempting tool call with config parameter", tool_name=tool_name)
                raw_result = await tool.ainvoke(kwargs, config={})
            except TypeError as e:
                logger.debug("Tool call with config failed, trying alternatives", tool_name=tool_name, error=str(e))
                if "config" in str(e):
                    # Fallback to direct _arun call with config
                    try:
                        logger.debug("Attempting direct _arun with config", tool_name=tool_name)
                        raw_result = await tool._arun(config={}, **kwargs)
                    except Exception as e2:
                        logger.debug("Direct _arun with config failed, trying simple ainvoke", tool_name=tool_name, error=str(e2))
                        # Final fallback to simple ainvoke
                        raw_result = await tool.ainvoke(kwargs)
                else:
                    logger.error("Unexpected TypeError in tool call", tool_name=tool_name, error=str(e))
                    raise e
            except Exception as e:
                # Log detailed error information for debugging
                logger.error(
                    "Tool execution failed", 
                    tool_name=tool_name, 
                    error=str(e), 
                    error_type=type(e).__name__,
                    provided_args=list(kwargs.keys()),
                    tool_description=getattr(tool, 'description', 'No description')
                )
                
                # Return a structured error that the LLM can understand
                error_msg = f"Tool '{tool_name}' failed: {str(e)}"
                if hasattr(tool, 'args_schema') and tool.args_schema:
                    try:
                        schema = tool.args_schema.model_json_schema()
                        required_params = schema.get('required', [])
                        if required_params:
                            error_msg += f" Required parameters: {required_params}"
                    except:
                        pass
                
                raise Exception(error_msg)
            
            tool_execution_time = (time.time() - tool_execution_start) * 1000
            
            # Process the result with intelligent truncation and source extraction
            processing_start = time.time()
            processed_result = ContentProcessor.process_tool_result(
                tool_name, raw_result, query_context, citation_manager
            )
            processing_time = (time.time() - processing_start) * 1000
            
            total_tool_time = (time.time() - tool_start_time) * 1000
            
            # Add timing information to the result
            timing_info = {
                "total_time_ms": int(total_tool_time),
                "tool_lookup_ms": int(tool_lookup_time),
                "execution_ms": int(tool_execution_time),
                "processing_ms": int(processing_time)
            }
            
            # Log processing information with timing
            if processed_result.get("processing", {}).get("truncated", False):
                processing_info = processed_result["processing"]
                logger.info(
                    "Tool result processed with truncation",
                    tool_name=tool_name,
                    original_tokens=processing_info["original_tokens"],
                    final_tokens=processing_info["final_tokens"],
                    truncation_method=processing_info["truncation_method"],
                    timing=timing_info
                )
            else:
                logger.info(
                    "Tool called successfully",
                    tool_name=tool_name,
                    result_type=type(raw_result).__name__,
                    timing=timing_info
                )
            
            # Add timing info to the processed result
            processed_result["timing"] = timing_info
            
            return processed_result
            
        except Exception as e:
            error_time = (time.time() - tool_start_time) * 1000
            logger.error(
                "Tool call failed",
                tool_name=tool_name,
                error=str(e),
                time_to_error_ms=int(error_time)
            )
            return {
                "error": f"Tool call failed: {str(e)}",
                "timing": {
                    "total_time_ms": int(error_time),
                    "failed": True
                }
            }
    
    async def call_tools_parallel(self, tool_calls: List[Dict[str, Any]], query_context: str = "", citation_manager: CitationManager = None) -> List[Dict[str, Any]]:
        """
        Call multiple tools in parallel for better performance
        
        Args:
            tool_calls: List of tool call dicts with 'name' and 'args' keys
            query_context: User query for context-aware processing
            citation_manager: Citation manager for source tracking
            
        Returns:
            List of tool results in same order as input
        """
        if not tool_calls:
            return []
        
        logger.info("Calling multiple tools in parallel", tool_count=len(tool_calls))
        start_time = time.time()
        
        # Create coroutines for all tool calls
        tasks = []
        for tool_call in tool_calls:
            task = self.call_tool(
                tool_name=tool_call["name"],
                query_context=query_context,
                citation_manager=citation_manager,
                **tool_call.get("args", {})
            )
            tasks.append(task)
        
        # Execute all tools in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle any exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    "Parallel tool call failed",
                    tool_name=tool_calls[i]["name"],
                    error=str(result)
                )
                processed_results.append({
                    "success": False,
                    "error": str(result),
                    "tool_name": tool_calls[i]["name"]
                })
            else:
                processed_results.append(result)
        
        total_time = (time.time() - start_time) * 1000
        logger.info(
            "Parallel tool calls completed",
            tool_count=len(tool_calls),
            total_time_ms=int(total_time),
            successful_calls=sum(1 for r in processed_results if r.get("success", False))
        )
        
        return processed_results
    
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get list of available tool information with detailed schemas"""
        tools_info = []
        
        for tool in self.tools:
            tool_info = {
                "name": tool.name,
                "description": tool.description,
                "server": "unknown"  # TODO: Track which server each tool comes from
            }
            
            # Add detailed parameter information if available
            if hasattr(tool, 'args_schema') and tool.args_schema:
                try:
                    schema = tool.args_schema.model_json_schema()
                    tool_info["parameters"] = {
                        "type": "object",
                        "properties": schema.get("properties", {}),
                        "required": schema.get("required", [])
                    }
                    
                    # Add parameter descriptions for better LLM understanding
                    if "properties" in schema:
                        tool_info["parameter_descriptions"] = {}
                        for param_name, param_info in schema["properties"].items():
                            desc = param_info.get("description", "")
                            param_type = param_info.get("type", "string")
                            tool_info["parameter_descriptions"][param_name] = f"{param_type}: {desc}"
                            
                except Exception as e:
                    logger.debug("Could not extract tool schema", tool_name=tool.name, error=str(e))
                    tool_info["parameters"] = {}
            else:
                tool_info["parameters"] = {}
            
            tools_info.append(tool_info)
        
        return tools_info
    
    def get_loaded_servers(self) -> List[str]:
        """Get list of loaded MCP servers"""
        return self.loaded_servers.copy()

    def _enhance_sources_with_llm_urls(self, content: str, sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract URLs from LLM response <SOURCES> section and enhance source metadata"""
        enhanced_sources = []
        
        # Extract URLs from the LLM's <SOURCES> section using regex
        sources_section_match = re.search(r'<SOURCES>(.*?)</SOURCES>', content, re.DOTALL)
        
        citation_urls = {}
        if sources_section_match:
            sources_section = sources_section_match.group(1)
            # Pattern: [1] [Title](URL)
            sources_pattern = r'\[(\d+)\]\s*\[([^\]]+)\]\(([^)]+)\)'
            matches = re.findall(sources_pattern, sources_section)
            
            # Create a mapping of citation number to URL
            for match in matches:
                citation_num = int(match[0])
                title = match[1]
                url = match[2]
                citation_urls[citation_num] = {
                    'title': title,
                    'url': url
                }
                logger.debug(
                    "Extracted URL from <SOURCES> section",
                    citation_num=citation_num,
                    title=title,
                    url=url
                )
        
        # Enhance each source with the extracted URL if available
        for i, source in enumerate(sources):
            source_copy = source.copy()
            citation_num = i + 1  # 1-based citation numbers
            
            if citation_num in citation_urls:
                # Update with LLM-extracted URL and title
                llm_data = citation_urls[citation_num]
                source_copy['url'] = llm_data['url']
                source_copy['title'] = llm_data['title']
                logger.debug(
                    "Enhanced source with LLM URL",
                    citation_num=citation_num,
                    title=llm_data['title'],
                    url=llm_data['url']
                )
            
            enhanced_sources.append(source_copy)
        
        return enhanced_sources


async def create_agent_with_tools(tools: List[BaseTool]) -> 'AgentExecutor':
    """
    Create a LangChain AgentExecutor with the provided tools
    
    Args:
        tools: List of LangChain tools
        
    Returns:
        AgentExecutor configured with the tools
    """
    from langchain.agents import create_openai_tools_agent, AgentExecutor
    from langchain.prompts import ChatPromptTemplate
    
    # Create a simple prompt template
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful assistant with access to various tools. Use them to answer user questions accurately."),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])
    
    # Create LLM (using Anthropic Claude)
    llm = ChatAnthropic(
        model="claude-3-5-sonnet-20241022",
        temperature=0.1,
        max_tokens=4000,
        timeout=60
    )
    
    # Create agent
    agent = create_openai_tools_agent(llm, tools, prompt)
    
    # Create agent executor
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        max_iterations=3,
        max_execution_time=60,
        handle_parsing_errors=True
    )
    
    return agent_executor


async def load_mcp_tools() -> List[BaseTool]:
    """
    Load MCP tools from all available sources (user sources + bot sources)
    
    Returns:
        List of LangChain tools from MCP servers
    """
    from src.db.base import AsyncSessionLocal
    from src.db.models import Source
    from sqlalchemy import select
    import uuid
    
    try:
        async with AsyncSessionLocal() as db:
            # Create MCPAgent and load tools
            mcp_agent = MCPAgent()
            total_tools_loaded = 0
            
            # First, try to load tools from all bot sources
            try:
                # Get all bot-owned sources
                bot_sources_query = select(Source).where(Source.owner_bot_id.isnot(None))
                bot_sources_result = await db.execute(bot_sources_query)
                bot_sources = bot_sources_result.scalars().all()
                
                if bot_sources:
                    bot_source_ids = [source.source_id for source in bot_sources]
                    logger.info(f"Loading tools from {len(bot_source_ids)} bot sources")
                    
                    bot_tool_count = await mcp_agent.load_mcp_endpoints_from_bot_sources(
                        db, bot_source_ids
                    )
                    total_tools_loaded += bot_tool_count
                    logger.info(f"Loaded {bot_tool_count} tools from bot sources")
                
            except Exception as e:
                logger.warning("Failed to load bot sources", error=str(e))
            
            # Second, try to load tools from user sources (all users)
            try:
                # Get all user-owned sources  
                user_sources_query = select(Source).where(Source.owner_user_id.isnot(None))
                user_sources_result = await db.execute(user_sources_query)
                user_sources = user_sources_result.scalars().all()
                
                if user_sources:
                    # Group sources by user to load them efficiently
                    user_source_groups = {}
                    for source in user_sources:
                        user_id = source.owner_user_id
                        if user_id not in user_source_groups:
                            user_source_groups[user_id] = []
                        user_source_groups[user_id].append(source)
                    
                    logger.info(f"Loading tools from {len(user_sources)} user sources across {len(user_source_groups)} users")
                    
                    # Load tools for each user
                    for user_id, sources in user_source_groups.items():
                        try:
                            user_tool_count = await mcp_agent.load_mcp_endpoints_from_user_sources(
                                db, user_id, force_refresh=True
                            )
                            total_tools_loaded += user_tool_count
                            logger.info(f"Loaded {user_tool_count} tools for user {user_id}")
                        except Exception as e:
                            logger.warning(f"Failed to load tools for user {user_id}", error=str(e))
                            
            except Exception as e:
                logger.warning("Failed to load user sources", error=str(e))
            
            # Log final results
            if total_tools_loaded > 0:
                logger.info(
                    "Global MCP tools loaded successfully",
                    total_tool_count=total_tools_loaded,
                    actual_tools=len(mcp_agent.tools),
                    loaded_servers=mcp_agent.get_loaded_servers()
                )
                return mcp_agent.tools
            else:
                logger.info("No MCP tools loaded - system will work with empty tool set")
                # Return empty list but don't treat as error
                # This allows the system to work even without configured sources
                return []
                
    except Exception as e:
        logger.error("Failed to load MCP tools", error=str(e))
        return [] 
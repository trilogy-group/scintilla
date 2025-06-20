"""
MCP Loader Utilities

Extracts common loading patterns from MCPAgent to reduce duplication.
"""

import uuid
import time
from typing import List, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_mcp_adapters.client import MultiServerMCPClient
import structlog

from src.db.mcp_credentials import MCPCredentialManager

logger = structlog.get_logger()


class MCPConfigBuilder:
    """Builds MCP configurations from database configurations"""
    
    @staticmethod
    def build_mcp_config(config: dict, source_name: str) -> Optional[dict]:
        """
        Build MCP client configuration for different server types
        
        Args:
            config: Source configuration with credentials
            source_name: Unique name for this source
            
        Returns:
            MCP configuration dict or None if unsupported
        """
        server_type_str = config["server_type"].value if hasattr(config["server_type"], 'value') else str(config["server_type"])
        logger.debug("Building MCP config", source_name=source_name, server_type=server_type_str)
        
        if server_type_str == "CUSTOM_SSE":
            # For MCP Hive, use mcp-proxy with command line args
            server_url = config["server_url"]
            api_key = config.get("credentials", {})
            
            if not api_key:
                logger.error("No API key found for CUSTOM_SSE source", source_name=source_name)
                return None
            
            return {
                "command": "mcp-proxy",
                "args": [
                    "--headers",
                    "x-api-key",
                    api_key,
                    server_url
                ],
                "transport": "stdio"
            }
            
        elif server_type_str == "DIRECT_SSE":
            # For direct SSE, use URL with custom headers
            server_url = config["server_url"]
            headers = config.get("credentials", {})
            
            return {
                "command": "mcp-sse-client",
                "args": [
                    "--url", server_url,
                    "--headers", str(headers)
                ],
                "transport": "stdio"
            }
            
        elif server_type_str == "SOCKET":
            # For socket connections
            socket_path = config.get("socket_path", "/tmp/mcp.sock")
            return {
                "command": "mcp-socket",
                "args": [socket_path],
                "transport": "stdio"
            }
            
        else:
            logger.warning(f"Unsupported server type: {server_type_str} for {source_name}")
            return None


class MCPServerConfigProcessor:
    """Processes database configurations into server configs"""
    
    @staticmethod
    async def build_server_configs(configurations: List[dict]) -> Dict[str, dict]:
        """
        Build server configs from database configurations
        
        Args:
            configurations: List of source configurations from database
            
        Returns:
            Dictionary of server configs keyed by source name
        """
        server_configs = {}
        
        for i, config in enumerate(configurations):
            source_name = f"{config['name'].lower().replace(' ', '_')}_{i}"
            
            try:
                mcp_config = MCPConfigBuilder.build_mcp_config(config, source_name)
                
                if mcp_config:
                    server_configs[source_name] = mcp_config
                    server_type_str = config["server_type"].value if hasattr(config["server_type"], 'value') else str(config["server_type"])
                    
                    logger.debug(
                        "Built MCP client config",
                        source_name=source_name,
                        server_type=server_type_str,
                        transport=mcp_config.get("transport", "unknown")
                    )
                
            except Exception as e:
                logger.error(
                    "Failed to build config for MCP source",
                    source_id=config.get("source_id"),
                    source_name=config.get("name"),
                    error=str(e)
                )
                continue
        
        return server_configs


class MCPEndpointLoader:
    """Unified MCP endpoint loader to replace duplicate methods"""
    
    def __init__(self, agent_instance):
        """Initialize with reference to the MCPAgent instance"""
        self.agent = agent_instance
    
    async def load_from_user_sources(
        self, 
        db: AsyncSession, 
        user_id: uuid.UUID
    ) -> int:
        """Load MCP endpoints from user's personal sources"""
        configurations = await MCPCredentialManager.get_user_sources_with_credentials(db, user_id)
        return await self._load_from_configurations(configurations, f"user sources for {user_id}")
    
    async def load_from_bot_sources(
        self, 
        db: AsyncSession, 
        source_ids: List[uuid.UUID]
    ) -> int:
        """Load MCP endpoints from bot sources"""
        configurations = await MCPCredentialManager.get_bot_sources_with_credentials(db, source_ids)
        return await self._load_from_configurations(configurations, f"bot sources {source_ids}")
    
    async def load_merged_sources(
        self, 
        db: AsyncSession, 
        user_id: uuid.UUID,
        bot_source_ids: Optional[List[uuid.UUID]] = None
    ) -> int:
        """Load MCP endpoints from both user and bot sources"""
        user_configurations = await MCPCredentialManager.get_user_sources_with_credentials(db, user_id)
        
        bot_configurations = []
        if bot_source_ids:
            bot_configurations = await MCPCredentialManager.get_bot_sources_with_credentials(db, bot_source_ids)
        
        all_configurations = user_configurations + bot_configurations
        return await self._load_from_configurations(
            all_configurations, 
            f"merged sources (user: {user_id}, bots: {bot_source_ids})"
        )
    
    async def _load_from_configurations(self, configurations: List[dict], source_description: str) -> int:
        """
        Common loading logic extracted from all three methods
        
        Args:
            configurations: List of source configurations
            source_description: Description for logging
            
        Returns:
            Number of tools loaded
        """
        load_start = time.time()
        logger.info("Loading MCP endpoints", source_description=source_description)
        
        if not configurations:
            logger.warning("No configurations found", source_description=source_description)
            return 0
        
        # Build server configs
        config_build_start = time.time()
        server_configs = await MCPServerConfigProcessor.build_server_configs(configurations)
        config_build_time = (time.time() - config_build_start) * 1000
        
        if not server_configs:
            logger.warning("No valid server configurations built", source_description=source_description)
            return 0
        
        # Update loaded servers list
        for config in configurations:
            if config.get("name"):
                server_type_str = config["server_type"].value if hasattr(config["server_type"], 'value') else str(config["server_type"])
                self.agent.loaded_servers.append(f"{config['name']} ({server_type_str})")
        
        logger.info(
            "Server configs built",
            source_description=source_description,
            server_count=len(server_configs),
            config_build_time_ms=int(config_build_time)
        )
        
        try:
            # Create MCP client
            mcp_client_start = time.time()
            self.agent.mcp_client = await self.agent._create_mcp_client_from_configs(server_configs)
            mcp_client_time = (time.time() - mcp_client_start) * 1000
            
            # Load tools
            tools_load_start = time.time()
            self.agent.tools = await self.agent.mcp_client.get_tools()
            tools_load_time = (time.time() - tools_load_start) * 1000
            
            total_load_time = (time.time() - load_start) * 1000
            
            logger.info(
                "Successfully loaded MCP tools",
                source_description=source_description,
                tool_count=len(self.agent.tools),
                timing_breakdown={
                    "total_time_ms": int(total_load_time),
                    "config_build_time_ms": int(config_build_time),
                    "mcp_client_creation_ms": int(mcp_client_time),
                    "tools_load_time_ms": int(tools_load_time)
                }
            )
            
            return len(self.agent.tools)
            
        except Exception as e:
            error_time = (time.time() - load_start) * 1000
            logger.error(
                "Failed to load MCP endpoints",
                source_description=source_description,
                error=str(e),
                time_to_error_ms=int(error_time)
            )
            self.agent.tools = []
            return 0 
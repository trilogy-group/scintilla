"""
Global MCP agent management to avoid circular imports
"""

import uuid
import structlog
from typing import Optional
from src.agents.langchain_mcp import MCPAgent

logger = structlog.get_logger()

# Global MCP tool cache - initialized once at startup
_global_mcp_agent: Optional[MCPAgent] = None

def set_global_mcp_agent(agent: MCPAgent) -> None:
    """Set the global MCP agent (called during server startup)"""
    global _global_mcp_agent
    _global_mcp_agent = agent
    logger.info("Global MCP agent set", tool_count=len(agent.tools) if agent else 0)

def get_global_mcp_agent() -> Optional[MCPAgent]:
    """Get the globally cached MCP agent"""
    return _global_mcp_agent

def clear_global_mcp_agent() -> None:
    """Clear the global MCP agent (called during server shutdown)"""
    global _global_mcp_agent
    _global_mcp_agent = None
    logger.info("Global MCP agent cleared")

async def initialize_global_mcp_agent(db, default_user_id: uuid.UUID) -> Optional[MCPAgent]:
    """Initialize the global MCP agent with tools loaded"""
    try:
        logger.info("Initializing global MCP agent...")
        
        agent = MCPAgent()
        tool_count = await agent.load_mcp_endpoints_from_user_sources(
            db, default_user_id, force_refresh=True
        )
        
        if tool_count > 0:
            set_global_mcp_agent(agent)
            logger.info(
                "Successfully initialized global MCP agent",
                tool_count=tool_count,
                loaded_servers=agent.get_loaded_servers()
            )
            return agent
        else:
            logger.warning("No MCP tools loaded during initialization")
            return None
            
    except Exception as e:
        logger.error("Failed to initialize global MCP agent", error=str(e))
        return None 
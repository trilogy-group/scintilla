"""
MCP Utilities Module

Shared utilities for MCP agents to avoid code duplication.
"""

from typing import List
from langchain_core.tools import BaseTool
import structlog

logger = structlog.get_logger()

# Shared configuration
SEARCH_KEYWORDS = [
    'search', 'get', 'list', 'find', 'retrieve', 'fetch', 'read', 
    'query', 'browse', 'view', 'show', 'check', 'status', 'info',
    'contents', 'repositories', 'issues', 'commits', 'files'
]

ACTION_KEYWORDS = [
    'create', 'update', 'delete', 'submit', 'add', 'remove', 'modify',
    'edit', 'write', 'post', 'put', 'patch', 'fork', 'push', 'implement',
    'ticket', 'jira', 'enhancement', 'deploy'
]


def filter_search_tools(tools: List[BaseTool]) -> List[BaseTool]:
    """
    Filter tools to only include search/read-only operations
    
    Shared utility used by both FastMCPAgent and MCPAgent to avoid duplication.
    """
    filtered_tools = []
    
    for tool in tools:
        name_desc = (tool.name + " " + tool.description).lower()
        
        has_search = any(keyword in name_desc for keyword in SEARCH_KEYWORDS)
        has_action = any(keyword in name_desc for keyword in ACTION_KEYWORDS)
        
        if has_search and not has_action:
            filtered_tools.append(tool)
    
    logger.debug(
        "Filtered tools for search-only operations",
        original_count=len(tools),
        filtered_count=len(filtered_tools),
        excluded_count=len(tools) - len(filtered_tools)
    )
    
    return filtered_tools


def build_tools_context(tools: List[BaseTool]) -> str:
    """Build tool context string for LLM prompts"""
    tools_info = []
    for tool in tools:
        tools_info.append(f"- {tool.name}: {tool.description}")
    return "\n".join(tools_info) 
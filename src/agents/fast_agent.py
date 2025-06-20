"""
Fast MCP Agent - Loads tools from database cache and delegates to working MCPAgent

Performance improvements:
1. Loads tool metadata from database (milliseconds vs seconds) 
2. Uses proven working MCPAgent for actual execution
3. Detects meta queries to avoid unnecessary tool calls
4. Clean, maintainable code without overengineering
"""

import uuid
import json
import time
import re
from datetime import datetime
from typing import List, Dict, Any, Optional, AsyncGenerator, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from langchain_core.tools import BaseTool
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
import structlog

from src.db.models import Source, SourceTool, Message
from src.db.tool_cache import ToolCacheService
from src.agents.langchain_mcp import MCPAgent
from src.agents.citations import CitationManager
from src.agents.mcp_utils import filter_search_tools

logger = structlog.get_logger()

# Configuration constants
MAX_TOOL_ITERATIONS = 10
CONVERSATION_HISTORY_LIMIT = 10
TOOL_PREVIEW_LENGTH = 500
DEFAULT_TEMPERATURE = 0.1

class FastMCPAgent:
    """
    Fast MCP Agent - thin wrapper around working MCPAgent
    
    Loads tools from database cache for speed, delegates execution to proven MCPAgent
    """
    
    def __init__(self):
        self.tools: List[BaseTool] = []
        self.loaded_sources: List[str] = []
        self.citation_manager: CitationManager = CitationManager()
        self._tool_metadata: List[Dict] = []
        self._working_agent: Optional[MCPAgent] = None
    
    async def load_tools_from_cache(
        self, 
        db: AsyncSession, 
        user_id: uuid.UUID,
        bot_source_ids: Optional[List[uuid.UUID]] = None
    ) -> int:
        """Load tools using working MCPAgent + fast cache metadata"""
        logger.info("FastMCPAgent loading", user_id=user_id, bot_source_ids=bot_source_ids)
        
        # Create working MCPAgent for tool execution
        self._working_agent = MCPAgent()
        
        # Load tools into working agent using proven approach
        if bot_source_ids:
            tool_count = await self._working_agent.load_mcp_endpoints_merged(
                db, user_id, bot_source_ids
            )
        else:
            tool_count = await self._working_agent.load_mcp_endpoints_from_user_sources(
                db, user_id
            )
        
        if tool_count == 0:
            logger.warning("No tools loaded")
            return 0
        
        # Get tool metadata from cache for UI
        source_ids = await self._get_source_ids(db, user_id, bot_source_ids)
        cached_tools = await ToolCacheService.get_cached_tools_for_sources(db, source_ids)
        
        # Use working agent's tools for LLM binding (proper schemas)
        self.tools = self._working_agent.tools.copy()
        self._tool_metadata = cached_tools
        self.loaded_sources = self._working_agent.get_loaded_servers()
        
        logger.info("FastMCPAgent ready", 
                   tools=len(self.tools), sources=len(self.loaded_sources))
        
        return len(self.tools)

    async def _get_source_ids(
        self, 
        db: AsyncSession, 
        user_id: uuid.UUID, 
        bot_source_ids: Optional[List[uuid.UUID]]
    ) -> List[uuid.UUID]:
        """Get all relevant source IDs"""
        source_ids = []
        
        # User sources
        user_sources = await db.execute(
            select(Source.source_id).where(
                Source.owner_user_id == user_id,
                Source.is_active == True
            )
        )
        source_ids.extend([s[0] for s in user_sources.fetchall()])
        
        # Bot sources if provided
        if bot_source_ids:
            bot_sources = await db.execute(
                select(Source.source_id).where(
                    Source.source_id.in_(bot_source_ids),
                    Source.is_active == True
                )
            )
            source_ids.extend([s[0] for s in bot_sources.fetchall()])
        
        return source_ids
    
    def is_meta_query(self, message: str) -> bool:
        """Detect meta queries about the system itself"""
        meta_patterns = [
            "what tools", "what can you do", "what are you capable of",
            "list tools", "available tools", "help", "what functions",
            "what commands", "show me tools", "what do you have access to"
        ]
        message_lower = message.lower().strip()
        return any(pattern in message_lower for pattern in meta_patterns)
    
    def generate_meta_response(self) -> str:
        """Generate response for meta queries"""
        if not self.tools:
            return """I don't currently have access to any tools or knowledge sources. 

To get started:
1. Configure sources in the Sources tab
2. Create/mention bots with knowledge sources
3. Ask questions that require searching

Once configured, I'll help you search your knowledge bases."""

        # Group tools by source
        tools_by_source = {}
        for i, tool in enumerate(self.tools):
            source_name = "Unknown Source"
            if i < len(self._tool_metadata):
                source_name = self._tool_metadata[i].get("source_name", source_name)
            
            if source_name not in tools_by_source:
                tools_by_source[source_name] = []
            tools_by_source[source_name].append({
                "name": tool.name,
                "description": tool.description
            })
        
        response = f"I have access to **{len(self.tools)} tools** from **{len(self.loaded_sources)} sources**:\n\n"
        
        for source_name, tools in tools_by_source.items():
            response += f"**{source_name}:**\n"
            for tool in tools[:5]:  # Show max 5 per source
                response += f"- `{tool['name']}`: {tool['description']}\n"
            if len(tools) > 5:
                response += f"- ... and {len(tools) - 5} more tools\n"
            response += "\n"
        
        response += """**Example queries:**
- "Search for information about [topic]"
- "Find documentation on [feature]"
- "@[botname] what is [question]"

Just ask me anything!"""
        
        return response
    
    def filter_search_tools(self) -> List[BaseTool]:
        """Filter to search/read-only tools"""
        return filter_search_tools(self.tools)
    
    async def load_conversation_history(
        self, 
        db: AsyncSession, 
        conversation_id: uuid.UUID
    ) -> List[Any]:
        """Load conversation history for context"""
        try:
            result = await db.execute(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at.desc())
                .limit(CONVERSATION_HISTORY_LIMIT)
            )
            messages = list(reversed(result.scalars().all()))
            
            langchain_messages = []
            for msg in messages:
                # Extract data early to avoid greenlet issues
                role = msg.role
                content = msg.content
                
                if role == "user":
                    langchain_messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    langchain_messages.append(AIMessage(content=content))
            
            return langchain_messages
            
        except Exception as e:
            logger.warning("Failed to load conversation history", error=str(e))
            return []

    def _create_llm(self, llm_provider: str, llm_model: str):
        """Create LLM instance"""
        import os
        
        if llm_provider == "anthropic":
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY not set")
            return ChatAnthropic(model=llm_model, temperature=DEFAULT_TEMPERATURE, api_key=api_key)
            
        elif llm_provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY not set")
            return ChatOpenAI(model=llm_model, temperature=DEFAULT_TEMPERATURE, api_key=api_key)
            
        else:
            raise ValueError(f"Unsupported LLM provider: {llm_provider}")

    def _create_system_prompt(self, search_tools: List[BaseTool]) -> str:
        """Create system prompt for LLM"""
        tools_info = [f"- {tool.name}: {tool.description}" for tool in search_tools]
        tools_context = "\n".join(tools_info)
        server_context = ", ".join(self.loaded_sources)
        
        return f"""You are Scintilla, IgniteTech's intelligent knowledge assistant.

CRITICAL CITATION REQUIREMENTS:
- ALWAYS cite sources using [1], [2], [3] format
- Place citations immediately after relevant information
- Include <SOURCES> section at end with proper URLs

Available search tools ({len(search_tools)} tools):
{tools_context}

Connected sources: {server_context}

Approach:
1. Use relevant search tools for user's query
2. Extract URLs/IDs from tool results
3. Create proper citations [1], [2], [3] in text
4. Include Sources section with this format:

<SOURCES>
[1] [Document Title](https://docs.google.com/document/d/FILE_ID/edit)
[2] [Repository Name](https://github.com/user/repo)
</SOURCES>

Always use search tools and cite sources properly."""

    async def _execute_tool_calls(
        self, 
        tool_calls: List[Dict], 
        message: str
    ) -> Tuple[List[ToolMessage], List[Dict]]:
        """Execute tool calls via working agent and return results"""
        tool_results = []
        tools_called = []
        
        for tool_call in tool_calls:
            tool_name = tool_call['name']
            tool_args = tool_call['args']
            
            try:
                # Use working agent's proven call_tool method
                result_dict = await self._working_agent.call_tool(
                    tool_name=tool_name,
                    query_context=message,
                    citation_manager=self.citation_manager,
                    **tool_args
                )
                
                # Extract result from working agent's response format
                if isinstance(result_dict, dict):
                    if result_dict.get("error"):
                        tool_result = f"Tool error: {result_dict['error']}"
                    else:
                        tool_result = result_dict.get("result", str(result_dict))
                else:
                    tool_result = str(result_dict)
                
                tools_called.append({
                    "tool": tool_name,
                    "arguments": tool_args,
                    "result": tool_result
                })
                
                # Create tool message for conversation
                tool_message = ToolMessage(
                    content=str(tool_result),
                    tool_call_id=tool_call['id']
                )
                tool_results.append(tool_message)
                
            except Exception as e:
                error_result = f"Tool execution failed: {str(e)}"
                
                tools_called.append({
                    "tool": tool_name,
                    "arguments": tool_args,
                    "error": str(e)
                })
                
                tool_message = ToolMessage(
                    content=error_result,
                    tool_call_id=tool_call['id']
                )
                tool_results.append(tool_message)
        
        return tool_results, tools_called

    async def query(
        self,
        message: str,
        llm_provider: str = "anthropic", 
        llm_model: str = "claude-sonnet-4-20250514",
        conversation_id: Optional[uuid.UUID] = None,
        db_session: Optional[AsyncSession] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute query with streaming response"""
        query_start = time.time()
        
        # Handle meta queries
        if self.is_meta_query(message):
            yield {
                "type": "final_response",
                "content": self.generate_meta_response(),
                "tool_calls": [],
                "tools_available": len(self.tools),
                "servers_connected": len(self.loaded_sources),
                "sources": [],
                "processing_stats": {
                    "total_tools_called": 0,
                    "query_type": "meta",
                    "response_time_ms": int((time.time() - query_start) * 1000),
                    "sources_found": 0
                }
            }
            return
        
        # Validate tools available
        if not self.tools:
            yield {"type": "error", "error": "No tools available. Configure sources first."}
            return
        
        search_tools = self.filter_search_tools()
        if not search_tools:
            yield {"type": "error", "error": "No search tools available"}
            return
        
        try:
            # Initialize components
            llm = self._create_llm(llm_provider, llm_model)
            llm_with_tools = llm.bind_tools(search_tools)
            system_prompt = self._create_system_prompt(search_tools)
            
            # Clear citations for new query
            self.citation_manager.clear()
            
            yield {
                "type": "thinking",
                "content": f"Searching {len(search_tools)} tools from {len(self.loaded_sources)} sources..."
            }
            
            # Setup conversation
            messages = [SystemMessage(content=system_prompt)]
            
            # Add conversation history
            if conversation_id and db_session:
                history = await self.load_conversation_history(db_session, conversation_id)
                messages.extend(history)
            
            messages.append(HumanMessage(content=message))
            
            # Execute conversation loop
            tools_called = []
            iteration = 0
            
            while iteration < MAX_TOOL_ITERATIONS:
                iteration += 1
                
                # Get LLM response
                response = await llm_with_tools.ainvoke(messages)
                messages.append(response)
                
                # Check for tool calls
                if hasattr(response, 'tool_calls') and response.tool_calls:
                    # Stream tool call notifications
                    for tool_call in response.tool_calls:
                        yield {
                            "type": "tool_call",
                            "tool_name": tool_call['name'],
                            "arguments": tool_call['args'],
                            "status": "running"
                        }
                    
                    # Execute tools and get results
                    tool_results, call_results = await self._execute_tool_calls(
                        response.tool_calls, message
                    )
                    
                    # Stream tool results
                    for result in call_results:
                        tool_result = result.get("result", "")
                        preview = tool_result[:TOOL_PREVIEW_LENGTH]
                        if len(tool_result) > TOOL_PREVIEW_LENGTH:
                            preview += "..."
                        
                        yield {
                            "type": "tool_result",
                            "tool_name": result["tool"],
                            "result": preview,
                            "status": "completed" if "error" not in result else "error"
                        }
                    
                    tools_called.extend(call_results)
                    messages.extend(tool_results)
                    continue
                else:
                    # Final response
                    final_content = response.content
                    break
            
            # Process final response with citations
            if iteration >= MAX_TOOL_ITERATIONS:
                final_content = getattr(response, 'content', "Maximum iterations reached")
            
            # Add citation references
            reference_list = self.citation_manager.generate_reference_list()
            if reference_list:
                final_content += f"\n\n{reference_list}"
            
            # Enhance sources with URLs (using working agent's proven method)
            enhanced_sources = self._working_agent._enhance_sources_with_llm_urls(
                final_content, 
                self.citation_manager.get_sources_metadata()
            )
            
            # Generate processing stats
            total_tools_called = len(tools_called)
            
            yield {
                "type": "final_response",
                "content": final_content,
                "tool_calls": tools_called,
                "tools_available": len(search_tools),
                "servers_connected": len(self.loaded_sources),
                "sources": enhanced_sources,
                "processing_stats": {
                    "total_tools_called": total_tools_called,
                    "sources_found": len(self.citation_manager.sources),
                    "query_type": "fast_mcp_agent",
                    "response_time_ms": int((time.time() - query_start) * 1000)
                }
            }
            
        except Exception as e:
            logger.error("Query execution failed", error=str(e))
            yield {"type": "error", "error": f"Query failed: {str(e)}"} 
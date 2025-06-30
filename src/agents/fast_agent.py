"""
Fast MCP Agent - Simplified agent using centralized FastMCP module

Performance improvements:
1. Loads tools from database cache (milliseconds vs seconds) 
2. Uses centralized FastMCP service for all MCP operations
3. Clean, maintainable code without duplication
4. Proper conversation history and citations
5. Context size management to prevent overflow
"""

import uuid
import time
from typing import List, Dict, Any, Optional, AsyncGenerator, Tuple
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from langchain_core.tools import BaseTool
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
import structlog

from src.db.models import Message
from src.agents.fast_mcp import FastMCPToolManager
from src.agents.context_manager import ContextManager

logger = structlog.get_logger()

# Scintilla Local Agent Protocol - User must use these URL schemes for local tools
SCINTILLA_LOCAL_SCHEMES = [
    "local://",     # Generic local execution: local://tool-name
    "stdio://",     # STDIO MCP servers: stdio://path/to/server
    "agent://",     # Local agent execution: agent://capability-name
]

# Configuration constants
MAX_TOOL_ITERATIONS = 10
CONVERSATION_HISTORY_LIMIT = 10
TOOL_PREVIEW_LENGTH = 500
DEFAULT_TEMPERATURE = 0.1


class FastMCPAgent:
    """
    Simplified Fast MCP Agent using centralized FastMCP service
    
    Responsibilities:
    - Load tools from database cache via FastMCPToolManager
    - Execute conversations with LLM + tool calling
    - Handle citations and streaming responses
    - Manage context size to prevent overflow
    """
    
    def __init__(self):
        """Initialize FastMCPAgent"""
        self.tool_manager = FastMCPToolManager()
        self.tools: List[BaseTool] = []
        self.loaded_sources: List[str] = []
        self.source_instructions: Dict[str, str] = {}  # Map source name to instructions
        self.context_manager = None  # Will be initialized in query() based on model
        
        # Tool classification for local vs remote execution
        self.local_tools: List[BaseTool] = []
        self.remote_tools: List[BaseTool] = []
        
        logger.info("FastMCPAgent initialized")
    
    async def load_tools_from_cache(
        self, 
        db: AsyncSession, 
        user_id: uuid.UUID,
        bot_source_ids: Optional[List[uuid.UUID]] = None
    ) -> int:
        """Load tools from database cache using FastMCP"""
        logger.info("Loading FastMCP tools from cache", user_id=user_id, bot_source_ids=bot_source_ids)
        
        # Load tools via centralized tool manager
        tool_count = await self.tool_manager.load_tools_for_user(
            db=db,
            user_id=user_id,
            bot_source_ids=bot_source_ids
        )
        
        # Store references for compatibility
        self.tools = self.tool_manager.get_tools()
        self.loaded_sources = self.tool_manager.get_server_names()
        
        # Get source instructions from the tool manager
        self.source_instructions = await self.tool_manager.get_source_instructions(db)
        
        # Classify tools for routing
        self._classify_tools()
        
        logger.info("FastMCP tools loaded and classified", 
                   tool_count=tool_count, 
                   sources=len(self.loaded_sources),
                   local_tools=len(self.local_tools),
                   remote_tools=len(self.remote_tools))
        return tool_count
    
    async def load_tools_for_specific_sources(
        self, 
        db: AsyncSession, 
        user_id: uuid.UUID,
        source_ids: List[uuid.UUID]
    ) -> int:
        """Load tools from database cache for specific source IDs only"""
        logger.info("Loading FastMCP tools for specific sources", user_id=user_id, source_ids=source_ids)
        
        # Load tools via centralized tool manager
        tool_count = await self.tool_manager.load_tools_for_specific_sources(
            db=db,
            user_id=user_id,
            source_ids=source_ids
        )
        
        # Store references for compatibility
        self.tools = self.tool_manager.get_tools()
        self.loaded_sources = self.tool_manager.get_server_names()
        
        # Get source instructions from the tool manager
        self.source_instructions = await self.tool_manager.get_source_instructions(db)
        
        # Classify tools for routing
        self._classify_tools()
        
        logger.info("FastMCP tools loaded and classified for specific sources", 
                   tool_count=tool_count, 
                   sources=len(self.loaded_sources),
                   local_tools=len(self.local_tools),
                   remote_tools=len(self.remote_tools))
        return tool_count
    
    def filter_search_tools(self) -> List[BaseTool]:
        """Filter to search/read-only tools"""
        return self.tool_manager.filter_search_tools()
    
    def _classify_tools(self):
        """Classify tools as local or remote based on patterns"""
        self.local_tools = []
        self.remote_tools = []
        
        for tool in self.tools:
            if self._is_local_tool(tool):
                self.local_tools.append(tool)
            else:
                self.remote_tools.append(tool)
    
    def _is_local_tool(self, tool: BaseTool) -> bool:
        """
        Determine if a tool should be executed locally using Scintilla's explicit URL scheme.
        
        Users must use one of these URL schemes in their source configuration:
        - local://tool-name     (generic local execution)
        - stdio://path/to/server (STDIO MCP servers)  
        - agent://capability    (local agent execution)
        """
        
        # Check tool metadata for source information
        if hasattr(tool, 'metadata') and tool.metadata:
            source_id = tool.metadata.get('source_id')
            if source_id:
                # Find the source URL from loaded server configs
                for config in self.tool_manager.server_configs:
                    if config.source_id == source_id:
                        source_url = config.server_url.lower()
                        
                        # Check for Scintilla local schemes
                        for scheme in SCINTILLA_LOCAL_SCHEMES:
                            if source_url.startswith(scheme):
                                logger.info(f"✅ Tool {tool.name} marked as LOCAL due to scheme '{scheme}' in {source_url}")
                                return True
                        
                        # If no local scheme found, it's remote
                        logger.debug(f"☁️ Tool {tool.name} marked as REMOTE - URL: {source_url}")
                        return False
        
        # No source metadata found - assume remote for safety
        logger.warning(f"⚠️ Tool {tool.name} has no source metadata - assuming REMOTE")
        return False
    
    async def _execute_local_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Execute a tool via local agents"""
        try:
            # Import here to avoid circular imports
            from src.api.local_agents import execute_local_tool
            
            # Execute via local agent system
            result = await execute_local_tool(tool_name, arguments, timeout_seconds=60)
            
            if result.get("success"):
                return result.get("result", "")
            else:
                error_msg = result.get("error", "Unknown error")
                logger.warning(f"Local tool execution failed: {tool_name}", error=error_msg)
                return f"Error executing local tool {tool_name}: {error_msg}"
                
        except Exception as e:
            logger.error(f"Failed to execute local tool {tool_name}", error=str(e))
            return f"Error executing local tool {tool_name}: {str(e)}"
    
    async def load_conversation_history(
        self, 
        db: AsyncSession, 
        conversation_id: uuid.UUID
    ) -> List[Any]:
        """Load conversation history for context (enhanced for better follow-up handling)"""
        try:
            result = await db.execute(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at.desc())
                .limit(10)  # Increased from 6 to 10 for better context
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
            
            logger.info(f"Loaded {len(langchain_messages)} conversation messages for context")
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
        
        # Build source-specific instructions section with validation emphasis
        instructions_section = ""
        if self.source_instructions:
            instructions_section = "\n\n🔒 CRITICAL SOURCE-SPECIFIC INSTRUCTIONS:\n"
            instructions_section += "These instructions are MANDATORY and must be followed strictly:\n\n"
            for source_name, instructions in self.source_instructions.items():
                if instructions:  # Only include if instructions exist
                    instructions_section += f"**{source_name}:**\n{instructions}\n\n"
            
            instructions_section += "⚠️ FAILURE TO FOLLOW THESE INSTRUCTIONS IS NOT ACCEPTABLE ⚠️\n"
            instructions_section += "Always validate your response against these requirements before responding.\n"
            instructions_section += "\n🔍 SEARCH VALIDATION REQUIREMENT:\n"
            instructions_section += "Before calling any search tool, check if source-specific filters need to be automatically applied.\n"
            instructions_section += "If instructions specify mandatory project/space filters, include them in EVERY search.\n"
        
        return f"""You are Scintilla, IgniteTech's intelligent knowledge assistant with access to {len(search_tools)} search tools from: {server_context}

CONVERSATION CONTEXT: You maintain conversation context across messages. When users ask follow-up questions, they're building on previous responses. For example:
- User: "What are the open tickets?"
- Assistant: [provides ticket list]
- User: "Is there documentation for these?" ← This refers to the tickets from previous response

DECISION MATRIX - When to use tools vs respond directly:

USE TOOLS when users ask about:
- Specific information that needs searching ("What is Eloquens?", "How does X work?")
- Follow-up questions requiring new searches ("documentation for these", "status of that project")
- Technical documentation or implementation details
- Recent updates, changes, or current status
- Specific files, documents, or code repositories
- Troubleshooting or configuration help
- Any query requiring factual information from knowledge bases

RESPOND DIRECTLY for:
- General capability questions ("What can you do?", "What tools do you have?")
- Simple explanations of basic concepts you already covered
- Clarifications about previous responses (only if no new search needed)
- Meta questions about your functions

AVAILABLE SEARCH TOOLS ({len(search_tools)} tools):
{tools_context}

CITATION REQUIREMENTS (only when using tools):
- Cite sources using [1], [2], [3] format ONLY when specifically referencing information from that source
- Don't add citations to general introductory sentences or summaries
- Only cite when the information comes directly from a specific tool result
- For example: "The ticket PDR-148554 has status 'Requested' [1]" NOT "Here are the tickets [1]:"
- Focus on citation accuracy - URL formatting and link validation will be handled automatically
- I will provide a comprehensive Sources section automatically - do NOT add your own <SOURCES> section

CAPABILITY RESPONSE (when asked what you can do):
"I have access to {len(search_tools)} search tools from {len(self.loaded_sources)} knowledge sources. I can help you find information about technical documentation, code repositories, project details, and more. Just ask me specific questions about topics you're interested in!"

Be intelligent about tool usage - search when information is needed, respond directly when appropriate.{instructions_section}"""
    
    async def _execute_tool_calls(
        self, 
        tool_calls: List[Dict], 
        message: str
    ) -> Tuple[List[ToolMessage], List[Dict], List[Dict]]:
        """Execute tool calls and return results with metadata for flexible citation handling"""
        tool_results = []
        tools_called = []
        tool_metadata = []  # Collect metadata for citation processing
        
        for tool_call in tool_calls:
            tool_name = tool_call['name']
            tool_args = tool_call['args']
            
            try:
                # Find the tool by name
                target_tool = None
                for tool in self.tools:
                    if tool.name == tool_name:
                        target_tool = tool
                        break
                
                if not target_tool:
                    error_result = f"Tool '{tool_name}' not found"
                    tools_called.append({
                        "tool": tool_name,
                        "arguments": tool_args,
                        "error": error_result
                    })
                    
                    tool_message = ToolMessage(
                        content=error_result,
                        tool_call_id=tool_call['id']
                    )
                    tool_results.append(tool_message)
                    continue
                
                # Route to local or remote execution
                if self._is_local_tool(target_tool):
                    # Execute via local agents
                    logger.info(f"🏠 Executing local tool: {tool_name}", args=tool_args)
                    tool_result = await self._execute_local_tool(tool_name, tool_args)
                else:
                    # Execute via remote MCP (existing logic)
                    logger.info(f"☁️ Executing remote tool: {tool_name}", args=tool_args)
                    tool_result = await target_tool.ainvoke(tool_args)
                
                # Process tool result to extract metadata (flexible approach)
                from src.agents.tool_result_processor import ToolResultProcessor
                metadata = ToolResultProcessor.process_tool_result(
                    tool_name=tool_name,
                    tool_result=tool_result,
                    tool_params=tool_args
                )
                
                # Store metadata for later citation processing
                tool_metadata.append({
                    "tool_name": tool_name,
                    "tool_args": tool_args,
                    "metadata": metadata.to_dict(),
                    "raw_result": str(tool_result)
                })
                
                logger.info(
                    f"📊 Tool metadata extracted",
                    tool=tool_name,
                    urls=len(metadata.urls),
                    titles=len(metadata.titles),
                    identifiers=list(metadata.identifiers.keys())
                )
                
                tools_called.append({
                    "tool": tool_name,
                    "arguments": tool_args,
                    "result": str(tool_result)
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
        
        return tool_results, tools_called, tool_metadata
    
    async def query(
        self,
        message: str,
        llm_provider: str = "anthropic", 
        llm_model: str = "claude-sonnet-4-20250514",
        conversation_id: Optional[uuid.UUID] = None,
        db_session: Optional[AsyncSession] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute query with streaming response and context size management"""
        query_start = time.time()
        
        # Validate tools available
        if not self.tools:
            yield {"type": "error", "error": "No tools available. Configure sources first."}
            return
        
        search_tools = self.filter_search_tools()
        if not search_tools:
            yield {"type": "error", "error": "No search tools available"}
            return
        
        try:
            # PREPROCESS QUERY: Incorporate bot instructions into the query itself
            original_message = message
            message = await self._preprocess_query_with_instructions(message)
            
            if message != original_message:
                yield {
                    "type": "query_preprocessed",
                    "original_query": original_message,
                    "modified_query": message
                }
            
            # Initialize components
            llm = self._create_llm(llm_provider, llm_model)
            llm_with_tools = llm.bind_tools(search_tools)
            
            # Initialize context manager for this query
            self.context_manager = ContextManager(llm_model)
            
            # Create system prompt
            system_prompt = self._create_system_prompt(search_tools)
            
            yield {
                "type": "thinking",
                "content": f"Searching {len(search_tools)} tools from {len(self.loaded_sources)} sources..."
            }
            
            # Setup conversation with context management
            conversation_history = []
            
            # Add conversation history
            if conversation_id and db_session:
                conversation_history = await self.load_conversation_history(db_session, conversation_id)
            
            # Execute conversation loop
            tools_called = []
            all_tool_metadata = []  # Collect all metadata across iterations
            iteration = 0
            tool_results_str = []  # Collect tool results for context management
            
            while iteration < MAX_TOOL_ITERATIONS:
                iteration += 1
                
                # Optimize context before each LLM call (but NOT citation context yet)
                optimized_history, optimized_tool_results, _ = self.context_manager.optimize_context(
                    system_prompt=system_prompt,
                    conversation_history=conversation_history,
                    current_message=message,
                    tool_results=tool_results_str,
                    citation_context=""  # Don't add citation context during tool iterations
                )
                
                # Build messages for this iteration
                messages = [SystemMessage(content=system_prompt)]
                
                # Filter out any SystemMessage objects from history to avoid multiple system messages
                filtered_history = [msg for msg in optimized_history if not isinstance(msg, SystemMessage)]
                messages.extend(filtered_history)
                messages.append(HumanMessage(content=message))
                
                # DO NOT add standalone tool results - this causes tool_use_id mismatches
                # The conversation_history already contains proper tool use/result pairs
                
                # Log context usage
                estimated_tokens = self.context_manager.estimate_current_context(
                    system_prompt=system_prompt,
                    conversation_history=optimized_history,
                    current_message=message,
                    tool_results=optimized_tool_results,
                    citation_context=""
                )
                logger.info(f"Context usage: ~{estimated_tokens} tokens (iteration {iteration})")
                
                # Get LLM response
                response = await llm_with_tools.ainvoke(messages)
                
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
                    
                    # Execute tools and get results with metadata
                    tool_results, call_results, tool_metadata = await self._execute_tool_calls(
                        response.tool_calls, message
                    )
                    
                    # Store metadata for final citation processing
                    all_tool_metadata.extend(tool_metadata)
                    
                    # Collect tool result strings for context management
                    for result in call_results:
                        tool_result_str = result.get("result", "")
                        if tool_result_str:
                            # Truncate large tool results immediately
                            truncated_result = self.context_manager.truncate_tool_result(tool_result_str)
                            tool_results_str.append(truncated_result)
                    
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
                    
                    # Update conversation history for next iteration
                    conversation_history.append(AIMessage(content=response.content or ""))
                    conversation_history.extend(tool_results)
                    
                    continue
                else:
                    # No more tool calls - prepare for final response
                    break
            
            # FINAL RESPONSE GENERATION WITH CITATIONS
            # Now we have all tool results and metadata - generate final response with proper citations
            
            # Build citation guidance from collected metadata
            citation_guidance = self._build_citation_guidance(all_tool_metadata)
            
            # Create final prompt with citation guidance - use conversation history instead of recreating tool results
            final_messages = [SystemMessage(content=system_prompt)]
            
            # Filter out any SystemMessage objects from history to avoid multiple system messages
            filtered_history = [msg for msg in optimized_history if not isinstance(msg, SystemMessage)]
            final_messages.extend(filtered_history)
            final_messages.append(HumanMessage(content=message))
            
            # DO NOT add standalone tool results - this causes tool_use_id mismatches
            # The optimized_history already contains proper tool use/result pairs
            
            # Add citation guidance as a HumanMessage (not SystemMessage to avoid multiple system messages)
            if citation_guidance:
                citation_prompt = f"""Based on the tool results above, here is information you can cite:

{citation_guidance}

IMPORTANT CITATION INSTRUCTIONS:
1. Use [1], [2], [3] format when citing specific information from sources
2. Only cite when directly referencing information from a source
3. Match citation numbers to the source list above
4. Keep ticket IDs as plain text (like PDR-148559, not links)
5. Add citations for EACH ticket you mention - if you mention 5 tickets, use [1], [2], [3], [4], [5]
6. Citations should appear in the order of the source list above
7. Focus on accuracy - formatting will be validated and fixed automatically

EXAMPLE: "The ticket PDR-148559 has status 'Closed' [1] and PDR-148558 also has status 'Closed' [2]."

Please provide your response with proper citations based on the tool results."""
                
                final_messages.append(HumanMessage(content=citation_prompt))
            
            # Get final response with proper citations
            final_response = await llm.ainvoke(final_messages)
            final_content = final_response.content
            
            # Process final response with citations
            if iteration >= MAX_TOOL_ITERATIONS:
                final_content = "I've reached the maximum number of tool iterations. Here's what I found:\n\n" + final_content
            
            # Remove any <SOURCES> sections the LLM might have added
            import re
            final_content = re.sub(r'<SOURCES>.*?</SOURCES>', '', final_content, flags=re.DOTALL).strip()
            
            # LLM-BASED VALIDATION STEP - Use LLM intelligence to validate and fix issues
            if citation_guidance and all_tool_metadata:
                final_content = await self._validate_and_fix_response(
                    llm, final_content, citation_guidance, all_tool_metadata
                )
            
            # SKIP post-processing clickable links - we want only [1], [2], [3] citations to be clickable
            # final_content = self._create_clickable_links(final_content, all_tool_metadata)
            
            # Build sources list from metadata
            sources = self._build_sources_from_metadata(all_tool_metadata, final_content)
            
            # Generate processing stats including context management info
            total_tools_called = len(tools_called)
            
            yield {
                "type": "final_response",
                "content": final_content,
                "tool_calls": tools_called,
                "tools_available": len(search_tools),
                "servers_connected": len(self.loaded_sources),
                "sources": sources,
                "processing_stats": {
                    "total_tools_called": total_tools_called,
                    "sources_found": len(sources),
                    "query_type": "fast_mcp_agent",
                    "response_time_ms": int((time.time() - query_start) * 1000),
                    "context_tokens_used": estimated_tokens,
                    "context_optimized": len(conversation_history) != len(optimized_history),
                    "conversation_messages_kept": len(optimized_history) if optimized_history else 0,
                    "conversation_messages_total": len(conversation_history) if conversation_history else 0
                }
            }
            
            logger.info("FastMCPAgent query completed successfully with flexible citation system")
            
        except Exception as e:
            logger.exception("Query execution failed")
            yield {
                "type": "error", 
                "error": f"Query failed: {str(e)}",
                "details": str(e)
            }
    
    def _build_citation_guidance(self, tool_metadata: List[Dict]) -> str:
        """Build citation guidance from tool metadata for the final LLM call"""
        if not tool_metadata:
            return ""
        
        citation_lines = []
        source_num = 1
        
        for meta in tool_metadata:
            tool_name = meta['tool_name']
            metadata = meta['metadata']
            
            # Skip if no useful information
            if not any([metadata.get('urls'), metadata.get('titles'), metadata.get('identifiers')]):
                continue
            
            # Special handling for Jira results with multiple tickets
            if (metadata.get('source_type') == 'jira' and 
                metadata.get('identifiers', {}).get('tickets') and
                len(metadata.get('urls', [])) > 1):
                
                # Create separate citation entry for each ticket
                tickets = metadata['identifiers']['tickets'].split(',')
                urls = metadata.get('urls', [])
                titles = metadata.get('titles', [])
                
                for i, ticket in enumerate(tickets):
                    ticket = ticket.strip()
                    if not ticket:
                        continue
                    
                    # Use corresponding URL if available
                    ticket_url = None
                    for url in urls:
                        if f'/browse/{ticket}' in url:
                            ticket_url = url
                            break
                    
                    # Find title for this ticket
                    ticket_title = None
                    for title in titles:
                        if ticket in title:
                            ticket_title = title
                            break
                    
                    if not ticket_title:
                        ticket_title = f"{ticket}: Jira Issue"
                    
                    # Build citation entry for this ticket
                    citation_parts = [f"[{source_num}] {ticket_title}"]
                    
                    if ticket_url:
                        citation_parts.append(f"   URL: {ticket_url}")
                    
                    citation_parts.append(f"   Ticket: {ticket}")
                    citation_parts.append(f"   Type: jira")
                    
                    citation_lines.extend(citation_parts)
                    citation_lines.append("")  # Empty line between sources
                    source_num += 1
            else:
                # Standard single-source handling
                citation_parts = []
                
                # Use first title if available
                if metadata.get('titles'):
                    citation_parts.append(f"[{source_num}] {metadata['titles'][0]}")
                else:
                    citation_parts.append(f"[{source_num}] {tool_name} results")
                
                # Add primary URL if available
                if metadata.get('urls'):
                    citation_parts.append(f"   URL: {metadata['urls'][0]}")
                
                # Add identifiers
                if metadata.get('identifiers'):
                    ids = metadata['identifiers']
                    if ids.get('primary_ticket'):
                        citation_parts.append(f"   Ticket: {ids['primary_ticket']}")
                    if ids.get('pr_number'):
                        citation_parts.append(f"   PR: #{ids['pr_number']}")
                    if ids.get('issue_number'):
                        citation_parts.append(f"   Issue: #{ids['issue_number']}")
                
                # Add source type
                if metadata.get('source_type'):
                    citation_parts.append(f"   Type: {metadata['source_type']}")
                
                citation_lines.extend(citation_parts)
                citation_lines.append("")  # Empty line between sources
                source_num += 1
        
        return "\n".join(citation_lines)
    
    def _create_clickable_links(self, content: str, tool_metadata: List[Dict]) -> str:
        """Create clickable links for identifiers found in content"""
        import re
        
        # Build mapping of identifiers to URLs
        id_to_url = {}
        
        for meta in tool_metadata:
            metadata = meta['metadata']
            urls = metadata.get('urls', [])
            identifiers = metadata.get('identifiers', {})
            
            if not urls:
                continue
            
            primary_url = urls[0]
            
            # Map ticket IDs
            if identifiers.get('primary_ticket'):
                id_to_url[identifiers['primary_ticket']] = primary_url
            
            # Map all tickets if available
            if identifiers.get('tickets'):
                for ticket in identifiers['tickets'].split(','):
                    if ticket and ticket not in id_to_url:
                        # Try to construct URL for this ticket
                        if 'jira' in metadata.get('source_type', ''):
                            base_url = primary_url.rsplit('/browse/', 1)[0]
                            id_to_url[ticket] = f"{base_url}/browse/{ticket}"
        
        # Replace identifiers with clickable links, but avoid ones already in markdown links
        def replace_identifier(match):
            full_match = match.group(0)
            identifier = match.group(1)
            start_pos = match.start()
            
            # Check if this identifier is already inside a markdown link
            # Look for preceding '[' and check if there's a corresponding '](' pattern
            preceding_text = content[:start_pos]
            if '[' in preceding_text:
                # Find the last '[' before this position
                last_bracket = preceding_text.rfind('[')
                if last_bracket != -1:
                    # Check if there's a '](' pattern after our identifier
                    following_text = content[match.end():]
                    if following_text.startswith(']('):
                        # This identifier is already part of a markdown link, don't replace
                        return full_match
            
            # Safe to replace
            if identifier in id_to_url:
                url = id_to_url[identifier]
                return f'[{identifier}]({url})'
            return full_match
        
        # Pattern for ticket IDs
        ticket_pattern = r'\b([A-Z][A-Z0-9]*-\d+)\b'
        content = re.sub(ticket_pattern, replace_identifier, content)
        
        return content
    
    def _build_sources_from_metadata(self, tool_metadata: List[Dict], final_content: str) -> List[Dict]:
        """Build sources list from tool metadata, filtered by what's actually cited"""
        import re
        
        # Find all citation references in the final content
        citation_pattern = r'\[(\d+)\]'
        referenced_citations = set()
        for match in re.finditer(citation_pattern, final_content):
            referenced_citations.add(int(match.group(1)))
        
        sources = []
        source_num = 1
        
        for meta in tool_metadata:
            metadata = meta['metadata']
            
            # Skip if no useful information
            if not any([metadata.get('urls'), metadata.get('titles'), metadata.get('identifiers')]):
                continue
            
            # Special handling for Jira results with multiple tickets
            if (metadata.get('source_type') == 'jira' and 
                metadata.get('identifiers', {}).get('tickets') and
                len(metadata.get('urls', [])) > 1):
                
                # Create separate source entry for each ticket that's referenced
                tickets = metadata['identifiers']['tickets'].split(',')
                urls = metadata.get('urls', [])
                titles = metadata.get('titles', [])
                
                for i, ticket in enumerate(tickets):
                    ticket = ticket.strip()
                    if not ticket:
                        continue
                    
                    # Only include if this source number is referenced
                    if source_num in referenced_citations:
                        # Use corresponding URL if available
                        ticket_url = None
                        for url in urls:
                            if f'/browse/{ticket}' in url:
                                ticket_url = url
                                break
                        
                        # Find title for this ticket
                        ticket_title = None
                        for title in titles:
                            if ticket in title:
                                ticket_title = title
                                break
                        
                        if not ticket_title:
                            ticket_title = f"{ticket}: Jira Issue"
                        
                        source = {
                            "title": ticket_title,
                            "url": ticket_url,
                            "source_type": "jira",
                            "snippet": metadata.get('snippet', '')[:300],
                            "metadata": {
                                "tool": meta['tool_name'],
                                "identifiers": {"primary_ticket": ticket}
                            }
                        }
                        sources.append(source)
                    
                    source_num += 1
            else:
                # Standard single-source handling
                # Only include if this source number is referenced
                if source_num in referenced_citations:
                    source = {
                        "title": metadata['titles'][0] if metadata.get('titles') else f"{meta['tool_name']} results",
                        "url": metadata['urls'][0] if metadata.get('urls') else None,
                        "source_type": metadata.get('source_type', 'tool_result'),
                        "snippet": metadata.get('snippet', '')[:300],
                        "metadata": {
                            "tool": meta['tool_name'],
                            "identifiers": metadata.get('identifiers', {})
                        }
                    }
                    sources.append(source)
                
                source_num += 1
        
        return sources

    async def _validate_and_fix_response(self, llm, final_content, citation_guidance, all_tool_metadata):
        """Use LLM intelligence to validate and fix common issues in responses"""
        validation_prompt = f"""Please review and fix any issues in this response:

ORIGINAL RESPONSE:
{final_content}

AVAILABLE CITATION INFORMATION:
{citation_guidance}

COMMON ISSUES TO FIX:
1. Broken or malformed URLs - remove or fix them
2. Missing citations for specific claims - add appropriate [1], [2], [3] citations
3. Incorrect citation numbers - match them to the source list above
4. Redundant or duplicate information
5. Poor formatting or structure

Please return the corrected response with proper citations. Keep the same tone and content, just fix technical issues."""

        try:
            validation_response = await llm.ainvoke([HumanMessage(content=validation_prompt)])
            validated_content = validation_response.content.strip()
            
            # Basic sanity check - don't replace if validation made it much shorter/longer
            if len(validated_content) < len(final_content) * 0.5:
                logger.warning("Validation made response too short, keeping original")
                return final_content
            elif len(validated_content) > len(final_content) * 2:
                logger.warning("Validation made response too long, keeping original") 
                return final_content
            else:
                logger.info("Response validated and potentially improved")
                return validated_content
                
        except Exception as e:
            logger.warning(f"Response validation failed: {e}, keeping original")
            return final_content

    async def _preprocess_query_with_instructions(self, user_query: str) -> str:
        """
        Preprocess user query to incorporate bot instructions automatically
        Uses a lightweight LLM to intelligently modify the query based on source instructions
        """
        if not self.source_instructions:
            return user_query
        
        # Build instruction context for preprocessing
        instruction_context = []
        for source_name, instructions in self.source_instructions.items():
            if instructions and ('project' in instructions.lower() or 'space' in instructions.lower()):
                instruction_context.append(f"**{source_name}**: {instructions}")
        
        if not instruction_context:
            return user_query
        
        # Create preprocessing prompt
        preprocessing_prompt = f"""You are a query preprocessor. Your job is to modify user queries to automatically include required filters based on source instructions.

SOURCE INSTRUCTIONS:
{chr(10).join(instruction_context)}

TASK: Modify the user's query to automatically include the required filters. Make it sound natural.

EXAMPLES:
- "what tickets we have" → "what tickets we have in XINETBSE project"
- "open tickets" → "open XINETBSE tickets" 
- "show me bugs" → "show me bugs in XINETBSE project"
- "confluence pages about X" → "confluence pages about X in XINET space"

USER QUERY: "{user_query}"

MODIFIED QUERY (make it natural and specific):"""

        try:
            # Use a lightweight LLM for preprocessing (faster/cheaper)
            preprocessing_llm = self._create_llm("anthropic", "claude-3-5-haiku-20241022")
            
            response = await preprocessing_llm.ainvoke([HumanMessage(content=preprocessing_prompt)])
            modified_query = response.content.strip()
            
            # Validation checks
            if len(modified_query) > len(user_query) * 3:  # Prevent runaway responses
                logger.warning("Query preprocessing resulted in overly long query, using original")
                return user_query
            
            if len(modified_query) < 3:  # Prevent empty responses
                logger.warning("Query preprocessing resulted in too short query, using original") 
                return user_query
            
            # Only use modified query if it's meaningfully different
            if modified_query.lower().strip() != user_query.lower().strip():
                logger.info(f"🔄 Query preprocessed: '{user_query}' → '{modified_query}'")
                return modified_query
            else:
                return user_query
                
        except Exception as e:
            logger.warning(f"Query preprocessing failed: {e}, using original query")
            return user_query
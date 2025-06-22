"""
Fast MCP Agent - Simplified agent using centralized FastMCP module

Performance improvements:
1. Loads tools from database cache (milliseconds vs seconds) 
2. Uses centralized FastMCP service for all MCP operations
3. Clean, maintainable code without duplication
4. Proper conversation history and citations
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
from src.agents.citations import CitationManager

logger = structlog.get_logger()

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
    """
    
    def __init__(self):
        """Initialize FastMCPAgent"""
        self.tool_manager = FastMCPToolManager()
        self.tools: List[BaseTool] = []
        self.loaded_sources: List[str] = []
        self.source_instructions: Dict[str, str] = {}  # Map source name to instructions
        self.citation_manager = CitationManager()
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
        
        logger.info("FastMCP tools loaded", tool_count=tool_count, sources=len(self.loaded_sources))
        return tool_count
    
    def filter_search_tools(self) -> List[BaseTool]:
        """Filter to search/read-only tools"""
        return self.tool_manager.filter_search_tools()
    
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
        
        # Build source-specific instructions section
        instructions_section = ""
        if self.source_instructions:
            instructions_section = "\n\nSOURCE-SPECIFIC INSTRUCTIONS:\n"
            for source_name, instructions in self.source_instructions.items():
                if instructions:  # Only include if instructions exist
                    instructions_section += f"\n**{source_name}:**\n{instructions}\n"
        
        return f"""You are Scintilla, IgniteTech's intelligent knowledge assistant with access to {len(search_tools)} search tools from: {server_context}

DECISION MATRIX - When to use tools vs respond directly:

USE TOOLS when users ask about:
- Specific information that needs searching ("What is Eloquens?", "How does X work?")
- Technical documentation or implementation details
- Recent updates, changes, or current status
- Specific files, documents, or code repositories
- Troubleshooting or configuration help
- Any query requiring factual information from knowledge bases

RESPOND DIRECTLY for:
- General capability questions ("What can you do?", "What tools do you have?")
- Simple explanations of basic concepts
- Requests for help or guidance on using the system
- Meta questions about your functions

AVAILABLE SEARCH TOOLS ({len(search_tools)} tools):
{tools_context}

CITATION REQUIREMENTS (only when using tools):
- ALWAYS cite sources using [1], [2], [3] format after relevant information
- ONLY cite information that came from actual tool results
- Don't worry about making links clickable - I'll handle that in post-processing
- I will provide a comprehensive Sources section automatically - do NOT add your own <SOURCES> section

CAPABILITY RESPONSE (when asked what you can do):
"I have access to {len(search_tools)} search tools from {len(self.loaded_sources)} knowledge sources. I can help you find information about technical documentation, code repositories, project details, and more. Just ask me specific questions about topics you're interested in!"

Be intelligent about tool usage - search when information is needed, respond directly when appropriate.{instructions_section}"""
    
    async def _execute_tool_calls(
        self, 
        tool_calls: List[Dict], 
        message: str
    ) -> Tuple[List[ToolMessage], List[Dict]]:
        """Execute tool calls and return results"""
        tool_results = []
        tools_called = []
        
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
                
                # Execute the tool
                tool_result = await target_tool.ainvoke(tool_args)
                
                # Enhanced source extraction using SimpleSourceExtractor
                from src.agents.citations import SimpleSourceExtractor
                logger.info(f"🔧 CALLING CITATION EXTRACTION: tool={tool_name}, result_length={len(str(tool_result))}")
                extracted_sources = SimpleSourceExtractor.extract_sources(
                    tool_name=tool_name,
                    result_data=tool_result,
                    tool_params=tool_args
                )
                logger.info(f"🔧 CITATION RESULT: {len(extracted_sources)} sources extracted")
                
                # Add extracted sources to citation manager
                if extracted_sources:
                    self.citation_manager.add_sources(extracted_sources)
                else:
                    # Check if this is a failed tool call - if so, don't add fallback source
                    result_str = str(tool_result)
                    if len(result_str.strip()) < 50 or "Error calling tool" in result_str:
                        logger.info(f"🚫 SKIPPING FALLBACK SOURCE for failed tool call: {tool_name}")
                    else:
                        # Only add fallback for genuine extraction failures (not failed tool calls)
                        from src.agents.citations import Source
                        source = Source(
                            title=f"{tool_name} result",
                            url="",
                            source_type="mcp_tool",
                            snippet=result_str[:300],
                            metadata={"tool": tool_name, "arguments": tool_args}
                        )
                        self.citation_manager.add_sources([source])
                        logger.info(f"📎 ADDED FALLBACK SOURCE for {tool_name}")
                
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
            
            # Remove LLM's basic <SOURCES> section and add our comprehensive one
            import re
            final_content = re.sub(r'<SOURCES>.*?</SOURCES>', '', final_content, flags=re.DOTALL).strip()
            
            # Post-process with LLM to create clickable links and polish citations
            final_content = await self._post_process_response_with_llm(llm, final_content)
            
            # Don't add reference list to text - will show in Sources section instead
            # reference_list = self.citation_manager.generate_reference_list()
            # if reference_list:
            #     final_content += f"\n\n{reference_list}"
            
            # Generate enhanced sources for the Sources section (user loves this!)
            enhanced_sources = self._enhance_sources_with_urls(
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
            
            logger.info("FastMCPAgent query completed successfully")
            
        except Exception as e:
            logger.error("Query execution failed", error=str(e))
            yield {"type": "error", "error": f"Query failed: {str(e)}"}

    def _filter_unused_citations(self, content: str) -> None:
        """Filter citation manager to only keep sources actually referenced in content"""
        import re
        
        # Find all citation references in the content [1], [2], [3], etc.
        citation_pattern = r'\[(\d+)\]'
        referenced_citations = set()
        
        for match in re.finditer(citation_pattern, content):
            citation_num = int(match.group(1))
            referenced_citations.add(citation_num)
        
        if not referenced_citations:
            # No citations found, clear all sources
            self.citation_manager.clear()
            logger.info("No citation references found, cleared all sources")
            return
        
        # Keep only sources that are actually referenced
        original_count = len(self.citation_manager.sources)
        filtered_sources = []
        
        # Special handling for Jira: if we have multiple Jira ticket sources and [1] is referenced,
        # keep all Jira sources from the same tool call (they're individual tickets from one search)
        jira_sources = [s for s in self.citation_manager.sources if s.source_type == "jira" and s.metadata.get("tool") in ["jira_search", "search"]]
        has_jira_citation = any(i + 1 in referenced_citations for i in range(len(self.citation_manager.sources)) 
                               if self.citation_manager.sources[i].source_type == "jira")
        
        for i, source in enumerate(self.citation_manager.sources):
            citation_index = i + 1  # Citations are 1-indexed
            
            # Keep if directly referenced
            if citation_index in referenced_citations:
                filtered_sources.append(source)
            # Special case: Keep all Jira ticket sources if any Jira source is referenced
            elif (source.source_type == "jira" and 
                  source.metadata.get("tool") in ["jira_search", "search"] and 
                  has_jira_citation and
                  len(jira_sources) > 1):
                filtered_sources.append(source)
                logger.info(f"🎫 KEEPING JIRA TICKET: {source.title} (part of multi-ticket result)")
        
        # Update citation manager with filtered sources
        self.citation_manager.sources = filtered_sources
        
        filtered_count = len(filtered_sources)
        removed_count = original_count - filtered_count
        
        logger.info(
            "Filtered unused citations",
            original_count=original_count,
            filtered_count=filtered_count,
            removed_count=removed_count,
            referenced_citations=sorted(referenced_citations),
            jira_sources_kept=len([s for s in filtered_sources if s.source_type == "jira"])
        )

    async def _post_process_response_with_llm(self, llm, content: str) -> str:
        """Use LLM to post-process response: create clickable links, polish citations"""
        if not self.citation_manager.sources:
            return content
        
        # Create ticket ID to URL mapping for LLM
        ticket_urls = {}
        for source in self.citation_manager.sources:
            if source.url:
                # Extract ticket ID from title (like "MKT-1183: ...")
                import re
                title_match = re.match(r'^([A-Z]+-\d+):', source.title)
                if title_match:
                    ticket_id = title_match.group(1)
                    ticket_urls[ticket_id] = source.url
        
        # Create mapping text for LLM
        ticket_mapping = []
        for ticket_id, url in ticket_urls.items():
            ticket_mapping.append(f"{ticket_id} → {url}")
        mapping_text = "\n".join(ticket_mapping)
        
        logger.info(f"Post-processing with {len(ticket_urls)} ticket URLs: {list(ticket_urls.keys())}")
        
        post_process_prompt = f"""TASK: Convert ALL ticket IDs to clickable markdown links in this response.

RESPONSE TO PROCESS:
{content}

TICKET ID → URL MAPPING:
{mapping_text}

INSTRUCTIONS:
1. Find EVERY ticket ID in the response (pattern: LETTERS-NUMBERS like MYP-330, GFIRADAR-19, etc.)
2. Convert to markdown link: MYP-330 becomes [MYP-330](url)
3. Keep everything else EXACTLY the same (including citations [1], [2], etc.)
4. Be thorough - don't miss any ticket IDs

EXAMPLES:
- "MYP-330: Configuration" → "[MYP-330](url): Configuration"  
- "GFIRADAR-19: RADAR charts" → "[GFIRADAR-19](url): RADAR charts"

CRITICAL: Find and convert ALL ticket IDs mentioned in the text. Use the exact URLs from the mapping above.

OUTPUT: Return the response with ALL ticket IDs converted to clickable markdown links."""

        try:
            post_process_message = HumanMessage(content=post_process_prompt)
            processed_response = await llm.ainvoke([post_process_message])
            processed_content = processed_response.content.strip()
            
            # Filter citations based on what's actually used in processed response
            self._filter_unused_citations(processed_content)
            
            logger.info("LLM post-processing completed")
            return processed_content
            
        except Exception as e:
            logger.warning("LLM post-processing failed, using regex fallback", error=str(e))
            # Fallback: Use regex to create clickable links
            processed_content = self._create_clickable_links_regex(content)
            self._filter_unused_citations(processed_content)
            return processed_content

    def _create_clickable_links_regex(self, content: str) -> str:
        """Fallback: Use regex to convert ticket IDs to clickable links"""
        import re
        
        # Create URL mapping from sources
        ticket_to_url = {}
        for source in self.citation_manager.sources:
            if source.url:
                # Extract ticket ID from title (like "MKT-1183: ...")
                title_match = re.match(r'^([A-Z]+-\d+):', source.title)
                if title_match:
                    ticket_id = title_match.group(1)
                    ticket_to_url[ticket_id] = source.url
        
        logger.info(f"Regex fallback: Found {len(ticket_to_url)} ticket URLs: {list(ticket_to_url.keys())}")
        
        # Replace ticket IDs with clickable links
        def replace_ticket(match):
            ticket_id = match.group(1)
            if ticket_id in ticket_to_url:
                url = ticket_to_url[ticket_id]
                logger.info(f"Converting {ticket_id} to clickable link: {url}")
                return f'[{ticket_id}]({url})'
            else:
                logger.warning(f"No URL found for ticket {ticket_id}")
                return ticket_id  # Keep original if no URL found
        
        # Find ticket patterns like ABC-123, PROJECT-456, etc.
        # More comprehensive pattern to catch various formats
        ticket_pattern = r'\b([A-Z]+[A-Z0-9]*-\d+)\b'
        processed_content = re.sub(ticket_pattern, replace_ticket, content)
        
        logger.info("Applied regex fallback for clickable links")
        return processed_content

    def _enhance_sources_with_urls(self, content: str, sources_metadata: List[Dict]) -> List[Dict]:
        """Convert citation manager sources to frontend-compatible format"""
        enhanced_sources = []
        
        # Get sources directly from citation manager
        for source in self.citation_manager.sources:
            enhanced_source = {
                "title": source.title,
                "source_type": source.source_type,
                "url": source.url if source.url else None,
                "snippet": source.snippet,
                "metadata": source.metadata
            }
            enhanced_sources.append(enhanced_source)
        
        return enhanced_sources
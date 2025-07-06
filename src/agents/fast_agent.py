"""
Fast MCP Agent - Simplified agent using centralized FastMCP module

Performance improvements:
1. Loads tools from database cache (milliseconds vs seconds) 
2. Uses centralized FastMCP service for all MCP operations
3. Clean, maintainable code without duplication
4. Proper conversation history and citations
5. Context size management to prevent overflow
"""

import asyncio
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
MAX_TOOL_ITERATIONS = 20  # Increased to support comprehensive multi-source searching
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
        bot_source_ids: Optional[List[uuid.UUID]] = None,
        selected_bot_ids: Optional[List[uuid.UUID]] = None
    ) -> int:
        """Load tools from database cache using FastMCP"""
        logger.info("Loading FastMCP tools from cache", user_id=user_id, bot_source_ids=bot_source_ids, selected_bot_ids=selected_bot_ids)
        
        # Load tools via centralized tool manager
        tool_count = await self.tool_manager.load_tools_for_user(
            db=db,
            user_id=user_id,
            bot_source_ids=bot_source_ids
        )
        
        # Store references for compatibility
        self.tools = self.tool_manager.get_tools()
        self.loaded_sources = self.tool_manager.get_server_names()
        
        # Get source instructions from the tool manager (FIXED: Pass selected bot IDs)
        self.source_instructions = await self.tool_manager.get_source_instructions(db, selected_bot_ids)
        
        # Debug log source instructions for preprocessing
        if self.source_instructions:
            logger.info("📋 Source instructions loaded for preprocessing", 
                       instruction_count=len(self.source_instructions))
            for source_name, instructions in self.source_instructions.items():
                if instructions:
                    has_project = 'project' in instructions.lower()
                    has_space = 'space' in instructions.lower()
                    logger.debug("📄 Source instruction details", 
                               source=source_name, 
                               has_project_filter=has_project,
                               has_space_filter=has_space,
                               instruction_length=len(instructions))
        else:
            logger.info("❌ No source instructions found")
        
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
        source_ids: List[uuid.UUID],
        selected_bot_ids: Optional[List[uuid.UUID]] = None
    ) -> int:
        """Load tools from database cache for specific source IDs only"""
        logger.info("Loading FastMCP tools for specific sources", user_id=user_id, source_ids=source_ids, selected_bot_ids=selected_bot_ids)
        
        # Load tools via centralized tool manager
        tool_count = await self.tool_manager.load_tools_for_specific_sources(
            db=db,
            user_id=user_id,
            source_ids=source_ids
        )
        
        # Store references for compatibility
        self.tools = self.tool_manager.get_tools()
        self.loaded_sources = self.tool_manager.get_server_names()
        
        # Get source instructions from the tool manager (FIXED: Pass selected bot IDs)
        self.source_instructions = await self.tool_manager.get_source_instructions(db, selected_bot_ids)
        
        # Debug log source instructions for preprocessing
        if self.source_instructions:
            logger.info("📋 Source instructions loaded for preprocessing", 
                       instruction_count=len(self.source_instructions))
            for source_name, instructions in self.source_instructions.items():
                if instructions:
                    has_project = 'project' in instructions.lower()
                    has_space = 'space' in instructions.lower()
                    logger.debug("📄 Source instruction details", 
                               source=source_name, 
                               has_project_filter=has_project,
                               has_space_filter=has_space,
                               instruction_length=len(instructions))
        else:
            logger.info("❌ No source instructions found")
        
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
                    # Simple text-only AI message - don't try to reconstruct tool calls from stored messages
                    # Tool call/result reconstruction from database is complex and error-prone
                    # Instead, rely on the fresh conversation history built during this session
                    langchain_messages.append(AIMessage(content=content))
            
            # Validate the conversation history to ensure no orphaned tool results
            validated_messages = self._validate_conversation_history(langchain_messages)
            
            logger.info(f"Loaded {len(validated_messages)} conversation messages for context (validated from {len(langchain_messages)})")
            return validated_messages
            
        except Exception as e:
            logger.warning("Failed to load conversation history", error=str(e))
            return []
    
    def _validate_conversation_history(self, messages: List[Any]) -> List[Any]:
        """
        Validate conversation history to ensure no orphaned tool calls/results
        Remove any ToolMessage objects that don't have corresponding AIMessage with tool calls
        """
        validated = []
        
        for i, msg in enumerate(messages):
            # Always keep user messages and regular AI messages
            if (hasattr(msg, '__class__') and 
                ('HumanMessage' in str(msg.__class__) or 
                 ('AIMessage' in str(msg.__class__) and not (hasattr(msg, 'tool_calls') and msg.tool_calls)))):
                validated.append(msg)
            
            # For AI messages with tool calls, only keep if we have the complete set
            elif (hasattr(msg, '__class__') and 'AIMessage' in str(msg.__class__) and 
                  hasattr(msg, 'tool_calls') and msg.tool_calls):
                
                # Collect expected tool call IDs
                expected_tool_ids = set()
                for tool_call in msg.tool_calls:
                    if isinstance(tool_call, dict) and 'id' in tool_call:
                        expected_tool_ids.add(tool_call['id'])
                    elif hasattr(tool_call, 'id'):
                        expected_tool_ids.add(tool_call.id)
                
                # Check if we have all corresponding tool results
                found_tool_ids = set()
                j = i + 1
                while j < len(messages) and expected_tool_ids - found_tool_ids:
                    next_msg = messages[j]
                    if (hasattr(next_msg, '__class__') and 'ToolMessage' in str(next_msg.__class__) and
                        hasattr(next_msg, 'tool_call_id')):
                        if next_msg.tool_call_id in expected_tool_ids:
                            found_tool_ids.add(next_msg.tool_call_id)
                        j += 1
                    else:
                        break
                
                # Only include if we have complete tool call/result pairs
                if found_tool_ids == expected_tool_ids:
                    validated.append(msg)
                    # Also include the corresponding tool results
                    j = i + 1
                    while j < len(messages) and found_tool_ids:
                        next_msg = messages[j]
                        if (hasattr(next_msg, '__class__') and 'ToolMessage' in str(next_msg.__class__) and
                            hasattr(next_msg, 'tool_call_id') and 
                            next_msg.tool_call_id in expected_tool_ids):
                            validated.append(next_msg)
                            found_tool_ids.remove(next_msg.tool_call_id)
                        j += 1
                else:
                    logger.warning(f"Removing incomplete tool call sequence: expected {len(expected_tool_ids)} results, found {len(found_tool_ids)}")
            
            # Skip orphaned ToolMessage objects (they should be handled above)
            elif hasattr(msg, '__class__') and 'ToolMessage' in str(msg.__class__):
                # These will be included when processing their corresponding AI message above
                continue
        
        return validated
    
    def _validate_message_sequence_for_claude(self, messages: List[Any]) -> List[Any]:
        """
        Final validation to ensure no orphaned tool results that would cause Claude API errors
        This is a safety net to catch any tool call/result mismatches before sending to Claude
        """
        validated_messages = []
        available_tool_call_ids = set()
        
        for i, msg in enumerate(messages):
            # SystemMessage and HumanMessage - always include
            if (hasattr(msg, '__class__') and 
                ('SystemMessage' in str(msg.__class__) or 'HumanMessage' in str(msg.__class__))):
                validated_messages.append(msg)
                # Reset available tool call IDs after user message (new conversation turn)
                if 'HumanMessage' in str(msg.__class__):
                    available_tool_call_ids.clear()
            
            # AIMessage - check for tool calls
            elif hasattr(msg, '__class__') and 'AIMessage' in str(msg.__class__):
                validated_messages.append(msg)
                
                # Collect tool call IDs from this AI message
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    for tool_call in msg.tool_calls:
                        if isinstance(tool_call, dict) and 'id' in tool_call:
                            available_tool_call_ids.add(tool_call['id'])
                        elif hasattr(tool_call, 'id'):
                            available_tool_call_ids.add(tool_call.id)
            
            # ToolMessage - only include if we have matching tool call ID
            elif hasattr(msg, '__class__') and 'ToolMessage' in str(msg.__class__):
                if hasattr(msg, 'tool_call_id') and msg.tool_call_id in available_tool_call_ids:
                    validated_messages.append(msg)
                    # Remove the tool call ID since it's now used
                    available_tool_call_ids.remove(msg.tool_call_id)
                else:
                    logger.warning(f"Removing orphaned tool result with ID: {getattr(msg, 'tool_call_id', 'unknown')}")
                    logger.warning(f"Available tool call IDs: {available_tool_call_ids}")
            
            else:
                # Unknown message type - include it
                validated_messages.append(msg)
        
        # Log if we removed anything
        removed_count = len(messages) - len(validated_messages)
        if removed_count > 0:
            logger.warning(f"Removed {removed_count} orphaned tool result messages to prevent Claude API errors")
        
        return validated_messages
    
    def _clean_conversation_sequence(self, messages: List[Any]) -> List[Any]:
        """
        Clean conversation sequence to ensure proper Human/AI alternation and remove incomplete messages.
        This fixes the core issue causing empty responses.
        """
        if not messages:
            return []
        
        cleaned_messages = []
        last_msg_type = None
        
        for msg in messages:
            msg_type = type(msg).__name__
            
            # Skip incomplete AI messages (ones that don't have proper tool calls/results)
            if msg_type == 'AIMessage':
                # If message has content and it looks like an incomplete response, skip it
                if hasattr(msg, 'content'):
                    content = str(msg.content)
                    # Skip messages that are incomplete coverage guidance or partial responses
                    if any(phrase in content for phrase in [
                        "I've searched", "but should also check", "for comprehensive coverage",
                        "I apologize, but after searching", "I don't have enough specific information",
                        "Let me search", "for more information"
                    ]):
                        logger.info(f"Skipping incomplete AI message: {repr(content[:50])}")
                        continue
                
                # Skip consecutive AIMessages (keep only the last one in a sequence)
                if last_msg_type == 'AIMessage':
                    # Replace the previous AIMessage with this one
                    if cleaned_messages and type(cleaned_messages[-1]).__name__ == 'AIMessage':
                        cleaned_messages[-1] = msg
                        logger.info("Replaced consecutive AIMessage with newer one")
                    else:
                        cleaned_messages.append(msg)
                else:
                    cleaned_messages.append(msg)
            
            # Keep HumanMessages and ToolMessages as-is, but avoid consecutive HumanMessages
            elif msg_type == 'HumanMessage':
                if last_msg_type != 'HumanMessage':
                    cleaned_messages.append(msg)
                else:
                    logger.info("Skipping consecutive HumanMessage")
            
            else:
                # ToolMessage and other types
                cleaned_messages.append(msg)
            
            last_msg_type = msg_type
        
        # Final validation: ensure we don't end with consecutive messages of same type
        if len(cleaned_messages) >= 2:
            # Remove trailing incomplete sequences
            if (type(cleaned_messages[-1]).__name__ == type(cleaned_messages[-2]).__name__ and
                type(cleaned_messages[-1]).__name__ in ['AIMessage', 'HumanMessage']):
                cleaned_messages.pop(-2)
                logger.info("Removed consecutive message from end of sequence")
        
        removed_count = len(messages) - len(cleaned_messages)
        if removed_count > 0:
            logger.warning(f"Cleaned conversation history: removed {removed_count} problematic messages")
        
        return cleaned_messages
    
    def _clean_final_response(self, content: str) -> str:
        """
        Clean up final response content to remove leftover coverage guidance, 
        iteration feedback, and other artifacts from failed queries.
        
        BE CAREFUL: Only remove specific problematic patterns, not legitimate content.
        """
        import re
        
        if not isinstance(content, str):
            content = str(content)
        
        # ONLY remove function call artifacts that shouldn't be in user responses
        content = re.sub(r'<function_calls>.*?</function_calls>', '', content, flags=re.DOTALL)
        content = re.sub(r'<invoke.*?</invoke>', '', content, flags=re.DOTALL)
        content = re.sub(r'<function_result>.*?</function_result>', '', content, flags=re.DOTALL)
        
        # Remove standalone coverage guidance messages (but NOT full explanations)
        # Only remove short, standalone guidance messages like:
        # "I've searched documentation but should also check tickets for comprehensive coverage."
        content = re.sub(r'^I\'ve searched [^.]{1,50} but should also check [^.]{1,50} for comprehensive coverage\.\s*$', '', content, flags=re.MULTILINE)
        content = re.sub(r'^Let me search additional source types to provide a complete answer\.\s*$', '', content, flags=re.MULTILINE)
        
        # Clean up multiple newlines and whitespace
        content = re.sub(r'\n\s*\n\s*\n+', '\n\n', content)
        content = content.strip()
        
        return content
    
    def _create_llm(self, llm_provider: str, llm_model: str):
        """Create LLM instance"""
        import os
        
        if llm_provider == "anthropic":
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY not set")
            return ChatAnthropic(
                model=llm_model, 
                temperature=DEFAULT_TEMPERATURE, 
                api_key=api_key,
                timeout=120.0,  # 2 minute timeout per request for complex queries
                max_retries=1,  # Reduce retries from default 2 to 1
                max_tokens=4000  # Limit response length to speed up generation
            )
            
        elif llm_provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY not set")
            return ChatOpenAI(model=llm_model, temperature=DEFAULT_TEMPERATURE, api_key=api_key)
            
        else:
            raise ValueError(f"Unsupported LLM provider: {llm_provider}")
    
    def _create_system_prompt(self, search_tools: List[BaseTool]) -> str:
        """Create system prompt for LLM"""
        # Enhanced tools info that includes parameter descriptions with examples
        tools_info = []
        query_language_guidance = []  # Collect specific guidance for query languages
        
        for tool in search_tools:
            tool_line = f"- {tool.name}: {tool.description}"
            
            # Extract important parameter descriptions that contain examples or syntax guidance
            if hasattr(tool, 'args_schema') and tool.args_schema:
                param_descriptions = []
                if hasattr(tool.args_schema, 'model_fields'):
                    # Pydantic v2
                    for field_name, field_info in tool.args_schema.model_fields.items():
                        if hasattr(field_info, 'description') and field_info.description:
                            desc = field_info.description
                            # Include descriptions that contain examples or important syntax info
                            if any(keyword in desc.lower() for keyword in ['example', 'syntax', 'format', 'language', 'query']):
                                param_descriptions.append(f"  • {field_name}: {desc}")
                                
                                # Detect query language patterns and extract specific guidance
                                self._extract_query_language_guidance(field_name, desc, query_language_guidance)
                                
                elif hasattr(tool.args_schema, '__fields__'):
                    # Pydantic v1
                    for field_name, field_info in tool.args_schema.__fields__.items():
                        if hasattr(field_info, 'field_info') and hasattr(field_info.field_info, 'description'):
                            desc = field_info.field_info.description
                            # Include descriptions that contain examples or important syntax info
                            if any(keyword in desc.lower() for keyword in ['example', 'syntax', 'format', 'language', 'query']):
                                param_descriptions.append(f"  • {field_name}: {desc}")
                                
                                # Detect query language patterns and extract specific guidance
                                self._extract_query_language_guidance(field_name, desc, query_language_guidance)
                
                # Add parameter descriptions if we found any with examples
                if param_descriptions:
                    tool_line += "\n" + "\n".join(param_descriptions)
            
            tools_info.append(tool_line)
        
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
            instructions_section += "\n📊 DATA COUNT REQUIREMENT:\n"
            instructions_section += "When counting items (tickets, documents, etc.), ALWAYS read count fields like 'total', 'count', or 'size' from responses.\n"
            instructions_section += "Individual items may be limited for display, but count fields show the actual totals.\n"
        
        # Build query language specific guidance (NEW ENHANCEMENT)
        query_guidance_section = ""
        if query_language_guidance:
            query_guidance_section = "\n\n🔧 CRITICAL QUERY LANGUAGE REQUIREMENTS:\n"
            for guidance in set(query_language_guidance):  # Remove duplicates
                query_guidance_section += f"• {guidance}\n"
        
        return f"""You are Scintilla, IgniteTech's intelligent knowledge assistant with access to {len(search_tools)} search tools from: {server_context}

CONVERSATION CONTEXT: You maintain conversation context across messages. When users ask follow-up questions, they're building on previous responses. For example:
- User: "What are the open tickets?"
- Assistant: [provides ticket list]
- User: "Is there documentation for these?" ← This refers to the tickets from previous response

🔧 CRITICAL TOOL CALLING PROTOCOL:
If you need more information to answer a question completely, you MUST make tool calls immediately. 
NEVER say "Let me search for more information" or describe your intent to search - just make the tool calls directly.

Your response should either be:
1. **Tool calls** (if you need more information)
2. **Final answer** (if you have sufficient information)

DO NOT mix these - don't provide partial answers followed by statements about searching more.

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
{tools_context}{query_guidance_section}

MULTI-SOURCE SEARCH STRATEGY:
🎯 COMPREHENSIVE COVERAGE REQUIREMENT:
- For status/integration queries: Search tickets AND communications AND documentation
- For technical issues: Search bug reports AND discussions AND knowledge bases  
- For project updates: Search project tools AND email discussions AND documentation
- Continue searching until you have comprehensive coverage across relevant source types

📋 SOURCE TYPE PLANNING:
Before searching, consider which source types are relevant:
- **Technical Status**: Jira/tickets + email discussions + documentation
- **Integration Issues**: Bug reports + support communications + technical docs
- **Project Updates**: Project management tools + team communications + release docs
- **Implementation Details**: Code repositories + technical documentation + design discussions

🔄 ITERATION GUIDELINES:
- Don't stop after finding results from ONE source type
- Search 2-3 complementary sources for comprehensive answers
- Use different tools that cover different information types
- If first search finds tickets, also search communications about those tickets
- If you find technical issues, also look for related discussions or documentation

⚠️ STOPPING CRITERIA:
- Stop only after checking relevant source types OR after 4-5 meaningful searches
- Don't repeat the same search tool with identical parameters
- If sources consistently return empty, then conclude information isn't available

CITATION REQUIREMENTS (only when using tools):
- Cite sources using markdown links [Title](URL) format when referencing information from that source
- Don't add citations to general introductory sentences or summaries
- Only cite when the information comes directly from a specific tool result
- For example: "The ticket [PDR-148554: Bug Report](https://jira.company.com/browse/PDR-148554) has status 'Requested'" NOT "Here are the tickets [1]:"
- Use the exact titles and URLs I provide in the citation guidance
- Focus on citation accuracy - only reference sources that directly support your statements
- Do NOT add your own <SOURCES> section - I will handle the sources list automatically

CAPABILITY RESPONSE (when asked what you can do):
"I have access to {len(search_tools)} search tools from {len(self.loaded_sources)} knowledge sources. I can help you find information about technical documentation, code repositories, project details, and more. Just ask me specific questions about topics you're interested in!"

Be intelligent about tool usage - search when information is needed, respond directly when appropriate.{instructions_section}"""
    
    def _analyze_query_for_source_types(self, query: str, available_tools: List[BaseTool]) -> Dict[str, List[str]]:
        """
        Analyze the query to suggest which source types should be searched for comprehensive coverage
        Returns mapping of source types to relevant tool names
        """
        query_lower = query.lower()
        
        # Classify available tools by source type
        tool_types = {
            "tickets": [],      # Jira, GitHub issues, etc.
            "communications": [], # Gmail, Slack, Teams, etc.  
            "documentation": [], # Confluence, wikis, etc.
            "code": [],         # GitHub, GitLab repositories
            "files": []         # File systems, document stores
        }
        
        # Categorize available tools
        for tool in available_tools:
            tool_name_lower = tool.name.lower()
            
            if any(keyword in tool_name_lower for keyword in ['jira', 'github', 'ticket', 'issue', 'bug']):
                tool_types["tickets"].append(tool.name)
            elif any(keyword in tool_name_lower for keyword in ['gmail', 'email', 'slack', 'teams', 'chat']):
                tool_types["communications"].append(tool.name)
            elif any(keyword in tool_name_lower for keyword in ['confluence', 'wiki', 'documentation', 'docs']):
                tool_types["documentation"].append(tool.name)
            elif any(keyword in tool_name_lower for keyword in ['github', 'gitlab', 'git', 'repository', 'code']):
                tool_types["code"].append(tool.name)
            elif any(keyword in tool_name_lower for keyword in ['file', 'document', 'storage']):
                tool_types["files"].append(tool.name)
        
        # Analyze query patterns to suggest relevant source types
        suggested_types = []
        
        # Status/integration queries benefit from multiple sources
        if any(keyword in query_lower for keyword in ['status', 'integration', 'progress', 'update', 'current']):
            suggested_types.extend(["tickets", "communications", "documentation"])
        
        # Technical issue queries
        elif any(keyword in query_lower for keyword in ['error', 'bug', 'issue', 'problem', 'failure', 'not working']):
            suggested_types.extend(["tickets", "communications", "documentation"])
        
        # Implementation/how-to queries
        elif any(keyword in query_lower for keyword in ['how', 'implement', 'setup', 'configure', 'install']):
            suggested_types.extend(["documentation", "code", "communications"])
        
        # Project/planning queries
        elif any(keyword in query_lower for keyword in ['project', 'plan', 'roadmap', 'timeline', 'milestone']):
            suggested_types.extend(["tickets", "communications", "documentation"])
        
        # Default: suggest tickets and documentation as baseline
        if not suggested_types:
            suggested_types = ["tickets", "documentation"]
        
        # Filter to only include types that have available tools
        relevant_sources = {}
        for source_type in suggested_types:
            if tool_types[source_type]:  # Only include if we have tools for this type
                relevant_sources[source_type] = tool_types[source_type]
        
        logger.info("Query analysis for multi-source search", 
                   query_keywords=[word for word in query_lower.split() if len(word) > 3],
                   suggested_source_types=list(relevant_sources.keys()),
                   available_tools_by_type={k: len(v) for k, v in tool_types.items() if v})
        
        return relevant_sources

    def _extract_query_language_guidance(self, field_name: str, description: str, guidance_list: List[str]) -> None:
        """Extract specific query language guidance from parameter descriptions"""
        desc_lower = description.lower()
        field_lower = field_name.lower()
        
        # Detect JQL (Jira Query Language) patterns - more permissive detection
        if 'jql' in field_lower or 'jira query language' in desc_lower:
            # Always add JQL guidance when we detect JQL, regardless of ORDER BY mention
            guidance_list.append("JQL (Jira Query Language) requires search criteria before ORDER BY clauses. Use 'project IS NOT EMPTY ORDER BY created DESC' for all tickets, never just 'ORDER BY created DESC'. For recent items, use 'updated >= -1d ORDER BY updated DESC' or 'created >= -1d ORDER BY created DESC'.")
        
        # Detect SQL patterns
        elif ('sql' in field_lower or 'sql query' in desc_lower) and ('select' in desc_lower or 'from' in desc_lower):
            guidance_list.append("SQL queries must include SELECT and FROM clauses. Follow the provided examples exactly")
        
        # Detect GraphQL patterns
        elif 'graphql' in desc_lower and '{' in description:
            guidance_list.append("GraphQL queries must be properly formatted with curly braces and field selections as shown in examples")
        
        # Generic query language detection for anything with examples and ORDER BY
        elif 'query' in field_lower and 'order by' in desc_lower and 'example' in desc_lower:
            guidance_list.append("Query language syntax requires search criteria before ORDER BY clauses. Always include search conditions as shown in the examples")
    
    def _parse_invoke_syntax(self, content: str) -> List[Dict]:
        """
        Parse text-based <invoke> syntax into LangChain tool call format
        Handles cases where LLM generates <invoke name="tool"><parameter name="param">value</parameter></invoke>
        """
        import re
        import uuid
        
        tool_calls = []
        
        # Find all <invoke> blocks
        invoke_pattern = r'<invoke name="([^"]+)">(.*?)</invoke>'
        
        for match in re.finditer(invoke_pattern, content, re.DOTALL):
            tool_name = match.group(1)
            params_content = match.group(2)
            
            # Parse parameters from <parameter> tags
            param_pattern = r'<parameter name="([^"]+)">(.*?)</parameter>'
            arguments = {}
            
            for param_match in re.finditer(param_pattern, params_content, re.DOTALL):
                param_name = param_match.group(1)
                param_value = param_match.group(2).strip()
                arguments[param_name] = param_value
            
            # Create tool call in LangChain format
            tool_call = {
                'name': tool_name,
                'args': arguments,
                'id': str(uuid.uuid4())  # Generate unique ID
            }
            
            tool_calls.append(tool_call)
            logger.info(f"📝 Parsed tool call from <invoke> syntax: {tool_name} with {arguments}")
        
        return tool_calls
    
    def _generate_performance_summary(self, timings: Dict) -> str:
        """Generate a formatted performance summary table"""
        
        # Calculate totals and averages
        total_duration = timings["total_duration"]
        total_tool_calls = len(timings["total_tool_calls"])
        total_iterations = len(timings["iterations"])
        
        # Calculate tool call statistics
        tool_call_durations = [t["duration"] for t in timings["total_tool_calls"]]
        avg_tool_call = sum(tool_call_durations) / len(tool_call_durations) if tool_call_durations else 0
        total_tool_time = sum(tool_call_durations)
        
        # Calculate LLM call statistics
        llm_call_durations = [t["duration"] for t in timings["llm_calls"]]
        avg_llm_call = sum(llm_call_durations) / len(llm_call_durations) if llm_call_durations else 0
        total_llm_time = sum(llm_call_durations)
        
        # Calculate iteration statistics
        iteration_durations = [t["duration"] for t in timings["iterations"]]
        avg_iteration = sum(iteration_durations) / len(iteration_durations) if iteration_durations else 0
        
        # Calculate context optimization statistics
        context_opt_durations = [t["duration"] for t in timings["context_optimization"]]
        total_context_opt_time = sum(context_opt_durations)
        
        # Build the summary table
        summary_lines = [
            "🚀 PERFORMANCE BREAKDOWN",
            "=" * 60,
            f"📊 OVERVIEW",
            f"  Total Duration:        {total_duration:.3f}s",
            f"  Total Iterations:      {total_iterations}",
            f"  Total Tool Calls:      {total_tool_calls}",
            "",
            f"⏱️  TIMING BREAKDOWN",
            f"  Preprocessing:         {timings['preprocessing']['duration']:.3f}s ({(timings['preprocessing']['duration']/total_duration*100):.1f}%)",
            f"  Tool Setup:           {timings['tool_setup']['duration']:.3f}s ({(timings['tool_setup']['duration']/total_duration*100):.1f}%)",
            f"  Conversation Loading:  {timings['conversation_loading']['duration']:.3f}s ({(timings['conversation_loading']['duration']/total_duration*100):.1f}%)",
            f"  Context Optimization:  {total_context_opt_time:.3f}s ({(total_context_opt_time/total_duration*100):.1f}%)",
            f"  LLM Calls (Total):     {total_llm_time:.3f}s ({(total_llm_time/total_duration*100):.1f}%)",
            f"  Tool Execution:        {total_tool_time:.3f}s ({(total_tool_time/total_duration*100):.1f}%)",
            f"  Citation Building:     {timings['citation_building']['duration']:.3f}s ({(timings['citation_building']['duration']/total_duration*100):.1f}%)",
            f"  Final Processing:      {timings['final_processing']['duration']:.3f}s ({(timings['final_processing']['duration']/total_duration*100):.1f}%)",
            "",
            f"📈 AVERAGES",
            f"  Average Iteration:     {avg_iteration:.3f}s",
            f"  Average LLM Call:      {avg_llm_call:.3f}s",
            f"  Average Tool Call:     {avg_tool_call:.3f}s",
            "",
            f"🔧 TOOL CALLS DETAIL"
        ]
        
        # Add individual tool call details
        for i, tool_call in enumerate(timings["total_tool_calls"]):
            tool_name = tool_call["tool_name"].replace("ignitetech___atlassian_", "")  # Shorten names
            summary_lines.append(f"  {i+1}. {tool_name}: {tool_call['duration']:.3f}s (iteration {tool_call['iteration']})")
        
        if timings["llm_calls"]:
            summary_lines.extend([
                "",
                f"🤖 LLM CALLS DETAIL"
            ])
            
            for i, llm_call in enumerate(timings["llm_calls"]):
                call_type = llm_call["type"]
                iteration = llm_call["iteration"]
                model_info = f" [{llm_call.get('model', 'unknown')}]" if llm_call.get('model') else ""
                summary_lines.append(f"  {i+1}. {call_type}: {llm_call['duration']:.3f}s (iteration {iteration}){model_info}")
        
        summary_lines.extend([
            "",
            f"🎯 PERFORMANCE INSIGHTS",
            f"  Tool/LLM Ratio:        {(total_tool_time/total_llm_time):.2f}:1" if total_llm_time > 0 else "  Tool/LLM Ratio:        N/A",
            f"  Processing Efficiency: {((total_tool_time + total_llm_time)/total_duration*100):.1f}% (core work vs overhead)",
            "=" * 60
        ])
        
        return "\n".join(summary_lines)
    
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
        
        # Performance timing collection
        timings = {
            "query_start": query_start,
            "preprocessing": {"start": 0, "end": 0, "duration": 0},
            "tool_setup": {"start": 0, "end": 0, "duration": 0},
            "conversation_loading": {"start": 0, "end": 0, "duration": 0},
            "iterations": [],  # List of iteration timings
            "total_tool_calls": [],  # Individual tool call timings
            "context_optimization": [],  # Context optimization timings
            "llm_calls": [],  # LLM call timings
            "citation_building": {"start": 0, "end": 0, "duration": 0},
            "final_processing": {"start": 0, "end": 0, "duration": 0},
            "query_end": 0,
            "total_duration": 0
        }
        
        # Validate tools available
        timings["tool_setup"]["start"] = time.time()
        if not self.tools:
            yield {"type": "error", "error": "No tools available. Configure sources first."}
            return
        
        search_tools = self.filter_search_tools()
        if not search_tools:
            yield {"type": "error", "error": "No search tools available"}
            return
        timings["tool_setup"]["end"] = time.time()
        timings["tool_setup"]["duration"] = timings["tool_setup"]["end"] - timings["tool_setup"]["start"]
        
        try:
            # PREPROCESS QUERY: Incorporate bot instructions into the query itself
            timings["preprocessing"]["start"] = time.time()
            original_message = message
            logger.info("🚀 Starting query processing", original_message=original_message)
            
            message = await self._preprocess_query_with_instructions(message)
            
            timings["preprocessing"]["end"] = time.time()
            timings["preprocessing"]["duration"] = timings["preprocessing"]["end"] - timings["preprocessing"]["start"]
            
            if message != original_message:
                logger.info("🔄 Query was modified by preprocessing", 
                           original=original_message, 
                           modified=message)
                yield {
                    "type": "query_preprocessed",
                    "original_query": original_message,
                    "modified_query": message
                }
            else:
                logger.info("➡️ Query unchanged by preprocessing", query=message)
            
            # Initialize components
            llm = self._create_llm(llm_provider, llm_model)
            llm_with_tools = llm.bind_tools(search_tools)
            
            # Initialize context manager for this query
            self.context_manager = ContextManager(llm_model)
            
            # Analyze query to suggest relevant source types
            suggested_sources = self._analyze_query_for_source_types(message, search_tools)
            
            # Create system prompt
            system_prompt = self._create_system_prompt(search_tools)
            
            # Build comprehensive search guidance
            search_guidance = f"Searching {len(search_tools)} tools from {len(self.loaded_sources)} sources"
            
            if suggested_sources:
                source_types = list(suggested_sources.keys())
                search_guidance += f"\n🎯 Comprehensive coverage needed: {', '.join(source_types)}"
                
                # Add specific tool suggestions
                for source_type, tools in suggested_sources.items():
                    search_guidance += f"\n  • {source_type.title()}: {tools[0]}" + (f" (and {len(tools)-1} more)" if len(tools) > 1 else "")
            
            yield {
                "type": "thinking", 
                "content": search_guidance
            }
            
            # Setup conversation with context management
            conversation_history = []
            
            # Add conversation history
            timings["conversation_loading"]["start"] = time.time()
            if conversation_id and db_session:
                loaded_history = await self.load_conversation_history(db_session, conversation_id)
                # Additional cleanup: for new queries, limit how much old history we include
                # This prevents mixing of old failed attempts with new queries
                if loaded_history:
                    # Check for signs of conversation corruption (too many orphaned tool results)
                    validated_messages = self._validate_message_sequence_for_claude(loaded_history)
                    removed_count = len(loaded_history) - len(validated_messages)
                    
                    if removed_count > 5:  # If we had to remove more than 5 orphaned messages
                        logger.warning(f"Detected corrupted conversation history with {removed_count} orphaned tool results - starting fresh")
                        conversation_history = []  # Start fresh to prevent further corruption
                    else:
                        # Only keep the most recent 4 messages (2 conversation turns) to prevent confusion
                        conversation_history = validated_messages[-4:] if len(validated_messages) > 4 else validated_messages
                        logger.info(f"Limited conversation history from {len(loaded_history)} to {len(conversation_history)} messages for clarity")
            timings["conversation_loading"]["end"] = time.time()
            timings["conversation_loading"]["duration"] = timings["conversation_loading"]["end"] - timings["conversation_loading"]["start"]
            
            # Execute conversation loop
            tools_called = []
            all_tool_metadata = []  # Collect all metadata across iterations
            iteration = 0
            tool_results_str = []  # Collect tool results for context management
            
            # Track source type coverage for multi-source search encouragement
            source_types_searched = set()
            suggested_source_types = set(suggested_sources.keys()) if suggested_sources else set()
            
            # Create a faster model for tool calling if enabled and using slow model
            fast_llm_with_tools = None
            from src.config import settings
            
            if (settings.enable_fast_tool_calling and 
                llm_model == "claude-sonnet-4-20250514" and 
                settings.fast_tool_calling_model != llm_model):
                logger.info(f"🚀 Using {settings.fast_tool_calling_model} for faster tool calling iterations")
                fast_llm = self._create_llm(llm_provider, settings.fast_tool_calling_model)
                fast_llm_with_tools = fast_llm.bind_tools(search_tools)
            
            while iteration < MAX_TOOL_ITERATIONS:
                iteration += 1
                iteration_start = time.time()
                
                # Optimize context before each LLM call (but NOT citation context yet)
                context_opt_start = time.time()
                optimized_history, optimized_tool_results, _ = self.context_manager.optimize_context(
                    system_prompt=system_prompt,
                    conversation_history=conversation_history,
                    current_message=message,
                    tool_results=tool_results_str,
                    citation_context=""  # Don't add citation context during tool iterations
                )
                context_opt_end = time.time()
                timings["context_optimization"].append({
                    "iteration": iteration,
                    "duration": context_opt_end - context_opt_start
                })
                
                # Build messages for this iteration
                messages = [SystemMessage(content=system_prompt)]
                
                # Filter out any SystemMessage objects from history to avoid multiple system messages
                filtered_history = [msg for msg in optimized_history if not isinstance(msg, SystemMessage)]
                messages.extend(filtered_history)
                messages.append(HumanMessage(content=message))
                
                # CRITICAL: Validate message sequence to prevent tool_use_id mismatches
                messages = self._validate_message_sequence_for_claude(messages)
                
                # Log context usage
                estimated_tokens = self.context_manager.estimate_current_context(
                    system_prompt=system_prompt,
                    conversation_history=optimized_history,
                    current_message=message,
                    tool_results=optimized_tool_results,
                    citation_context=""
                )
                logger.info(f"Context usage: ~{estimated_tokens} tokens (iteration {iteration})")
                
                # Get LLM response - use faster model for tool calling if available
                llm_call_start = time.time()
                current_llm_with_tools = fast_llm_with_tools if fast_llm_with_tools else llm_with_tools
                model_used = settings.fast_tool_calling_model if fast_llm_with_tools else llm_model
                logger.info(f"🧠 Using model: {model_used} for iteration {iteration}")
                response = await current_llm_with_tools.ainvoke(messages)
                llm_call_end = time.time()
                timings["llm_calls"].append({
                    "iteration": iteration,
                    "duration": llm_call_end - llm_call_start,
                    "type": "tool_calling",
                    "model": model_used
                })
                
                # Check for tool calls (both structured and text-based formats)
                tool_calls_to_execute = []
                
                if hasattr(response, 'tool_calls') and response.tool_calls:
                    # Standard LangChain tool calls
                    tool_calls_to_execute = response.tool_calls
                elif response.content and isinstance(response.content, str) and '<invoke' in response.content:
                    # Fallback: Parse text-based tool invocation syntax
                    logger.warning("⚠️ LLM used text-based tool calling - parsing <invoke> syntax")
                    tool_calls_to_execute = self._parse_invoke_syntax(response.content)
                    
                    # Clean up the response content by removing <invoke> blocks
                    import re
                    cleaned_content = re.sub(r'<invoke name="[^"]+">.*?</invoke>', '', response.content, flags=re.DOTALL)
                    response.content = cleaned_content.strip()
                
                if tool_calls_to_execute:
                    # Stream tool call notifications
                    for tool_call in tool_calls_to_execute:
                        logger.info("🔧 Tool call initiated", 
                                   tool_name=tool_call['name'], 
                                   arguments=tool_call['args'])
                        yield {
                            "type": "tool_call",
                            "tool_name": tool_call['name'],
                            "arguments": tool_call['args'],
                            "status": "running"
                        }
                    
                    # Execute tools and get results with metadata
                    tools_exec_start = time.time()
                    tool_results, call_results, tool_metadata = await self._execute_tool_calls(
                        tool_calls_to_execute, message
                    )
                    tools_exec_end = time.time()
                    
                    # Record individual tool call timings
                    for i, tool_call in enumerate(tool_calls_to_execute):
                        timings["total_tool_calls"].append({
                            "iteration": iteration,
                            "tool_name": tool_call['name'],
                            "duration": tools_exec_end - tools_exec_start,  # We'll improve this later for individual tools
                            "args": tool_call['args']
                        })
                    
                    # Store metadata for final citation processing
                    all_tool_metadata.extend(tool_metadata)
                    
                    # Track source types that have been searched
                    for tool_call in tool_calls_to_execute:
                        tool_name = tool_call['name'].lower()
                        if any(keyword in tool_name for keyword in ['jira', 'github', 'ticket', 'issue', 'bug']):
                            source_types_searched.add("tickets")
                        elif any(keyword in tool_name for keyword in ['gmail', 'email', 'slack', 'teams', 'chat']):
                            source_types_searched.add("communications")
                        elif any(keyword in tool_name for keyword in ['confluence', 'wiki', 'documentation', 'docs']):
                            source_types_searched.add("documentation")
                        elif any(keyword in tool_name for keyword in ['github', 'gitlab', 'git', 'repository', 'code']):
                            source_types_searched.add("code")
                        elif any(keyword in tool_name for keyword in ['file', 'document', 'storage']):
                            source_types_searched.add("files")
                    
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
                    # Ensure response content is a string
                    content_str = ""
                    if response.content:
                        content_str = response.content if isinstance(response.content, str) else str(response.content)
                    conversation_history.append(AIMessage(content=content_str, tool_calls=tool_calls_to_execute))
                    conversation_history.extend(tool_results)
                    
                    # Record iteration timing
                    iteration_end = time.time()
                    timings["iterations"].append({
                        "iteration": iteration,
                        "duration": iteration_end - iteration_start,
                        "tool_calls": len(tool_calls_to_execute)
                    })
                    
                    continue
                else:
                    # No tool calls - check multi-source coverage
                    unsearched_types = suggested_source_types - source_types_searched
                    
                    # Check if we already provided coverage guidance in a recent iteration
                    recent_coverage_guidance = False
                    for timing in timings["iterations"][-2:]:  # Check last 2 iterations
                        if timing.get("coverage_guidance"):
                            recent_coverage_guidance = True
                            break
                    
                    # Only provide coverage guidance if:
                    # 1. We have unsearched types
                    # 2. We haven't exceeded iteration limit for coverage checks
                    # 3. We haven't already provided coverage guidance recently
                    if (unsearched_types and 
                        iteration < 6 and  # Reduce from 8 to 6 to avoid excessive iterations
                        not recent_coverage_guidance):  # Don't repeat coverage guidance
                        
                        logger.info(f"🔍 Multi-source coverage check: {len(source_types_searched)} searched, {len(unsearched_types)} remaining",
                                   searched=list(source_types_searched),
                                   remaining=list(unsearched_types))
                        
                        # Add a guidance message to conversation to encourage more searching
                        coverage_guidance = f"""I've searched {list(source_types_searched)} but should also check {list(unsearched_types)} for comprehensive coverage. Let me search additional source types to provide a complete answer."""
                        
                        conversation_history.append(AIMessage(content=coverage_guidance))
                        
                        # Record iteration timing and continue
                        iteration_end = time.time()
                        timings["iterations"].append({
                            "iteration": iteration,
                            "duration": iteration_end - iteration_start,
                            "tool_calls": 0,
                            "coverage_guidance": True
                        })
                        continue
                    else:
                        # Sufficient coverage, reached iteration limit, or already provided guidance - prepare for final response
                        if recent_coverage_guidance:
                            logger.info(f"🚫 Skipping coverage guidance - already provided in recent iteration")
                        
                        logger.info(f"✅ Multi-source search complete",
                                   searched_types=list(source_types_searched),
                                   suggested_types=list(suggested_source_types),
                                   coverage_complete=len(unsearched_types) == 0,
                                   recent_guidance_provided=recent_coverage_guidance)
                        
                        # Add the LLM's response to conversation history before final response
                        if response.content:
                            # Ensure content is a string before adding to conversation
                            content_str = response.content if isinstance(response.content, str) else str(response.content)
                            conversation_history.append(AIMessage(content=content_str))
                        
                        # Record final iteration timing (no tools called)
                        iteration_end = time.time()
                        timings["iterations"].append({
                            "iteration": iteration,
                            "duration": iteration_end - iteration_start,
                            "tool_calls": 0
                        })
                        break
            
            # FINAL RESPONSE GENERATION WITH CITATIONS
            # Now we have all tool results and metadata - generate final response with proper citations
            
            # Build citation guidance from collected metadata
            timings["citation_building"]["start"] = time.time()
            citation_guidance = self._build_citation_guidance(all_tool_metadata)
            timings["citation_building"]["end"] = time.time()
            timings["citation_building"]["duration"] = timings["citation_building"]["end"] - timings["citation_building"]["start"]
            
            # Create final prompt with citation guidance - use conversation history instead of recreating tool results
            final_messages = [SystemMessage(content=system_prompt)]
            
            # Filter and clean conversation history to ensure proper Human/AI alternation
            filtered_history = [msg for msg in optimized_history if not isinstance(msg, SystemMessage)]
            
            # Clean up conversation history - remove incomplete AI messages and fix alternation
            cleaned_history = self._clean_conversation_sequence(filtered_history)
            final_messages.extend(cleaned_history)
            
            # Combine user message with citation guidance in a single HumanMessage
            user_content = message
            if citation_guidance:
                user_content += f"""

Available sources for citations:

{citation_guidance}

IMPORTANT: Use markdown links exactly as shown above when citing these sources. Format: [Title](URL)"""
            
            final_messages.append(HumanMessage(content=user_content))
            
            # CRITICAL: Validate final message sequence to prevent tool_use_id mismatches
            final_messages = self._validate_message_sequence_for_claude(final_messages)
            
            # Get final response with proper citations (with timeout handling)
            # DEBUG: Log what's being sent to final LLM call
            logger.info(f"🔍 FINAL LLM CALL DEBUG - Message count: {len(final_messages)}")
            for i, msg in enumerate(final_messages):
                msg_type = type(msg).__name__
                content_preview = str(msg.content)[:100] if hasattr(msg, 'content') else "no content"
                logger.info(f"  Message {i}: {msg_type} - {repr(content_preview)}")
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    logger.info(f"    Tool calls: {len(msg.tool_calls)}")
                if hasattr(msg, 'tool_call_id'):
                    logger.info(f"    Tool call ID: {msg.tool_call_id}")
            
            final_llm_start = time.time()
            try:
                final_response = await llm.ainvoke(final_messages)
                final_llm_end = time.time()
                timings["llm_calls"].append({
                    "iteration": "final",
                    "duration": final_llm_end - final_llm_start,
                    "type": "final_response",
                    "model": llm_model  # Use original model for final response
                })
                # Ensure final_content is a string to avoid regex errors
                if isinstance(final_response.content, str):
                    final_content = final_response.content
                elif isinstance(final_response.content, list):
                    # Handle structured content - join if it's a list
                    final_content = "\n".join(str(item) for item in final_response.content)
                else:
                    final_content = str(final_response.content)
                
                # TEMPORARILY DISABLE CLEANUP TO DEBUG EMPTY CONTENT ISSUE
                # final_content = self._clean_final_response(final_content)
            except asyncio.TimeoutError:
                # Handle timeout gracefully with a fallback response
                final_llm_end = time.time()
                timings["llm_calls"].append({
                    "iteration": "final",
                    "duration": final_llm_end - final_llm_start,
                    "type": "final_response_timeout",
                    "model": llm_model,
                    "error": "timeout"
                })
                
                # Generate a fallback response based on tool results
                if tools_called:
                    tool_summary = f"I used {len(tools_called)} tools and found relevant information, but the final response generation timed out. "
                    
                    # Extract key information from recent tool calls
                    recent_results = []
                    for tool_call in tools_called[-2:]:  # Last 2 tool calls
                        result = tool_call.get('result', '')
                        if result and len(result) > 20:
                            preview = result[:200].replace('\n', ' ')
                            if len(result) > 200:
                                preview += "..."
                            recent_results.append(f"• {preview}")
                    
                    if recent_results:
                        final_content = tool_summary + "Here's what I found:\n\n" + "\n".join(recent_results)
                    else:
                        final_content = tool_summary + "Please try rephrasing your question or asking something more specific."
                else:
                    final_content = "I encountered a timeout while generating the response. Please try rephrasing your question."
                
                logger.warning("Final LLM response timed out, using fallback response", 
                              tools_used=len(tools_called), 
                              timeout_duration=final_llm_end - final_llm_start)
            
            # Process final response with citations
            timings["final_processing"]["start"] = time.time()
            if iteration >= MAX_TOOL_ITERATIONS:
                # Analyze tool results to provide better feedback
                empty_results_count = 0
                tool_attempts = {}
                
                for tool_call in tools_called:
                    tool_name = tool_call.get('tool', 'unknown')
                    tool_attempts[tool_name] = tool_attempts.get(tool_name, 0) + 1
                    
                    # Check if result appears to be empty
                    result = tool_call.get('result', '')
                    if ('[]' in result or '"issues": []' in result or 
                        '"total": 0' in result or '"total": -1' in result or
                        len(result.strip()) < 50):
                        empty_results_count += 1
                
                # Provide better feedback based on what happened
                if empty_results_count >= iteration * 0.7:  # 70%+ empty results
                    iteration_feedback = f"I searched extensively but couldn't find results matching your query. I tried {iteration} different search approaches, but most returned empty results. This might mean:\n\n• The information doesn't exist in the connected sources\n• The search terms need to be more specific\n• Different sources might have the information you're looking for\n\nHere's what I found with the available data:\n\n"
                elif len(tool_attempts) == 1:  # Repeated same tool
                    tool_name = list(tool_attempts.keys())[0]
                    iteration_feedback = f"I tried the same search tool ({tool_name}) {iteration} times with different parameters but reached the iteration limit. Here's the best result I found:\n\n"
                else:
                    iteration_feedback = f"I reached the maximum number of search iterations ({iteration} attempts across {len(tool_attempts)} different tools). Here's what I found:\n\n"
                
                final_content = iteration_feedback + final_content
            
            # Remove any <SOURCES> sections the LLM might have added
            import re
            if isinstance(final_content, str):
                final_content = re.sub(r'<SOURCES>.*?</SOURCES>', '', final_content, flags=re.DOTALL).strip()
            elif isinstance(final_content, list):
                # Handle case where final_content is a list of content blocks
                final_content = str(final_content)
                final_content = re.sub(r'<SOURCES>.*?</SOURCES>', '', final_content, flags=re.DOTALL).strip()
            else:
                # Ensure it's a string
                final_content = str(final_content)
            
            # No validation step needed - let the LLM respond naturally
            
            # SKIP post-processing clickable links - we want markdown links [Title](URL) to be preserved as-is
            # final_content = self._create_clickable_links(final_content, all_tool_metadata)
            
            # Build sources list from metadata using simple format
            sources = self._build_sources_from_metadata_simple(all_tool_metadata, final_content)
            timings["final_processing"]["end"] = time.time()
            timings["final_processing"]["duration"] = timings["final_processing"]["end"] - timings["final_processing"]["start"]
            
            # Generate processing stats including context management info
            total_tools_called = len(tools_called)
            
            # Finalize timing data
            timings["query_end"] = time.time()
            timings["total_duration"] = timings["query_end"] - timings["query_start"]
            
            # Generate performance summary table
            performance_summary = self._generate_performance_summary(timings)
            
            # Yield performance data as debug info
            yield {
                "type": "performance_debug",
                "performance_summary": performance_summary,
                "raw_timings": timings
            }
            
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
                    "conversation_messages_total": len(conversation_history) if conversation_history else 0,
                    "performance_breakdown": performance_summary,
                    "multi_source_coverage": {
                        "suggested_source_types": list(suggested_source_types) if suggested_source_types else [],
                        "searched_source_types": list(source_types_searched),
                        "coverage_complete": len(suggested_source_types - source_types_searched) == 0 if suggested_source_types else True,
                        "coverage_percentage": int((len(source_types_searched) / len(suggested_source_types)) * 100) if suggested_source_types else 100
                    }
                }
            }
            
            logger.info("FastMCPAgent query completed successfully with flexible citation system")
            
        except Exception as e:
            logger.exception("Query execution failed")
            
            # Generate performance data even on error
            timings["query_end"] = time.time()
            timings["total_duration"] = timings["query_end"] - timings["query_start"]
            performance_summary = self._generate_performance_summary(timings)
            
            yield {
                "type": "performance_debug",
                "performance_summary": performance_summary,
                "raw_timings": timings,
                "error": True
            }
            
            yield {
                "type": "error", 
                "error": f"Query failed: {str(e)}",
                "details": str(e),
                "multi_source_coverage": {
                    "suggested_source_types": list(suggested_source_types) if 'suggested_source_types' in locals() and suggested_source_types else [],
                    "searched_source_types": list(source_types_searched) if 'source_types_searched' in locals() else [],
                    "coverage_complete": False,
                    "coverage_percentage": 0
                }
            }
    
    def _build_citation_guidance(self, tool_metadata: List[Dict]) -> str:
        """Build citation guidance from tool metadata for the final LLM call"""
        if not tool_metadata:
            return ""
        
        # NEW: Build markdown link guidance instead of numbered citations
        return self._build_markdown_link_guidance(tool_metadata)
    
    def _build_markdown_link_guidance(self, tool_metadata: List[Dict]) -> str:
        """Build simple markdown link guidance"""
        if not tool_metadata:
            return ""
        
        guidance_lines = []
        
        for meta in tool_metadata:
            metadata = meta['metadata']
            
            # Skip if no useful information
            if not any([metadata.get('urls'), metadata.get('titles'), metadata.get('identifiers')]):
                continue
            
            # Special handling for Jira results with multiple tickets
            if (metadata.get('source_type') == 'jira' and 
                metadata.get('identifiers', {}).get('tickets') and
                len(metadata.get('urls', [])) > 1):
                
                # Create separate guidance for each ticket
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
                    
                    if ticket_url:
                        guidance_lines.append(f"- [{ticket_title}]({ticket_url})")
            else:
                # Standard single-source handling
                if metadata.get('urls') and metadata.get('titles'):
                    title = metadata['titles'][0]
                    url = metadata['urls'][0]
                    guidance_lines.append(f"- [{title}]({url})")
        
        return "\n".join(guidance_lines)
    
    def _build_sources_from_metadata(self, tool_metadata: List[Dict], final_content: str) -> List[Dict]:
        """Build sources list from tool metadata, filtered by what's actually cited"""
        import re
        
        # Find all citation references in the final content
        citation_pattern = r'\[(\d+)\]'
        referenced_citations = set()
        
        # Ensure final_content is a string
        if not isinstance(final_content, str):
            final_content = str(final_content)
            
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

    def _build_sources_from_metadata_simple(self, tool_metadata: List[Dict], final_content: str) -> List[Dict]:
        """Build simple sources list from tool metadata for markdown links"""
        import re
        
        # Find all markdown links in the final content
        # Use non-greedy match to handle titles with nested brackets like [Title with [brackets]]
        markdown_pattern = r'\[(.*?)\]\(([^)]+)\)'
        referenced_sources = {}
        
        # Ensure final_content is a string
        if not isinstance(final_content, str):
            final_content = str(final_content)
        
        for match in re.finditer(markdown_pattern, final_content):
            title = match.group(1)
            url = match.group(2)
            referenced_sources[title] = url
        
        sources = []
        
        for meta in tool_metadata:
            metadata = meta['metadata']
            
            # Skip if no useful information
            if not any([metadata.get('urls'), metadata.get('titles'), metadata.get('identifiers')]):
                continue
            
            # Special handling for Jira results with multiple tickets
            if (metadata.get('source_type') == 'jira' and 
                metadata.get('identifiers', {}).get('tickets') and
                len(metadata.get('urls', [])) > 1):
                
                # Create separate source entry for each ticket
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
                    
                    # Check if this source is referenced in the content (flexible matching)
                    is_referenced = False
                    for ref_title, ref_url in referenced_sources.items():
                        if (ticket_title == ref_title or  # Exact title match
                            ticket in ref_title or  # Ticket ID in referenced title
                            (ticket_url and ticket_url == ref_url)):  # URL match
                            is_referenced = True
                            break
                    
                    if is_referenced and ticket_url:
                        # Avoid duplicates by checking if URL already exists
                        if not any(s.get("url") == ticket_url for s in sources):
                            sources.append({
                                "title": ticket_title,
                                "url": ticket_url
                            })
            else:
                # Standard single-source handling
                if metadata.get('urls') and metadata.get('titles'):
                    title = metadata['titles'][0]
                    url = metadata['urls'][0]
                    
                    # Check if this source is referenced in the content (flexible matching)
                    is_referenced = False
                    for ref_title, ref_url in referenced_sources.items():
                        if (title == ref_title or  # Exact title match
                            url == ref_url):  # URL match
                            is_referenced = True
                            break
                    
                    if is_referenced:
                        # Avoid duplicates by checking if URL already exists
                        if not any(s.get("url") == url for s in sources):
                            sources.append({
                                "title": title,
                                "url": url
                            })
        
        return sources

    async def _validate_and_fix_response(self, llm, final_content, citation_guidance, all_tool_metadata):
        """Use LLM intelligence to validate and fix common issues in responses"""
        validation_prompt = f"""Fix any issues in this response and return ONLY the corrected content without explanations.

ORIGINAL RESPONSE:
{final_content}

AVAILABLE SOURCES FOR MARKDOWN LINKS:
{citation_guidance}

ISSUES TO FIX:
1. Broken or malformed URLs - remove or fix them
2. Missing markdown links - add appropriate [Source Title](URL) links for referenced sources
3. Incorrect URLs or titles - match them to the source information above
4. Redundant or duplicate information
5. Poor formatting or structure

CRITICAL: Return ONLY the corrected response content. Do NOT add sections like "Issues Fixed:", explanations, or meta-commentary about what was changed. Just provide the clean, corrected response with proper markdown links."""

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

    def _generate_context_examples(self, instruction_context: List[str]) -> Dict[str, str]:
        """
        Generate dynamic examples based on actual business context to avoid hardcoded references
        """
        import re  # Move import to top
        
        # Extract project and space names from the actual context
        project_names = []
        space_names = []
        
        for instruction in instruction_context:
            instruction_lower = instruction.lower()
            
            # Look for project patterns
            if 'project' in instruction_lower:
                # Pattern: "use only [PROJECT] project" or "project [PROJECT]"
                project_matches = re.findall(r'(?:use only|project)\s+([A-Z][A-Z0-9]+)(?:\s+project)?', instruction, re.IGNORECASE)
                project_names.extend(project_matches)
            
            # Look for space patterns - improved logic
            if 'space' in instruction_lower:
                # Pattern: "[SPACE_NAME] space" or "in [SPACE_NAME] space"
                space_matches = re.findall(r'(?:in\s+)?([A-Za-z][A-Za-z\s]+?)\s+space', instruction, re.IGNORECASE)
                # Clean up extracted space names (remove common prefixes)
                clean_spaces = []
                for space in space_matches:
                    space = space.strip()
                    # Remove common prefixes that indicate direction rather than name
                    space = re.sub(r'^(search in|in)\s+', '', space, flags=re.IGNORECASE)
                    if len(space) > 2:
                        clean_spaces.append(space)
                space_names.extend(clean_spaces)
        
        # Use actual names if found, otherwise use placeholders
        project_example = project_names[0] if project_names else "[PROJECT_NAME]"
        space_example = space_names[0] if space_names else "[SPACE_NAME]"
        
        # Ensure space example doesn't cause issues in bad examples
        space_key = space_example[:3].upper() if space_example != "[SPACE_NAME]" else "SPC"
        
        # Generate contextual examples
        good_examples = [
            f'- "how many tickets are open?" → "how many tickets are open in the {project_example} project?"',
            f'- "show me recent issues" → "show me recent issues from the {project_example} project"',
            f'- "find documentation" → "find documentation in the {space_example} space"'
        ]
        
        bad_examples = [
            f'- "how many tickets?" → "project = {project_example} AND status = Open" (technical syntax)',
            f'- "recent issues" → "project = {project_example} AND created > -30d" (query language)', 
            f'- "find docs" → "space.key = \'{space_key}\' AND type = page" (technical format)'
        ]
        
        return {
            'good': '\n'.join(good_examples),
            'bad': '\n'.join(bad_examples)
        }

    async def _preprocess_query_with_instructions(self, user_query: str) -> str:
        """
        Preprocess user query to incorporate bot instructions automatically
        Uses a lightweight LLM to intelligently modify the query based on source instructions
        """
        logger.info("🔄 Starting query preprocessing", original_query=user_query)
        
        if not self.source_instructions:
            logger.info("❌ No source instructions found, skipping preprocessing")
            return user_query
        
        # Build instruction context for preprocessing
        instruction_context = []
        for source_name, instructions in self.source_instructions.items():
            if instructions and ('project' in instructions.lower() or 'space' in instructions.lower()):
                instruction_context.append(f"**{source_name}**: {instructions}")
                logger.info("📋 Found relevant instructions", source=source_name, has_project_filter='project' in instructions.lower(), has_space_filter='space' in instructions.lower())
        
        if not instruction_context:
            logger.info("❌ No relevant filtering instructions found (no 'project' or 'space' keywords)")
            return user_query
        
        logger.info("✅ Building preprocessing prompt", instruction_sources=len(instruction_context))
        
        # Extract key terms from business context for dynamic examples  
        context_examples = self._generate_context_examples(instruction_context)
        
        # Create preprocessing prompt - TOOL-AGNOSTIC and NATURAL LANGUAGE focused
        preprocessing_prompt = f"""You are a natural language query enhancer. Add business context to user queries while keeping them conversational and tool-agnostic.

BUSINESS CONTEXT:
{chr(10).join(instruction_context)}

TASK: Enhance the user's query by adding relevant business context mentioned above. Keep it natural and conversational.

EXAMPLES:
✅ GOOD - Add context naturally:
{context_examples['good']}

❌ BAD - Don't use technical syntax:
{context_examples['bad']}

RULES:
- Maximum 2x the length of the original query
- Add business context (project names, space names) in natural language
- Keep it conversational and human-readable
- NEVER use technical syntax, query languages, or tool-specific formats
- If the query already mentions the required context, don't duplicate it
- Return ONLY the enhanced query, NO explanations, NO meta-commentary

USER QUERY: "{user_query}"

ENHANCED QUERY (return only the query, nothing else):"""

        logger.debug("📝 Preprocessing prompt created", prompt_length=len(preprocessing_prompt))

        try:
            # Use a lightweight LLM for preprocessing (faster/cheaper)
            logger.info("🤖 Calling preprocessing LLM (claude-3-5-haiku)")
            preprocessing_llm = self._create_llm("anthropic", "claude-3-5-haiku-20241022")
            
            response = await preprocessing_llm.ainvoke([HumanMessage(content=preprocessing_prompt)])
            modified_query = response.content.strip()
            
            logger.info("📤 LLM response received", 
                       modified_query=modified_query, 
                       original_length=len(user_query), 
                       modified_length=len(modified_query))
            
            # Validation checks
            if len(modified_query) > len(user_query) * 2:  # Prevent runaway responses
                logger.warning("❌ Query preprocessing resulted in overly long query, using original", 
                              original_length=len(user_query),
                              modified_length=len(modified_query),
                              ratio=len(modified_query) / len(user_query),
                              max_allowed_ratio=2.0)
                return user_query
            
            if len(modified_query) < 3:  # Prevent empty responses
                logger.warning("❌ Query preprocessing resulted in too short query, using original")
                return user_query
            
            # Only use modified query if it's meaningfully different
            if modified_query.lower().strip() != user_query.lower().strip():
                logger.info("✅ Query successfully preprocessed", 
                           original_query=user_query, 
                           modified_query=modified_query,
                           change_detected=True)
                return modified_query
            else:
                logger.info("🔄 Query unchanged after preprocessing", 
                           reason="Modified query identical to original")
                return user_query
                
        except Exception as e:
            logger.error("💥 Query preprocessing failed", 
                        error=str(e), 
                        error_type=type(e).__name__,
                        original_query=user_query)
            return user_query
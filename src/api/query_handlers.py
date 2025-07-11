"""
Query Handlers Module

Handles test mode and production mode query processing.
Extracted from query.py to improve maintainability.
"""

import uuid
import asyncio
from typing import AsyncGenerator, List, Optional
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog

from src.api.models import QueryRequest
from src.db.models import Source, SourceShare, BotSourceAssociation
from src.agents.fast_agent import FastMCPAgent
from src.config import TEST_MODE

logger = structlog.get_logger()


class TestModeHandler:
    """Handles test mode queries with mock responses"""
    
    @staticmethod
    async def handle_test_query(
        request: QueryRequest, 
        conversation_id: uuid.UUID,
        conversation_context: List[str] = None
    ) -> AsyncGenerator[dict, None]:
        """Handle test mode query with context-aware mock responses"""
        
        yield {"type": "status", "message": "Running in test mode with mock responses..."}
        
        # Load conversation context
        context_str = ""
        if conversation_context:
            context_str = "\n".join(conversation_context)
            yield {
                "type": "status", 
                "message": f"Loaded {len(conversation_context)} previous messages for context"
            }
        
        # Simulate tool usage
        await asyncio.sleep(0.5)
        yield {
            "type": "tool_call",
            "tool_name": "search_documents",
            "arguments": {"query": request.message[:50]},
            "status": "running"
        }
        
        await asyncio.sleep(1.0)
        
        # Generate context-aware response
        message_lower = request.message.lower()
        context_lower = context_str.lower() if context_str else ""
        
        response, tool_calls = TestModeHandler._generate_mock_response(
            message_lower, context_lower, request.message, context_str
        )
        
        yield {
            "type": "tool_result",
            "tool_name": "search_documents", 
            "result": "Mock search completed",
            "status": "completed"
        }
        
        yield {
            "type": "final_response",
            "content": response,
            "tool_calls": tool_calls,
            "test_mode": True,
            "sources": [],
            "processing_stats": {
                "total_tools_called": 1,
                "query_type": "test_mode",
                "response_time_ms": 1500,
                "sources_found": 0
            }
        }
    
    @staticmethod
    def _generate_mock_response(
        message_lower: str, 
        context_lower: str, 
        original_message: str, 
        context_str: str
    ) -> tuple[str, list]:
        """Generate mock response based on message content and context"""
        
        if "language" in message_lower and ("xinet" in context_lower or "c++" in context_lower):
            response = """Based on our previous discussion about Xinet, here are the programming languages it uses:

**Primary Languages:**
- **C++**: The core Xinet server is written in C++ for high performance
- **Python**: Used for scripting and some backend components  
- **JavaScript**: The web portal (Xinet Portal) uses modern JavaScript frameworks
- **SQL**: MySQL database for data persistence

**Development Tools:**
- Visual Studio for C++ development
- Node.js for the web portal development
- CMake for building the server components
- npm/webpack for frontend asset management

The architecture separates performance-critical server code (C++) from the user interface (JavaScript) for optimal performance and maintainability."""
            
            tool_calls = [{"tool": "get_system_info", "system": "xinet", "info_type": "language"}]
            
        elif "language" in message_lower and ("scintilla" in context_lower or "python" in context_lower):
            response = """Based on our previous discussion about Scintilla, here are the programming languages it uses:

**Backend:**
- **Python**: FastAPI framework for the REST API
- **SQL**: PostgreSQL for database operations

**Frontend:**
- **JavaScript/TypeScript**: React with Vite for the user interface
- **CSS**: Tailwind CSS for styling

**Integration:**
- **Python**: LangChain for AI agent orchestration
- **JSON**: MCP (Model Context Protocol) for tool integration

Scintilla is designed as a modern, async-first application using Python's FastAPI for high-performance backend operations and React for a responsive user interface."""
            
            tool_calls = [{"tool": "get_system_info", "system": "scintilla", "info_type": "language"}]
            
        elif "xinet" in message_lower:
            response = """Based on the documentation search, here's what I found about Xinet:

**Xinet Architecture:**
Xinet follows a traditional client-server architecture. The core server is written in C++ for performance, while the web portal uses modern JavaScript frameworks. The system integrates with MySQL for data persistence and supports various file formats including Adobe Creative Suite files.

**Development Environment:**
Development environment setup requires Visual Studio for C++ components and Node.js for the web portal. The build system uses CMake for the server components and npm/webpack for frontend assets.

**Key Components:**
- Xinet Server (C++)
- Xinet Portal (JavaScript)
- Xinet Pilot
- Adobe Plugins

This information comes from the Xinet Architecture Overview and Development Guide documentation."""
            
            tool_calls = [{"tool": "search_documents", "query": "xinet architecture", "results": 2}]
            
        elif "scintilla" in message_lower:
            response = """Here's what I found about Scintilla:

**Technical Specification:**
Scintilla is built using FastAPI for the backend API, providing async support and automatic OpenAPI documentation. The frontend uses React with Vite for fast development builds. The system integrates with multiple MCP (Model Context Protocol) servers to provide federated search across different knowledge sources.

**Architecture:**
- Backend: Python with FastAPI
- Frontend: React with Vite
- Database: PostgreSQL
- Integration: MCP servers for federated search

**Key Features:**
- Federated search across multiple knowledge sources
- Real-time streaming responses
- Conversation management
- Tool integration via MCP protocol

This is IgniteTech's in-house federated search and chat tool."""
            
            tool_calls = [{"tool": "get_system_info", "system": "scintilla", "info_type": "all"}]
            
        else:
            # Generic response that acknowledges context if available
            context_hint = ""
            if context_str:
                context_hint = f"\n\n*Note: I can see our previous conversation. Feel free to ask follow-up questions!*"
            
            response = f"""I've processed your query: "{original_message}"

In test mode, I can help you with information about:
- **Xinet**: Digital Asset Management system (C++ and Python)
- **Scintilla**: IgniteTech's federated search tool (Python and React)

Try asking about "What is Xinet?" or "Tell me about Scintilla" to see more detailed responses.{context_hint}"""
            
            tool_calls = [{"tool": "general_search", "query": original_message, "mode": "test"}]
        
        return response, tool_calls


class ProductionModeHandler:
    """Handles production mode queries with real MCP tools"""
    
    def __init__(self, db: AsyncSession, user_id: uuid.UUID, conversation_manager=None):
        self.db = db
        self.user_id = user_id
        self.conversation_manager = conversation_manager
    
    async def handle_production_query(
        self, 
        request: QueryRequest, 
        conversation_id: uuid.UUID
    ) -> AsyncGenerator[dict, None]:
        """Handle production mode query with real MCP tools"""
        
        # Load conversation context if available
        if self.conversation_manager:
            conversation_context = await self.conversation_manager.load_conversation_history(
                conversation_id=conversation_id
            )
        else:
            conversation_context = []
        
        # Get bot source IDs from frontend-parsed bot mentions
        # Handle both UUID list (selected_bots) and object list (selectedBots)
        active_bot_ids = []
        if request.bot_ids:
            active_bot_ids.extend(request.bot_ids)
        elif request.selected_bots:
            active_bot_ids.extend(request.selected_bots)
        elif request.selectedBots:
            # Extract bot_id from bot objects
            for bot_obj in request.selectedBots:
                if isinstance(bot_obj, dict) and 'bot_id' in bot_obj:
                    active_bot_ids.append(bot_obj['bot_id'])
        
        bot_source_ids = []
        if active_bot_ids:
            # Query for sources associated with bots through BotSourceAssociation table
            bot_sources_query = (
                select(BotSourceAssociation.source_id)
                .join(Source, BotSourceAssociation.source_id == Source.source_id)
                .where(
                    BotSourceAssociation.bot_id.in_(active_bot_ids),
                    Source.is_active.is_(True)
                )
            )
            result = await self.db.execute(bot_sources_query)
            bot_source_ids = [row[0] for row in result.fetchall()]
        
        # Handle selected_sources parameter - filter which sources to use
        selected_source_ids = request.selected_sources or []
        if selected_source_ids or bot_source_ids:
            logger.info(
                "Using explicit source selection",
                selected_sources_count=len(selected_source_ids),
                bot_sources_count=len(bot_source_ids),
                selected_source_ids=selected_source_ids,
                bot_source_ids=bot_source_ids,
                user_id=self.user_id
            )
            # Only use the explicitly selected sources + bot sources (no fallback to all user sources)
            combined_source_ids = list(set(selected_source_ids + bot_source_ids))
        else:
            # No sources selected and no bots selected - load no sources
            logger.info(
                "No sources or bots selected - no tools will be loaded",
                user_id=self.user_id
            )
            combined_source_ids = []
        
        # Create and load fast agent from database cache
        try:
            fast_agent = FastMCPAgent()
            logger.info("FastMCPAgent created", user_id=self.user_id)
            
            # Load tools with filtered source IDs and selected bot IDs for proper instruction handling
            total_tools_loaded = await fast_agent.load_tools_for_specific_sources(
                db=self.db,
                user_id=self.user_id,
                source_ids=combined_source_ids,  # Use filtered source list
                selected_bot_ids=active_bot_ids  # CRITICAL FIX: Pass selected bot IDs for instruction filtering
            )
            logger.info(
                "Tools loaded with source filtering", 
                tools_count=total_tools_loaded, 
                source_ids_used=combined_source_ids,
                selected_sources_count=len(selected_source_ids),
                bot_sources_count=len(bot_source_ids),
                user_id=self.user_id
            )
            
        except Exception as e:
            logger.error("Fast agent loading failed", error=str(e), user_id=self.user_id)
            yield {
                "type": "error",
                "error": f"Agent initialization failed: {str(e)}"
            }
            return
        
        # Handle case with no tools available
        if total_tools_loaded == 0:
            response = await self._generate_no_tools_response(active_bot_ids, request.message, selected_source_ids)
            yield {
                "type": "final_response",
                "content": response,
                "tool_calls": [],
                "no_tools_available": True,
                "sources": [],
                "processing_stats": {
                    "total_tools_called": 0,
                    "query_type": "no_tools",
                    "response_time_ms": 0,
                    "sources_found": 0,
                    "selected_sources_count": len(selected_source_ids)
                }
            }
            return
        
        # We have tools - proceed with normal execution
        logger.info(
            "Fast tools loaded from database cache with source filtering",
            total_tools=total_tools_loaded,
            bot_sources=len(bot_source_ids),
            selected_sources=len(selected_source_ids),
            loaded_sources=len(fast_agent.loaded_sources),
            user_id=self.user_id
        )
        
        yield {
            "type": "status", 
            "message": f"Loaded {total_tools_loaded} tools from {len(selected_source_ids) if selected_source_ids else 'all'} selected sources..."
        }
        
        yield {
            "type": "tools_loaded",
            "tool_count": total_tools_loaded,
            "bot_sources": len(bot_source_ids),
            "selected_sources": len(selected_source_ids),
            "loaded_sources": len(fast_agent.loaded_sources),
            "source_type": "filtered_database_cached",
            "test_mode": False
        }
        
        # Stream query results using fast agent with conversation history
        try:
            async for chunk in fast_agent.query(
                message=request.message,
                llm_provider=request.llm_provider or "anthropic",
                llm_model=request.llm_model or "claude-sonnet-4-20250514",
                conversation_id=conversation_id,
                db_session=self.db
            ):
                yield chunk
            
            logger.info("Production query handler completed successfully")
                
        except Exception as e:
            logger.error("Fast agent query failed", error=str(e))
            yield {
                "type": "error",
                "error": f"Query processing failed: {str(e)}"
            }
    
    async def _generate_no_tools_response(self, active_bot_ids: List[uuid.UUID], message: str, selected_source_ids: List[uuid.UUID] = None) -> str:
        """Generate helpful response when no tools are available"""
        
        if selected_source_ids and len(selected_source_ids) > 0:
            return f"""I understand you're asking: "{message}"

However, I don't have access to tools from the {len(selected_source_ids)} selected source(s). This could be because:

1. **Sources Not Ready**: The selected sources haven't cached their tools yet
2. **No Tools Available**: The selected sources don't have any tools configured  
3. **Access Issues**: The selected sources might not be accessible or have connection problems
4. **MCP Server Issues**: The Model Context Protocol servers for these sources aren't responding

**What you can do:**
- Try selecting different sources from the source selector
- Go to the **Sources** section to check source status and refresh tools
- Wait a moment and try again (sources might be caching tools)
- Check with your administrator about the selected source configurations

You can also clear your source selection to use all available sources, or try asking a general question."""

        elif active_bot_ids:
            return f"""I understand you're asking: "{message}"

However, I don't currently have access to any knowledge sources or tools to provide specific information. This could be because:

1. **No Sources Configured**: The mentioned bots don't have configured knowledge sources
2. **MCP Tools Not Available**: The Model Context Protocol tools aren't loaded  
3. **Database Connection Issues**: I cannot access the knowledge bases

**What you can do:**
- Configure knowledge sources in the **Sources** section
- Set up **Bots** with specific data sources  
- Check with your administrator about MCP tool configuration

I can still help with general questions that don't require specific knowledge base access."""

        else:
            return f"""I see you're asking: "{message}"

I don't currently have access to specific knowledge sources to answer this question. Here's how to get better results:

**Option 1: Select Sources**
- Use the **Sources** dropdown to select specific knowledge sources
- Only tools from selected sources will be used for your query

**Option 2: Use Bots with Knowledge Sources**
- Go to the **Bots** section to create or use existing bots
- Mention bots in your query using `@botname` to access their knowledge
- Each bot can have specific data sources configured

**Option 3: Configure Knowledge Sources**  
- Visit the **Sources** section to add knowledge bases
- Connect document repositories, databases, or other data sources
- Configure access credentials for your knowledge systems

**Option 4: Ask General Questions**
I can help with general information that doesn't require specific knowledge base access.

Try selecting some sources first, then ask your question again!"""


class QueryHandler:
    """Main query handler that routes to test or production mode"""
    
    def __init__(self, db: AsyncSession, user_id: uuid.UUID):
        self.db = db
        self.user_id = user_id
        self.conversation_manager = None  # Will be injected if needed
    
    async def handle_test_query(
        self, 
        request: QueryRequest, 
        conversation_id: uuid.UUID
    ) -> AsyncGenerator[dict, None]:
        """Handle test mode query"""
        
        # Load conversation context if available
        if self.conversation_manager:
            conversation_context = await self.conversation_manager.load_conversation_history(
                conversation_id=conversation_id
            )
        else:
            conversation_context = []
        
        async for chunk in TestModeHandler.handle_test_query(
            request, conversation_id, conversation_context
        ):
            yield chunk
    
    async def handle_production_query(
        self, 
        request: QueryRequest, 
        conversation_id: uuid.UUID
    ) -> AsyncGenerator[dict, None]:
        """Handle production mode query"""
        
        handler = ProductionModeHandler(self.db, self.user_id, self.conversation_manager)
        async for chunk in handler.handle_production_query(request, conversation_id):
            yield chunk 
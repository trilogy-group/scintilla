"""
Query API endpoint with streaming support

Handles the main /query endpoint that:
- Loads MCP endpoints from bot credential management system
- Creates simplified MCP agent with tools
- Streams responses via Server-Sent Events  
- Persists conversation history
"""

import json
import uuid
import re
import asyncio
from typing import Optional, AsyncGenerator
from datetime import datetime, timezone
import traceback

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog

from src.api.models import QueryRequest, QueryResponse
from src.db.base import AsyncSessionLocal
from src.db.models import User, Conversation, Message
from src.agents.langchain_mcp import MCPAgent
from src.auth.mock import get_current_user
from src.global_mcp import get_global_mcp_agent

logger = structlog.get_logger()
router = APIRouter()


def generate_conversation_title(user_message: str) -> str:
    """Generate a meaningful conversation title from the user's message"""
    # Clean the message
    clean_message = re.sub(r'[^\w\s]', '', user_message).strip()
    
    # Take first 50 characters and add ellipsis if needed
    if len(clean_message) <= 50:
        return clean_message
    else:
        # Try to break at word boundary
        truncated = clean_message[:50]
        last_space = truncated.rfind(' ')
        if last_space > 20:  # Only break at word if it's not too short
            return truncated[:last_space] + "..."
        else:
            return truncated + "..."


async def get_or_create_conversation(
    db: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: Optional[uuid.UUID] = None,
    user_message: Optional[str] = None
) -> Conversation:
    """Get existing conversation or create new one with proper title"""
    
    if conversation_id:
        # Get existing conversation
        query = select(Conversation).where(
            Conversation.conversation_id == conversation_id,
            Conversation.user_id == user_id
        )
        result = await db.execute(query)
        conversation = result.scalar_one_or_none()
        
        if not conversation:
            raise HTTPException(
                status_code=404, 
                detail="Conversation not found"
            )
        
        return conversation
    
    else:
        # Create new conversation with title from user message
        title = generate_conversation_title(user_message) if user_message else "New Conversation"
        
        conversation = Conversation(
            conversation_id=uuid.uuid4(),
            user_id=user_id,
            title=title
        )
        
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)
        
        logger.info(
            "Created new conversation",
            conversation_id=conversation.conversation_id,
            title=title,
            user_id=user_id
        )
        
        return conversation


async def save_messages_and_create_conversation(
    db: AsyncSession,
    user_id: uuid.UUID,
    user_message: str,
    assistant_response: str,
    llm_provider: str,
    llm_model: str,
    conversation_id: Optional[uuid.UUID] = None,
    tool_calls: Optional[list] = None,
    citations: Optional[list] = None
) -> tuple[uuid.UUID, uuid.UUID]:
    """Save messages and create conversation if needed. Returns (conversation_id, message_id)"""
    
    # Get or create conversation
    conversation = await get_or_create_conversation(
        db=db,
        user_id=user_id,
        conversation_id=conversation_id,
        user_message=user_message
    )
    
    # Capture conversation ID before any operations
    conv_id = conversation.conversation_id
    
    # Generate message IDs before creating objects
    user_msg_id = uuid.uuid4()
    assistant_msg_id = uuid.uuid4()
    
    # Save user message
    user_msg = Message(
        message_id=user_msg_id,
        conversation_id=conv_id,
        role="user",
        content=user_message
    )
    db.add(user_msg)
    
    # Save assistant message
    assistant_msg = Message(
        message_id=assistant_msg_id,
        conversation_id=conv_id,
        role="assistant",
        content=assistant_response,
        tools_used=tool_calls,
        citations=citations,
        llm_provider=llm_provider,
        llm_model=llm_model
    )
    db.add(assistant_msg)
    
    # Update conversation timestamp with timezone-aware datetime
    conversation.updated_at = datetime.now(timezone.utc)
    
    # Commit all changes
    await db.commit()
    
    # Return captured IDs (no object access after commit)
    return conv_id, assistant_msg_id


async def format_sse_chunk(chunk: dict) -> str:
    """Format a chunk as SSE data"""
    return f"data: {json.dumps(chunk)}\n\n"


async def handle_query_request(request: QueryRequest, user_id: uuid.UUID) -> AsyncGenerator[str, None]:
    """Handle streaming query request with globally cached MCP tools"""
    
    request_start_time = datetime.now(timezone.utc)
    logger.info(
        "Query request started",
        user_id=user_id,
        message_length=len(request.message),
        timestamp=request_start_time.isoformat()
    )
    
    try:
        async with AsyncSessionLocal() as db:
            # Check sources configuration
            if not request.bot_ids and not request.use_user_sources:
                yield await format_sse_chunk({
                    "type": "error",
                    "error": "No sources specified (no bots and user sources disabled)"
                })
                return

            # Get globally cached MCP agent instead of loading tools per request
            mcp_agent = get_global_mcp_agent()
            
            if mcp_agent is None or len(mcp_agent.tools) == 0:
                # Fallback: load tools if global agent not available
                logger.warning("Global MCP agent not available, falling back to per-request loading")
                
                yield await format_sse_chunk({
                    "type": "status",
                    "message": "Loading MCP tools (fallback mode)..."
                })
                
                mcp_agent = MCPAgent()
                
                # Use asyncio.create_task to potentially parallelize MCP loading with timeout
                try:
                    if request.bot_ids and request.use_user_sources:
                        # Load both user sources and bot sources in parallel
                        user_task = asyncio.create_task(
                            mcp_agent.load_mcp_endpoints_from_user_sources(db, user_id)
                        )
                        bot_task = asyncio.create_task(
                            mcp_agent.load_mcp_endpoints_from_bot_sources(db, request.bot_ids)
                        )
                        
                        # Wait for both to complete with timeout
                        user_tool_count, bot_tool_count = await asyncio.wait_for(
                            asyncio.gather(user_task, bot_task),
                            timeout=60  # 60 second timeout for MCP loading
                        )
                        tool_count = user_tool_count + bot_tool_count
                        source_type = "user sources + bots"
                    elif request.bot_ids:
                        # Load only bot sources with timeout
                        tool_count = await asyncio.wait_for(
                            mcp_agent.load_mcp_endpoints_from_bot_sources(db, request.bot_ids),
                            timeout=60
                        )
                        source_type = "bots only"
                    elif request.use_user_sources:
                        # Load only user sources with timeout
                        tool_count = await asyncio.wait_for(
                            mcp_agent.load_mcp_endpoints_from_user_sources(db, user_id),
                            timeout=60
                        )
                        source_type = "user sources only"
                    else:
                        yield await format_sse_chunk({
                            "type": "error",
                            "error": "No sources specified (no bots and user sources disabled)"
                        })
                        return
                        
                except asyncio.TimeoutError:
                    logger.error("MCP loading timed out in fallback mode", timeout_seconds=60, user_id=user_id)
                    
                    yield await format_sse_chunk({
                        "type": "error",
                        "error": "MCP tool loading timed out after 60 seconds. This may be due to network issues or mcp-proxy dependency resolution problems."
                    })
                    return
            else:
                # Use globally cached tools - this should be instant!
                tool_count = len(mcp_agent.tools)
                source_type = "cached global tools"
                
                logger.info(
                    "Using globally cached MCP tools",
                    tool_count=tool_count,
                    loaded_servers=mcp_agent.get_loaded_servers(),
                    user_id=user_id
                )

            if tool_count == 0:
                yield await format_sse_chunk({
                    "type": "error",
                    "error": f"No MCP tools available from {source_type}"
                })
                return

            # Send tools loaded notification
            yield await format_sse_chunk({
                "type": "tools_loaded",
                "tool_count": tool_count,
                "source_type": source_type,
                "loaded_servers": mcp_agent.get_loaded_servers()
            })

            # Continue with query processing using the MCP agent
            query_start_time = datetime.now(timezone.utc)
            
            # Capture the full response for saving to database
            full_response = ""
            tool_calls_used = []
            conversation_id_result = None
            
            # Stream the query response
            async for chunk in mcp_agent.query(
                message=request.message,
                llm_provider=request.llm_provider,
                llm_model=request.llm_model,
                mode=request.mode or "conversational",
                require_sources=request.require_sources,
                min_sources=request.min_sources or 2,
                search_depth=request.search_depth or "thorough",
                conversation_id=request.conversation_id,
                db_session=db
            ):
                # Capture data for database saving
                if chunk.get("type") == "final_response":
                    full_response = chunk.get("content", "")
                    tool_calls_used = chunk.get("tool_calls", [])
                
                yield await format_sse_chunk(chunk)

            # Save conversation and messages after streaming completes
            if full_response:
                try:
                    conversation_id_result, message_id = await save_messages_and_create_conversation(
                        db=db,
                        user_id=user_id,
                        user_message=request.message,
                        assistant_response=full_response,
                        llm_provider=request.llm_provider or "anthropic",
                        llm_model=request.llm_model or "claude-sonnet-4-20250514",
                        conversation_id=request.conversation_id,
                        tool_calls=tool_calls_used,
                        citations=None  # Could extract from sources if needed
                    )
                    
                    # Send final completion message with conversation details
                    yield await format_sse_chunk({
                        "type": "conversation_saved",
                        "conversation_id": str(conversation_id_result),
                        "message_id": str(message_id)
                    })
                    
                    logger.info(
                        "Conversation saved successfully",
                        conversation_id=str(conversation_id_result),
                        message_id=str(message_id),
                        user_id=user_id
                    )
                    
                except Exception as e:
                    logger.error(
                        "Failed to save conversation",
                        error=str(e),
                        user_id=user_id
                    )
                    yield await format_sse_chunk({
                        "type": "error",
                        "error": f"Failed to save conversation: {str(e)}"
                    })

    except Exception as e:
        logger.error(
            "Query request failed",
            user_id=user_id,
            error=str(e),
            traceback=traceback.format_exc()
        )
        yield await format_sse_chunk({
            "type": "error",
            "error": f"Query processing failed: {str(e)}"
        })


async def save_conversation_background(
    db: AsyncSession,
    user_id: uuid.UUID,
    request: QueryRequest,
    request_start_time: datetime,
    query_start_time: datetime
):
    """Save conversation in background task for better performance"""
    try:
        db_save_start = datetime.now(timezone.utc)
        
        async with AsyncSessionLocal() as db:
            conversation_id, message_id = await save_messages_and_create_conversation(
                db=db,
                user_id=user_id,
                user_message=request.message,
                assistant_response=request.message,  # Assuming the response is the same as the query
                llm_provider=request.llm_provider,
                llm_model=request.llm_model,
                conversation_id=request.conversation_id,
                tool_calls=None,
                citations=None
            )
            
            db_save_end = datetime.now(timezone.utc)
            db_save_time = (db_save_end - db_save_start).total_seconds() * 1000
            
            logger.info(
                "Background conversation save completed",
                conversation_id=str(conversation_id),
                message_id=str(message_id),
                db_save_time_ms=int(db_save_time),
                user_id=user_id
            )
            
    except Exception as e:
        logger.error("Background conversation save failed", error=str(e), user_id=user_id)


@router.post("/query")
async def query_endpoint(
    request: QueryRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user)
):
    """
    Main query endpoint with streaming support
    
    Executes user queries using MCP tools and streams back responses
    via Server-Sent Events.
    """
    logger.info(
        "Query request received",
        user_id=user.user_id,
        message_length=len(request.message),
        bot_ids=request.bot_ids,
        stream=request.stream
    )
    
    # Always use streaming for now (non-streaming mode had old model references)
    return StreamingResponse(
        handle_query_request(request, user.user_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",  
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        }
    ) 
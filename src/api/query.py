"""
Query API endpoint with streaming support

Handles the main /query endpoint for federated search and chat.
"""

import json
import uuid
from typing import Optional, AsyncGenerator
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from src.api.models import QueryRequest, QueryResponse, QuerySyncResponse
from src.api.query_handlers import QueryHandler
from src.api.conversation_manager import ConversationManager
from src.auth.google_oauth import get_current_user
from src.db.base import get_db_session
from src.db.models import User
from src.config import TEST_MODE

logger = structlog.get_logger()
router = APIRouter()


async def format_sse_chunk(chunk: dict) -> str:
    """Format a chunk as Server-Sent Events data"""
    return f"data: {json.dumps(chunk)}\n\n"


async def accumulate_query_result(query_generator, conversation_id: uuid.UUID) -> QuerySyncResponse:
    """
    Accumulate streaming query results into a single response
    
    Args:
        query_generator: Async generator yielding query chunks
        conversation_id: Conversation ID for the response
        
    Returns:
        QuerySyncResponse with accumulated results
    """
    
    content = ""
    tools_used = []
    citations = []
    processing_stats = {}
    llm_provider = None
    llm_model = None
    message_id = None
    
    async for chunk in query_generator:
        chunk_type = chunk.get("type")
        
        if chunk_type == "final_response":
            content = chunk.get("content", "")
            tools_used = chunk.get("tool_calls", [])
            citations = chunk.get("sources", [])
            processing_stats = chunk.get("processing_stats", {})
            llm_provider = chunk.get("llm_provider")
            llm_model = chunk.get("llm_model")
            message_id = chunk.get("message_id")
            break
        elif chunk_type == "error":
            content = f"Error: {chunk.get('error', 'Unknown error occurred')}"
            break
    
    # Generate message ID if not provided
    if not message_id:
        message_id = uuid.uuid4()
    
    return QuerySyncResponse(
        message_id=message_id if isinstance(message_id, uuid.UUID) else uuid.UUID(str(message_id)),
        conversation_id=conversation_id,
        content=content,
        llm_provider=llm_provider,
        llm_model=llm_model,
        tools_used=[tool.get("tool", "") for tool in tools_used if isinstance(tool, dict)],
        citations=citations,
        processing_stats=processing_stats,
        created_at=datetime.now(timezone.utc)
    )


@router.post("/query")
async def query_endpoint(
    request: QueryRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Main query endpoint with streaming or non-streaming response
    
    Handles both test mode and production federated search.
    Returns streaming response by default, or JSON response if stream=False.
    """
    
    # Initialize handlers
    query_handler = QueryHandler(db, user.user_id)
    conversation_manager = ConversationManager(db)
    
    # Inject conversation manager into query handler
    query_handler.conversation_manager = conversation_manager
    
    # Get or create conversation
    conversation = await conversation_manager.get_or_create_conversation(
        user_id=user.user_id,
        conversation_id=request.conversation_id,
        user_message=request.message
    )
    
    # Handle non-streaming response
    if request.stream is False:
        try:
            logger.info("Processing non-streaming query", user_id=user.user_id)
            
            # Create query generator
            if TEST_MODE:
                query_gen = query_handler.handle_test_query(request, conversation.conversation_id)
            else:
                query_gen = query_handler.handle_production_query(request, conversation.conversation_id)
            
            # Accumulate all results
            result = await accumulate_query_result(query_gen, conversation.conversation_id)
            
            # Save conversation in background
            final_chunk = {
                "type": "final_response",
                "content": result.content,
                "sources": result.citations,
                "processing_stats": result.processing_stats
            }
            background_tasks.add_task(
                conversation_manager.save_conversation_background,
                request=request,
                conversation_id=conversation.conversation_id,
                final_chunk=final_chunk
            )
            
            logger.info("Non-streaming query completed", user_id=user.user_id)
            # Convert UUID and datetime fields to strings for JSON serialization
            result_dict = result.dict()
            result_dict["message_id"] = str(result_dict["message_id"])
            result_dict["conversation_id"] = str(result_dict["conversation_id"])
            if "created_at" in result_dict and result_dict["created_at"]:
                result_dict["created_at"] = result_dict["created_at"].isoformat()
            return JSONResponse(content=result_dict)
            
        except Exception as e:
            logger.error("Non-streaming query failed", error=str(e), user_id=user.user_id)
            raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")
    
    # Handle streaming response (existing logic)
    async def stream_response():
        try:
            logger.info("Starting stream response")
            
            # Immediately send conversation_saved event to frontend so it knows the conversation ID
            conversation_saved_chunk = {
                "type": "conversation_saved",
                "conversation_id": str(conversation.conversation_id),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            yield await format_sse_chunk(conversation_saved_chunk)
            
            logger.info("Conversation ready, starting query processing")
            
            # Capture final chunk for saving
            final_chunk = None
            
            # Handle the query based on mode
            if TEST_MODE:
                logger.info("Processing test mode query")
                async for chunk in query_handler.handle_test_query(request, conversation.conversation_id):
                    if chunk.get("type") == "final_response":
                        final_chunk = chunk
                        logger.info("Captured final response chunk")
                    yield await format_sse_chunk(chunk)
            else:
                logger.info("Processing production mode query")
                async for chunk in query_handler.handle_production_query(request, conversation.conversation_id):
                    if chunk.get("type") == "final_response":
                        final_chunk = chunk
                        logger.info("Captured final response chunk")
                    yield await format_sse_chunk(chunk)
            
            logger.info("Query processing completed, setting up background task")
            
            # Save conversation in background with captured final chunk
            background_tasks.add_task(
                conversation_manager.save_conversation_background,
                request=request,
                conversation_id=conversation.conversation_id,
                final_chunk=final_chunk
            )
            
            logger.info("Background task queued, sending completion signals")
            
            # Send completion chunk before [DONE]
            completion_chunk = {
                "type": "complete",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            yield await format_sse_chunk(completion_chunk)
            
            # Send completion signal to frontend
            logger.info("Sending completion signal to frontend")
            yield "data: [DONE]\n\n"
            
            logger.info("Stream response completed successfully")
            
        except Exception as e:
            logger.error("Query endpoint failed", error=str(e), user_id=user.user_id)
            error_chunk = {
                "type": "error",
                "error": f"Query failed: {str(e)}",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            yield await format_sse_chunk(error_chunk)
            # Send completion chunk before [DONE] even on error
            completion_chunk = {
                "type": "complete",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            yield await format_sse_chunk(completion_chunk)
            # Send completion signal even on error
            yield "data: [DONE]\n\n"
    
    return StreamingResponse(
        stream_response(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    ) 
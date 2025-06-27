"""
Query API endpoint with streaming support

Handles the main /query endpoint for federated search and chat.
"""

import json
import uuid
from typing import Optional, AsyncGenerator
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from src.api.models import QueryRequest, QueryResponse
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


@router.post("/query")
async def query_endpoint(
    request: QueryRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Main query endpoint with streaming response
    
    Handles both test mode and production federated search
    """
    async def stream_response():
        try:
            logger.info("Starting stream response")
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
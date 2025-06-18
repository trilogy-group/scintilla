"""
Conversations management API endpoints

Handles CRUD operations for conversation history.
"""

import uuid
from typing import List, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload
import structlog

from src.db.base import get_db_session
from src.db.models import User, Conversation, Message
from src.auth.mock import get_current_user

logger = structlog.get_logger()
router = APIRouter()


# Response Models
class ConversationResponse(BaseModel):
    """Conversation information response"""
    conversation_id: uuid.UUID
    user_id: uuid.UUID
    title: Optional[str]
    message_count: int
    created_at: datetime
    updated_at: datetime
    last_message_preview: Optional[str] = None

class MessageResponse(BaseModel):
    """Message information response"""
    message_id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    tools_used: Optional[List] = None
    citations: Optional[List] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    created_at: datetime

class ConversationWithMessagesResponse(BaseModel):
    """Conversation with full message history"""
    conversation_id: uuid.UUID
    user_id: uuid.UUID
    title: Optional[str]
    created_at: datetime
    updated_at: datetime
    messages: List[MessageResponse]


@router.get("/conversations", response_model=List[ConversationResponse])
async def list_user_conversations(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """List conversations owned by the current user"""
    
    # Get conversations with message counts
    query = (
        select(
            Conversation,
            func.count(Message.message_id).label('message_count'),
            func.max(Message.created_at).label('last_message_time')
        )
        .outerjoin(Message)
        .where(Conversation.user_id == user.user_id)
        .group_by(Conversation.conversation_id)
        .order_by(desc(func.coalesce(func.max(Message.created_at), Conversation.created_at)))
    )
    
    result = await db.execute(query)
    conversations_data = result.all()
    
    # Get last message preview for each conversation
    conversation_responses = []
    for conv_data in conversations_data:
        conversation, message_count, last_message_time = conv_data
        
        # Get last message preview
        last_msg_query = (
            select(Message.content)
            .where(Message.conversation_id == conversation.conversation_id)
            .order_by(desc(Message.created_at))
            .limit(1)
        )
        last_msg_result = await db.execute(last_msg_query)
        last_message = last_msg_result.scalar_one_or_none()
        
        # Create preview (first 100 chars)
        preview = None
        if last_message:
            preview = last_message[:100] + "..." if len(last_message) > 100 else last_message
        
        conversation_responses.append(ConversationResponse(
            conversation_id=conversation.conversation_id,
            user_id=conversation.user_id,
            title=conversation.title,
            message_count=message_count or 0,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            last_message_preview=preview
        ))
    
    return conversation_responses


@router.get("/conversations/{conversation_id}", response_model=ConversationWithMessagesResponse)
async def get_conversation_with_messages(
    conversation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get a specific conversation with all messages"""
    
    # Get conversation
    query = select(Conversation).where(
        Conversation.conversation_id == conversation_id,
        Conversation.user_id == user.user_id
    )
    
    result = await db.execute(query)
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    # Get messages
    messages_query = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    
    messages_result = await db.execute(messages_query)
    messages = messages_result.scalars().all()
    
    message_responses = [
        MessageResponse(
            message_id=msg.message_id,
            conversation_id=msg.conversation_id,
            role=msg.role,
            content=msg.content,
            tools_used=msg.tools_used,
            citations=msg.citations,
            llm_provider=msg.llm_provider,
            llm_model=msg.llm_model,
            created_at=msg.created_at
        )
        for msg in messages
    ]
    
    return ConversationWithMessagesResponse(
        conversation_id=conversation.conversation_id,
        user_id=conversation.user_id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=message_responses
    )


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Delete a conversation and all its messages"""
    
    # Get conversation
    query = select(Conversation).where(
        Conversation.conversation_id == conversation_id,
        Conversation.user_id == user.user_id
    )
    
    result = await db.execute(query)
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    # Delete all messages first (due to foreign key constraints)
    messages_delete_query = Message.__table__.delete().where(
        Message.conversation_id == conversation_id
    )
    await db.execute(messages_delete_query)
    
    # Delete conversation
    await db.delete(conversation)
    await db.commit()
    
    logger.info(
        "Conversation deleted",
        conversation_id=conversation_id,
        user_id=user.user_id
    )
    
    return {"message": "Conversation deleted successfully"}


@router.put("/conversations/{conversation_id}/title")
async def update_conversation_title(
    conversation_id: uuid.UUID,
    title: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Update conversation title"""
    
    # Get conversation
    query = select(Conversation).where(
        Conversation.conversation_id == conversation_id,
        Conversation.user_id == user.user_id
    )
    
    result = await db.execute(query)
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    # Update title
    conversation.title = title
    conversation.updated_at = datetime.now(timezone.utc)
    
    await db.commit()
    
    logger.info(
        "Conversation title updated",
        conversation_id=conversation_id,
        title=title,
        user_id=user.user_id
    )
    
    return {"message": "Conversation title updated successfully"} 
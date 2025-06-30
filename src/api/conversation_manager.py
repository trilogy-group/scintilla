"""
Conversation Management Module

Handles conversation creation, history loading, and message persistence.
Extracted from query.py to improve maintainability.
"""

import uuid
import re
from typing import Optional
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog

from src.db.models import User, Conversation, Message
from src.api.models import QueryRequest

logger = structlog.get_logger()


class ConversationManager:
    """Manages conversation lifecycle and persistence"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    def generate_conversation_title(self, user_message: str) -> str:
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
        self,
        user_id: uuid.UUID,
        conversation_id: Optional[uuid.UUID] = None,
        user_message: Optional[str] = None
    ) -> Conversation:
        """Get existing conversation or create new one with proper title"""
        
        logger.info(
            "get_or_create_conversation called",
            conversation_id=conversation_id,
            user_id=user_id
        )
        
        if conversation_id:
            # Get existing conversation
            query = select(Conversation).where(
                Conversation.conversation_id == conversation_id,
                Conversation.user_id == user_id
            )
            result = await self.db.execute(query)
            conversation = result.scalar_one_or_none()
            
            if conversation:
                logger.info("Using existing conversation", conversation_id=conversation_id)
                return conversation
            else:
                logger.warning(
                    "Conversation not found, creating new one",
                    requested_conversation_id=conversation_id
                )
        
        # Create new conversation with title from user message
        title = self.generate_conversation_title(user_message) if user_message else "New Conversation"
        
        new_conversation_id = uuid.uuid4()
        conversation = Conversation(
            conversation_id=new_conversation_id,
            user_id=user_id,
            title=title
        )
        
        self.db.add(conversation)
        await self.db.commit()
        await self.db.refresh(conversation)
        
        logger.info(
            "Created new conversation",
            conversation_id=new_conversation_id,
            title=title,
            user_id=user_id
        )
        
        return conversation
    
    async def save_messages(
        self,
        conversation_id: uuid.UUID,
        user_message: str,
        assistant_response: str,
        llm_provider: str,
        llm_model: str,
        tool_calls: Optional[list] = None,
        citations: Optional[list] = None,
        selected_bots: Optional[list] = None,
        selected_sources: Optional[list] = None
    ) -> tuple[uuid.UUID, uuid.UUID]:
        """Save user and assistant messages to conversation"""
        
        # Generate message IDs
        user_msg_id = uuid.uuid4()
        assistant_msg_id = uuid.uuid4()
        
        # Save user message with selected bots and sources
        user_msg = Message(
            message_id=user_msg_id,
            conversation_id=conversation_id,
            role="user",
            content=user_message,
            selected_bots=selected_bots or [],
            selected_sources=selected_sources or []
        )
        self.db.add(user_msg)
        
        # Save assistant message
        assistant_msg = Message(
            message_id=assistant_msg_id,
            conversation_id=conversation_id,
            role="assistant",
            content=assistant_response,
            tools_used=tool_calls,
            citations=citations,
            llm_provider=llm_provider,
            llm_model=llm_model
        )
        self.db.add(assistant_msg)
        
        # Update conversation timestamp
        conversation_query = select(Conversation).where(
            Conversation.conversation_id == conversation_id
        )
        result = await self.db.execute(conversation_query)
        conversation = result.scalar_one_or_none()
        
        if conversation:
            conversation.updated_at = datetime.now(timezone.utc)
        
        await self.db.commit()
        
        return user_msg_id, assistant_msg_id
    
    async def load_conversation_history(
        self,
        conversation_id: uuid.UUID,
        limit: int = 10
    ) -> list:
        """Load conversation history for context"""
        try:
            result = await self.db.execute(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at.desc())
                .limit(limit)
            )
            messages = list(reversed(result.scalars().all()))
            
            context_parts = []
            for msg in messages:
                # Extract data early to avoid greenlet issues
                role = msg.role
                content = msg.content
                
                role_name = "Human" if role == "user" else "Assistant"
                context_parts.append(f"{role_name}: {content}")
            
            return context_parts
            
        except Exception as e:
            logger.warning("Failed to load conversation history", error=str(e))
            return []
    
    async def save_conversation_background(
        self,
        request: QueryRequest,
        conversation_id: uuid.UUID,
        final_chunk: Optional[dict] = None
    ):
        """Save conversation in background task"""
        try:
            if final_chunk and final_chunk.get("content"):
                await self.save_messages(
                    conversation_id=conversation_id,
                    user_message=request.message,
                    assistant_response=final_chunk["content"],
                    llm_provider=request.llm_provider or "anthropic",
                    llm_model=request.llm_model or "claude-sonnet-4-20250514",
                    tool_calls=final_chunk.get("tool_calls"),
                    citations=final_chunk.get("sources"),
                    selected_bots=request.selectedBots,
                    selected_sources=request.selected_sources
                )
                
                logger.info("Background conversation save completed", conversation_id=conversation_id)
            else:
                logger.warning("No final chunk to save", conversation_id=conversation_id)
                
        except Exception as e:
            logger.error("Background conversation save failed", error=str(e)) 
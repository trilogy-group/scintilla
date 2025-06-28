"""
Database models for Scintilla
"""

import uuid
from datetime import datetime
from typing import List, Optional
from enum import Enum
from sqlalchemy import Column, String, Text, DateTime, Boolean, ForeignKey, ARRAY
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .base import Base


class User(Base):
    """User model for authentication and authorization"""
    __tablename__ = "users"
    
    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    picture_url = Column(String(500), nullable=True)
    is_admin = Column(Boolean, default=False, nullable=False)
    last_login = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    owned_sources = relationship("Source", back_populates="owner", cascade="all, delete-orphan")
    created_bots = relationship("Bot", back_populates="created_by_user", cascade="all, delete-orphan")
    bot_access = relationship("UserBotAccess", back_populates="user", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    agent_tokens = relationship("UserAgentToken", back_populates="user", cascade="all, delete-orphan")
    
    # Source sharing relationships
    granted_source_shares = relationship("SourceShare", foreign_keys="SourceShare.granted_by_user_id", back_populates="granted_by_user")
    received_source_shares = relationship("SourceShare", foreign_keys="SourceShare.shared_with_user_id", back_populates="shared_with_user")


class Source(Base):
    """Source model - represents individual MCP server connections"""
    __tablename__ = "sources"
    
    source_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    instructions = Column(Text, nullable=True)  # Instructions for this source when used in bots
    server_url = Column(String(500), nullable=False)  # Base SSE URL or full URL with embedded auth
    
    # Simplified authentication - store plain text headers or embed in URL
    # If auth_headers provided: use server_url as SSE endpoint + headers
    # If auth_headers empty: use server_url as full URL with embedded auth (Hive style)
    auth_headers = Column(JSONB, nullable=True, default=dict)  # {"Authorization": "Bearer token"} or {"x-api-key": "key"}
    
    # Tool caching metadata
    tools_last_cached_at = Column(DateTime(timezone=True), nullable=True)
    tools_cache_status = Column(String(50), default="pending", nullable=False)  # pending, cached, error
    tools_cache_error = Column(Text, nullable=True)
    
    # Ownership - either user-owned or bot-owned
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True)
    owner_bot_id = Column(UUID(as_uuid=True), ForeignKey("bots.bot_id"), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    owner = relationship("User", back_populates="owned_sources")
    owner_bot = relationship("Bot", back_populates="owned_sources")
    tools = relationship("SourceTool", back_populates="source", cascade="all, delete-orphan")
    
    # New sharing and association relationships
    shares = relationship("SourceShare", back_populates="source", cascade="all, delete-orphan")
    bot_associations = relationship("BotSourceAssociation", back_populates="source", cascade="all, delete-orphan")


class BotSourceAssociation(Base):
    """Association between bots and sources with custom instructions"""
    __tablename__ = "bot_source_associations"
    
    bot_id = Column(UUID(as_uuid=True), ForeignKey("bots.bot_id"), primary_key=True)
    source_id = Column(UUID(as_uuid=True), ForeignKey("sources.source_id"), primary_key=True)
    custom_instructions = Column(Text, nullable=True)  # Bot-specific instructions for this source
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    bot = relationship("Bot", back_populates="source_associations")
    source = relationship("Source", back_populates="bot_associations")


class SourceShare(Base):
    """Source sharing between users"""
    __tablename__ = "source_shares"
    
    source_id = Column(UUID(as_uuid=True), ForeignKey("sources.source_id"), primary_key=True)
    shared_with_user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), primary_key=True)
    granted_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    granted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    source = relationship("Source", back_populates="shares")
    shared_with_user = relationship("User", foreign_keys=[shared_with_user_id], back_populates="received_source_shares")
    granted_by_user = relationship("User", foreign_keys=[granted_by_user_id], back_populates="granted_source_shares")


class Bot(Base):
    """Bot model - represents collections of sources with specific purposes"""
    __tablename__ = "bots"
    
    bot_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    source_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)  # Keep for backward compatibility
    
    # User ownership and sharing configuration
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    is_public = Column(Boolean, default=False, nullable=False)
    allowed_user_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    created_by_user = relationship("User", back_populates="created_bots")
    user_access = relationship("UserBotAccess", back_populates="bot", cascade="all, delete-orphan")
    owned_sources = relationship("Source", back_populates="owner_bot", cascade="all, delete-orphan")
    
    # New source association relationship
    source_associations = relationship("BotSourceAssociation", back_populates="bot", cascade="all, delete-orphan")


class UserBotAccess(Base):
    """Explicit user access to bots"""
    __tablename__ = "user_bot_access"
    
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), primary_key=True)
    bot_id = Column(UUID(as_uuid=True), ForeignKey("bots.bot_id"), primary_key=True)
    granted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="bot_access")
    bot = relationship("Bot", back_populates="user_access")


class Conversation(Base):
    """Conversation model for chat history"""
    __tablename__ = "conversations"
    
    conversation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    title = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    """Message model for individual chat messages"""
    __tablename__ = "messages"
    
    message_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.conversation_id"), nullable=False)
    role = Column(String(20), nullable=False)  # 'user', 'assistant', 'system'
    content = Column(Text, nullable=False)
    
    # LLM metadata
    llm_provider = Column(String(100), nullable=True)
    llm_model = Column(String(200), nullable=True)
    
    # Tool usage tracking
    tools_used = Column(JSONB, nullable=True, default=list)
    citations = Column(JSONB, nullable=True, default=list)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    conversation = relationship("Conversation", back_populates="messages")


class SourceTool(Base):
    """Cached tool metadata from MCP servers - populated during source creation/refresh"""
    __tablename__ = "source_tools"
    
    tool_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(UUID(as_uuid=True), ForeignKey("sources.source_id"), nullable=False)
    
    # Tool metadata from MCP server
    tool_name = Column(String(255), nullable=False)
    tool_description = Column(Text, nullable=True)
    tool_schema = Column(JSONB, nullable=True)  # Full JSON schema for the tool
    
    # Caching metadata
    last_refreshed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    source = relationship("Source", back_populates="tools")

    def __repr__(self):
        return f"<SourceTool(tool_name='{self.tool_name}', source_id='{self.source_id}')>"


class UserAgentToken(Base):
    """User tokens for local agent authentication"""
    __tablename__ = "user_agent_tokens"
    
    token_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    token_hash = Column(String(128), nullable=False, unique=True, index=True)  # SHA-256 hash
    token_prefix = Column(String(8), nullable=False)  # First 8 chars for display
    name = Column(String(100), nullable=True)  # User-given name for token
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)  # Optional expiration
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationship
    user = relationship("User", back_populates="agent_tokens")
    
    def __repr__(self):
        return f"<UserAgentToken(prefix='{self.token_prefix}', user_id='{self.user_id}')>" 
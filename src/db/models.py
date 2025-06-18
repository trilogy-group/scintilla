"""
Database models for Scintilla
"""

import uuid
from datetime import datetime
from typing import List, Optional
from enum import Enum
from sqlalchemy import Column, String, Text, DateTime, Boolean, ForeignKey, ARRAY, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .base import Base


class MCPServerType(Enum):
    """MCP Server types"""
    CUSTOM_SSE = "CUSTOM_SSE"


class CredentialType(Enum):
    """Credential types for MCP servers"""
    API_KEY_HEADER = "API_KEY_HEADER"


class User(Base):
    """User model for authentication and authorization"""
    __tablename__ = "users"
    
    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    picture_url = Column(String(500), nullable=True)
    is_admin = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    owned_sources = relationship("Source", back_populates="owner", cascade="all, delete-orphan")
    created_bots = relationship("Bot", back_populates="created_by_admin", cascade="all, delete-orphan")
    bot_access = relationship("UserBotAccess", back_populates="user", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")


class Source(Base):
    """Source model - represents individual MCP server connections"""
    __tablename__ = "sources"
    
    source_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    server_type = Column(SQLEnum(MCPServerType), nullable=False)
    server_url = Column(String(500), nullable=False)
    required_fields = Column(JSONB, nullable=False, default=lambda: ["api_key"])
    
    # Ownership
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    owner = relationship("User", back_populates="owned_sources")
    credentials = relationship("MCPCredential", back_populates="source", cascade="all, delete-orphan")


class Bot(Base):
    """Bot model - represents collections of sources with specific purposes"""
    __tablename__ = "bots"
    
    bot_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    source_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)
    
    # Admin configuration
    created_by_admin_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True)
    is_public = Column(Boolean, default=False, nullable=False)
    allowed_user_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    created_by_admin = relationship("User", back_populates="created_bots")
    user_access = relationship("UserBotAccess", back_populates="bot", cascade="all, delete-orphan")


class UserBotAccess(Base):
    """Explicit user access to bots"""
    __tablename__ = "user_bot_access"
    
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), primary_key=True)
    bot_id = Column(UUID(as_uuid=True), ForeignKey("bots.bot_id"), primary_key=True)
    granted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="bot_access")
    bot = relationship("Bot", back_populates="user_access")


class MCPCredential(Base):
    """Encrypted credentials for MCP server connections"""
    __tablename__ = "mcp_credentials"
    
    credential_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(UUID(as_uuid=True), ForeignKey("sources.source_id"), nullable=False)
    credential_type = Column(SQLEnum(CredentialType), nullable=False)
    encrypted_value = Column(Text, nullable=False)  # Encrypted credential value
    field_name = Column(String(255), nullable=False)  # e.g., "api_key", "auth_token"
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    source = relationship("Source", back_populates="credentials")


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


class MCPToolCache(Base):
    """Cache for MCP tool information to avoid repeated tool listing"""
    __tablename__ = "mcp_tool_cache"
    
    cache_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    bot_source_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=True, default=list)  # Empty for user-only
    
    # Cached tool data
    tools_data = Column(JSONB, nullable=False)  # Serialized tool information
    loaded_servers = Column(ARRAY(String), nullable=False, default=list)
    tool_count = Column(String, nullable=False, default="0")
    
    # Cache metadata
    cache_key = Column(String(500), nullable=False, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_refreshed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User") 
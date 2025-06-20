"""
Pydantic models for API requests and responses
"""

from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime


class QueryRequest(BaseModel):
    """Chat query request"""
    message: str = Field(..., description="User message/query")
    conversation_id: Optional[UUID] = Field(None, description="Conversation ID (optional for new conversations)")
    mode: Optional[str] = Field("conversational", description="Query mode")
    stream: Optional[bool] = Field(True, description="Enable streaming response")
    requireSources: Optional[bool] = Field(False, description="Require sources in response")
    minSources: Optional[int] = Field(2, description="Minimum number of sources")
    searchDepth: Optional[str] = Field("thorough", description="Search depth")
    use_user_sources: Optional[bool] = Field(True, description="Use user sources")
    selected_sources: Optional[List[UUID]] = Field(None, description="Optional list of source IDs to use")
    selected_bots: Optional[List[UUID]] = Field(None, description="Optional list of bot IDs to use")
    bot_ids: Optional[List[UUID]] = Field(None, description="Bot IDs for compatibility")
    llm_provider: Optional[str] = Field(None, description="LLM provider")
    llm_model: Optional[str] = Field(None, description="LLM model")


class QueryResponse(BaseModel):
    """Chat query response"""
    message_id: UUID
    conversation_id: UUID
    content: str
    llm_provider: Optional[str]
    llm_model: Optional[str]
    tools_used: Optional[List[str]]
    citations: Optional[List[Dict[str, Any]]]
    created_at: datetime


class StreamChunk(BaseModel):
    """Individual chunk in streaming response"""
    
    type: str = Field(..., description="Chunk type: 'content', 'tool_call', 'error', etc.")
    content: Optional[str] = Field(None, description="Content for this chunk")
    
    # Tool call metadata (when type='tool_call')
    tool_name: Optional[str] = Field(None, description="Name of tool being called")
    tool_input: Optional[Dict[str, Any]] = Field(None, description="Tool input parameters")
    tool_output: Optional[str] = Field(None, description="Tool execution result")
    
    # LLM metadata
    provider: Optional[str] = Field(None, description="LLM provider")
    model: Optional[str] = Field(None, description="LLM model")
    
    # Error information (when type='error')
    error: Optional[str] = Field(None, description="Error message")


class BotSourceCreate(BaseModel):
    """Request to create a new source for a bot"""
    name: str = Field(..., description="Display name for the source")
    server_type: Literal["CUSTOM_SSE", "DIRECT_SSE", "WEBSOCKET"] = Field(..., description="Type of MCP server")
    server_url: str = Field(..., description="Base URL of the MCP server")
    credentials: Dict[str, str] = Field(..., description="Credential fields")
    description: Optional[str] = None
    instructions: Optional[str] = None  # Instructions for how this source should be used


class BotCreate(BaseModel):
    """Request to create a new bot with dedicated sources"""
    name: str = Field(..., description="Display name for the bot")
    description: Optional[str] = None
    sources: List[BotSourceCreate] = Field(..., description="List of sources to create for this bot")
    is_public: bool = Field(default=False, description="Whether the bot is publicly accessible")
    allowed_user_ids: Optional[List[UUID]] = Field(default=None, description="User IDs allowed to access this bot (if not public)")


class BotSourceUpdate(BaseModel):
    """Request to update or add a source to a bot"""
    source_id: Optional[UUID] = None  # If provided, update existing source
    name: str = Field(..., description="Display name for the source")
    server_type: Literal["CUSTOM_SSE", "DIRECT_SSE", "WEBSOCKET"] = Field(..., description="Type of MCP server")
    server_url: str = Field(..., description="Base URL of the MCP server")
    credentials: Optional[Dict[str, str]] = None  # Optional for existing sources
    description: Optional[str] = None
    instructions: Optional[str] = None


class BotUpdate(BaseModel):
    """Request to update a bot"""
    name: Optional[str] = None
    description: Optional[str] = None
    is_public: Optional[bool] = None
    allowed_user_ids: Optional[List[UUID]] = None
    sources: Optional[List[BotSourceUpdate]] = None  # Allow updating sources


class BotResponse(BaseModel):
    """Bot information response"""
    bot_id: UUID
    name: str
    description: Optional[str]
    source_ids: List[UUID]  # Keep for backward compatibility
    created_by_admin_id: UUID
    is_public: bool
    allowed_user_ids: List[UUID]
    created_at: datetime
    updated_at: Optional[datetime]


class ErrorResponse(BaseModel):
    """Error response model"""
    
    error: str = Field(..., description="Error message")
    error_type: Optional[str] = Field(None, description="Error type")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")


class SourceCreate(BaseModel):
    """Request to create a new source"""
    name: str = Field(..., description="Display name for the source")
    server_type: Literal["CUSTOM_SSE", "DIRECT_SSE", "WEBSOCKET"] = Field(..., description="Type of MCP server")
    server_url: str = Field(..., description="Base URL of the MCP server")
    credentials: Dict[str, str] = Field(..., description="Credential fields")
    description: Optional[str] = None
    instructions: Optional[str] = None  # Instructions for bot usage


class SourceResponse(BaseModel):
    """Source information response"""
    source_id: UUID
    name: str
    description: Optional[str]
    instructions: Optional[str]
    server_type: str
    server_url: str
    owner_user_id: Optional[UUID]
    owner_bot_id: Optional[UUID]
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]
    # Tool information
    tools_cache_status: Optional[str] = None  # "pending", "cached", "error", "caching"
    tools_last_cached_at: Optional[datetime] = None
    tools_cache_error: Optional[str] = None
    cached_tool_count: Optional[int] = None
    cached_tools: Optional[List[str]] = None  # List of tool names


class BotWithSourcesResponse(BotResponse):
    """Bot response with source details"""
    sources: List[SourceResponse]  # Full source information
    tool_count: Optional[int]
    user_has_access: bool


class ConversationCreate(BaseModel):
    """Request to create a new conversation"""
    title: Optional[str] = None


class ConversationResponse(BaseModel):
    """Conversation information response"""
    conversation_id: UUID
    user_id: UUID
    title: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]


class MessageCreate(BaseModel):
    """Request to create a new message"""
    content: str = Field(..., description="Message content")
    conversation_id: Optional[UUID] = Field(None, description="Conversation ID (optional for new conversations)")


class MessageResponse(BaseModel):
    """Message information response"""
    message_id: UUID
    conversation_id: UUID
    role: str
    content: str
    llm_provider: Optional[str]
    llm_model: Optional[str]
    tools_used: Optional[List[str]]
    citations: Optional[List[Dict[str, Any]]]
    created_at: datetime


class DeleteResponse(BaseModel):
    """Standard delete response"""
    message: str = "Resource deleted successfully"


class UserBotAccessResponse(BaseModel):
    """User bot access information"""
    user_id: UUID
    bot_id: UUID
    granted_at: datetime
    granted_by_admin_id: UUID


class HealthResponse(BaseModel):
    """Health check response"""
    status: str = "healthy"
    timestamp: datetime
    version: Optional[str] = None 
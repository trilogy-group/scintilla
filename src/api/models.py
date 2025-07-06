"""
Pydantic models for API requests and responses
"""

from typing import Optional, List, Dict, Any, Literal, Union
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime, timezone


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
    selectedBots: Optional[List[Dict[str, Any]]] = Field(None, description="Full bot objects for display purposes")
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


# Source configuration models
class BotSourceCreate(BaseModel):
    """Request to create a new source for a bot"""
    name: str = Field(..., description="Display name for the source")
    server_url: str = Field(..., description="Base URL of the MCP server")
    credentials: Dict[str, Any] = Field(..., description="Credential fields - can contain auth_headers object or other auth data")
    description: Optional[str] = None
    instructions: Optional[str] = None  # Instructions for how this source should be used


class BotSourceReference(BaseModel):
    """Reference to existing source with bot-specific instructions"""
    source_id: UUID = Field(..., description="Existing source to reference")
    custom_instructions: Optional[str] = Field(None, description="Bot-specific instructions for this source")


class BotSourceConfig(BaseModel):
    """Union type for bot source configuration"""
    type: Literal["create", "reference"] = Field(..., description="Whether to create new or reference existing")
    
    # For creating new source (when type="create")
    create_data: Optional[BotSourceCreate] = None
    
    # For referencing existing source (when type="reference")  
    reference_data: Optional[BotSourceReference] = None


# Enhanced bot models
class BotCreate(BaseModel):
    """Request to create a new bot with flexible source configuration"""
    name: str = Field(..., description="Display name for the bot")
    description: Optional[str] = None
    source_configs: List[BotSourceConfig] = Field(default=[], description="Mix of new sources and existing references")
    is_public: bool = Field(default=False, description="Whether the bot is publicly accessible")
    shared_with_users: Optional[List[UUID]] = Field(default=[], description="User IDs to share this bot with")
    
    # Legacy support for backward compatibility
    sources: Optional[List[BotSourceCreate]] = Field(None, description="Legacy: List of sources to create for this bot")


class BotSourceUpdate(BaseModel):
    """Request to update or add a source to a bot"""
    source_id: Optional[UUID] = None  # If provided, update existing source
    name: str = Field(..., description="Display name for the source")
    server_url: str = Field(..., description="Base URL of the MCP server")
    credentials: Optional[Dict[str, Any]] = None  # Optional for existing sources - can contain auth_headers object
    description: Optional[str] = None
    instructions: Optional[str] = None


class BotUpdate(BaseModel):
    """Request to update a bot"""
    name: Optional[str] = None
    description: Optional[str] = None
    is_public: Optional[bool] = None
    shared_with_users: Optional[List[UUID]] = None
    source_configs: Optional[List[BotSourceConfig]] = None  # New flexible source configuration
    
    # Legacy support
    sources: Optional[List[BotSourceUpdate]] = None  # Allow updating sources (legacy)


class BotResponse(BaseModel):
    """Bot information response"""
    bot_id: UUID
    name: str
    description: Optional[str]
    source_ids: List[UUID]  # Keep for backward compatibility
    created_by_user_id: UUID  # Changed from created_by_admin_id
    is_public: bool
    shared_with_users: List[UUID]  # Changed from allowed_user_ids for clarity
    created_at: datetime
    updated_at: Optional[datetime]


class BotSourceAssociationResponse(BaseModel):
    """Bot-source association with custom instructions"""
    source_id: UUID
    source_name: str
    custom_instructions: Optional[str]
    source_type: str  # "owned", "shared", "bot_owned"
    created_at: datetime
    # Tool information
    cached_tool_count: Optional[int] = None
    tools_cache_status: Optional[str] = None
    tools_last_cached_at: Optional[datetime] = None


# Source sharing models
class SourceShareCreate(BaseModel):
    """Request to share a source with users"""
    source_id: UUID = Field(..., description="Source to share")
    shared_with_user_ids: List[UUID] = Field(..., description="User IDs to share with")


class SourceShareResponse(BaseModel):
    """Source sharing information"""
    source_id: UUID
    source_name: str
    shared_with_user_id: UUID
    shared_with_user_name: str
    granted_by_user_id: UUID
    granted_by_user_name: str
    granted_at: datetime


class ErrorResponse(BaseModel):
    """Error response model"""
    
    error: str = Field(..., description="Error message")
    error_type: Optional[str] = Field(None, description="Error type")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")


class SourceCreate(BaseModel):
    """Request to create a new source"""
    name: str = Field(..., description="Display name for the source")
    server_url: str = Field(..., description="Base URL of the MCP server")
    credentials: Dict[str, Any] = Field(..., description="Credential fields - can contain auth_headers object or other auth data")
    description: Optional[str] = None
    instructions: Optional[str] = None  # Instructions for bot usage
    is_public: Optional[bool] = Field(default=False, description="Whether source is available to all users")
    shared_with_users: Optional[List[UUID]] = Field(default=[], description="User IDs to share this source with")


class SourceUpdate(BaseModel):
    """Request to update an existing source"""
    name: Optional[str] = Field(None, description="Display name for the source")
    description: Optional[str] = Field(None, description="Source description")
    instructions: Optional[str] = Field(None, description="Instructions for bot usage")
    server_url: Optional[str] = Field(None, description="Base URL of the MCP server")
    credentials: Optional[Dict[str, Any]] = Field(None, description="Credential fields - can contain auth_headers object or other auth data")
    is_public: Optional[bool] = Field(None, description="Whether source is available to all users")
    shared_with_users: Optional[List[UUID]] = Field(None, description="User IDs to share this source with")


class SourceResponse(BaseModel):
    """Source information response"""
    source_id: UUID
    name: str
    description: Optional[str]
    instructions: Optional[str]
    server_url: str
    owner_user_id: Optional[UUID]
    owner_bot_id: Optional[UUID]
    owner_type: Optional[str] = None  # "user", "bot", or None
    is_shared_with_user: Optional[bool] = None  # Whether current user has access via sharing
    is_public: bool = False  # Whether source is available to all users
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
    sources: List[SourceResponse]  # Full source information (legacy)
    source_associations: List[BotSourceAssociationResponse]  # New association-based sources
    tool_count: Optional[int]
    user_has_access: bool


class UserResponse(BaseModel):
    """User information response"""
    user_id: UUID
    email: str
    name: str
    picture_url: Optional[str]
    created_at: datetime


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
    selected_bots: Optional[List[Dict[str, Any]]] = None
    selected_sources: Optional[List[Dict[str, Any]]] = None
    created_at: datetime


class DeleteResponse(BaseModel):
    """Standard delete response"""
    message: str = "Resource deleted successfully"


class UserBotAccessResponse(BaseModel):
    """User bot access information"""
    user_id: UUID
    bot_id: UUID
    granted_at: datetime


class HealthResponse(BaseModel):
    """Health check response"""
    status: str = "healthy"
    timestamp: datetime
    version: Optional[str] = None


class RefreshResponse(BaseModel):
    """Response for tool refresh operations"""
    message: str = Field(..., description="Status message")
    tools_count: int = Field(..., description="Number of tools refreshed")
    timestamp: datetime = Field(..., description="Timestamp of refresh operation")


# Non-streaming query response
class QuerySyncResponse(BaseModel):
    """Non-streaming query response"""
    message_id: UUID
    conversation_id: UUID
    content: str
    llm_provider: Optional[str]
    llm_model: Optional[str]
    tools_used: Optional[List[str]]
    citations: Optional[List[Dict[str, Any]]]
    processing_stats: Optional[Dict[str, Any]]
    created_at: datetime


# Local Agent models
class AgentRegistration(BaseModel):
    """Model for agent registration - lightweight, just capabilities"""
    agent_id: str = Field(..., description="Unique identifier for the agent")
    name: str = Field(..., description="Human-readable name for the agent")
    capabilities: List[str] = Field(..., description="List of server/capability names this agent can handle")
    version: Optional[str] = Field(default=None, description="Agent version")
    user_id: Optional[str] = Field(default=None, description="User ID who registered this agent")
    last_ping: Optional[str] = Field(default=None, description="Last ping timestamp")


class AgentTask(BaseModel):
    """Task to be executed by a local agent"""
    task_id: str = Field(..., description="Unique task identifier")
    tool_name: str = Field(..., description="Tool to execute")
    arguments: Dict[str, Any] = Field(..., description="Tool arguments")
    timeout_seconds: int = Field(default=60, description="Task timeout in seconds")
    created_at: str = Field(..., description="Task creation timestamp")


class AgentTaskRequest(BaseModel):
    """Request to execute a task via local agents"""
    tool_name: str = Field(..., description="Tool to execute")
    arguments: Dict[str, Any] = Field(..., description="Tool arguments")
    timeout_seconds: Optional[int] = Field(default=60, description="Task timeout in seconds")


class AgentTaskResult(BaseModel):
    """Result of a task executed by a local agent"""
    task_id: str = Field(..., description="Task identifier")
    agent_id: str = Field(..., description="Agent that executed the task")
    success: bool = Field(..., description="Whether the task succeeded")
    result: Optional[str] = Field(None, description="Task result data")
    error: Optional[str] = Field(None, description="Error message if task failed")
    execution_time_ms: Optional[int] = Field(None, description="Task execution time in milliseconds")
    completed_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), description="Task completion timestamp")


class AgentPollResponse(BaseModel):
    """Response to agent polling for work"""
    has_work: bool = Field(..., description="Whether there is work available")
    task: Optional[AgentTask] = Field(None, description="Task to execute if available")


class AgentInfo(BaseModel):
    """Information about a registered agent"""
    agent_id: str
    name: str
    capabilities: List[str]
    active_tasks: int
    last_seen: Optional[str]


class AgentStatusResponse(BaseModel):
    """Status of the local agent system"""
    registered_agents: int = Field(..., description="Number of registered agents")
    pending_tasks: int = Field(..., description="Number of pending tasks")
    active_tasks: int = Field(..., description="Number of active tasks")
    agents: List[AgentInfo] = Field(..., description="List of registered agents")


class ToolRefreshRequest(BaseModel):
    """Request to refresh tools from a registered agent"""
    agent_id: str = Field(..., description="Agent ID to refresh tools from")
    capability: str = Field(..., description="Specific capability/server to refresh tools for")


class ToolRefreshResponse(BaseModel):
    """Response from tool refresh operation"""
    success: bool
    message: str
    tools_discovered: int
    capability: str
    agent_id: str


# Agent Token Management models
class AgentTokenCreate(BaseModel):
    """Request to create a new agent token"""
    name: Optional[str] = Field(default=None, description="Optional name for the token")
    expires_days: Optional[int] = Field(default=None, description="Optional expiration in days (default: no expiration)")


class AgentTokenResponse(BaseModel):
    """Response containing agent token information"""
    token_id: UUID
    name: Optional[str]
    token_prefix: str  # First 8 characters for display
    token: Optional[str] = Field(default=None, description="Full token (only shown once during creation)")
    last_used_at: Optional[datetime]
    expires_at: Optional[datetime]
    is_active: bool
    created_at: datetime


class AgentTokenListResponse(BaseModel):
    """List of user's agent tokens"""
    tokens: List[AgentTokenResponse]


# Add new simplified response models at the end of the file

class SimpleSource(BaseModel):
    """Simplified source for the new response format"""
    title: str = Field(..., description="Source title")
    url: str = Field(..., description="Source URL")


class SimpleQueryResponse(BaseModel):
    """Simplified query response format with inline markdown links"""
    answer: str = Field(..., description="Answer with inline markdown links")
    sources: List[SimpleSource] = Field(..., description="List of sources referenced in the answer") 
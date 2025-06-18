"""
Pydantic models for API requests and responses
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from uuid import UUID


class QueryRequest(BaseModel):
    """Request model for the main query endpoint"""
    
    message: str = Field(..., description="User's query message")
    conversation_id: Optional[UUID] = Field(None, description="Existing conversation ID")
    bot_ids: List[UUID] = Field(default_factory=list, description="Bot IDs to use for tools")
    use_user_sources: bool = Field(default=True, description="Whether to include user's personal sources")
    
    # Query mode and behavior
    mode: str = Field(default="conversational", description="Query mode: 'conversational' or 'search'")
    require_sources: bool = Field(default=True, description="Require evidence from multiple sources")
    min_sources: int = Field(default=2, description="Minimum number of sources to search")
    search_depth: str = Field(default="thorough", description="Search depth: 'quick', 'thorough', 'exhaustive'")
    
    # LLM configuration
    llm_provider: Optional[str] = Field(None, description="LLM provider: 'openai' or 'anthropic'")
    llm_model: Optional[str] = Field(None, description="Specific model to use")
    
    # Optional settings
    stream: bool = Field(True, description="Whether to stream the response")


class QueryResponse(BaseModel):
    """Response model for successful query"""
    
    conversation_id: UUID = Field(..., description="Conversation ID")
    message_id: int = Field(..., description="Message ID")
    content: str = Field(..., description="Response content")
    
    # LLM metadata
    llm_provider: str = Field(..., description="LLM provider used")
    llm_model: str = Field(..., description="Model used")
    
    # Tool usage
    tools_used: List[str] = Field(default_factory=list, description="Names of tools used")
    citations: Optional[List[Dict[str, Any]]] = Field(None, description="Source citations")


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


class BotCreate(BaseModel):
    """Request model for creating a bot"""
    
    display_name: str = Field(..., description="Bot display name")
    description: Optional[str] = Field(None, description="Bot description")
    is_public: bool = Field(False, description="Whether bot is public")


class BotEndpointCreate(BaseModel):
    """Request model for adding an MCP endpoint to a bot"""
    
    mcp_url: str = Field(..., description="Full MCP URL with API key")
    name: Optional[str] = Field(None, description="Friendly name for endpoint")
    description: Optional[str] = Field(None, description="Endpoint description")


class BotResponse(BaseModel):
    """Response model for bot information"""
    
    bot_id: UUID = Field(..., description="Bot ID")
    display_name: str = Field(..., description="Bot display name")
    description: Optional[str] = Field(None, description="Bot description")
    is_public: bool = Field(..., description="Whether bot is public")
    owner_email: str = Field(..., description="Bot owner email")
    
    # Endpoint information
    endpoint_count: int = Field(..., description="Number of MCP endpoints")
    tool_count: Optional[int] = Field(None, description="Total number of tools available")
    
    # Timestamps
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: Optional[str] = Field(None, description="Last update timestamp")


class BotEndpointResponse(BaseModel):
    """Response model for bot endpoint information"""
    
    endpoint_id: UUID = Field(..., description="Endpoint ID")
    bot_id: UUID = Field(..., description="Bot ID")
    sse_url: str = Field(..., description="SSE URL (without API key)")
    name: Optional[str] = Field(None, description="Endpoint name")
    description: Optional[str] = Field(None, description="Endpoint description")
    
    # Health status
    is_active: bool = Field(..., description="Whether endpoint is active")
    is_healthy: Optional[bool] = Field(None, description="Health check status")
    last_health_check: Optional[str] = Field(None, description="Last health check time")
    health_error: Optional[str] = Field(None, description="Last health error")
    
    # Tool information
    tool_count: Optional[int] = Field(None, description="Number of tools available")
    tools: Optional[List[str]] = Field(None, description="Available tool names")


class ToolStatus(BaseModel):
    """Status of MCP tools and servers"""
    
    total_tools: int = Field(..., description="Total number of tools available")
    server_count: int = Field(..., description="Number of MCP servers")
    healthy_servers: int = Field(..., description="Number of healthy servers")
    
    tools: List[Dict[str, Any]] = Field(..., description="Tool information")
    servers: List[Dict[str, Any]] = Field(..., description="Server status")


class ErrorResponse(BaseModel):
    """Error response model"""
    
    error: str = Field(..., description="Error message")
    error_type: Optional[str] = Field(None, description="Error type")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details") 
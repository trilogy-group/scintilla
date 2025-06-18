"""
MCP (Model Context Protocol) client for SSE communication

Handles:
- Tool discovery via tools/list
- Tool execution via tools/call  
- SSE connection management
- Error handling and retries
"""

import asyncio
import json
import uuid
from typing import Dict, List, Optional, Any, AsyncGenerator
from dataclasses import dataclass, field
import httpx
import structlog
from urllib.parse import urljoin

logger = structlog.get_logger()


@dataclass
class MCPTool:
    """Represents an MCP tool"""
    name: str
    description: str
    inputSchema: Dict[str, Any]
    server_url: str
    server_id: Optional[str] = None


@dataclass 
class MCPServer:
    """Represents an MCP server connection"""
    base_url: str
    api_key: str
    server_id: Optional[str] = None
    is_healthy: bool = False
    tools: List[MCPTool] = field(default_factory=list)
    last_error: Optional[str] = None


class MCPClient:
    """Client for communicating with MCP servers via SSE"""
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.servers: Dict[str, MCPServer] = {}
        
    async def add_server(self, base_url: str, api_key: str, server_id: Optional[str] = None) -> str:
        """
        Add an MCP server to the client
        
        Args:
            base_url: Base SSE URL (without API key)
            api_key: API key for authentication
            server_id: Optional server identifier
            
        Returns:
            Server key for future reference
        """
        server_key = server_id or f"server_{len(self.servers)}"
        server = MCPServer(
            base_url=base_url,
            api_key=api_key,
            server_id=server_id
        )
        
        self.servers[server_key] = server
        
        # Test connection and discover tools
        await self._health_check(server_key)
        if server.is_healthy:
            await self._discover_tools(server_key)
            
        return server_key
    
    async def _health_check(self, server_key: str) -> bool:
        """Check if MCP server is responsive using legacy SSE transport"""
        server = self.servers.get(server_key)
        if not server:
            return False
            
        try:
            # Try to establish SSE connection to test connectivity
            message_endpoint = await self._establish_sse_connection(server)
            
            if message_endpoint:
                server.is_healthy = True
                server.last_error = None
                server.message_endpoint = message_endpoint
                
                logger.info(
                    "MCP server health check passed",
                    server_key=server_key,
                    url=server.base_url,
                    message_endpoint=message_endpoint,
                    healthy=True
                )
                
                return True
            else:
                server.is_healthy = False
                server.last_error = "Failed to get message endpoint"
                
                logger.warning(
                    "MCP server health check failed",
                    server_key=server_key,
                    url=server.base_url,
                    error="No message endpoint received"
                )
                
                return False
                
        except Exception as e:
            server.is_healthy = False
            server.last_error = str(e)
            logger.error(
                "MCP server health check failed",
                server_key=server_key,
                url=server.base_url,
                error=str(e)
            )
            return False
    
    async def _discover_tools(self, server_key: str) -> List[MCPTool]:
        """Discover available tools from MCP server"""
        server = self.servers.get(server_key)
        if not server or not server.is_healthy:
            return []
            
        try:
            tools = await self._call_mcp_method(server_key, "tools/list", {})
            
            if tools and "tools" in tools:
                server.tools = [
                    MCPTool(
                        name=tool["name"],
                        description=tool["description"],
                        inputSchema=tool["inputSchema"],
                        server_url=server.base_url,
                        server_id=server.server_id
                    )
                    for tool in tools["tools"]
                ]
                
                logger.info(
                    "Discovered MCP tools",
                    server_key=server_key,
                    tool_count=len(server.tools),
                    tool_names=[tool.name for tool in server.tools]
                )
            
            return server.tools
            
        except Exception as e:
            logger.error(
                "Failed to discover tools",
                server_key=server_key,
                error=str(e)
            )
            return []
    
    async def _establish_sse_connection(self, server: MCPServer) -> Optional[str]:
        """
        Establish SSE connection and get message endpoint
        
        Returns:
            Message endpoint URL or None if failed
        """
        # Construct SSE URL with API key
        sse_url = f"{server.base_url}?x-api-key={server.api_key}"
        
        try:
            import asyncio
            
            async with httpx.AsyncClient(timeout=10) as client:  # Shorter timeout for connection
                async with client.stream(
                    "GET",
                    sse_url,
                    headers={"Accept": "text/event-stream"}
                ) as response:
                    response.raise_for_status()
                    
                    # Parse SSE stream to get endpoint with timeout
                    lines_iter = response.aiter_lines()
                    
                    # Wait max 5 seconds for endpoint event
                    try:
                        # Use asyncio.wait_for for broader Python compatibility
                        async def read_endpoint():
                            async for line in lines_iter:
                                logger.debug(f"SSE line: '{line}'")
                                
                                if line.startswith("event: endpoint"):
                                    # Next line should contain the endpoint URL
                                    try:
                                        data_line = await lines_iter.__anext__()
                                        logger.debug(f"Data line: '{data_line}'")
                                        
                                        if data_line.startswith("data: "):
                                            endpoint_path = data_line[6:].strip()
                                            logger.debug(f"Endpoint path: '{endpoint_path}'")
                                            
                                            # Construct full message endpoint URL
                                            from urllib.parse import urljoin, urlparse
                                            parsed = urlparse(server.base_url)
                                            base_url = f"{parsed.scheme}://{parsed.netloc}"
                                            
                                            # Handle both absolute and relative URLs
                                            if endpoint_path.startswith('http'):
                                                message_url = endpoint_path
                                            else:
                                                message_url = urljoin(base_url, endpoint_path)
                                            
                                            logger.info(
                                                "Got MCP message endpoint",
                                                server_url=server.base_url,
                                                base_url=base_url,
                                                endpoint_path=endpoint_path,
                                                message_endpoint=message_url
                                            )
                                            return message_url
                                    except StopAsyncIteration:
                                        logger.warning("No data line after endpoint event")
                                        break
                                
                                # Handle ping messages
                                if line.startswith(": ping"):
                                    logger.debug("Received ping message")
                                    continue
                                    
                                # Also handle empty lines or other events
                                if line.strip() == "":
                                    continue
                                    
                            return None
                        
                        result = await asyncio.wait_for(read_endpoint(), timeout=5.0)
                        if result:
                            return result
                                    
                    except asyncio.TimeoutError:
                        logger.warning("Timeout waiting for endpoint event")
                        return None
                            
        except Exception as e:
            logger.error(
                "Failed to establish SSE connection",
                server_url=server.base_url,
                error=str(e)
            )
            return None
        
        return None

    async def _call_mcp_method(self, server_key: str, method: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Call an MCP method using legacy SSE transport
        
        Args:
            server_key: Server identifier
            method: MCP method name (e.g., "tools/list", "tools/call")
            params: Method parameters
            
        Returns:
            Response data or None if failed
        """
        server = self.servers.get(server_key)
        if not server:
            raise ValueError(f"Server {server_key} not found")
            
        # Get or establish message endpoint
        if not hasattr(server, 'message_endpoint'):
            message_endpoint = await self._establish_sse_connection(server)
            if not message_endpoint:
                return None
            server.message_endpoint = message_endpoint
        
        request_id = str(uuid.uuid4())
        request_data = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params
        }
        
        logger.debug(
            "Calling MCP method via legacy SSE",
            server_key=server_key,
            method=method,
            request_id=request_id,
            endpoint=server.message_endpoint
        )
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # POST to message endpoint with API key in URL
                # Add API key to the message endpoint URL
                from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
                parsed = urlparse(server.message_endpoint)
                query_params = parse_qs(parsed.query)
                query_params['x-api-key'] = [server.api_key]
                new_query = urlencode(query_params, doseq=True)
                message_url = urlunparse((
                    parsed.scheme, parsed.netloc, parsed.path,
                    parsed.params, new_query, parsed.fragment
                ))
                
                logger.debug(
                    "Posting to message endpoint",
                    server_key=server_key,
                    message_url=message_url,
                    method=method
                )
                
                response = await client.post(
                    message_url,
                    json=request_data,
                    headers={
                        "Content-Type": "application/json"
                    }
                )
                
                logger.debug(
                    "MCP method response",
                    server_key=server_key,
                    status_code=response.status_code,
                    response_headers=dict(response.headers)
                )
                
                if response.status_code == 200:
                    response_data = response.json()
                    logger.info(
                        "MCP method call successful",
                        server_key=server_key,
                        method=method,
                        response_data=response_data
                    )
                    return response_data
                else:
                    response_text = response.text
                    logger.error(
                        "MCP method call failed",
                        server_key=server_key,
                        status_code=response.status_code,
                        response_text=response_text
                    )
                    return None
                    
        except Exception as e:
            logger.error(
                "MCP method call failed",
                server_key=server_key,
                method=method,
                error=str(e)
            )
            return None
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Call a specific tool across all servers
        
        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments
            
        Returns:
            Tool result or None if failed
        """
        # Find which server has this tool
        for server_key, server in self.servers.items():
            for tool in server.tools:
                if tool.name == tool_name:
                    return await self._call_tool_on_server(server_key, tool_name, arguments)
                    
        logger.warning(f"Tool {tool_name} not found on any server")
        return None
    
    async def _call_tool_on_server(self, server_key: str, tool_name: str, arguments: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Call a tool on a specific server"""
        try:
            result = await self._call_mcp_method(
                server_key,
                "tools/call",
                {
                    "name": tool_name,
                    "arguments": arguments
                }
            )
            
            logger.info(
                "Tool called successfully",
                server_key=server_key,
                tool_name=tool_name,
                has_result=result is not None
            )
            
            return result
            
        except Exception as e:
            logger.error(
                "Tool call failed",
                server_key=server_key,
                tool_name=tool_name,
                error=str(e)
            )
            return None
    
    def get_all_tools(self) -> List[MCPTool]:
        """Get all available tools from all servers"""
        all_tools = []
        for server in self.servers.values():
            all_tools.extend(server.tools)
        return all_tools
    
    def get_server_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all servers"""
        return {
            server_key: {
                "url": server.base_url,
                "healthy": server.is_healthy,
                "tool_count": len(server.tools),
                "last_error": server.last_error
            }
            for server_key, server in self.servers.items()
        } 
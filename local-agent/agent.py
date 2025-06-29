#!/usr/bin/env python3
"""
Scintilla Local Agent

A local agent that manages Docker-based MCP servers, communicates with them
via stdio using the MCP protocol, and acts as a bridge to Scintilla server.
"""

import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from uuid import uuid4
import signal
import subprocess

import aiohttp
import yaml
from pydantic import BaseModel

# Configuration Models
class AgentConfig(BaseModel):
    """Agent configuration"""
    agent_id: str
    server_url: str
    agent_token: str = ""  # Agent authentication token
    capabilities: List[str]
    poll_interval: float = 2.0
    mcp_servers_config: str = "mcp_servers.yaml"
    log_level: str = "INFO"
    docker_timeout: int = 30
    
    # Retry and reliability configuration
    max_retry_attempts: int = 5
    initial_retry_delay: float = 1.0
    retry_backoff_multiplier: float = 2.0
    max_retry_delay: float = 60.0
    health_check_interval: float = 30.0
    connection_timeout: float = 10.0

class MCPServerConfig(BaseModel):
    """MCP Server configuration"""
    name: str
    image: str
    tag: str = "latest"
    environment: Dict[str, str] = {}
    volumes: Dict[str, str] = {}
    capabilities: List[str] = []
    auto_start: bool = True

class MCPRequest(BaseModel):
    """MCP protocol request"""
    jsonrpc: str = "2.0"
    id: Union[str, int]
    method: str
    params: Optional[Dict[str, Any]] = None

class MCPResponse(BaseModel):
    """MCP protocol response"""
    jsonrpc: str = "2.0"
    id: Union[str, int]
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None

class DockerMCPServer:
    """Manages a single Docker-based MCP server"""
    
    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        self.name = config['name']
        self.image = config['image']
        self.tag = config.get('tag', 'latest')
        self.environment = config.get('environment', {})
        self.volumes = config.get('volumes', {})
        self.process = None
        self.stdin = None
        self.stdout = None
        self.logger = logger
        self.tools = []  # Keep tools list for compatibility
        
    async def start(self):
        """Start the MCP server in interactive Docker container"""
        # Build Docker command based on official mcp-atlassian documentation
        cmd = [
            'docker', 'run', '--rm', '-i',
        ]
        
        # Add environment variables
        for key, value in self.environment.items():
            cmd.extend(['-e', key])
        
        # Add the image
        cmd.append(f"{self.image}:{self.tag}")
        
        # Add specific arguments for mcp-atlassian (Server/Data Center)
        if 'atlassian' in self.name.lower():
            cmd.extend(['--transport', 'stdio'])
            # Add verbose flag for debugging
            cmd.append('-v')
        
        self.logger.info(f"Starting Docker container with command: {' '.join(cmd)}")
        
        # Create environment for the process
        env = os.environ.copy()
        env.update(self.environment)
        
        try:
            # Start the process with interactive stdin/stdout
            self.process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            
            self.stdin = self.process.stdin
            self.stdout = self.process.stdout
            
            self.logger.info(f"Docker container {self.name} started successfully (PID: {self.process.pid})")
            
            # Initialize MCP connection
            await self._initialize_mcp()
            
        except Exception as e:
            self.logger.error(f"Failed to start Docker container {self.name}: {e}")
            raise
    
    async def _initialize_mcp(self):
        """Initialize MCP connection and discover capabilities"""
        try:
            # Send MCP initialization
            init_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "clientInfo": {
                        "name": "scintilla-local-agent",
                        "version": "1.0.0"
                    }
                }
            }
            
            await self._send_message(init_request)
            response = await self._receive_message()
            self.logger.info(f"MCP initialized for {self.name}: {response}")
            
            # Send initialized notification
            initialized_notification = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized"
            }
            
            await self._send_message(initialized_notification)
            
            # Discover tools
            await self._discover_tools()
            
        except Exception as e:
            self.logger.error(f"Failed to initialize MCP for {self.name}: {e}")
            raise
    
    async def _discover_tools(self):
        """Discover available tools from the MCP server"""
        try:
            # Request tools list - use proper MCP protocol format
            tools_request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list"
                # Note: No params field for basic tools/list according to MCP spec
            }
            
            await self._send_message(tools_request)
            response = await self._receive_message()
            
            if response and "result" in response:
                self.tools = response["result"].get("tools", [])
                self.logger.info(f"Discovered {len(self.tools)} tools for {self.name}")
                for tool in self.tools[:5]:  # Log first 5 tools
                    self.logger.info(f"  - {tool.get('name', 'unknown')}: {tool.get('description', 'no description')}")
            else:
                self.logger.warning(f"No tools discovered for {self.name}: {response}")
                
        except Exception as e:
            self.logger.error(f"Failed to discover tools for {self.name}: {e}")
            # Don't raise - tools discovery failure shouldn't stop the server
    
    async def _send_message(self, message: Dict[str, Any]):
        """Send JSON-RPC message to MCP server"""
        if not self.stdin:
            raise RuntimeError(f"Docker container {self.name} not started")
        
        json_str = json.dumps(message)
        self.logger.debug(f"Sending to {self.name}: {json_str}")
        
        self.stdin.write(f"{json_str}\n".encode('utf-8'))
        await self.stdin.drain()
    
    async def _receive_message(self) -> Dict[str, Any]:
        """Receive JSON-RPC message from MCP server"""
        if not self.stdout:
            raise RuntimeError(f"Docker container {self.name} not started")
        
        try:
            # Read line from stdout
            line = await self.stdout.readline()
            if not line:
                raise RuntimeError(f"MCP server {self.name} closed connection")
            
            json_str = line.decode('utf-8').strip()
            self.logger.debug(f"Received from {self.name}: {json_str}")
            
            if not json_str:
                return {}
            
            return json.loads(json_str)
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON from {self.name}: {e}")
            return {}
        except Exception as e:
            self.logger.error(f"Failed to receive message from {self.name}: {e}")
            raise
    
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool on the MCP server"""
        try:
            request = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": name,
                    "arguments": arguments
                }
            }
            
            await self._send_message(request)
            response = await self._receive_message()
            
            if "error" in response:
                self.logger.error(f"Tool call error for {name}: {response['error']}")
                return {"error": response["error"]}
            
            return response.get("result", {})
            
        except Exception as e:
            self.logger.error(f"Failed to call tool {name} on {self.name}: {e}")
            return {"error": str(e)}
    
    # Compatibility method for existing code
    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool on this MCP server (compatibility method)"""
        result = await self.call_tool(tool_name, parameters)
        if "error" in result:
            return {
                "success": False,
                "error": result["error"]
            }
        return {
            "success": True,
            "result": result
        }
    
    async def stop(self):
        """Stop the Docker container"""
        if self.process:
            try:
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self.logger.warning(f"Force killing Docker container {self.name}")
                self.process.kill()
                await self.process.wait()
            finally:
                self.process = None
                self.stdin = None
                self.stdout = None
                self.logger.info(f"Docker container {self.name} stopped")

class ScintillaLocalAgent:
    """Local agent that manages Docker-based MCP servers"""
    
    def __init__(self):
        self.config = None
        self.mcp_servers: Dict[str, DockerMCPServer] = {}
        self.task_queue = asyncio.Queue()
        self.running = False
        self.session = None
        
        # Connection state tracking
        self.is_registered = False
        self.is_connected = False
        self.consecutive_failures = 0
        self.last_successful_poll = None
        self.last_registration_attempt = None
        
        # Configuration paths
        self.config_path = Path(__file__).parent / "config.yaml"
        self.mcp_config_path = Path(__file__).parent / "mcp_servers.yaml"
        
        # Setup logging
        self.logger = self._setup_logging()
        
    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration"""
        logger = logging.getLogger("scintilla_agent")
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
        return logger
        
    async def load_config(self) -> None:
        """Load agent configuration from YAML file"""
        try:
            with open(self.config_path, 'r') as f:
                config_data = yaml.safe_load(f)
                self.config = AgentConfig(**config_data)
                
            # Update log level
            self.logger.setLevel(getattr(logging, self.config.log_level.upper()))
            self.logger.info(f"Loaded config for agent {self.config.agent_id}")
            
        except FileNotFoundError:
            self.logger.error(f"Config file not found: {self.config_path}")
            raise
        except Exception as e:
            self.logger.error(f"Failed to load config: {e}")
            raise
            
    async def _load_mcp_servers(self):
        """Load and start MCP servers from configuration"""
        try:
            with open(self.mcp_config_path, 'r') as f:
                config_data = yaml.safe_load(f)
            
            servers_config = config_data.get('servers', [])
            
            for server_config in servers_config:
                if not server_config.get('auto_start', True):
                    self.logger.info(f"⏸️ Skipping disabled server: {server_config['name']}")
                    continue
                
                try:
                    self.logger.info(f"🚀 Loading MCP server: {server_config['name']}")
                    
                    # Create MCP server with the dictionary config directly
                    mcp_server = DockerMCPServer(server_config, self.logger)
                    
                    # Start the server
                    await mcp_server.start()
                    
                    # Add to our registry
                    self.mcp_servers[server_config['name']] = mcp_server
                    
                    # Register capabilities with Scintilla
                    await self._register_capabilities(server_config['name'], server_config.get('capabilities', []))
                    
                    self.logger.info(f"✅ Successfully loaded {server_config['name']}")
                    
                except Exception as e:
                    self.logger.error(f"❌ Failed to load MCP server {server_config['name']}: {e}")
                    continue
            
            self.logger.info(f"📋 Loaded {len(self.mcp_servers)} MCP servers")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to load MCP servers configuration: {e}")
            raise
    
    async def _register_capabilities(self, server_name: str, capabilities: List[str]) -> None:
        """Register capabilities for a specific MCP server"""
        self.logger.debug(f"Registering capabilities for {server_name}: {capabilities}")
        # This is a placeholder - capabilities are collected during server registration
        # and sent to the main Scintilla server in register_with_server()
            
    async def register_with_server(self) -> bool:
        """Register this agent with the Scintilla server"""
        try:
            # Check if agent token is configured
            if not self.config.agent_token:
                self.logger.error("❌ No agent token configured. Generate one from the web UI at /api/agent-tokens")
                return False
            
            # Just register basic capabilities for MCP servers this agent can handle
            # Tools will be discovered separately via the refresh-tools endpoint
            server_capabilities = []
            for server_name in self.mcp_servers.keys():
                server_capabilities.append(server_name)
            
            # Combine with general capabilities from config
            combined_capabilities = list(set(server_capabilities + self.config.capabilities))
                    
            registration_data = {
                "agent_id": self.config.agent_id,
                "name": f"Local Agent {self.config.agent_id}",
                "capabilities": combined_capabilities,
                "version": "1.0.0"
            }
            
            # Prepare headers with agent token
            headers = {
                "Authorization": f"Bearer {self.config.agent_token}",
                "Content-Type": "application/json"
            }
            
            self.logger.info(f"Registering with {len(combined_capabilities)} capabilities: {combined_capabilities}")
            
            async with self.session.post(
                f"{self.config.server_url}/api/agents/register",
                json=registration_data,
                headers=headers
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    self.logger.info(f"Successfully registered with server: {result}")
                    return True
                else:
                    error_text = await response.text()
                    self.logger.error(f"Registration failed ({response.status}): {error_text}")
                    return False
                    
        except Exception as e:
            self.logger.error(f"Registration error: {e}")
            return False
            
    async def poll_for_work(self) -> Optional[Dict[str, Any]]:
        """Poll the server for work"""
        try:
            async with self.session.post(
                f"{self.config.server_url}/api/agents/poll/{self.config.agent_id}"
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("has_work"):
                        self.logger.info(f"📥 Received task: {result['task']['task_id']} - {result['task']['tool_name']}")
                        return result["task"]
                    return None
                elif response.status != 204:  # 204 is expected for no work
                    error_text = await response.text()
                    self.logger.warning(f"Poll failed ({response.status}): {error_text}")
                    return None
                else:
                    return None
                    
        except Exception as e:
            self.logger.error(f"Polling error: {e}")
            return None
            
    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool on the appropriate MCP server"""
        # Find which MCP server has this tool
        for server_name, mcp_server in self.mcp_servers.items():
            if any(tool.get("name") == tool_name for tool in mcp_server.tools):
                self.logger.info(f"🔧 Executing {tool_name} on {server_name}")
                return await mcp_server.call_tool(tool_name, parameters)
                
        return {
            "success": False,
            "error": f"Tool '{tool_name}' not found on any MCP server",
            "available_tools": [
                {"tool": tool.get("name", "unknown"), "server": server_name}
                for server_name, mcp_server in self.mcp_servers.items()
                for tool in mcp_server.tools
            ]
        }
        
    async def submit_result(self, task_id: str, result: Dict[str, Any]) -> bool:
        """Submit task result back to server"""
        try:
            # Check if this is already in AgentTaskResult format (for discovery tasks)
            if "success" in result and isinstance(result.get("success"), bool):
                # This is already in the right format (discovery task result)
                result_data = {
                    "task_id": task_id,
                    "agent_id": self.config.agent_id,
                    "success": result["success"],
                    "result": json.dumps(result["result"]) if result.get("result") else None,
                    "error": result.get("error"),
                    "execution_time_ms": None
                }
            elif "error" in result:
                # Tool execution failed
                result_data = {
                    "task_id": task_id,
                    "agent_id": self.config.agent_id,
                    "success": False,
                    "result": None,
                    "error": str(result["error"]),
                    "execution_time_ms": None
                }
            elif "isError" in result and result["isError"]:
                # MCP returned an error result
                error_text = "Unknown error"
                if "content" in result and result["content"]:
                    for content in result["content"]:
                        if content.get("type") == "text":
                            error_text = content.get("text", "Unknown error")
                            break
                
                result_data = {
                    "task_id": task_id,
                    "agent_id": self.config.agent_id,
                    "success": False,
                    "result": None,
                    "error": error_text,
                    "execution_time_ms": None
                }
            else:
                # Tool execution succeeded
                result_text = ""
                if "content" in result and result["content"]:
                    for content in result["content"]:
                        if content.get("type") == "text":
                            result_text += content.get("text", "")
                else:
                    result_text = str(result)
                
                result_data = {
                    "task_id": task_id,
                    "agent_id": self.config.agent_id,
                    "success": True,
                    "result": result_text,
                    "error": None,
                    "execution_time_ms": None
                }
            
            # Prepare headers with agent token
            headers = {
                "Authorization": f"Bearer {self.config.agent_token}",
                "Content-Type": "application/json"
            }
            
            async with self.session.post(
                f"{self.config.server_url}/api/agents/results/{task_id}",
                json=result_data,
                headers=headers
            ) as response:
                if response.status == 200:
                    self.logger.info(f"📤 Result submitted for task {task_id}")
                    return True
                else:
                    error_text = await response.text()
                    self.logger.error(f"Result submission failed ({response.status}): {error_text}")
                    return False
                    
        except Exception as e:
            self.logger.error(f"Result submission error: {e}")
            return False
    
    def _calculate_retry_delay(self, attempt: int) -> float:
        """Calculate retry delay with exponential backoff"""
        delay = self.config.initial_retry_delay * (self.config.retry_backoff_multiplier ** attempt)
        return min(delay, self.config.max_retry_delay)
    
    async def _retry_with_backoff(self, operation_name: str, operation_func, *args, **kwargs):
        """Execute an operation with exponential backoff retry logic"""
        for attempt in range(self.config.max_retry_attempts):
            try:
                result = await operation_func(*args, **kwargs)
                if result:  # Success
                    if attempt > 0:
                        self.logger.info(f"🔄 {operation_name} succeeded after {attempt + 1} attempts")
                    self.consecutive_failures = 0
                    return result
            except Exception as e:
                self.logger.warning(f"⚠️ {operation_name} attempt {attempt + 1} failed: {e}")
            
            # If this wasn't the last attempt, wait before retrying
            if attempt < self.config.max_retry_attempts - 1:
                delay = self._calculate_retry_delay(attempt)
                self.logger.info(f"⏳ Waiting {delay:.1f}s before retry {attempt + 2}/{self.config.max_retry_attempts}")
                await asyncio.sleep(delay)
        
        # All attempts failed
        self.consecutive_failures += 1
        self.logger.error(f"❌ {operation_name} failed after {self.config.max_retry_attempts} attempts")
        return False
    
    async def _register_with_retry(self) -> bool:
        """Register with server with retry logic"""
        self.logger.info("📡 Attempting registration with retry logic...")
        
        async def _do_registration():
            return await self.register_with_server()
        
        success = await self._retry_with_backoff("Registration", _do_registration)
        
        if success:
            self.is_registered = True
            self.is_connected = True
            self.last_registration_attempt = time.time()
            self.logger.info("✅ Successfully registered with server")
        else:
            self.is_registered = False
            self.is_connected = False
            self.logger.error("❌ Failed to register with server after all retries")
        
        return success
    
    async def _check_server_health(self) -> bool:
        """Check if server is responding"""
        try:
            timeout = aiohttp.ClientTimeout(total=self.config.connection_timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"{self.config.server_url}/health") as response:
                    return response.status == 200
        except Exception as e:
            self.logger.debug(f"Health check failed: {e}")
            return False
    
    async def _handle_connection_loss(self):
        """Handle connection loss and attempt reconnection"""
        self.is_connected = False
        self.is_registered = False
        
        self.logger.warning("🔌 Connection lost to server, attempting reconnection...")
        
        # Wait for server to be healthy again
        while self.running:
            if await self._check_server_health():
                self.logger.info("🔄 Server is healthy, attempting re-registration...")
                
                # Recreate session if needed
                if not self.session or self.session.closed:
                    if self.session:
                        await self.session.close()
                    timeout = aiohttp.ClientTimeout(total=self.config.connection_timeout)
                    self.session = aiohttp.ClientSession(timeout=timeout)
                
                # Attempt re-registration
                if await self._register_with_retry():
                    self.logger.info("🎉 Successfully reconnected and re-registered!")
                    break
                else:
                    self.logger.error("❌ Re-registration failed, will retry health check...")
            
            # Wait before next health check
            await asyncio.sleep(self.config.health_check_interval)
    
    async def _poll_with_reliability(self) -> Optional[Dict[str, Any]]:
        """Poll for work with reliability handling"""
        try:
            task = await self.poll_for_work()
            
            # Update connection state on successful poll
            if task is not None or self.consecutive_failures == 0:
                self.last_successful_poll = time.time()
                if not self.is_connected:
                    self.is_connected = True
                    self.logger.info("🔗 Connection restored")
            
            return task
            
        except Exception as e:
            self.consecutive_failures += 1
            self.logger.warning(f"⚠️ Poll failed ({self.consecutive_failures} consecutive failures): {e}")
            
            # If we have too many consecutive failures, assume connection is lost
            if self.consecutive_failures >= 3:
                await self._handle_connection_loss()
            
            return None
            
    async def process_task(self, task: Dict[str, Any]) -> None:
        """Process a single task"""
        task_id = task["task_id"]
        tool_name = task["tool_name"]
        arguments = task.get("arguments", {})  # Changed from "parameters" to "arguments"
        
        self.logger.info(f"🏗️  Processing task {task_id}: {tool_name} with args: {arguments}")
        
        # Handle special discovery task
        if tool_name == "__discovery__":
            capability = arguments.get('capability')
            if not capability:
                result = {
                    "success": False,
                    "error": "Discovery task missing 'capability' argument"
                }
            else:
                # Return tools for the specific capability
                tools_for_capability = []
                for server_name, server_instance in self.mcp_servers.items():
                    if server_name == capability:
                        if hasattr(server_instance, 'tools') and server_instance.tools:
                            tools_for_capability = server_instance.tools
                        break
                
                result = {
                    "success": True,
                    "result": {
                        "capability": capability,
                        "tools": tools_for_capability
                    }
                }
            
            # Submit the discovery result
            await self.submit_result(task_id, result)
            return
        
        # Handle regular tool execution
        result = await self.execute_tool(tool_name, arguments)
        
        # Submit the result
        await self.submit_result(task_id, result)
        
    async def run_polling_loop(self) -> None:
        """Main polling loop with reliability features"""
        self.logger.info("🚀 Starting reliable polling loop...")
        
        while self.running:
            try:
                # Only poll if we're registered and connected
                if self.is_registered and self.is_connected:
                    # Poll for work with reliability handling
                    task = await self._poll_with_reliability()
                    
                    if task:
                        # Process the task
                        await self.process_task(task)
                    else:
                        # No work available, wait before next poll
                        await asyncio.sleep(self.config.poll_interval)
                else:
                    # Not connected, try to reconnect
                    self.logger.info("🔄 Not connected, attempting reconnection...")
                    await self._handle_connection_loss()
                    
            except Exception as e:
                self.logger.error(f"Error in polling loop: {e}")
                # If we get an unexpected error, assume connection issues
                await self._handle_connection_loss()
                
        self.logger.info("🛑 Reliable polling loop stopped")
        
    async def start(self) -> None:
        """Start the agent with reliability features"""
        try:
            # Load configuration
            await self.load_config()
            
            # Load and start MCP servers
            await self._load_mcp_servers()
            
            # Create HTTP session with timeout
            timeout = aiohttp.ClientTimeout(total=self.config.connection_timeout)
            self.session = aiohttp.ClientSession(timeout=timeout)
            
            # Register with server using retry logic
            if not await self._register_with_retry():
                raise Exception("Failed to register with server after all retries")
                
            # Start polling
            self.running = True
            await self.run_polling_loop()
            
        except Exception as e:
            self.logger.error(f"Agent startup failed: {e}")
            raise
        finally:
            await self.cleanup()
                
    async def cleanup(self) -> None:
        """Clean up resources"""
        self.logger.info("🧹 Cleaning up...")
        
        # Stop all MCP servers
        for server_name, mcp_server in self.mcp_servers.items():
            await mcp_server.stop()
            
        # Close HTTP session
        if self.session:
            await self.session.close()
            
    async def stop(self) -> None:
        """Stop the agent gracefully"""
        self.logger.info("🛑 Stopping agent...")
        self.running = False

def signal_handler(agent: ScintillaLocalAgent):
    """Handle shutdown signals"""
    def handler(signum, frame):
        print("\n🛑 Received shutdown signal...")
        asyncio.create_task(agent.stop())
    return handler

async def main():
    """Main entry point"""
    agent = ScintillaLocalAgent()
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler(agent))
    signal.signal(signal.SIGTERM, signal_handler(agent))
    
    try:
        await agent.start()
    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user")
    except Exception as e:
        print(f"❌ Agent failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 
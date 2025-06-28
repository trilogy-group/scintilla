"""
Local Agent API endpoints for STDIO MCP servers

Provides polling-based architecture for local proxy agents that can:
1. Register with the main server
2. Poll for work (tool execution tasks)
3. Submit results back

This enables local MCP servers (STDIO-based) to integrate with Scintilla
via local proxy agents.
"""

import uuid
import asyncio
from typing import Dict, Optional, List, Any
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from src.api.models import (
    AgentRegistration, AgentTask, AgentTaskRequest, 
    AgentTaskResult, AgentPollResponse, AgentStatusResponse,
    ToolRefreshRequest, ToolRefreshResponse
)
from src.auth.google_oauth import get_current_user, get_current_user_with_agent_token
from src.db.base import get_db_session
from src.db.models import User, Source, SourceTool

logger = structlog.get_logger()
router = APIRouter(prefix="/agents", tags=["local-agents"])


class LocalAgentManager:
    """
    In-memory task queue and agent registry for local MCP agents
    
    In production, this could be moved to Redis or database for clustering.
    For now, keeps everything in memory for simplicity.
    """
    
    def __init__(self):
        self.agents: Dict[str, AgentRegistration] = {}
        self.pending_tasks: Dict[str, AgentTask] = {}  # task_id -> task
        self.agent_tasks: Dict[str, List[str]] = {}    # agent_id -> [task_ids]
        self.task_results: Dict[str, AgentTaskResult] = {}  # task_id -> result
        self.task_futures: Dict[str, asyncio.Future] = {}  # task_id -> future
    
    def register_agent(self, registration: AgentRegistration) -> bool:
        """Register a local agent and track its capabilities"""
        self.agents[registration.agent_id] = registration
        if registration.agent_id not in self.agent_tasks:
            self.agent_tasks[registration.agent_id] = []
        
        logger.info("Local agent registered", 
                   agent_id=registration.agent_id, 
                   capabilities=registration.capabilities,
                   agent_name=registration.name)
        return True
    
    def get_agent_work(self, agent_id: str) -> Optional[AgentTask]:
        """Get pending work for a specific agent based on its capabilities"""
        if agent_id not in self.agents:
            logger.warning("Unknown agent requesting work", agent_id=agent_id)
            return None
        
        agent = self.agents[agent_id]
        agent_capabilities = set(agent.capabilities)
        
        logger.debug("Agent polling for work", 
                   agent_id=agent_id, 
                   agent_capabilities=list(agent_capabilities),
                   pending_tasks_count=len(self.pending_tasks))
        
        # Find a task this agent can handle
        for task_id, task in list(self.pending_tasks.items()):
            logger.info("Checking task compatibility",
                       task_id=task_id,
                       task_tool_name=task.tool_name,
                       agent_capabilities=list(agent_capabilities),
                       tool_in_capabilities=task.tool_name in agent_capabilities,
                       is_discovery_task=task.tool_name == "__discovery__")
            
            # Check if agent can handle this task
            can_handle = False
            
            # Special handling for discovery tasks - any agent can handle these
            if task.tool_name == "__discovery__":
                can_handle = True
            # Direct capability match (for high-level capabilities)
            elif task.tool_name in agent_capabilities:
                can_handle = True
            # Tool name mapping to capabilities
            else:
                # Map tool names to capabilities based on prefixes
                tool_to_capability_mapping = {
                    'jira_': ['jira_operations', 'khoros-atlassian', 'atlassian_integration'],
                    'confluence_': ['confluence_operations', 'khoros-atlassian', 'atlassian_integration'],
                    'atlassian_': ['atlassian_integration', 'khoros-atlassian']
                }
                
                for prefix, required_capabilities in tool_to_capability_mapping.items():
                    if task.tool_name.startswith(prefix):
                        if any(cap in agent_capabilities for cap in required_capabilities):
                            can_handle = True
                            break
            
            if can_handle:
                # Assign task to agent
                del self.pending_tasks[task_id]
                self.agent_tasks[agent_id].append(task_id)
                
                logger.info("Task assigned to local agent", 
                           task_id=task_id, 
                           agent_id=agent_id, 
                           tool=task.tool_name,
                           agent_capabilities=list(agent_capabilities))
                return task
        
        if len(self.pending_tasks) > 0:
            logger.info("No matching tasks found for agent",
                       agent_id=agent_id,
                       pending_tasks=[{"task_id": tid, "tool_name": t.tool_name} for tid, t in self.pending_tasks.items()])
        
        return None
    
    def submit_task(self, tool_name: str, arguments: Dict[str, Any], timeout_seconds: int = 60) -> str:
        """Submit a task for local execution and return task ID"""
        task_id = str(uuid.uuid4())
        task = AgentTask(
            task_id=task_id,
            tool_name=tool_name,
            arguments=arguments,
            timeout_seconds=timeout_seconds,
            created_at=datetime.now(timezone.utc).isoformat()
        )
        
        self.pending_tasks[task_id] = task
        
        # Create future for result waiting
        future = asyncio.Future()
        self.task_futures[task_id] = future
        
        logger.info("Task submitted for local agents", 
                   task_id=task_id, 
                   tool=tool_name,
                   pending_tasks=len(self.pending_tasks))
        return task_id
    
    def complete_task(self, task_id: str, result: AgentTaskResult) -> bool:
        """Mark task as completed and notify waiters"""
        self.task_results[task_id] = result
        
        # Resolve the future if it exists
        if task_id in self.task_futures:
            future = self.task_futures[task_id]
            if not future.done():
                future.set_result(result)
            del self.task_futures[task_id]
        
        # Remove from agent's task list
        for agent_id, task_list in self.agent_tasks.items():
            if task_id in task_list:
                task_list.remove(task_id)
                break
        
        logger.info("Task completed by local agent", 
                   task_id=task_id,
                   success=result.success,
                   remaining_tasks=len(self.pending_tasks))
        return True
    
    async def wait_for_task_result(self, task_id: str, timeout_seconds: int = 60) -> Optional[AgentTaskResult]:
        """Wait for a task to complete and return the result"""
        if task_id not in self.task_futures:
            # Task might already be completed
            return self.task_results.get(task_id)
        
        try:
            future = self.task_futures[task_id]
            result = await asyncio.wait_for(future, timeout=timeout_seconds)
            return result
        except asyncio.TimeoutError:
            logger.warning("Task timed out waiting for local agent", 
                          task_id=task_id, 
                          timeout=timeout_seconds)
            # Clean up
            if task_id in self.task_futures:
                del self.task_futures[task_id]
            return None
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status of the local agent system"""
        return {
            "registered_agents": len(self.agents),
            "pending_tasks": len(self.pending_tasks),
            "active_tasks": sum(len(tasks) for tasks in self.agent_tasks.values()),
            "agents": [
                {
                    "agent_id": agent_id,
                    "name": agent.name,
                    "capabilities": agent.capabilities,
                    "active_tasks": len(self.agent_tasks.get(agent_id, [])),
                    "last_seen": agent.last_ping
                }
                for agent_id, agent in self.agents.items()
            ]
        }
    
    def cleanup_stale_agents(self, max_age_minutes: int = 15):
        """Remove agents that haven't pinged recently"""
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=max_age_minutes)
        stale_agents = []
        
        for agent_id, agent in list(self.agents.items()):
            # Only clean up if last_ping exists and is actually old
            if agent.last_ping:
                try:
                    last_ping_dt = datetime.fromisoformat(agent.last_ping.replace('Z', '+00:00'))
                    if last_ping_dt < cutoff:
                        stale_agents.append(agent_id)
                except (ValueError, TypeError) as e:
                    logger.warning("Invalid last_ping format, keeping agent", agent_id=agent_id, error=str(e))
        
        for agent_id in stale_agents:
            del self.agents[agent_id]
            if agent_id in self.agent_tasks:
                # Re-queue any tasks assigned to this agent
                for task_id in self.agent_tasks[agent_id]:
                    if task_id in self.task_results:
                        continue  # Already completed
                    
                    # Find the task and re-queue it
                    for pending_task in list(self.pending_tasks.values()):
                        if pending_task.task_id == task_id:
                            self.pending_tasks[task_id] = pending_task
                            break
                
                del self.agent_tasks[agent_id]
            
            logger.info("Cleaned up stale agent", agent_id=agent_id)


# Global instance
local_agent_manager = LocalAgentManager()


@router.post("/register")
async def register_agent(
    registration: AgentRegistration,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user_with_agent_token),
    db: AsyncSession = Depends(get_db_session)
):
    """Register a local proxy agent with its capabilities"""
    
    # Add user context to registration
    registration.user_id = str(user.user_id)
    registration.last_ping = datetime.now(timezone.utc).isoformat()
    
    success = local_agent_manager.register_agent(registration)
    
    if success:
        # Don't schedule cleanup on every registration - too aggressive
        # background_tasks.add_task(local_agent_manager.cleanup_stale_agents)
        
        return {
            "success": True,
            "message": f"Agent '{registration.name}' registered successfully",
            "agent_id": registration.agent_id,
            "capabilities": registration.capabilities
        }
    else:
        raise HTTPException(status_code=400, detail="Failed to register agent")


@router.post("/poll/{agent_id}")
async def poll_for_work(
    agent_id: str
) -> AgentPollResponse:
    """Poll for work assignments for a specific agent"""
    
    # Update agent's last ping if registered
    if agent_id in local_agent_manager.agents:
        local_agent_manager.agents[agent_id].last_ping = datetime.now(timezone.utc).isoformat()
    
    # Get work for this agent
    task = local_agent_manager.get_agent_work(agent_id)
    
    if task:
        return AgentPollResponse(
            has_work=True,
            task=task
        )
    else:
        return AgentPollResponse(
            has_work=False,
            task=None
        )


@router.post("/results/{task_id}")
async def submit_task_result(
    task_id: str,
    result: AgentTaskResult,
    user: User = Depends(get_current_user_with_agent_token)
):
    """Submit the result of a completed task"""
    
    success = local_agent_manager.complete_task(task_id, result)
    
    if success:
        return {
            "success": True,
            "message": "Task result submitted successfully",
            "task_id": task_id
        }
    else:
        raise HTTPException(status_code=400, detail="Failed to submit task result")


@router.get("/status")
async def get_agent_status(
    user: User = Depends(get_current_user)
) -> AgentStatusResponse:
    """Get the current status of the local agent system"""
    
    status = local_agent_manager.get_status()
    
    return AgentStatusResponse(
        registered_agents=status["registered_agents"],
        pending_tasks=status["pending_tasks"],
        active_tasks=status["active_tasks"],
        agents=status["agents"]
    )


@router.post("/execute")
async def execute_tool_via_local_agent(
    request: AgentTaskRequest,
    user: User = Depends(get_current_user)
):
    """
    Execute a tool via local agents (for testing or direct API access)
    
    This submits a task and waits for completion.
    """
    
    # Submit task
    task_id = local_agent_manager.submit_task(
        tool_name=request.tool_name,
        arguments=request.arguments,
        timeout_seconds=request.timeout_seconds or 60
    )
    
    # Wait for result
    result = await local_agent_manager.wait_for_task_result(
        task_id, 
        timeout_seconds=request.timeout_seconds or 60
    )
    
    if result:
        return {
            "success": True,
            "task_id": task_id,
            "result": result.dict()
        }
    else:
        return {
            "success": False,
            "task_id": task_id,
            "error": "Task timed out or no capable agent available"
        }


# Helper function for FastMCPAgent integration
async def execute_local_tool(tool_name: str, arguments: Dict[str, Any], timeout_seconds: int = 60) -> Dict[str, Any]:
    """
    Execute a tool via local agents from within FastMCPAgent
    
    Returns:
        Dict with 'success', 'result', and optionally 'error' keys
    """
    
    # Submit task
    task_id = local_agent_manager.submit_task(
        tool_name=tool_name,
        arguments=arguments,
        timeout_seconds=timeout_seconds
    )
    
    # Wait for result
    result = await local_agent_manager.wait_for_task_result(task_id, timeout_seconds)
    
    if result and result.success:
        return {
            "success": True,
            "result": result.result,
            "tool_name": tool_name,
            "arguments": arguments
        }
    elif result:
        return {
            "success": False,
            "error": result.error or "Unknown error",
            "tool_name": tool_name,
            "arguments": arguments
        }
    else:
        return {
            "success": False,
            "error": "Tool execution timed out or no capable agent available",
            "tool_name": tool_name,
            "arguments": arguments
        }


@router.post("/refresh-tools")
async def refresh_agent_tools(
    request: ToolRefreshRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
) -> ToolRefreshResponse:
    """
    Refresh tools for a specific agent capability and cache them in the database.
    
    This is separate from registration - it queries the agent for its actual tools
    and stores them in the SourceTool table for fast query-time access.
    """
    
    # Check if agent is registered
    if request.agent_id not in local_agent_manager.agents:
        raise HTTPException(status_code=404, detail=f"Agent {request.agent_id} not found")
    
    agent = local_agent_manager.agents[request.agent_id]
    
    # Verify agent can handle this capability
    if request.capability not in agent.capabilities:
        raise HTTPException(
            status_code=400, 
            detail=f"Agent {request.agent_id} does not have capability '{request.capability}'"
        )
    
    try:
        # Find or create a Source for this local capability
        # Use a local:// URL scheme to identify it as local
        source_url = f"local://{request.capability}"
        
        # Check if source exists
        from sqlalchemy import select
        result = await db.execute(
            select(Source).where(Source.server_url == source_url)
        )
        source = result.scalars().first()
        
        if not source:
            # Create new source for this local capability
            source = Source(
                name=f"Local {request.capability}",
                server_url=source_url,
                is_direct_sse=False,  # Local agents use polling, not SSE
                created_by_user_id=user.user_id,
                bot_id=None,  # Not tied to a specific bot
                tools_cache_status="refreshing"
            )
            db.add(source)
            await db.flush()  # Get the source_id
        
        # Extract source_id early to avoid greenlet issues
        source_id = source.source_id
        source_name = source.name
        
        # Submit a tool discovery task to the agent
        logger.info(
            "Submitting discovery task",
            agent_id=request.agent_id,
            capability=request.capability
        )
        
        discovery_task_id = local_agent_manager.submit_task(
            tool_name="__discovery__",  # Special internal task
            arguments={"capability": request.capability},
            timeout_seconds=30
        )
        
        logger.info(
            "Discovery task submitted",
            task_id=discovery_task_id,
            pending_tasks=len(local_agent_manager.pending_tasks)
        )
        
        # Wait for the agent to provide its tools
        result = await local_agent_manager.wait_for_task_result(discovery_task_id, timeout_seconds=30)
        
        if not result or not result.success:
            error_msg = result.error if result else "Tool discovery timed out"
            
            # Update source with error
            source.tools_cache_status = "error"
            source.tools_cache_error = error_msg
            await db.commit()
            
            return ToolRefreshResponse(
                success=False,
                message=error_msg,
                tools_discovered=0,
                capability=request.capability,
                agent_id=request.agent_id
            )
        
        # Parse tools from agent response
        tools_data = result.result
        if isinstance(tools_data, str):
            import json
            try:
                tools_data = json.loads(tools_data)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse tools JSON: {e}, raw data: {tools_data}")
                return ToolRefreshResponse(
                    success=False,
                    message=f"Failed to parse agent response: {str(e)}",
                    tools_discovered=0,
                    capability=request.capability,
                    agent_id=request.agent_id
                )
        
        # tools_data should now be a dict
        if not isinstance(tools_data, dict):
            logger.error(f"Expected dict from agent, got {type(tools_data)}: {tools_data}")
            return ToolRefreshResponse(
                success=False,
                message=f"Invalid response format from agent: expected dict, got {type(tools_data)}",
                tools_discovered=0,
                capability=request.capability,
                agent_id=request.agent_id
            )
        
        tools = tools_data.get("tools", [])
        
        # Clear existing cached tools for this source
        from sqlalchemy import delete
        await db.execute(
            delete(SourceTool).where(SourceTool.source_id == source_id)
        )
        
        # Cache the discovered tools
        from datetime import datetime, timezone
        tools_count = 0
        
        for tool in tools:
            if isinstance(tool, dict) and tool.get("name"):
                source_tool = SourceTool(
                    source_id=source_id,
                    tool_name=tool["name"],
                    tool_description=tool.get("description", ""),
                    tool_schema=tool.get("inputSchema", {}),
                    last_refreshed_at=datetime.now(timezone.utc),
                    is_active=True
                )
                db.add(source_tool)
                tools_count += 1
        
        # Update source status
        source.tools_cache_status = "cached"
        source.tools_last_cached_at = datetime.now(timezone.utc)
        source.tools_cache_error = None
        
        await db.commit()
        
        logger.info(
            "Tools refreshed successfully",
            agent_id=request.agent_id,
            capability=request.capability,
            tools_count=tools_count,
            source_id=source_id
        )
        
        return ToolRefreshResponse(
            success=True,
            message=f"Successfully refreshed {tools_count} tools",
            tools_discovered=tools_count,
            capability=request.capability,
            agent_id=request.agent_id
        )
        
    except Exception as e:
        logger.error(
            "Tool refresh failed",
            agent_id=request.agent_id,
            capability=request.capability,
            error=str(e)
        )
        
        return ToolRefreshResponse(
            success=False,
            message=f"Tool refresh failed: {str(e)}",
            tools_discovered=0,
            capability=request.capability,
            agent_id=request.agent_id
        ) 
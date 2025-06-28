# Local Agent Architecture - Improved Design

## Overview

This document describes the improved local agent architecture that properly separates concerns between agent registration and tool discovery/caching.

## Problem with Previous Architecture

The original implementation mixed concerns:

1. **Agent Registration** included full tool data with schemas
2. **Tool Discovery** tried to re-discover tools from registered agents during queries
3. **Database Caching** happened during tool discovery rather than as a separate process
4. **Complex Logic** with fallbacks between actual tools and capability-based generation

This led to:
- Confusing code paths
- Duplicated tool metadata
- Poor separation of concerns
- Inconsistent behavior between registration and query time

## New Architecture

### 1. Agent Registration (Lightweight)

**Purpose**: Just register that an agent is available and ready to work.

**Endpoint**: `POST /api/agents/register`

**Data**:
```json
{
  "agent_id": "local-agent-1",
  "name": "Local Agent local-agent-1", 
  "capabilities": ["khoros-atlassian", "jira_operations", "confluence_operations"],
  "version": "1.0.0"
}
```

**What it does**:
- Registers agent as available for work
- Lists high-level capabilities (server names)
- Does NOT include tool schemas or detailed tool metadata
- Lightweight and fast

### 2. Tool Refresh (Separate Process)

**Purpose**: Discover actual tools from agents and cache them in the database.

**Endpoint**: `POST /api/agents/refresh-tools`

**Data**:
```json
{
  "agent_id": "local-agent-1",
  "capability": "khoros-atlassian"
}
```

**What it does**:
- Submits a special `__discovery__` task to the agent
- Agent returns actual tools with full schemas for the specific capability
- Caches tools in the `SourceTool` table with proper metadata
- Creates/updates `Source` records for `local://capability` URLs
- Separate from registration - can be done on-demand or scheduled

**Agent Handling**:
```python
# Agent recognizes special discovery task
if tool_name == "__discovery__":
    capability = arguments.get('capability')
    tools_for_capability = []
    
    # Find MCP server that matches capability
    for server_name, server_instance in self.mcp_servers.items():
        if server_name == capability:
            tools_for_capability = server_instance.tools
            break
    
    return {
        "success": True,
        "result": json.dumps({
            "capability": capability,
            "tools": tools_for_capability  # Full tool schemas
        })
    }
```

### 3. Query Time (Use Cached Tools)

**Purpose**: Fast tool lookup using pre-cached database records.

**What it does**:
- `FastMCPToolManager` loads tools from `SourceTool` table
- No live agent queries during query processing
- Fast and reliable tool metadata access
- Consistent behavior

**Tool Discovery Logic**:
```python
# Check if tools are cached for local://capability
async def _discover_tools_from_local_agent(db, source_id, server_url):
    # Count cached tools for this source
    tool_count = await db.execute(
        select(func.count(SourceTool.tool_name))
        .where(SourceTool.source_id == source_id)
        .where(SourceTool.is_active == True)
    )
    
    if tool_count > 0:
        return True, f"Using {tool_count} cached tools", tool_count
    
    # No cached tools - user needs to refresh first
    return False, "Please use POST /api/agents/refresh-tools first", 0
```

## Workflow

### Initial Setup
1. **Start Agent**: Agent registers with basic capabilities
2. **Refresh Tools**: Admin/user calls refresh-tools for each capability
3. **Tools Cached**: Database now has tool metadata for fast access

### Query Processing  
1. **Load Tools**: FastMCPToolManager loads from database cache
2. **Execute Query**: LLM uses tools with proper schemas
3. **Route Calls**: Local tools routed to agents, remote to MCP servers

### Tool Updates
1. **Agent Restart**: Only requires re-registration (lightweight)
2. **Tool Changes**: Call refresh-tools to update cache
3. **No Downtime**: Cache updates independent of agent availability

## Benefits

### 1. Clear Separation of Concerns
- **Registration**: Agent availability and basic capabilities
- **Tool Discovery**: Separate process for schema discovery and caching
- **Query Processing**: Fast database-driven tool access

### 2. Better Performance
- Registration is lightweight and fast
- Query processing uses pre-cached tools (no live agent queries)
- Tool discovery only happens when needed

### 3. Easier Debugging
- Clear data flow: Registration → Refresh → Query
- Explicit cache state in database
- No complex fallback logic during queries

### 4. Better Reliability  
- Tool availability independent of live agent queries
- Cached tools survive agent restarts
- Clear error messages when tools not cached

### 5. Operational Flexibility
- Can refresh tools without restarting agents
- Can schedule tool refreshes independently
- Can debug tool issues by checking cache state

## API Endpoints

### Agent Management
- `POST /api/agents/register` - Register agent (lightweight)
- `POST /api/agents/poll/{agent_id}` - Poll for work
- `POST /api/agents/results/{task_id}` - Submit results
- `GET /api/agents/status` - Check agent status

### Tool Management  
- `POST /api/agents/refresh-tools` - Refresh tools for capability
- `GET /api/sources/` - Check cached tool sources

### Query Processing
- `POST /api/query` - Execute queries using cached tools

## Testing

Use the test script to verify the architecture:

```bash
# 1. Start server
uvicorn src.main:app --reload

# 2. Start agent  
cd local-agent && python agent.py

# 3. Test the workflow
python scripts/test_local_agent_architecture.py
```

The test demonstrates:
1. Agent registration with capabilities
2. Tool refresh for specific capabilities
3. Database cache verification
4. Query execution using cached tools

## Migration from Old Architecture

The old architecture automatically included tools in registration. The new architecture requires:

1. **Agent Code**: Remove tool data from registration payload
2. **Tool Discovery**: Add `__discovery__` task handling to agents
3. **Cache Management**: Use refresh-tools endpoint to populate cache
4. **Query Processing**: Remove complex agent-query logic from FastMCP

This results in cleaner, more maintainable, and more performant code. 
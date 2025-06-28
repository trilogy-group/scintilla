#!/usr/bin/env python3
"""
Test script for the new local agent architecture

This demonstrates the improved separation of concerns:
1. Agent Registration - lightweight, just capabilities
2. Tool Refresh - separate process that caches tools in database
3. Query Execution - uses cached tools for fast lookup

Usage:
1. Start the main Scintilla server: uvicorn src.main:app --reload
2. Start a local agent: cd local-agent && python agent.py
3. Run this script: python scripts/test_local_agent_architecture.py
"""

import asyncio
import aiohttp
import json
from typing import Dict, Any

BASE_URL = "http://localhost:8000"

async def test_agent_status():
    """Check the status of registered agents"""
    print("🔍 Checking agent status...")
    
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BASE_URL}/api/agents/status") as response:
            if response.status == 200:
                data = await response.json()
                print(f"✅ Found {data['registered_agents']} registered agents")
                
                for agent in data['agents']:
                    print(f"   Agent: {agent['name']} (ID: {agent['agent_id']})")
                    print(f"   Capabilities: {agent['capabilities']}")
                    print(f"   Active tasks: {agent['active_tasks']}")
                    print()
                    
                return data['agents']
            else:
                print(f"❌ Failed to get agent status: {response.status}")
                return []

async def test_tool_refresh(agent_id: str, capability: str):
    """Test the tool refresh endpoint"""
    print(f"🔄 Refreshing tools for agent {agent_id}, capability {capability}...")
    
    refresh_request = {
        "agent_id": agent_id,
        "capability": capability
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{BASE_URL}/api/agents/refresh-tools", 
            json=refresh_request
        ) as response:
            if response.status == 200:
                data = await response.json()
                print(f"✅ Tool refresh successful: {data['message']}")
                print(f"   Tools discovered: {data['tools_discovered']}")
                return True
            else:
                error_text = await response.text()
                print(f"❌ Tool refresh failed ({response.status}): {error_text}")
                return False

async def test_query_with_local_tools():
    """Test a query that should use local tools"""
    print("🔍 Testing query with local tools...")
    
    query_request = {
        "message": "Search for issues in project XYZ",
        "stream": False
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{BASE_URL}/api/query", 
            json=query_request
        ) as response:
            if response.status == 200:
                data = await response.json()
                print(f"✅ Query successful!")
                print(f"   Response: {data.get('response', 'No response')[:200]}...")
                print(f"   Tools used: {len(data.get('tool_calls', []))}")
                
                for tool_call in data.get('tool_calls', []):
                    print(f"   - {tool_call.get('tool_name')} (source: {tool_call.get('source_classification', 'unknown')})")
                
                return True
            else:
                error_text = await response.text()
                print(f"❌ Query failed ({response.status}): {error_text}")
                return False

async def check_cached_tools():
    """Check what tools are cached in the database"""
    print("💾 Checking cached tools in database...")
    
    # This would require a database query endpoint, but for now we'll just check via sources
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BASE_URL}/api/sources/") as response:
            if response.status == 200:
                sources = await response.json()
                
                local_sources = [s for s in sources if s.get('server_url', '').startswith('local://')]
                print(f"✅ Found {len(local_sources)} local sources")
                
                for source in local_sources:
                    print(f"   Source: {source['name']} ({source['server_url']})")
                    print(f"   Cache status: {source.get('tools_cache_status', 'unknown')}")
                    if source.get('tools_cache_error'):
                        print(f"   Error: {source['tools_cache_error']}")
                    print()
                
                return local_sources
            else:
                print(f"❌ Failed to get sources: {response.status}")
                return []

async def main():
    """Main test flow"""
    print("🚀 Testing Local Agent Architecture\n")
    
    # Step 1: Check agent status
    agents = await test_agent_status()
    
    if not agents:
        print("❌ No agents found. Please start a local agent first.")
        return
    
    # Step 2: Check current cached tools
    await check_cached_tools()
    
    # Step 3: Refresh tools for the first agent
    agent = agents[0]
    agent_id = agent['agent_id']
    
    # Try to refresh tools for each capability
    for capability in agent['capabilities']:
        if capability in ['khoros-atlassian', 'jira', 'confluence']:  # Known server names
            success = await test_tool_refresh(agent_id, capability)
            if success:
                print(f"✅ Successfully refreshed tools for {capability}\n")
                break
    
    # Step 4: Check cached tools again
    await check_cached_tools()
    
    # Step 5: Test a query that should use the cached tools
    await test_query_with_local_tools()
    
    print("\n🎉 Test completed!")

if __name__ == "__main__":
    asyncio.run(main()) 
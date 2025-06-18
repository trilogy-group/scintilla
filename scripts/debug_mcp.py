#!/usr/bin/env python3
"""
Debug script to test MCP loading directly
"""

import asyncio
import time
from src.agents.langchain_mcp import MCPAgent
from src.db.base import AsyncSessionLocal
import uuid

async def debug_mcp_loading():
    """Debug MCP loading to see where it hangs"""
    
    print("🔍 Debug: Testing MCP loading directly...")
    
    # Create test user ID
    test_user_id = uuid.UUID('58d43e65-1176-49a4-ab61-0f765d8adb01')  # From logs
    
    async with AsyncSessionLocal() as db:
        print("📊 Database connection established")
        
        # Create MCP agent
        mcp_agent = MCPAgent()
        print("🤖 MCP agent created")
        
        # Test loading user sources
        print("⏳ Starting MCP endpoint loading...")
        start_time = time.time()
        
        try:
            tool_count = await mcp_agent.load_mcp_endpoints_from_user_sources(
                db, test_user_id
            )
            
            end_time = time.time()
            load_time = end_time - start_time
            
            print(f"✅ MCP loading completed!")
            print(f"   Tool count: {tool_count}")
            print(f"   Load time: {load_time:.2f}s")
            print(f"   Loaded servers: {mcp_agent.get_loaded_servers()}")
            
            if tool_count > 0:
                print("🛠️ Available tools:")
                for tool in mcp_agent.get_available_tools()[:5]:  # Show first 5
                    print(f"   - {tool['name']}: {tool['description']}")
            
        except Exception as e:
            end_time = time.time()
            load_time = end_time - start_time
            
            print(f"❌ MCP loading failed after {load_time:.2f}s")
            print(f"   Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_mcp_loading()) 
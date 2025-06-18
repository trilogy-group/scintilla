#!/usr/bin/env python3
"""
Test script to verify global MCP caching is working correctly
"""

import asyncio
import aiohttp
import json
import time

async def test_global_cache_performance():
    """Test that global caching provides significant performance improvement"""
    
    timeout = aiohttp.ClientTimeout(total=120, connect=30)
    connector = aiohttp.TCPConnector(limit=10, limit_per_host=5)
    
    async with aiohttp.ClientSession(
        timeout=timeout,
        connector=connector,
        read_bufsize=2**20
    ) as session:
        
        print("🔍 Testing global MCP cache performance...")
        
        # First, check if server has tools pre-loaded
        print("\n1. Checking server health and MCP status...")
        async with session.get("http://localhost:8000/health") as response:
            health = await response.json()
            print(f"   Server status: {health['status']}")
            print(f"   MCP loaded: {health['mcp']['loaded']}")
            print(f"   Tool count: {health['mcp']['tool_count']}")
            print(f"   Servers: {health['mcp']['servers']}")
        
        if not health['mcp']['loaded']:
            print("❌ Global MCP agent not loaded - server may still be starting up")
            return
        
        # Test multiple requests to see if they're fast
        print("\n2. Testing multiple query requests...")
        
        test_query = "What tools are available?"
        
        request_times = []
        
        for i in range(3):
            print(f"\n   Request {i+1}:")
            start_time = time.time()
            
            async with session.post(
                "http://localhost:8000/api/query",
                json={
                    "message": test_query,
                    "use_user_sources": True,
                    "bot_ids": [],
                    "stream": True
                }
            ) as response:
                first_chunk_time = None
                tools_loaded_time = None
                
                async for line in response.content:
                    line_str = line.decode('utf-8').strip()
                    
                    if line_str.startswith('data: '):
                        try:
                            data = json.loads(line_str[6:])
                            chunk_time = time.time()
                            
                            if first_chunk_time is None:
                                first_chunk_time = chunk_time
                                time_to_first_chunk = (first_chunk_time - start_time) * 1000
                                print(f"      First chunk: {time_to_first_chunk:.1f}ms")
                            
                            if data.get("type") == "tools_loaded":
                                tools_loaded_time = chunk_time
                                time_to_tools = (tools_loaded_time - start_time) * 1000
                                print(f"      Tools loaded: {time_to_tools:.1f}ms")
                                print(f"      Tool count: {data.get('tool_count', 0)}")
                                print(f"      Source type: {data.get('source_type', 'unknown')}")
                                
                                # If using cached tools, this should be very fast
                                if data.get('source_type') == 'cached global tools':
                                    print(f"      ✅ Using cached tools - excellent!")
                                else:
                                    print(f"      ⚠️  Not using cached tools - {data.get('source_type')}")
                                
                                break
                        except json.JSONDecodeError:
                            continue
                
                total_time = (time.time() - start_time) * 1000
                request_times.append(total_time)
                print(f"      Total time: {total_time:.1f}ms")
        
        # Analyze results
        print(f"\n3. Performance Analysis:")
        print(f"   Average request time: {sum(request_times) / len(request_times):.1f}ms")
        print(f"   Min time: {min(request_times):.1f}ms")
        print(f"   Max time: {max(request_times):.1f}ms")
        
        # Check if performance is good
        avg_time = sum(request_times) / len(request_times)
        if avg_time < 5000:  # Less than 5 seconds
            print(f"   ✅ Performance is good! Average {avg_time:.1f}ms")
        elif avg_time < 15000:  # Less than 15 seconds
            print(f"   ⚠️  Performance is acceptable: {avg_time:.1f}ms")
        else:
            print(f"   ❌ Performance is poor: {avg_time:.1f}ms")
        
        # Test if subsequent requests are consistently fast
        if len(request_times) > 1:
            first_request = request_times[0]
            subsequent_avg = sum(request_times[1:]) / len(request_times[1:])
            
            if subsequent_avg < first_request * 0.5:  # At least 50% faster
                print(f"   ✅ Caching is working! Subsequent requests {subsequent_avg:.1f}ms vs first {first_request:.1f}ms")
            else:
                print(f"   ⚠️  Caching may not be working optimally")

if __name__ == "__main__":
    asyncio.run(test_global_cache_performance()) 
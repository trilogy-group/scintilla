#!/usr/bin/env python3
"""
Test script to verify timeout fixes work correctly
"""

import asyncio
import aiohttp
import json
import time

async def test_timeout_handling():
    """Test that the server properly handles timeouts"""
    
    # Increase timeout to see if server responds with timeout error
    timeout = aiohttp.ClientTimeout(total=120, connect=30)  # 2 minutes total
    connector = aiohttp.TCPConnector(limit=10, limit_per_host=5)
    
    async with aiohttp.ClientSession(
        timeout=timeout,
        connector=connector,
        read_bufsize=2**20
    ) as session:
        
        print("🔍 Testing timeout handling...")
        start_time = time.time()
        
        try:
            async with session.post(
                "http://localhost:8000/api/query",
                json={
                    "message": "Hello, what tools are available?",
                    "stream": True,
                    "use_user_sources": True,
                    "bot_ids": [],
                    "llm_provider": "anthropic",
                    "llm_model": "claude-sonnet-4-20250514"
                },
                headers={"Content-Type": "application/json"}
            ) as response:
                
                print(f"📡 Response status: {response.status}")
                
                if response.status != 200:
                    text = await response.text()
                    print(f"❌ Error response: {text}")
                    return
                
                print("📦 Streaming response:")
                buffer = ""
                
                async for chunk in response.content.iter_chunked(8192):
                    chunk_str = chunk.decode('utf-8', errors='ignore')
                    buffer += chunk_str
                    
                    # Process complete lines
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        line = line.strip()
                        
                        if line.startswith('data: '):
                            try:
                                data = json.loads(line[6:])
                                elapsed = time.time() - start_time
                                
                                print(f"   📄 [{elapsed:.2f}s] {data.get('type', 'unknown')}")
                                
                                if data.get("type") == "status":
                                    print(f"      Status: {data.get('message')}")
                                elif data.get("type") == "error":
                                    print(f"      ❌ Error: {data.get('error')}")
                                    print(f"✅ Server properly returned timeout error after {elapsed:.2f}s")
                                    return
                                elif data.get("type") == "tools_loaded":
                                    print(f"      ✅ Tools loaded: {data.get('tool_count')}")
                                elif data.get("type") == "complete":
                                    print(f"      ✅ Query completed successfully!")
                                    return
                                    
                            except json.JSONDecodeError as e:
                                print(f"   ⚠️ JSON decode error: {e}")
                
                print(f"\n⏱️ Total time: {time.time() - start_time:.2f}s")
                
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"❌ Client error after {elapsed:.2f}s: {e}")

if __name__ == "__main__":
    asyncio.run(test_timeout_handling()) 
#!/usr/bin/env python3
"""
Simple test script to debug Scintilla server issues
"""

import asyncio
import aiohttp
import json
import time

async def test_simple_query():
    """Test a simple query to see what's happening"""
    
    timeout = aiohttp.ClientTimeout(total=300, connect=30)  # 5 minutes total
    connector = aiohttp.TCPConnector(limit=10, limit_per_host=5)
    
    async with aiohttp.ClientSession(
        timeout=timeout,
        connector=connector,
        read_bufsize=2**20  # 1MB read buffer
    ) as session:
        
        print("🔍 Testing simple health check...")
        async with session.get("http://localhost:8000/health") as response:
            health = await response.json()
            print(f"✅ Health: {health}")
        
        print("\n🔍 Testing simple query...")
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
                print(f"📡 Response headers: {dict(response.headers)}")
                
                if response.status != 200:
                    text = await response.text()
                    print(f"❌ Error response: {text}")
                    return
                
                print("\n📦 Streaming chunks:")
                chunk_count = 0
                buffer = ""
                
                async for chunk in response.content.iter_chunked(8192):
                    chunk_count += 1
                    chunk_str = chunk.decode('utf-8', errors='ignore')
                    buffer += chunk_str
                    
                    print(f"   Chunk {chunk_count}: {len(chunk)} bytes")
                    
                    # Process complete lines
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        line = line.strip()
                        
                        if line.startswith('data: '):
                            try:
                                data = json.loads(line[6:])
                                elapsed = time.time() - start_time
                                print(f"   📄 [{elapsed:.2f}s] {data.get('type', 'unknown')}: {str(data)[:100]}...")
                                
                                if data.get("type") == "complete":
                                    print("✅ Query completed!")
                                    return
                                    
                            except json.JSONDecodeError as e:
                                print(f"   ⚠️ JSON decode error: {e}")
                                print(f"   Raw line: {line[:200]}...")
                        elif line and not line.startswith(':'):
                            print(f"   📝 Non-data line: {line[:100]}")
                    
                    # Safety limit
                    if chunk_count > 100:
                        print("⚠️ Too many chunks, stopping...")
                        break
                
                print(f"\n⏱️ Total time: {time.time() - start_time:.2f}s")
                
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_simple_query()) 
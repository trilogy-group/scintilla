#!/usr/bin/env python3
"""
Test script for Scintilla API endpoints

Tests all the main endpoints including:
- Health check
- Streaming query mode 
- Non-streaming query mode
- Tool loading and MCP integration
"""

import asyncio
import aiohttp
import json
import uuid
from datetime import datetime

# Test configuration
BASE_URL = "http://localhost:8000"
MOCK_USER_HEADERS = {
    "Authorization": "Bearer mock_token_12345",
    "Content-Type": "application/json"
}

# Test bot ID (from our test data)
TEST_BOT_ID = "0225c5f8-6f24-460d-8efc-da1e7266014c"

async def test_health_endpoint():
    """Test the health check endpoint"""
    print("🔍 Testing health endpoint...")
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{BASE_URL}/health") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Health check passed: {data}")
                    return True
                else:
                    print(f"❌ Health check failed: {response.status}")
                    return False
        except Exception as e:
            print(f"❌ Health check error: {e}")
            return False

async def test_streaming_query():
    """Test the streaming query endpoint"""
    print("\n🔍 Testing streaming query endpoint...")
    
    query_data = {
        "message": "What tools do you have available? Can you help with code reviews?",
        "bot_ids": [TEST_BOT_ID],
        "stream": True,
        "llm_provider": "anthropic",
        "llm_model": "claude-3-5-sonnet-20241022"
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                f"{BASE_URL}/api/query",
                json=query_data,
                headers=MOCK_USER_HEADERS
            ) as response:
                if response.status == 200:
                    print("✅ Streaming request accepted")
                    
                    # Read streaming response
                    chunks_received = 0
                    tools_loaded = False
                    response_content = ""
                    
                    async for line in response.content:
                        if line:
                            try:
                                line_str = line.decode('utf-8').strip()
                                if line_str.startswith('data: '):
                                    json_data = line_str[6:]  # Remove 'data: ' prefix
                                    chunk = json.loads(json_data)
                                    chunks_received += 1
                                    
                                    print(f"📦 Chunk {chunks_received}: {chunk.get('type', 'unknown')}")
                                    
                                    if chunk.get('type') == 'tools_loaded':
                                        tools_loaded = True
                                        tool_count = chunk.get('tool_count', 0)
                                        print(f"🔧 Tools loaded: {tool_count}")
                                        
                                    elif chunk.get('type') == 'final_response':
                                        response_content = chunk.get('content', '')
                                        print(f"💬 Response: {response_content[:100]}...")
                                        
                                    elif chunk.get('type') == 'complete':
                                        message_id = chunk.get('message_id')
                                        print(f"✅ Completed with message ID: {message_id}")
                                        
                                    elif chunk.get('type') == 'error':
                                        print(f"❌ Error in stream: {chunk.get('error')}")
                                        return False
                                        
                            except json.JSONDecodeError:
                                continue
                            except Exception as e:
                                print(f"⚠️ Error processing chunk: {e}")
                                continue
                    
                    if tools_loaded and response_content:
                        print(f"✅ Streaming test successful! Received {chunks_received} chunks")
                        return True
                    else:
                        print(f"❌ Streaming test incomplete - tools: {tools_loaded}, response: {bool(response_content)}")
                        return False
                        
                else:
                    error_text = await response.text()
                    print(f"❌ Streaming query failed: {response.status} - {error_text}")
                    return False
                    
        except Exception as e:
            print(f"❌ Streaming query error: {e}")
            return False

async def test_non_streaming_query():
    """Test the non-streaming query endpoint"""
    print("\n🔍 Testing non-streaming query endpoint...")
    
    query_data = {
        "message": "Hello! What development tools can you help me with?",
        "bot_ids": [TEST_BOT_ID],
        "stream": False,
        "llm_provider": "anthropic",
        "llm_model": "claude-3-5-sonnet-20241022"
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                f"{BASE_URL}/api/query",
                json=query_data,
                headers=MOCK_USER_HEADERS
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print("✅ Non-streaming request successful")
                    print(f"💬 Response: {data.get('content', '')[:100]}...")
                    print(f"🔧 Tools used: {data.get('tools_used', [])}")
                    print(f"💾 Message ID: {data.get('message_id')}")
                    return True
                else:
                    error_text = await response.text()
                    print(f"❌ Non-streaming query failed: {response.status} - {error_text}")
                    return False
                    
        except Exception as e:
            print(f"❌ Non-streaming query error: {e}")
            return False

async def test_docs_endpoint():
    """Test the API documentation endpoint"""
    print("\n🔍 Testing API docs endpoint...")
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{BASE_URL}/docs") as response:
                if response.status == 200:
                    print("✅ API docs accessible")
                    return True
                else:
                    print(f"❌ API docs failed: {response.status}")
                    return False
        except Exception as e:
            print(f"❌ API docs error: {e}")
            return False

async def run_all_tests():
    """Run comprehensive test suite"""
    print("🚀 Starting Scintilla API endpoint tests...")
    print(f"📍 Base URL: {BASE_URL}")
    print(f"🤖 Test Bot ID: {TEST_BOT_ID}")
    print("=" * 60)
    
    results = {}
    
    # Test health endpoint
    results['health'] = await test_health_endpoint()
    
    # Test docs endpoint  
    results['docs'] = await test_docs_endpoint()
    
    # Test streaming query
    results['streaming'] = await test_streaming_query()
    
    # Test non-streaming query
    results['non_streaming'] = await test_non_streaming_query()
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY:")
    print("=" * 60)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name.ljust(15)}: {status}")
    
    total_tests = len(results)
    passed_tests = sum(results.values())
    
    print(f"\nTotal: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("🎉 All tests passed! System is working correctly.")
    else:
        print("⚠️ Some tests failed. Check the output above for details.")
    
    return passed_tests == total_tests

if __name__ == "__main__":
    asyncio.run(run_all_tests()) 
#!/usr/bin/env python3
"""
Test script for core Scintilla features:
1. Local agent support (registration, polling, task execution)
2. Stream/non-streaming query responses
3. Basic tool routing
"""

import asyncio
import aiohttp
import json
import time
from datetime import datetime

# Test configuration
BASE_URL = "http://localhost:8000"
MOCK_USER_HEADERS = {
    "Content-Type": "application/json"
}

# Test data - uses Scintilla local agent pattern
TEST_AGENT_DATA = {
    "agent_id": "test-agent-001",
    "name": "Test Local Agent",
    "capabilities": ["jira_search", "confluence_search", "local_test_tool"],
    "metadata": {
        "test": True,
        "url_scheme": "local://test-tools",
        "version": "1.0"
    }
}

TEST_TASK_DATA = {
    "tool_name": "jira_search",
    "arguments": {"query": "test query"},
    "timeout_seconds": 30
}


class CoreFeaturesTest:
    def __init__(self):
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def test_local_agent_registration(self):
        """Test local agent registration"""
        print("\n🔌 Testing local agent registration...")
        
        try:
            async with self.session.post(
                f"{BASE_URL}/api/agents/register",
                json=TEST_AGENT_DATA,
                headers=MOCK_USER_HEADERS
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Agent registration successful: {data.get('message')}")
                    print(f"   Agent ID: {data.get('agent_id')}")
                    print(f"   Capabilities: {data.get('capabilities')}")
                    return True
                else:
                    error_text = await response.text()
                    print(f"❌ Agent registration failed: {response.status} - {error_text}")
                    return False
        except Exception as e:
            print(f"❌ Agent registration error: {e}")
            return False

    async def test_agent_polling(self):
        """Test agent polling for work"""
        print("\n📋 Testing agent polling...")
        
        try:
            async with self.session.post(
                f"{BASE_URL}/api/agents/poll/{TEST_AGENT_DATA['agent_id']}",
                headers=MOCK_USER_HEADERS
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Agent polling successful")
                    print(f"   Has work: {data.get('has_work')}")
                    if data.get('task'):
                        task = data['task']
                        print(f"   Task ID: {task.get('task_id')}")
                        print(f"   Tool: {task.get('tool_name')}")
                    return True
                else:
                    error_text = await response.text()
                    print(f"❌ Agent polling failed: {response.status} - {error_text}")
                    return False
        except Exception as e:
            print(f"❌ Agent polling error: {e}")
            return False

    async def test_agent_status(self):
        """Test agent status endpoint"""
        print("\n📊 Testing agent status...")
        
        try:
            async with self.session.get(
                f"{BASE_URL}/api/agents/status",
                headers=MOCK_USER_HEADERS
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Agent status retrieved successfully")
                    print(f"   Registered agents: {data.get('registered_agents')}")
                    print(f"   Pending tasks: {data.get('pending_tasks')}")
                    print(f"   Active tasks: {data.get('active_tasks')}")
                    
                    agents = data.get('agents', [])
                    for agent in agents:
                        print(f"   Agent: {agent.get('name')} ({agent.get('agent_id')})")
                        print(f"     Capabilities: {agent.get('capabilities')}")
                        print(f"     Active tasks: {agent.get('active_tasks')}")
                    return True
                else:
                    error_text = await response.text()
                    print(f"❌ Agent status failed: {response.status} - {error_text}")
                    return False
        except Exception as e:
            print(f"❌ Agent status error: {e}")
            return False

    async def test_task_execution(self):
        """Test direct task execution via local agents"""
        print("\n⚙️ Testing task execution...")
        
        try:
            async with self.session.post(
                f"{BASE_URL}/api/agents/execute",
                json=TEST_TASK_DATA,
                headers=MOCK_USER_HEADERS
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Task execution response received")
                    print(f"   Success: {data.get('success')}")
                    print(f"   Task ID: {data.get('task_id')}")
                    
                    if data.get('success'):
                        result = data.get('result', {})
                        print(f"   Result: {result}")
                    else:
                        print(f"   Error: {data.get('error')}")
                    
                    return data.get('success', False)
                else:
                    error_text = await response.text()
                    print(f"❌ Task execution failed: {response.status} - {error_text}")
                    return False
        except Exception as e:
            print(f"❌ Task execution error: {e}")
            return False

    async def test_streaming_query(self):
        """Test streaming query endpoint"""
        print("\n🌊 Testing streaming query...")
        
        query_data = {
            "message": "What tools are available? Can you help with testing?",
            "stream": True,
            "llm_provider": "anthropic",
            "llm_model": "claude-3-5-sonnet-20241022"
        }
        
        try:
            async with self.session.post(
                f"{BASE_URL}/api/query",
                json=query_data,
                headers=MOCK_USER_HEADERS
            ) as response:
                if response.status == 200:
                    print("✅ Streaming request accepted")
                    
                    chunks_received = 0
                    has_final_response = False
                    
                    async for line in response.content:
                        if line:
                            try:
                                line_str = line.decode('utf-8').strip()
                                if line_str.startswith('data: '):
                                    json_data = line_str[6:]  # Remove 'data: ' prefix
                                    
                                    if json_data == '[DONE]':
                                        print("📝 Stream completed")
                                        break
                                    
                                    chunk = json.loads(json_data)
                                    chunks_received += 1
                                    chunk_type = chunk.get('type', 'unknown')
                                    
                                    print(f"📦 Chunk {chunks_received}: {chunk_type}")
                                    
                                    if chunk_type == 'final_response':
                                        has_final_response = True
                                        content = chunk.get('content', '')
                                        print(f"💬 Response: {content[:100]}...")
                                        
                                    elif chunk_type == 'error':
                                        print(f"❌ Error in stream: {chunk.get('error')}")
                                        
                            except json.JSONDecodeError:
                                continue
                            except Exception as e:
                                print(f"⚠️ Error processing chunk: {e}")
                                continue
                    
                    if chunks_received > 0 and has_final_response:
                        print(f"✅ Streaming test successful! Received {chunks_received} chunks")
                        return True
                    else:
                        print(f"❌ Streaming test incomplete - chunks: {chunks_received}, final: {has_final_response}")
                        return False
                        
                else:
                    error_text = await response.text()
                    print(f"❌ Streaming query failed: {response.status} - {error_text}")
                    return False
                    
        except Exception as e:
            print(f"❌ Streaming query error: {e}")
            return False

    async def test_non_streaming_query(self):
        """Test non-streaming query endpoint"""
        print("\n📄 Testing non-streaming query...")
        
        query_data = {
            "message": "Hello! What can you help me with?",
            "stream": False,
            "llm_provider": "anthropic",
            "llm_model": "claude-3-5-sonnet-20241022"
        }
        
        try:
            async with self.session.post(
                f"{BASE_URL}/api/query",
                json=query_data,
                headers=MOCK_USER_HEADERS
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print("✅ Non-streaming request successful")
                    print(f"💬 Response: {data.get('content', '')[:100]}...")
                    print(f"💾 Message ID: {data.get('message_id')}")
                    print(f"🆔 Conversation ID: {data.get('conversation_id')}")
                    
                    processing_stats = data.get('processing_stats', {})
                    if processing_stats:
                        print(f"📊 Processing stats: {processing_stats}")
                    
                    return True
                else:
                    error_text = await response.text()
                    print(f"❌ Non-streaming query failed: {response.status} - {error_text}")
                    return False
                    
        except Exception as e:
            print(f"❌ Non-streaming query error: {e}")
            return False

    async def test_health_check(self):
        """Test basic health check"""
        print("\n🏥 Testing health check...")
        
        try:
            async with self.session.get(f"{BASE_URL}/health") as response:
                if response.status == 200:
                    data = await response.json()
                    print("✅ Health check successful")
                    print(f"   Status: {data.get('status')}")
                    print(f"   Service: {data.get('service')}")
                    print(f"   Architecture: {data.get('architecture')}")
                    print(f"   Test mode: {data.get('test_mode')}")
                    return True
                else:
                    print(f"❌ Health check failed: {response.status}")
                    return False
        except Exception as e:
            print(f"❌ Health check error: {e}")
            return False


async def run_all_tests():
    """Run all core feature tests"""
    print("🚀 Starting Scintilla Core Features Test")
    print("=" * 50)
    
    test_results = {}
    
    async with CoreFeaturesTest() as tester:
        # Basic health check
        test_results['health'] = await tester.test_health_check()
        
        # Local agent tests
        test_results['agent_registration'] = await tester.test_local_agent_registration()
        test_results['agent_polling'] = await tester.test_agent_polling()
        test_results['agent_status'] = await tester.test_agent_status()
        test_results['task_execution'] = await tester.test_task_execution()
        
        # Query tests
        test_results['streaming_query'] = await tester.test_streaming_query()
        test_results['non_streaming_query'] = await tester.test_non_streaming_query()
    
    # Summary
    print("\n" + "=" * 50)
    print("📋 TEST RESULTS SUMMARY")
    print("=" * 50)
    
    passed = 0
    total = len(test_results)
    
    for test_name, result in test_results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name.replace('_', ' ').title()}: {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All core features working correctly!")
        return True
    else:
        print("⚠️ Some core features need attention")
        return False


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    exit(0 if success else 1) 
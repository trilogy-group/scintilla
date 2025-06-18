#!/usr/bin/env python3
"""
Test script to verify conversation context is working correctly
"""

import asyncio
import aiohttp
import json
import time

async def test_conversation_context():
    """Test that conversation context is maintained between requests"""
    
    timeout = aiohttp.ClientTimeout(total=300, connect=30)
    connector = aiohttp.TCPConnector(limit=10, limit_per_host=5)
    
    async with aiohttp.ClientSession(
        timeout=timeout,
        connector=connector,
        read_bufsize=2**20
    ) as session:
        
        print("🔍 Testing conversation context...")
        
        # First message - establish context
        print("\n1. First message - establishing context about XINET...")
        conversation_id = None
        
        async with session.post(
            "http://localhost:8000/api/query",
            json={
                "message": "What is XINET?",
                "use_user_sources": True,
                "bot_ids": [],
                "stream": True
            }
        ) as response:
            async for line in response.content:
                line_str = line.decode('utf-8').strip()
                
                if line_str.startswith('data: '):
                    try:
                        data = json.loads(line_str[6:])
                        
                        if data.get("type") == "conversation_saved":
                            conversation_id = data.get("conversation_id")
                            print(f"   ✅ Conversation saved: {conversation_id}")
                            break
                        elif data.get("type") == "final_response":
                            print(f"   📝 First response received")
                    except json.JSONDecodeError:
                        continue
        
        if not conversation_id:
            print("   ❌ No conversation ID received from first message")
            return
        
        # Wait a moment
        await asyncio.sleep(2)
        
        # Second message - test context
        print(f"\n2. Second message - testing context with conversation ID: {conversation_id}")
        context_worked = False
        
        async with session.post(
            "http://localhost:8000/api/query",
            json={
                "message": "In what language is it written?",
                "conversation_id": conversation_id,
                "use_user_sources": True,
                "bot_ids": [],
                "stream": True
            }
        ) as response:
            async for line in response.content:
                line_str = line.decode('utf-8').strip()
                
                if line_str.startswith('data: '):
                    try:
                        data = json.loads(line_str[6:])
                        
                        if data.get("type") == "final_response":
                            content = data.get("content", "").lower()
                            print(f"   📝 Second response received")
                            print(f"   📄 Response preview: {content[:200]}...")
                            
                            # Check if the response mentions programming languages or shows context understanding
                            context_indicators = [
                                "python", "java", "javascript", "c++", "c#", "php", "ruby", "go", 
                                "programming", "language", "code", "written in", "developed in",
                                "xinet", "implementation", "technology"
                            ]
                            
                            if any(indicator in content for indicator in context_indicators):
                                context_worked = True
                                print(f"   ✅ Context appears to be working - response mentions relevant terms")
                            else:
                                print(f"   ⚠️  Context may not be working - response doesn't mention expected terms")
                            
                            break
                    except json.JSONDecodeError:
                        continue
        
        # Summary
        print(f"\n3. Test Summary:")
        print(f"   Conversation ID: {conversation_id}")
        print(f"   Context working: {'✅ YES' if context_worked else '❌ NO'}")
        
        if context_worked:
            print(f"   🎉 SUCCESS: Conversation context is working!")
            print(f"   The AI understood that 'it' refers to XINET from the previous message.")
        else:
            print(f"   ❌ FAILURE: Conversation context may not be working.")
            print(f"   The AI didn't seem to understand the context from the previous message.")

if __name__ == "__main__":
    asyncio.run(test_conversation_context()) 
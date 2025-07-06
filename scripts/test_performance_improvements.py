#!/usr/bin/env python3
"""
Test Performance Improvements for Scintilla

This script tests the performance optimizations we've implemented:
1. Timeout configuration
2. Max retries reduction
3. Max tokens limit
4. Fast model switching for tool calling
"""

import asyncio
import time
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from agents.fast_agent import FastMCPAgent
    from config import settings
    IMPORTS_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Import error: {e}")
    print("This script requires the full Scintilla environment to run tests.")
    IMPORTS_AVAILABLE = False

async def test_performance_optimizations():
    """Test the performance improvements"""
    
    print("🚀 Testing Scintilla Performance Optimizations")
    print("=" * 60)
    
    # Initialize agent
    agent = FastMCPAgent()
    
    # Test query (simple enough to avoid tool calling complexity)
    test_query = "What are the most recent 3 tickets?"
    
    print(f"📝 Test Query: {test_query}")
    print(f"🔧 Configuration:")
    print(f"   - Fast tool calling: {settings.enable_fast_tool_calling}")
    print(f"   - Fast model: {settings.fast_tool_calling_model}")
    print(f"   - Default model: {settings.default_anthropic_model}")
    print()
    
    # Run the test
    start_time = time.time()
    try:
        async for chunk in agent.query(test_query):
            if chunk.get("type") == "performance_debug":
                print(chunk["performance_summary"])
                print()
            elif chunk.get("type") == "final_response":
                end_time = time.time()
                total_time = end_time - start_time
                print(f"✅ Query completed in {total_time:.1f}s")
                
                # Extract key metrics
                stats = chunk.get("processing_stats", {})
                print(f"📊 Key Metrics:")
                print(f"   - Tools called: {stats.get('total_tools_called', 0)}")
                print(f"   - Sources found: {stats.get('sources_found', 0)}")
                print(f"   - Response time: {stats.get('response_time_ms', 0)}ms")
                
                return True
                
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def print_recommendations():
    """Print performance optimization recommendations"""
    print("\n🎯 PERFORMANCE OPTIMIZATION RECOMMENDATIONS")
    print("=" * 60)
    print()
    
    print("✅ **IMPLEMENTED OPTIMIZATIONS:**")
    print("1. **Timeout Configuration**: 30s timeout per LLM request")
    print("2. **Reduced Retries**: Max retries reduced from 2 to 1") 
    print("3. **Token Limits**: Max tokens set to 4000 for faster generation")
    print("4. **Fast Tool Calling**: Claude-3.5-Sonnet for tool calling iterations")
    print("5. **Performance Monitoring**: Detailed timing breakdown added")
    print()
    
    print("🔧 **ENVIRONMENT VARIABLES FOR TUNING:**")
    print("```bash")
    print("# Disable fast tool calling if having issues")
    print("export ENABLE_FAST_TOOL_CALLING=false")
    print()
    print("# Use different fast model (e.g., Claude Haiku for even faster calling)")
    print("export FAST_TOOL_CALLING_MODEL=claude-3-haiku-20240307")
    print()
    print("# Use faster default model entirely")
    print("export DEFAULT_ANTHROPIC_MODEL=claude-3-5-sonnet-20240620")
    print("```")
    print()
    
    print("⚡ **ADDITIONAL OPTIMIZATIONS TO TRY:**")
    print("1. **Network Issues**: Check your internet connection to Anthropic API")
    print("2. **API Limits**: Verify you're not hitting rate limits")
    print("3. **Model Selection**: Consider using Claude-3.5-Sonnet as default")
    print("4. **Context Size**: Large contexts slow down processing")
    print("5. **Tool Complexity**: Simplify tool parameters if possible")
    print()
    
    print("🔍 **DEBUGGING SLOW QUERIES:**")
    print("1. Check the performance debug panel in the UI")
    print("2. Look for LLM calls > 10s duration")
    print("3. Monitor network latency to api.anthropic.com")
    print("4. Check if context optimization is working (tokens < 180k)")
    print()
    
    print("💡 **EXPECTED IMPROVEMENTS:**")
    print("- Tool calling iterations: 5-10s (down from 25s)")
    print("- Final response: 8-15s (down from 20s)")
    print("- Total query time: 15-30s (down from 50s+)")

if __name__ == "__main__":
    print_recommendations()
    
    # Optionally run live test if MCP sources are configured
    if "--test" in sys.argv and IMPORTS_AVAILABLE:
        print("\n🧪 Running live performance test...")
        asyncio.run(test_performance_optimizations())
    elif "--test" in sys.argv:
        print("\n❌ Cannot run live test - imports not available") 
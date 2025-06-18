#!/usr/bin/env python3
"""
Check dependencies required for MCP functionality
"""

import subprocess
import sys
import asyncio

async def check_command_available(command: str) -> bool:
    """Check if a command is available"""
    try:
        result = await asyncio.create_subprocess_exec(
            'which', command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await result.wait()
        return result.returncode == 0
    except Exception:
        return False

async def check_uvx_mcp_proxy():
    """Check if uvx and mcp-proxy are available"""
    try:
        print("🔍 Checking uvx availability...")
        uvx_available = await check_command_available('uvx')
        print(f"   uvx: {'✅ Available' if uvx_available else '❌ Not found'}")
        
        if uvx_available:
            print("\n🔍 Testing uvx mcp-proxy...")
            
            # Test if mcp-proxy can be resolved
            result = await asyncio.create_subprocess_exec(
                'uvx', '--help',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await result.wait()
            
            if result.returncode == 0:
                print("   uvx: ✅ Working")
                
                # Try to check mcp-proxy availability (with timeout)
                print("\n🔍 Testing mcp-proxy resolution...")
                try:
                    result = await asyncio.wait_for(
                        asyncio.create_subprocess_exec(
                            'uvx', 'mcp-proxy', '--help',
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE
                        ),
                        timeout=30  # 30 second timeout
                    )
                    await result.wait()
                    
                    if result.returncode == 0:
                        print("   mcp-proxy: ✅ Available and working")
                    else:
                        stderr = await result.stderr.read()
                        print(f"   mcp-proxy: ❌ Error - {stderr.decode()}")
                        
                except asyncio.TimeoutError:
                    print("   mcp-proxy: ⚠️ Timeout during resolution (this is likely the issue!)")
                    print("   This suggests mcp-proxy dependency resolution is hanging")
                    
            else:
                stderr = await result.stderr.read()
                print(f"   uvx: ❌ Error - {stderr.decode()}")
        
        print("\n🔍 Alternative: Checking if mcp-proxy is directly available...")
        mcp_proxy_direct = await check_command_available('mcp-proxy')
        print(f"   mcp-proxy (direct): {'✅ Available' if mcp_proxy_direct else '❌ Not found'}")
        
        print("\n📋 Recommendations:")
        if not uvx_available:
            print("   - Install uvx: pip install uvx")
        elif uvx_available:
            print("   - uvx is available but mcp-proxy resolution may be slow")
            print("   - Consider pre-installing mcp-proxy: uvx install mcp-proxy")
            print("   - Or use a direct mcp-proxy installation")
        
    except Exception as e:
        print(f"❌ Error checking dependencies: {e}")

if __name__ == "__main__":
    asyncio.run(check_uvx_mcp_proxy()) 
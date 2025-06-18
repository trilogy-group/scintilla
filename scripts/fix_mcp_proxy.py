#!/usr/bin/env python3
"""
Script to fix all instances of uvx mcp-proxy to use pre-installed mcp-proxy
"""

import re

def fix_mcp_proxy_usage():
    """Fix all uvx mcp-proxy instances in langchain_mcp.py"""
    
    file_path = "src/agents/langchain_mcp.py"
    
    print("🔧 Fixing mcp-proxy usage to use pre-installed version...")
    
    # Read the file
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Count original instances
    original_count = content.count('"command": "uvx"')
    print(f"   Found {original_count} instances of uvx mcp-proxy")
    
    # Replace uvx mcp-proxy with direct mcp-proxy
    # Pattern 1: Replace "command": "uvx" with "command": "mcp-proxy"
    content = re.sub(
        r'"command": "uvx"',
        '"command": "mcp-proxy"',
        content
    )
    
    # Pattern 2: Remove "mcp-proxy" from args array when it's the first element
    content = re.sub(
        r'"args": \[\s*"mcp-proxy",',
        '"args": [',
        content
    )
    
    # Count after replacement
    new_count = content.count('"command": "mcp-proxy"')
    remaining_uvx = content.count('"command": "uvx"')
    
    print(f"   ✅ Replaced {original_count} instances")
    print(f"   ✅ Now using direct mcp-proxy: {new_count} instances")
    print(f"   ✅ Remaining uvx instances: {remaining_uvx}")
    
    # Write back to file
    with open(file_path, 'w') as f:
        f.write(content)
    
    print("   ✅ File updated successfully!")

if __name__ == "__main__":
    fix_mcp_proxy_usage() 
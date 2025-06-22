#!/usr/bin/env python3
"""
Re-cache tools from sources that have tools with missing schemas
"""

import asyncio
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from src.db.base import AsyncSessionLocal
from src.db.models import Source, SourceTool
from src.agents.fast_mcp import FastMCPService
from sqlalchemy import select


async def find_sources_with_schema_issues():
    """Find sources that have tools with missing/empty schemas"""
    async with AsyncSessionLocal() as db:
        # Get all tools
        result = await db.execute(
            select(SourceTool, Source.name)
            .join(Source)
            .where(SourceTool.is_active.is_(True))
        )
        
        tools = result.all()
        
        # Find sources with schema issues
        problematic_sources = {}
        
        for tool, source_name in tools:
            # Check for missing or empty schema
            if tool.tool_schema is None or tool.tool_schema == {}:
                if tool.source_id not in problematic_sources:
                    problematic_sources[tool.source_id] = {
                        'name': source_name,
                        'tools': []
                    }
                
                problematic_sources[tool.source_id]['tools'].append({
                    'name': tool.tool_name,
                    'schema': tool.tool_schema
                })
        
        return problematic_sources


async def recache_source(source_id, source_name):
    """Re-cache tools for a specific source"""
    print(f"\n📦 Re-caching tools for: {source_name}")
    print("=" * 50)
    
    async with AsyncSessionLocal() as db:
        success, message, tool_count = await FastMCPService.discover_and_cache_tools(
            db, source_id
        )
        
        if success:
            print(f"✅ Success: {message}")
        else:
            print(f"❌ Failed: {message}")
        
        return success


async def main():
    print("🔧 TOOL RE-CACHING UTILITY")
    print("=" * 60)
    
    # Find problematic sources
    print("\n🔍 Finding sources with schema issues...")
    problematic_sources = await find_sources_with_schema_issues()
    
    if not problematic_sources:
        print("✅ No sources with schema issues found!")
        return
    
    print(f"\n❌ Found {len(problematic_sources)} sources with schema issues:")
    
    for source_id, info in problematic_sources.items():
        print(f"\n  📁 {info['name']} ({len(info['tools'])} tools with issues)")
        for tool in info['tools'][:3]:  # Show first 3
            schema_str = "None" if tool['schema'] is None else "{}"
            print(f"     - {tool['name']}: schema = {schema_str}")
        if len(info['tools']) > 3:
            print(f"     ... and {len(info['tools']) - 3} more")
    
    # Ask user if they want to re-cache
    print("\n" + "=" * 60)
    response = input("\n🤔 Do you want to re-cache these sources? (y/n): ")
    
    if response.lower() != 'y':
        print("❌ Cancelled")
        return
    
    # Re-cache each source
    print("\n🚀 Starting re-cache process...")
    
    success_count = 0
    for source_id, info in problematic_sources.items():
        if await recache_source(source_id, info['name']):
            success_count += 1
    
    print("\n" + "=" * 60)
    print(f"✅ COMPLETED: {success_count}/{len(problematic_sources)} sources re-cached successfully")


if __name__ == "__main__":
    asyncio.run(main()) 
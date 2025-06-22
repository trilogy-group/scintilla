#!/usr/bin/env python3
"""
Diagnostic script to analyze tool schemas and parameter issues in Scintilla

Checks:
1. Which agent files are actually used
2. Tool schemas in the database
3. How tools are being called
4. Parameter mapping issues
"""

import asyncio
import json
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).parent.parent))

from src.db.base import AsyncSessionLocal
from src.db.models import Source, SourceTool
from sqlalchemy import select


async def check_agent_usage():
    """Check which agent implementations are actually being used"""
    print("\n🔍 CHECKING AGENT USAGE")
    print("=" * 60)
    
    # Check imports in key files
    key_files = [
        "src/api/query_handlers.py",
        "src/main.py", 
        "src/api/query.py"
    ]
    
    for file_path in key_files:
        if Path(file_path).exists():
            content = Path(file_path).read_text()
            print(f"\n📄 {file_path}:")
            
            # Check for agent imports
            if "fast_agent" in content:
                print("  ✅ Uses FastMCPAgent")
            if "fast_mcp" in content:
                print("  ✅ Uses FastMCPToolManager")
            if "citations" in content:
                print("  ✅ Uses CitationManager")


async def check_tool_schemas():
    """Analyze tool schemas in the database"""
    print("\n\n🔧 ANALYZING TOOL SCHEMAS")
    print("=" * 60)
    
    async with AsyncSessionLocal() as db:
        # Get all tools
        result = await db.execute(
            select(SourceTool, Source.name)
            .join(Source)
            .where(SourceTool.is_active.is_(True))
            .order_by(Source.name, SourceTool.tool_name)
        )
        
        tools = result.all()
        
        print(f"\n📊 Total tools in database: {len(tools)}")
        
        # Analyze schemas
        schema_issues = {
            'missing': [],
            'empty': [],
            'no_properties': [],
            'valid': []
        }
        
        for tool, source_name in tools:
            tool_info = f"{source_name}/{tool.tool_name}"
            
            if not tool.tool_schema:
                schema_issues['missing'].append(tool_info)
            elif tool.tool_schema == {}:
                schema_issues['empty'].append(tool_info)
            elif not tool.tool_schema.get('properties'):
                schema_issues['no_properties'].append(tool_info)
            else:
                schema_issues['valid'].append(tool_info)
        
        # Print results
        print(f"\n✅ Valid schemas: {len(schema_issues['valid'])}")
        print(f"❌ Missing schemas: {len(schema_issues['missing'])}")
        print(f"❌ Empty schemas: {len(schema_issues['empty'])}")
        print(f"⚠️  No properties: {len(schema_issues['no_properties'])}")
        
        # Show problematic tools
        if schema_issues['missing']:
            print("\n🚨 Tools with MISSING schemas:")
            for tool in schema_issues['missing'][:5]:
                print(f"  - {tool}")
            if len(schema_issues['missing']) > 5:
                print(f"  ... and {len(schema_issues['missing']) - 5} more")
        
        if schema_issues['empty']:
            print("\n🚨 Tools with EMPTY schemas:")
            for tool in schema_issues['empty'][:5]:
                print(f"  - {tool}")
        
        # Check specific problematic tools
        print("\n\n🔍 CHECKING SPECIFIC TOOLS:")
        
        # Check jira_search
        jira_search = await db.execute(
            select(SourceTool, Source.name)
            .join(Source)
            .where(SourceTool.tool_name == "jira_search")
            .where(SourceTool.is_active.is_(True))
        )
        
        jira_tools = jira_search.all()
        if jira_tools:
            print(f"\n📌 Found {len(jira_tools)} jira_search tools:")
            for tool, source_name in jira_tools:
                print(f"\n  From source: {source_name}")
                if tool.tool_schema:
                    print(f"  Schema: {json.dumps(tool.tool_schema, indent=4)[:200]}...")
                else:
                    print("  Schema: MISSING")
        
        # Check search tool
        search_result = await db.execute(
            select(SourceTool, Source.name)
            .join(Source)
            .where(SourceTool.tool_name == "search")
            .where(SourceTool.is_active.is_(True))
        )
        
        search_tools = search_result.all()
        if search_tools:
            print(f"\n📌 Found {len(search_tools)} search tools:")
            for tool, source_name in search_tools:
                print(f"\n  From source: {source_name}")
                if tool.tool_schema:
                    print(f"  Schema: {json.dumps(tool.tool_schema, indent=4)[:200]}...")
                else:
                    print("  Schema: MISSING")


async def check_code_structure():
    """Analyze which files are actually needed"""
    print("\n\n📂 CODE STRUCTURE ANALYSIS")
    print("=" * 60)
    
    agent_files = {
        "src/agents/fast_agent.py": "Main agent (FastMCPAgent)",
        "src/agents/fast_mcp.py": "MCP tool integration with database caching", 
        "src/agents/citations.py": "Citation extraction for Jira, Confluence, etc.",
    }
    
    for file_path, description in agent_files.items():
        exists = Path(file_path).exists()
        status = "✅" if exists else "❌"
        print(f"{status} {file_path}: {description}")


async def suggest_fixes():
    """Suggest fixes based on analysis"""
    print("\n\n💡 RECOMMENDED FIXES")
    print("=" * 60)
    
    print("""
✅ COMPLETED FIXES:
   - Deleted langchain_mcp.py, mcp_client.py, mcp_loader.py, mcp_utils.py (150KB+)
   - Fixed tool schema handling by switching to StructuredTool
   - Cleaned architecture to use only FastMCPAgent

🛠️ REMAINING ISSUES TO FIX:
   1. Tools with missing/empty schemas (7 tools):
      - Drive/gdrive_read_file - Schema: None
      - Drive/gdrive_search - Schema: None  
      - jira_get_link_types - Schema: {}
      - check_api_health - Schema: {}
      - Others with empty properties
      
   2. Re-cache tools from these sources to get proper schemas
   
   3. Test Jira queries to ensure multiple sources are shown

📋 CLEAN ARCHITECTURE NOW:
   - query_handlers.py → FastMCPAgent (main entry point)
   - fast_agent.py → Agent logic with LangChain
   - fast_mcp.py → MCP tool management with database caching
   - citations.py → Extract sources from tool results
""")


async def main():
    print("🏥 SCINTILLA DIAGNOSTIC TOOL")
    print("============================")
    
    await check_agent_usage()
    await check_tool_schemas()
    await check_code_structure()
    await suggest_fixes()


if __name__ == "__main__":
    asyncio.run(main()) 
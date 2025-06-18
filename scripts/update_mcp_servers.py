#!/usr/bin/env python3
"""
Update MCP Server Configurations

This script updates the MCP server configurations to:
1. Replace the GitHub server with the new GitHub server URL
2. Add the Google Drive server
"""

import asyncio
import uuid
from datetime import datetime

from src.db.base import AsyncSessionLocal
from src.db.models import MCPServerType, CredentialType, MCPServer, BotMCPCredential
from src.db.mcp_credentials import MCPCredentialManager
from sqlalchemy import select, and_

# New server configurations
NEW_SERVERS = [
    {
        "name": "Hive GitHub Server",
        "description": "IgniteTech Hive GitHub MCP server for GitHub operations", 
        "base_url": "https://mcp-server.ti.trilogy.com/973d5eff/sse",
        "api_key": "sk-hive-api01-Njg1OTJmNTAtYTc0NS00N2RkLTkxMDUtODJlNmZmNjZiZDlm-MjBlZTMzAAA",
        "replace_existing": True  # Replace existing GitHub server
    },
    {
        "name": "Hive Google Drive Server",
        "description": "IgniteTech Hive Google Drive MCP server for document access",
        "base_url": "https://mcp-server.ti.trilogy.com/25f91dbf/sse", 
        "api_key": "sk-hive-api01-Njg1OTJmNTAtYTc0NS00N2RkLTkxMDUtODJlNmZmNjZiZDlm-MjBlZTMzAAA",
        "replace_existing": False  # New server
    }
]

# Bot ID that should be updated (the one used in the frontend)
TARGET_BOT_ID = "0225c5f8-6f24-460d-8efc-da1e7266014c"

async def update_mcp_server_configs():
    """Update MCP server configurations"""
    
    print("🔄 Updating MCP Server Configurations")
    print("=" * 50)
    
    async with AsyncSessionLocal() as db:
        try:
            # Convert string bot ID to UUID
            bot_id = uuid.UUID(TARGET_BOT_ID)
            
            for server_config in NEW_SERVERS:
                print(f"\n📡 Processing: {server_config['name']}")
                print(f"   URL: {server_config['base_url']}")
                print(f"   API Key: {server_config['api_key'][:30]}...")
                
                # Check if server already exists
                query = select(MCPServer).where(MCPServer.name == server_config["name"])
                result = await db.execute(query)
                existing_server = result.scalar_one_or_none()
                
                if existing_server and server_config["replace_existing"]:
                    print(f"   🔄 Updating existing server: {server_config['name']}")
                    
                    # Update server configuration
                    existing_server.base_url = server_config["base_url"]
                    existing_server.description = server_config["description"]
                    existing_server.updated_at = datetime.utcnow()
                    
                    server = existing_server
                    
                elif existing_server:
                    print(f"   ✅ Server already exists: {server_config['name']}")
                    server = existing_server
                    
                else:
                    print(f"   ➕ Creating new server: {server_config['name']}")
                    
                    # Create new server
                    server = await MCPCredentialManager.create_mcp_server(
                        db=db,
                        name=server_config["name"],
                        description=server_config["description"],
                        server_type=MCPServerType.CUSTOM_SSE,
                        credential_type=CredentialType.API_KEY_HEADER,
                        server_config={
                            "transport": "stdio"
                        },
                        required_fields=["api_key", "base_url"],
                        base_url=server_config["base_url"],
                        is_public=False
                    )
                
                # Update or create credentials for the target bot
                print(f"   🔐 Updating credentials for bot {bot_id}")
                
                credentials = {
                    "api_key": server_config["api_key"],
                    "base_url": server_config["base_url"]
                }
                
                try:
                    credential = await MCPCredentialManager.store_bot_credentials(
                        db=db,
                        bot_id=bot_id,
                        server_id=server.server_id,
                        credentials=credentials
                    )
                    
                    print(f"   ✅ Stored credentials: {credential.credential_id}")
                    
                except Exception as e:
                    print(f"   ❌ Failed to store credentials: {e}")
                    continue
            
            await db.commit()
            
            # Verify the configuration
            print(f"\n🔍 Verifying configuration for bot {bot_id}...")
            
            configurations = await MCPCredentialManager.get_bot_mcp_configuration(db, bot_id)
            
            print(f"✅ Bot has {len(configurations)} MCP server configurations:")
            for server, creds in configurations:
                print(f"   - {server.name}")
                print(f"     URL: {server.base_url}")
                print(f"     Type: {server.server_type.value}")
                print(f"     API Key: {creds.get('api_key', '')[:30]}...")
            
            print(f"\n🎉 MCP server configuration update completed successfully!")
            return True
            
        except Exception as e:
            print(f"\n❌ Error updating MCP servers: {e}")
            await db.rollback()
            return False

async def clean_old_servers():
    """Clean up old/unused MCP servers (optional)"""
    
    print("\n🧹 Cleaning up old MCP servers...")
    
    async with AsyncSessionLocal() as db:
        try:
            # Find servers that are no longer used
            query = select(MCPServer).where(
                and_(
                    MCPServer.is_active == True,
                    MCPServer.name.not_in([s["name"] for s in NEW_SERVERS])
                )
            )
            result = await db.execute(query)
            old_servers = result.scalars().all()
            
            for server in old_servers:
                # Check if server has any active credentials
                cred_query = select(BotMCPCredential).where(
                    and_(
                        BotMCPCredential.server_id == server.server_id,
                        BotMCPCredential.is_active == True
                    )
                )
                cred_result = await db.execute(cred_query)
                active_credentials = cred_result.scalars().all()
                
                if not active_credentials:
                    print(f"   🗑️  Deactivating unused server: {server.name}")
                    server.is_active = False
                else:
                    print(f"   ⚠️  Keeping server with active credentials: {server.name}")
            
            await db.commit()
            print("✅ Cleanup completed")
            
        except Exception as e:
            print(f"❌ Error during cleanup: {e}")
            await db.rollback()

async def main():
    """Main function"""
    
    print("🚀 Starting MCP Server Configuration Update")
    print(f"Target Bot ID: {TARGET_BOT_ID}")
    print("=" * 60)
    
    # Update server configurations
    success = await update_mcp_server_configs()
    
    if success:
        # Optionally clean up old servers
        await clean_old_servers()
        
        print("\n" + "=" * 60)
        print("✅ MCP Server Update Completed Successfully!")
        print("\nNext steps:")
        print("1. Restart the backend server")
        print("2. Test the new server configurations in the frontend")
        print("3. Verify tool discovery and functionality")
    else:
        print("\n❌ MCP Server Update Failed!")
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code) 
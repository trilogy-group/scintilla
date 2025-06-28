#!/usr/bin/env python3
"""
Test script for Scintilla Local Agent

This script tests the local agent functionality including:
- Configuration loading
- Docker container management
- MCP server communication
- Tool discovery and execution
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

# Add current directory to path to import agent
sys.path.insert(0, str(Path(__file__).parent))

from agent import ScintillaLocalAgent, DockerMCPServer

async def test_config_loading():
    """Test configuration loading"""
    print("🧪 Testing configuration loading...")
    
    agent = ScintillaLocalAgent()
    try:
        await agent.load_config()
        print(f"✅ Config loaded: agent_id={agent.config.agent_id}")
        return True
    except Exception as e:
        print(f"❌ Config loading failed: {e}")
        return False

async def test_mcp_server_config():
    """Test MCP server configuration loading"""
    print("🧪 Testing MCP server configuration...")
    
    agent = ScintillaLocalAgent()
    try:
        await agent.load_config()
        # Test config file exists and is readable
        import yaml
        with open(agent.mcp_config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        
        servers_config = config_data.get('servers', [])
        print(f"✅ MCP server config loaded: {len(servers_config)} servers configured")
        for server in servers_config:
            print(f"  - {server['name']}: {server['image']}")
        return True
    except Exception as e:
        print(f"❌ MCP server config failed: {e}")
        return False

async def test_docker_availability():
    """Test Docker availability"""
    print("🧪 Testing Docker availability...")
    
    import subprocess
    try:
        result = subprocess.run(["docker", "version"], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Docker is available")
            return True
        else:
            print(f"❌ Docker not available: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Docker test failed: {e}")
        return False

async def test_docker_image_pull():
    """Test pulling the MCP Atlassian image"""
    print("🧪 Testing Docker image pull...")
    
    import subprocess
    try:
        print("📦 Pulling ghcr.io/sooperset/mcp-atlassian:latest...")
        result = subprocess.run([
            "docker", "pull", "ghcr.io/sooperset/mcp-atlassian:latest"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Docker image pulled successfully")
            return True
        else:
            print(f"❌ Image pull failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Image pull test failed: {e}")
        return False

async def test_mcp_server_creation():
    """Test MCP server object creation"""
    print("🧪 Testing MCP server creation...")
    
    try:
        # Create a test logger
        test_logger = logging.getLogger("test")
        
        # Create a test configuration dictionary
        server_config = {
            "name": "test-server",
            "image": "ghcr.io/sooperset/mcp-atlassian",
            "tag": "latest",
            "environment": {
                "CONFLUENCE_URL": "https://test.confluence.com",
                "CONFLUENCE_PERSONAL_TOKEN": "test-confluence-token",
                "CONFLUENCE_SSL_VERIFY": "false",
                "JIRA_URL": "https://test.jira.com",
                "JIRA_PERSONAL_TOKEN": "test-jira-token",
                "JIRA_SSL_VERIFY": "false"
            },
            "capabilities": ["jira_operations", "confluence_operations"]
        }
        
        mcp_server = DockerMCPServer(server_config, test_logger)
        print(f"✅ MCP server created: {mcp_server.name}")
        return True
    except Exception as e:
        print(f"❌ MCP server creation failed: {e}")
        return False

async def test_agent_initialization():
    """Test full agent initialization (without Docker start)"""
    print("🧪 Testing agent initialization...")
    
    try:
        agent = ScintillaLocalAgent()
        await agent.load_config()
        
        # Test that the config paths exist
        print(f"✅ Agent initialized with config at {agent.mcp_config_path}")
        return True
    except Exception as e:
        print(f"❌ Agent initialization failed: {e}")
        return False

async def test_mcp_communication():
    """Test MCP communication with real Atlassian server (if credentials available)"""
    print("🧪 Testing MCP communication...")
    
    try:
        # Create a test logger
        test_logger = logging.getLogger("test_mcp")
        test_logger.setLevel(logging.INFO)
        if not test_logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            test_logger.addHandler(handler)
        
        # Load the real configuration
        import yaml
        config_path = Path(__file__).parent / "mcp_servers.yaml"
        
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        
        servers_config = config_data.get('servers', [])
        if not servers_config:
            print("⏭️  No servers configured, skipping MCP communication test")
            return True
        
        # Test with the first configured server
        server_config = servers_config[0]
        print(f"🔗 Testing MCP communication with {server_config['name']}")
        
        # Create and start the MCP server
        mcp_server = DockerMCPServer(server_config, test_logger)
        
        try:
            print("🚀 Starting Docker container...")
            await mcp_server.start()
            
            print("✅ MCP server started successfully!")
            print(f"📋 Discovered {len(mcp_server.tools)} tools")
            
            # List some tools
            for i, tool in enumerate(mcp_server.tools[:3]):
                print(f"  {i+1}. {tool.get('name', 'unknown')}: {tool.get('description', 'no description')}")
            
            if len(mcp_server.tools) > 3:
                print(f"  ... and {len(mcp_server.tools) - 3} more tools")
            
            return True
            
        finally:
            # Always clean up
            print("🧹 Stopping MCP server...")
            await mcp_server.stop()
            
    except Exception as e:
        print(f"❌ MCP communication test failed: {e}")
        return False

async def run_tests():
    """Run all tests"""
    print("🚀 Starting Scintilla Local Agent Tests\n")
    
    tests = [
        ("Configuration Loading", test_config_loading),
        ("MCP Server Config", test_mcp_server_config),
        ("Docker Availability", test_docker_availability),
        ("Docker Image Pull", test_docker_image_pull),
        ("MCP Server Creation", test_mcp_server_creation),
        ("Agent Initialization", test_agent_initialization),
        ("MCP Communication", test_mcp_communication),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Test '{test_name}' crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*50)
    print("TEST SUMMARY")
    print("="*50)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status:8} {test_name}")
        if result:
            passed += 1
    
    print(f"\nResults: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("🎉 All tests passed! The local agent is ready to use.")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
    
    return passed == len(results)

if __name__ == "__main__":
    asyncio.run(run_tests()) 
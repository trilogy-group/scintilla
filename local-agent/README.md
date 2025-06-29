# Scintilla Local Agent

A local agent that manages Docker-based MCP (Model Context Protocol) servers and acts as a bridge between your local environment and the Scintilla server.

## Features

- 🐳 **Docker Integration**: Automatically manages Docker containers running MCP servers
- 🔌 **MCP Protocol**: Full support for MCP 2024-11-05 protocol via stdio communication
- 🔄 **Polling Architecture**: Polls Scintilla server for work and executes tools locally
- 🏗️ **Tool Discovery**: Automatically discovers and registers tools from MCP servers
- 🔧 **Atlassian Integration**: Pre-configured for [mcp-atlassian](https://github.com/sooperset/mcp-atlassian) server
- 📋 **Flexible Configuration**: YAML-based configuration for easy customization
- 🛡️ **Reliability Features**: Automatic retry, health checking, and reconnection handling

## Reliability & Resilience

The local agent includes robust reliability features to handle real-world deployment scenarios:

### 🔄 Automatic Retry with Exponential Backoff
- Failed operations are automatically retried with increasing delays
- Prevents overwhelming a recovering server with rapid retry attempts
- Configurable retry limits and timing

### 🏥 Health Checking & Auto-Reconnection
- Continuously monitors server availability when disconnected
- Automatically re-registers when server restarts
- Maintains state consistency across reconnections

### 🔗 Connection State Management
- Tracks connection status and registration state
- Gracefully handles temporary network interruptions
- Distinguishes between temporary failures and persistent issues

**For detailed information about reliability features, see [RELIABILITY.md](RELIABILITY.md)**

## Quick Start

### Prerequisites

- Python 3.8+
- Docker
- Access to a running Scintilla server

### Installation

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure the agent:**
   ```bash
   # Copy the example config and customize for your environment
   cp config.yaml.example config.yaml
   # Edit config.yaml with your Scintilla server URL and agent token
   ```

3. **Configure MCP servers:**
   ```bash
   # Copy the example config and customize with your credentials
   cp mcp_servers.yaml.example mcp_servers.yaml
   # Edit mcp_servers.yaml with your actual API tokens and URLs
   ```

4. **Start the agent:**
   ```bash
   python agent.py
   ```

## Configuration

### Agent Configuration (`config.yaml`)

Copy `config.yaml.example` to `config.yaml` and customize for your environment:

```yaml
# Unique identifier for this agent instance
agent_id: "local-agent-1"

# Scintilla server URL
server_url: "http://localhost:8000"

# Agent capabilities
capabilities:
  - "docker_mcp_management"
  - "atlassian_integration"
  - "local_tool_execution"
  - "mcp_protocol_bridge"

# Polling interval (seconds)
poll_interval: 2.0

# MCP servers configuration file
mcp_servers_config: "mcp_servers.yaml"

# Docker timeout for operations
docker_timeout: 30

# Logging level
log_level: "INFO"
```

### MCP Servers Configuration (`mcp_servers.yaml`)

Copy `mcp_servers.yaml.example` to `mcp_servers.yaml` and customize with your credentials:

```yaml
servers:
  # Atlassian MCP Server
  - name: "khoros-atlassian"
    image: "ghcr.io/sooperset/mcp-atlassian"
    tag: "latest"
    auto_start: true
    capabilities:
      - "jira_operations"
      - "confluence_operations"
      - "atlassian_integration"
    environment:
      # Confluence configuration
      CONFLUENCE_URL: "https://confluence.dev.lithium.com"
      CONFLUENCE_PERSONAL_TOKEN: "your_confluence_token_here"
      CONFLUENCE_SSL_VERIFY: "false"
      # Jira configuration  
      JIRA_URL: "https://jira.dev.lithium.com"
      JIRA_PERSONAL_TOKEN: "your_jira_token_here"
      JIRA_SSL_VERIFY: "false"
    volumes: {}
```

## Setting up Atlassian Integration

1. **Get Personal Access Tokens:**
   - **For Confluence:** Go to your Confluence instance → Profile → Personal Access Tokens
   - **For Jira:** Go to your Jira instance → Profile → Personal Access Tokens
   - Create tokens with appropriate permissions for reading/writing content

2. **Configure environment variables in `mcp_servers.yaml`:**
   ```yaml
   environment:
     # Confluence configuration
     CONFLUENCE_URL: "https://confluence.dev.lithium.com"
     CONFLUENCE_PERSONAL_TOKEN: "your_confluence_token_here"
     CONFLUENCE_SSL_VERIFY: "false"
     # Jira configuration  
     JIRA_URL: "https://jira.dev.lithium.com"
     JIRA_PERSONAL_TOKEN: "your_jira_token_here"
     JIRA_SSL_VERIFY: "false"
   ```

3. **Test the connection:**
   ```bash
   # Pull the Docker image first
   docker pull ghcr.io/sooperset/mcp-atlassian:latest
   
   # Start the agent
   python agent.py
   ```

## Usage with Scintilla

Once the local agent is running and registered with Scintilla, you can use local tools by creating sources with the appropriate URL schemes:

### Creating Local Sources in Scintilla

1. **Atlassian Tools (via local agent):**
   ```
   # In Scintilla UI, create a source with:
   URL: local://atlassian-jira
   URL: local://atlassian-confluence
   ```

2. **The agent will:**
   - Receive tool execution requests from Scintilla
   - Route them to the appropriate MCP server container
   - Execute tools using MCP protocol
   - Return results to Scintilla

### Example Query Flow

1. User asks: "What Jira tickets are assigned to me?"
2. Scintilla routes to local agent (based on `local://` URL scheme)
3. Local agent executes Jira search tool in mcp-atlassian container
4. Results are returned through the polling mechanism
5. Scintilla displays the results to the user

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌──────────────────┐
│  Scintilla      │    │  Local Agent    │    │  Docker MCP      │
│  Server         │    │                 │    │  Server          │
│                 │    │                 │    │                  │
│  1. Query       │───▶│  2. Poll        │    │                  │
│  2. Route       │    │  3. Execute     │───▶│  4. MCP Protocol │
│  3. Response    │◀───│  4. Submit      │◀───│  5. Tool Result  │
└─────────────────┘    └─────────────────┘    └──────────────────┘
```

## MCP Protocol Communication

The agent communicates with MCP servers using the standard MCP protocol:

1. **Initialize**: Establish connection and capabilities
2. **Tools List**: Discover available tools
3. **Tool Call**: Execute tools with parameters
4. **Response**: Receive structured results

## Monitoring and Debugging

### Logs

The agent provides detailed logging:

```bash
2024-01-15 10:30:15 - scintilla_agent - INFO - 🐳 Started container atlassian: a1b2c3d4e5f6
2024-01-15 10:30:17 - scintilla_agent - INFO - ✅ Initialized MCP connection for atlassian
2024-01-15 10:30:18 - scintilla_agent - INFO - 📋 Loaded 15 tools from atlassian
2024-01-15 10:30:20 - scintilla_agent - INFO - Successfully registered with server
2024-01-15 10:30:22 - scintilla_agent - INFO - 🚀 Starting polling loop...
```

### Docker Container Status

Check running containers:
```bash
docker ps | grep mcp
```

### Agent Status

The agent reports its status to Scintilla including:
- Running MCP servers
- Available tools
- Container health

## Troubleshooting

### Common Issues

1. **Docker not available:**
   ```bash
   # Check Docker is running
   docker version
   ```

2. **MCP server fails to start:**
   ```bash
   # Check Docker logs
   docker logs <container-id>
   ```

3. **Authentication errors:**
   - Verify API tokens and credentials
   - Check network connectivity

4. **Agent registration fails:**
   - Verify Scintilla server URL
   - Check network connectivity
   - Review agent logs

### Debug Mode

Enable debug logging:
```yaml
log_level: "DEBUG"
```

This will show detailed MCP protocol messages and Docker operations.

## Adding Custom MCP Servers

To add your own MCP servers:

1. **Create a Dockerfile** for your MCP server
2. **Add configuration** in `mcp_servers.yaml`:
   ```yaml
   - name: "my-server"
     image: "my-registry/my-mcp-server"
     tag: "latest"
     auto_start: true
     capabilities:
       - "custom_operations"
     environment:
       API_KEY: "your-api-key"
     volumes:
       "/local/path": "/container/path"
   ```

3. **Implement MCP protocol** in your server
4. **Restart the agent** to pick up the new server

## Security Considerations

- **API Tokens**: Store securely, consider using environment variables
- **Network**: Agent communicates with Scintilla over HTTP (use HTTPS in production)
- **Docker**: Containers run with default Docker security settings
- **Volumes**: Be careful with volume mounts to avoid exposing sensitive data

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test with different MCP servers
5. Submit a pull request

## License

This project is licensed under the MIT License. 
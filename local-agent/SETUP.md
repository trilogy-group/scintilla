# Quick Setup Guide for Team Atlassian Configuration

This guide will help you quickly set up the Scintilla Local Agent with your team's Atlassian (Confluence + Jira) configuration.

## Step 1: Get Your Personal Access Tokens

You'll need to create Personal Access Tokens for both Confluence and Jira:

### Confluence Token
1. Go to https://confluence.dev.lithium.com
2. Click your profile → **Personal Access Tokens**
3. Create a new token with these permissions:
   - `Read` access for searching content
   - `Write` access if you want to create/edit pages
4. Copy the token

### Jira Token  
1. Go to https://jira.dev.lithium.com
2. Click your profile → **Personal Access Tokens**
3. Create a new token with these permissions:
   - `Read` access for searching issues
   - `Write` access if you want to create/edit issues
4. Copy the token

## Step 2: Configure the Local Agent

Edit the `mcp_servers.yaml` file and replace the placeholder tokens:

```yaml
servers:
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
      CONFLUENCE_PERSONAL_TOKEN: "YOUR_CONFLUENCE_TOKEN_HERE"  # ← Replace this
      CONFLUENCE_SSL_VERIFY: "false"
      # Jira configuration  
      JIRA_URL: "https://jira.dev.lithium.com"
      JIRA_PERSONAL_TOKEN: "YOUR_JIRA_TOKEN_HERE"  # ← Replace this
      JIRA_SSL_VERIFY: "false"
    volumes: {}
```

## Step 3: Pull the Docker Image

```bash
docker pull ghcr.io/sooperset/mcp-atlassian:latest
```

## Step 4: Test the Setup

Run the test script to verify everything is configured correctly:

```bash
python3 test_agent.py
```

## Step 5: Start the Agent

```bash
# Option 1: Use the startup script
./start.sh

# Option 2: Run directly
python3 agent.py
```

## Step 6: Configure Scintilla Sources

Once the local agent is running, create sources in Scintilla with these URLs:

- **For Confluence searches:** `local://confluence-search`
- **For Jira searches:** `local://jira-search`  
- **For general Atlassian tools:** `local://khoros-atlassian`

## Troubleshooting

### "Permission denied" errors
- Verify your Personal Access Tokens have the correct permissions
- Check that the tokens haven't expired

### "Connection refused" errors  
- Ensure you're on the company network or VPN
- Verify the URLs are accessible from your machine

### "Docker not found" errors
- Install Docker Desktop and ensure it's running
- Verify with: `docker version`

### Agent registration fails
- Check that your Scintilla server is running on `http://localhost:8000`
- Update the `server_url` in `config.yaml` if different

## Security Notes

- Never commit your Personal Access Tokens to version control
- Consider using environment variables for sensitive values:
  ```bash
  export CONFLUENCE_PERSONAL_TOKEN="your_token_here"
  export JIRA_PERSONAL_TOKEN="your_token_here"
  ```

## What's Next?

Once everything is working:

1. The local agent will automatically register with Scintilla
2. It will discover available tools from the mcp-atlassian container
3. You can query Confluence and Jira content through Scintilla
4. Tools will execute locally for security and performance

Example queries you can try in Scintilla:
- "Show me my assigned Jira tickets"
- "Search for recent Confluence pages about API documentation"
- "What are the open critical bugs in project XYZ?" 
# Local Agent Reliability Features

The Scintilla Local Agent includes robust reliability features to handle server restarts, network issues, and connection failures automatically.

## Features

### 🔄 Automatic Retry with Exponential Backoff
- Failed operations are automatically retried with increasing delays
- Prevents overwhelming a recovering server with rapid retry attempts
- Configurable retry limits and timing

### 🏥 Health Checking
- Continuously monitors server availability when disconnected
- Uses lightweight health check endpoint (`/health`)
- Only attempts re-registration when server is confirmed healthy

### 📡 Automatic Re-registration
- Detects when server restarts and agent registration is lost
- Automatically re-registers with all capabilities and tools
- Maintains state consistency across reconnections

### 🔗 Connection State Management
- Tracks connection status and registration state
- Gracefully handles temporary network interruptions
- Distinguishes between temporary failures and persistent issues

## Configuration

Configure reliability behavior in `config.yaml`:

```yaml
# Maximum number of retry attempts for failed operations
max_retry_attempts: 5

# Initial delay before first retry (in seconds)
initial_retry_delay: 1.0

# Backoff multiplier for exponential backoff
retry_backoff_multiplier: 2.0

# Maximum delay between retries (in seconds)
max_retry_delay: 60.0

# How often to check server health when disconnected (in seconds)
health_check_interval: 30.0

# Timeout for HTTP requests to server (in seconds)
connection_timeout: 10.0
```

## How It Works

### Initial Startup
1. Agent loads configuration and starts MCP servers
2. Attempts registration with retry logic
3. If registration fails, keeps retrying with exponential backoff
4. Only starts polling once successfully registered

### During Normal Operation
1. Polls for work with reliability monitoring
2. Tracks consecutive failures
3. After 3 consecutive failures, assumes connection is lost
4. Enters reconnection mode

### Reconnection Process
1. Marks agent as disconnected and unregistered
2. Performs health checks every `health_check_interval` seconds
3. When server is healthy, attempts re-registration with retry logic
4. Resumes normal polling once reconnected

### Exponential Backoff Algorithm
- **Attempt 1**: Wait `initial_retry_delay` seconds (default: 1s)
- **Attempt 2**: Wait `initial_retry_delay * backoff_multiplier` seconds (default: 2s)
- **Attempt 3**: Wait `initial_retry_delay * backoff_multiplier²` seconds (default: 4s)
- **Attempt 4**: Wait `initial_retry_delay * backoff_multiplier³` seconds (default: 8s)
- **Attempt 5**: Wait up to `max_retry_delay` seconds (default: 60s max)

## Logging

The agent provides detailed logging for reliability events:

- `🔄` Retry attempts and successes
- `⚠️` Connection warnings and failures  
- `🔌` Connection loss detection
- `🏥` Health check results
- `📡` Registration attempts
- `🎉` Successful reconnections

## Example Scenarios

### Server Restart
1. Agent detects polling failures
2. Enters reconnection mode
3. Health checks fail while server is down
4. When server comes back up, health check succeeds
5. Agent re-registers and resumes work

### Network Interruption
1. Agent detects consecutive polling failures
2. Attempts immediate reconnection
3. If network is restored quickly, minimal downtime
4. If network issue persists, falls back to health checking

### Temporary Server Overload
1. Registration or polling requests timeout
2. Exponential backoff prevents overwhelming server
3. Agent backs off gracefully and retries when server recovers

## Best Practices

1. **Tune for Your Environment**: Adjust retry settings based on your network and server characteristics
2. **Monitor Logs**: Watch for patterns in connection issues to identify infrastructure problems
3. **Set Reasonable Timeouts**: Balance between quick failure detection and patience for slow responses
4. **Test Resilience**: Regularly test by restarting the Scintilla server while agents are running

## Troubleshooting

### Agent Won't Connect Initially
- Check `server_url` is correct and server is running
- Verify `agent_token` is valid
- Check network connectivity and firewall rules

### Frequent Disconnections
- Review network stability between agent and server
- Check server logs for errors or resource issues
- Consider increasing `connection_timeout` for slow networks

### Slow Recovery After Server Restart
- Decrease `health_check_interval` for faster detection
- Adjust retry timing for quicker reconnection
- Verify health endpoint is responding quickly 
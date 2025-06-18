"""
URL parsing utilities for MCP endpoints

Handles parsing URLs like:
@https://mcp-server.ti.trilogy.com/0cf9bd44/sse?x-api-key=sk-hive-api01-...
"""

import re
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from typing import Tuple, Optional, Dict
import structlog

logger = structlog.get_logger()


class MCPUrlParseError(Exception):
    """Raised when MCP URL parsing fails"""
    pass


def parse_mcp_url(url: str) -> Tuple[str, Optional[str]]:
    """
    Parse an MCP URL with embedded API key.
    
    Args:
        url: URL string like "@https://server.com/path/sse?x-api-key=sk-..."
        
    Returns:
        Tuple of (base_url, api_key)
        
    Raises:
        MCPUrlParseError: If URL format is invalid
    """
    # Remove leading @ if present
    clean_url = url.lstrip('@')
    
    try:
        parsed = urlparse(clean_url)
    except Exception as e:
        raise MCPUrlParseError(f"Invalid URL format: {e}")
    
    if not parsed.scheme or not parsed.netloc:
        raise MCPUrlParseError("URL must include scheme and domain")
    
    # Parse query parameters
    query_params = parse_qs(parsed.query)
    
    # Extract API key from various possible parameter names
    api_key = None
    api_key_params = ['x-api-key', 'api-key', 'apikey', 'key', 'token']
    
    for param_name in api_key_params:
        if param_name in query_params:
            api_key = query_params[param_name][0]  # Take first value
            # Remove the API key from query params
            del query_params[param_name]
            break
    
    # Reconstruct URL without API key
    clean_query = urlencode(query_params, doseq=True)
    base_url = urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        clean_query,
        parsed.fragment
    ))
    
    logger.info(
        "Parsed MCP URL",
        base_url=base_url,
        has_api_key=api_key is not None,
        api_key_length=len(api_key) if api_key else 0
    )
    
    return base_url, api_key


def reconstruct_mcp_url(base_url: str, api_key: str, key_param: str = 'x-api-key') -> str:
    """
    Reconstruct a full MCP URL with API key.
    
    Args:
        base_url: Base URL without API key
        api_key: API key to embed
        key_param: Parameter name for the API key
        
    Returns:
        Full URL with embedded API key
    """
    parsed = urlparse(base_url)
    query_params = parse_qs(parsed.query)
    
    # Add API key
    query_params[key_param] = [api_key]
    
    # Reconstruct URL
    full_query = urlencode(query_params, doseq=True)
    full_url = urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        full_query,
        parsed.fragment
    ))
    
    return full_url


def validate_mcp_url(url: str) -> bool:
    """
    Validate that a URL looks like a valid MCP endpoint.
    
    Args:
        url: URL to validate
        
    Returns:
        True if URL appears valid for MCP
    """
    try:
        base_url, api_key = parse_mcp_url(url)
        
        # Basic validation checks
        parsed = urlparse(base_url)
        
        # Must be HTTPS (security requirement)
        if parsed.scheme != 'https':
            logger.warning("MCP URL should use HTTPS", url=base_url)
            return False
        
        # Should end with /sse (typical MCP pattern)
        if not parsed.path.endswith('/sse'):
            logger.warning("MCP URL should end with /sse", url=base_url, path=parsed.path)
        
        # Should have an API key
        if not api_key:
            logger.warning("MCP URL missing API key", url=base_url)
            return False
        
        # API key should look like a Hive key (starts with sk-hive-)
        if not api_key.startswith('sk-hive-'):
            logger.warning("API key doesn't look like Hive format", api_key_prefix=api_key[:10])
        
        return True
        
    except MCPUrlParseError as e:
        logger.error("MCP URL validation failed", error=str(e), url=url)
        return False


def extract_server_info(url: str) -> Dict[str, str]:
    """
    Extract useful server information from MCP URL.
    
    Args:
        url: MCP URL
        
    Returns:
        Dictionary with server info
    """
    try:
        base_url, api_key = parse_mcp_url(url)
        parsed = urlparse(base_url)
        
        # Extract server ID from path (e.g., /0cf9bd44/sse -> 0cf9bd44)
        path_parts = [p for p in parsed.path.split('/') if p]
        server_id = None
        
        if len(path_parts) >= 2 and path_parts[-1] == 'sse':
            server_id = path_parts[-2]
        
        return {
            'domain': parsed.netloc,
            'server_id': server_id,
            'path': parsed.path,
            'has_api_key': api_key is not None,
            'base_url': base_url
        }
        
    except MCPUrlParseError:
        return {}


# Example usage and testing
if __name__ == "__main__":
    # Test URL parsing
    test_url = "@https://mcp-server.ti.trilogy.com/0cf9bd44/sse?x-api-key=sk-hive-api01-test"
    
    try:
        base_url, api_key = parse_mcp_url(test_url)
        print(f"Base URL: {base_url}")
        print(f"API Key: {api_key[:20]}..." if api_key else "No API key")
        
        # Test reconstruction
        reconstructed = reconstruct_mcp_url(base_url, api_key)
        print(f"Reconstructed: {reconstructed}")
        
        # Test validation
        is_valid = validate_mcp_url(test_url)
        print(f"Valid: {is_valid}")
        
        # Test server info
        info = extract_server_info(test_url)
        print(f"Server info: {info}")
        
    except MCPUrlParseError as e:
        print(f"Error: {e}") 
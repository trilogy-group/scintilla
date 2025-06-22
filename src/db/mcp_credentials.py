"""
Simplified MCP Credential Management System

Handles plain text credential storage in the auth_headers JSONB field.
Unified approach for both Hive-style URLs and header-based authentication.
"""

import uuid
from typing import Dict, List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
import structlog

from .models import Source

logger = structlog.get_logger()


class SimplifiedCredentialManager:
    """
    Simplified credential manager using auth_headers JSONB field
    
    Two authentication modes:
    1. Header-based: auth_headers contains {"Authorization": "Bearer token"} or {"x-api-key": "key"}
    2. URL-embedded: auth_headers is empty, credentials embedded in server_url
    """
    
    @staticmethod
    async def store_source_auth(
        db: AsyncSession,
        source_id: uuid.UUID,
        server_url: str,
        auth_headers: Optional[Dict[str, str]] = None
    ) -> bool:
        """
        Store authentication for a source
        
        Args:
            db: Database session
            source_id: Source ID to store auth for
            server_url: Server URL (base SSE URL or full URL with embedded auth)
            auth_headers: Optional headers for authentication
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Update source with new auth configuration
            await db.execute(
                update(Source)
                .where(Source.source_id == source_id)
                .values(
                    server_url=server_url,
                    auth_headers=auth_headers or {}
                )
            )
            await db.commit()
            
            auth_type = "headers" if auth_headers else "url_embedded"
            logger.info(
                "Stored source authentication",
                source_id=source_id,
                auth_type=auth_type,
                header_count=len(auth_headers) if auth_headers else 0
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "Failed to store source authentication",
                source_id=source_id,
                error=str(e)
            )
            await db.rollback()
            return False
    
    @staticmethod
    async def get_source_auth(
        db: AsyncSession,
        source_id: uuid.UUID
    ) -> Optional[Dict[str, Any]]:
        """
        Get authentication configuration for a source
        
        Args:
            db: Database session
            source_id: Source ID to get auth for
            
        Returns:
            Dict with server_url and auth_headers, or None if not found
        """
        try:
            result = await db.execute(
                select(Source.server_url, Source.auth_headers)
                .where(Source.source_id == source_id)
            )
            source_data = result.first()
            
            if not source_data:
                logger.warning("Source not found", source_id=source_id)
                return None
            
            server_url, auth_headers = source_data
            
            return {
                "server_url": server_url,
                "auth_headers": auth_headers or {}
            }
            
        except Exception as e:
            logger.error(
                "Failed to get source authentication",
                source_id=source_id,
                error=str(e)
            )
            return None
    
    @staticmethod
    async def get_sources_auth_config(
        db: AsyncSession,
        source_ids: List[uuid.UUID]
    ) -> List[Dict[str, Any]]:
        """
        Get authentication configuration for multiple sources
        
        Args:
            db: Database session
            source_ids: List of source IDs to get auth for
            
        Returns:
            List of source configurations with auth
        """
        if not source_ids:
            return []
        
        try:
            result = await db.execute(
                select(Source.source_id, Source.name, Source.server_url, Source.auth_headers)
                .where(
                    Source.source_id.in_(source_ids),
                    Source.is_active.is_(True)
                )
            )
            
            configurations = []
            for source_id, name, server_url, auth_headers in result.all():
                config = {
                    "source_id": source_id,
                    "name": name,
                    "server_url": server_url,
                    "auth_headers": auth_headers or {}
                }
                configurations.append(config)
            
            logger.debug(
                "Retrieved source auth configurations",
                source_ids=source_ids,
                found_count=len(configurations)
            )
            
            return configurations
            
        except Exception as e:
            logger.error(
                "Failed to get sources auth configuration",
                source_ids=source_ids,
                error=str(e)
            )
            return []


# Compatibility layer for existing code
class MCPCredentialManager:
    """
    Compatibility layer that maintains the old interface while using the new system
    """
    
    @staticmethod
    async def get_source_credentials(
        db: AsyncSession,
        source_id: uuid.UUID
    ) -> Optional[Dict[str, str]]:
        """
        Get credentials for a source (compatibility method)
        
        Returns API key from auth_headers if available, otherwise extracts from URL
        """
        auth_config = await SimplifiedCredentialManager.get_source_auth(db, source_id)
        
        if not auth_config:
            return None
        
        # Extract API key from headers or URL
        auth_headers = auth_config.get("auth_headers", {})
        
        # Try to extract API key from various header formats
        api_key = None
        if "Authorization" in auth_headers:
            # Bearer token format
            auth_value = auth_headers["Authorization"]
            if auth_value.startswith("Bearer "):
                api_key = auth_value[7:]  # Remove "Bearer " prefix
        elif "x-api-key" in auth_headers:
            api_key = auth_headers["x-api-key"]
        elif "api_key" in auth_headers:
            api_key = auth_headers["api_key"]
        
        # If no API key in headers, try to extract from URL (Hive style)
        if not api_key:
            server_url = auth_config.get("server_url", "")
            if "x-api-key=" in server_url:
                # Extract from URL parameter
                from urllib.parse import urlparse, parse_qs
                parsed = urlparse(server_url)
                query_params = parse_qs(parsed.query)
                if "x-api-key" in query_params:
                    api_key = query_params["x-api-key"][0]
        
        return {"api_key": api_key} if api_key else {}
    
    @staticmethod
    async def store_source_credentials(
        db: AsyncSession,
        source_id: uuid.UUID,
        credentials: Dict[str, str]
    ) -> bool:
        """
        Store credentials for a source (compatibility method)
        """
        # Extract API key and determine storage method
        api_key = credentials.get("api_key")
        if not api_key:
            return False
        
        # Get current source info
        result = await db.execute(
            select(Source.server_url).where(Source.source_id == source_id)
        )
        current_url = result.scalar_one_or_none()
        
        if not current_url:
            return False
        
        # Decide whether to use headers or embed in URL
        # For now, default to headers approach for new sources
        auth_headers = {"Authorization": f"Bearer {api_key}"}
        
        return await SimplifiedCredentialManager.store_source_auth(
            db, source_id, current_url, auth_headers
        )
    
    @staticmethod
    async def get_user_sources_with_credentials(
        db: AsyncSession,
        user_id: uuid.UUID
    ) -> List[Dict[str, Any]]:
        """
        Get all sources for a user with their configurations (compatibility method)
        """
        try:
            # Get user's active sources
            result = await db.execute(
                select(Source.source_id, Source.name, Source.server_url, Source.auth_headers)
                .where(
                    Source.owner_user_id == user_id,
                    Source.is_active.is_(True)
                )
            )
            
            configurations = []
            for source_id, name, server_url, auth_headers in result.all():
                # Get credentials using compatibility method
                credentials = await MCPCredentialManager.get_source_credentials(db, source_id)
                
                if credentials and credentials.get("api_key"):
                    config = {
                        "source_id": source_id,
                        "name": name,
                        "server_url": server_url,
                        "credentials": credentials
                    }
                    configurations.append(config)
            
            return configurations
            
        except Exception as e:
            logger.error(
                "Failed to get user sources with credentials",
                user_id=user_id,
                error=str(e)
            )
            return []
    
    @staticmethod
    async def get_bot_sources_with_credentials(
        db: AsyncSession,
        source_ids: List[uuid.UUID]
    ) -> List[Dict[str, Any]]:
        """
        Get sources by IDs with their configurations (compatibility method)
        """
        try:
            if not source_ids:
                return []
            
            # Get sources by IDs
            result = await db.execute(
                select(Source.source_id, Source.name, Source.server_url, Source.auth_headers)
                .where(
                    Source.source_id.in_(source_ids),
                    Source.is_active.is_(True)
                )
            )
            
            configurations = []
            for source_id, name, server_url, auth_headers in result.all():
                # Get credentials using compatibility method
                credentials = await MCPCredentialManager.get_source_credentials(db, source_id)
                
                if credentials and credentials.get("api_key"):
                    config = {
                        "source_id": source_id,
                        "name": name,
                        "server_url": server_url,
                        "credentials": credentials
                    }
                    configurations.append(config)
            
            return configurations
            
        except Exception as e:
            logger.error(
                "Failed to get bot sources with credentials",
                source_ids=source_ids,
                error=str(e)
            )
            return []


# Convenience functions (compatibility)
async def get_source_credentials(
    db: AsyncSession,
    source_id: uuid.UUID
) -> Optional[Dict[str, str]]:
    """Convenience function for getting source credentials"""
    return await MCPCredentialManager.get_source_credentials(db, source_id)


async def store_source_credentials(
    db: AsyncSession,
    source_id: uuid.UUID,
    credentials: Dict[str, str]
) -> bool:
    """Convenience function for storing source credentials"""
    return await MCPCredentialManager.store_source_credentials(db, source_id, credentials)


async def get_user_sources_with_credentials(
    db: AsyncSession,
    user_id: uuid.UUID
) -> List[Dict[str, Any]]:
    """Convenience function for getting user sources with credentials"""
    return await MCPCredentialManager.get_user_sources_with_credentials(db, user_id)


async def get_bot_sources_with_credentials(
    db: AsyncSession,
    source_ids: List[uuid.UUID]
) -> List[Dict[str, Any]]:
    """Convenience function for getting bot sources with credentials"""
    return await MCPCredentialManager.get_bot_sources_with_credentials(db, source_ids) 
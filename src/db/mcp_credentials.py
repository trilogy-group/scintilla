"""
MCP Credential Management System

Handles encrypted storage and retrieval of MCP server credentials using AWS KMS.
Updated to work with Sources instead of Bots.
"""

import json
import uuid
from typing import Dict, List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
import structlog

from .models import Source, MCPCredential, User
from .encryption import encrypt_string, decrypt_string

logger = structlog.get_logger()


class MCPCredentialManager:
    """
    Manages encrypted MCP server credentials for sources
    """
    
    @staticmethod
    async def store_source_credentials(
        db: AsyncSession,
        source_id: uuid.UUID,
        credentials: Dict[str, str]
    ) -> bool:
        """
        Store encrypted credentials for a source
        
        Args:
            db: Database session
            source_id: Source ID to store credentials for
            credentials: Dictionary of credential field -> value
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get the source to validate it exists and get required fields
            result = await db.execute(
                select(Source).where(Source.source_id == source_id)
            )
            source = result.scalar_one_or_none()
            
            if not source:
                logger.error("Source not found", source_id=source_id)
                return False
            
            # Validate that all required fields are provided
            required_fields = source.required_fields or []
            missing_fields = [field for field in required_fields if field not in credentials]
            if missing_fields:
                logger.error(
                    "Missing required credential fields",
                    source_id=source_id,
                    missing_fields=missing_fields
                )
                return False
            
            # Delete existing credentials for this source
            await db.execute(
                select(MCPCredential).where(MCPCredential.source_id == source_id)
            )
            existing_creds = (await db.execute(
                select(MCPCredential).where(MCPCredential.source_id == source_id)
            )).scalars().all()
            
            for cred in existing_creds:
                await db.delete(cred)
            
            # Store each credential field
            for field_name, value in credentials.items():
                if not value:  # Skip empty values
                    continue
                    
                # Encrypt the credential value
                encrypted_value = encrypt_string(value)
                
                # Create credential record
                from .models import CredentialType
                credential = MCPCredential(
                    source_id=source_id,
                    credential_type=CredentialType.API_KEY_HEADER,
                    encrypted_value=encrypted_value,
                    field_name=field_name
                )
                
                db.add(credential)
            
            await db.commit()
            
            logger.info(
                "Stored credentials for source",
                source_id=source_id,
                field_count=len(credentials)
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "Failed to store source credentials",
                source_id=source_id,
                error=str(e)
            )
            await db.rollback()
            return False
    
    @staticmethod
    async def get_source_credentials(
        db: AsyncSession,
        source_id: uuid.UUID
    ) -> Optional[Dict[str, str]]:
        """
        Retrieve and decrypt credentials for a source
        
        Args:
            db: Database session
            source_id: Source ID to get credentials for
            
        Returns:
            Dictionary of decrypted credentials or None if not found
        """
        try:
            # Get all credentials for this source
            result = await db.execute(
                select(MCPCredential).where(MCPCredential.source_id == source_id)
            )
            credentials = result.scalars().all()
            
            if not credentials:
                logger.warning("No credentials found for source", source_id=source_id)
                return None
            
            # Decrypt each credential
            decrypted_creds = {}
            
            for cred in credentials:
                try:
                    decrypted_value = decrypt_string(cred.encrypted_value)
                    decrypted_creds[cred.field_name] = decrypted_value
                except Exception as e:
                    logger.error(
                        "Failed to decrypt credential",
                        source_id=source_id,
                        field_name=cred.field_name,
                        error=str(e)
                    )
                    return None
            
            logger.debug(
                "Retrieved credentials for source",
                source_id=source_id,
                field_count=len(decrypted_creds)
            )
            
            return decrypted_creds
            
        except Exception as e:
            logger.error(
                "Failed to get source credentials",
                source_id=source_id,
                error=str(e)
            )
            return None
    
    @staticmethod
    async def get_user_sources_with_credentials(
        db: AsyncSession,
        user_id: uuid.UUID
    ) -> List[Dict[str, Any]]:
        """
        Get all sources for a user with their MCP configurations
        
        Args:
            db: Database session
            user_id: User ID to get sources for
            
        Returns:
            List of source configurations with credentials
        """
        try:
            # Get all active sources for the user
            result = await db.execute(
                select(Source)
                .where(and_(
                    Source.owner_user_id == user_id,
                    Source.is_active == True
                ))
                .options(selectinload(Source.credentials))
            )
            sources = result.scalars().all()
            
            configurations = []
            
            for source in sources:
                # Get decrypted credentials
                credentials = await MCPCredentialManager.get_source_credentials(db, source.source_id)
                
                if credentials:
                    config = {
                        "source_id": source.source_id,
                        "name": source.name,
                        "server_type": source.server_type,
                        "server_url": source.server_url,
                        "credentials": credentials
                    }
                    configurations.append(config)
                else:
                    logger.warning(
                        "Source has no valid credentials, skipping",
                        source_id=source.source_id,
                        source_name=source.name
                    )
            
            logger.info(
                "Retrieved user sources with credentials",
                user_id=user_id,
                source_count=len(configurations)
            )
            
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
        Get sources by IDs with their MCP configurations (for bot access)
        
        Args:
            db: Database session
            source_ids: List of source IDs to get configurations for
            
        Returns:
            List of source configurations with credentials
        """
        try:
            if not source_ids:
                return []
            
            # Get all active sources by IDs
            result = await db.execute(
                select(Source)
                .where(and_(
                    Source.source_id.in_(source_ids),
                    Source.is_active == True
                ))
                .options(selectinload(Source.credentials))
            )
            sources = result.scalars().all()
            
            configurations = []
            
            for source in sources:
                # Get decrypted credentials
                credentials = await MCPCredentialManager.get_source_credentials(db, source.source_id)
                
                if credentials:
                    config = {
                        "source_id": source.source_id,
                        "name": source.name,
                        "server_type": source.server_type,
                        "server_url": source.server_url,
                        "credentials": credentials
                    }
                    configurations.append(config)
                else:
                    logger.warning(
                        "Source has no valid credentials, skipping",
                        source_id=source.source_id,
                        source_name=source.name
                    )
            
            logger.info(
                "Retrieved bot sources with credentials",
                source_ids=source_ids,
                found_count=len(configurations)
            )
            
            return configurations
            
        except Exception as e:
            logger.error(
                "Failed to get bot sources with credentials",
                source_ids=source_ids,
                error=str(e)
            )
            return []
    
    @staticmethod
    async def delete_source_credentials(
        db: AsyncSession,
        source_id: uuid.UUID
    ) -> bool:
        """
        Delete all credentials for a source
        
        Args:
            db: Database session
            source_id: Source ID to delete credentials for
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Delete all credentials for this source
            result = await db.execute(
                select(MCPCredential).where(MCPCredential.source_id == source_id)
            )
            credentials = result.scalars().all()
            
            for cred in credentials:
                await db.delete(cred)
            
            await db.commit()
            
            logger.info(
                "Deleted credentials for source",
                source_id=source_id,
                credential_count=len(credentials)
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "Failed to delete source credentials",
                source_id=source_id,
                error=str(e)
            )
            await db.rollback()
            return False

# Convenience functions for easier usage
async def store_source_credentials(
    db: AsyncSession,
    source_id: uuid.UUID,
    credentials: Dict[str, str]
) -> bool:
    """Convenience function for storing source credentials"""
    return await MCPCredentialManager.store_source_credentials(db, source_id, credentials)


async def get_source_credentials(
    db: AsyncSession,
    source_id: uuid.UUID
) -> Optional[Dict[str, str]]:
    """Convenience function for getting source credentials"""
    return await MCPCredentialManager.get_source_credentials(db, source_id)


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
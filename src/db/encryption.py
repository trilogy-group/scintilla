"""
Encryption utilities for API keys

Uses AES envelope encryption pattern:
1. Generate data encryption key (DEK) 
2. Encrypt API key with DEK
3. Encrypt DEK with Key Encryption Key (KEK)
4. Store encrypted API key + encrypted DEK

For development: uses mock KMS
For production: use AWS KMS
"""

import base64
import os
from typing import Tuple
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import structlog

from src.config import settings

logger = structlog.get_logger()


class MockKMS:
    """Mock KMS for development - DO NOT USE IN PRODUCTION"""
    
    def __init__(self):
        # Generate a deterministic KEK for development
        # In production, this would be managed by AWS KMS
        password = settings.encryption_password.encode()
        salt = b"scintilla_dev_salt_12345678"  # Fixed salt for development
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password))
        self._kek = Fernet(key)
        
        logger.warning("Using mock KMS - NOT suitable for production")
    
    def encrypt(self, plaintext: bytes) -> bytes:
        """Encrypt data with KEK"""
        return self._kek.encrypt(plaintext)
    
    def decrypt(self, ciphertext: bytes) -> bytes:
        """Decrypt data with KEK"""
        return self._kek.decrypt(ciphertext)


# Global KMS instance
_kms = MockKMS()


def generate_dek() -> bytes:
    """Generate a new data encryption key"""
    return Fernet.generate_key()


def encrypt_api_key(api_key: str) -> str:
    """
    Encrypt an API key using simple Fernet encryption
    
    Args:
        api_key: Plain text API key
        
    Returns:
        Base64 encoded encrypted API key
    """
    try:
        encrypted_bytes = _kms.encrypt(api_key.encode('utf-8'))
        encrypted_str = base64.urlsafe_b64encode(encrypted_bytes).decode('utf-8')
        
        logger.debug(
            "API key encrypted",
            api_key_length=len(api_key),
            encrypted_size=len(encrypted_str)
        )
        
        return encrypted_str
        
    except Exception as e:
        logger.error("API key encryption failed", error=str(e))
        raise


def decrypt_api_key(encrypted_api_key: str) -> str:
    """
    Decrypt an API key using simple Fernet encryption
    
    Args:
        encrypted_api_key: Base64 encoded encrypted API key
        
    Returns:
        Plain text API key
    """
    try:
        encrypted_bytes = base64.urlsafe_b64decode(encrypted_api_key.encode('utf-8'))
        decrypted_bytes = _kms.decrypt(encrypted_bytes)
        api_key = decrypted_bytes.decode('utf-8')
        
        logger.debug(
            "API key decrypted",
            api_key_length=len(api_key)
        )
        
        return api_key
        
    except Exception as e:
        logger.error("API key decryption failed", error=str(e))
        raise


def encrypt_string(plaintext: str) -> str:
    """
    Generic string encryption using simple Fernet encryption
    
    Args:
        plaintext: String to encrypt
        
    Returns:
        Base64 encoded encrypted string
    """
    return encrypt_api_key(plaintext)


def decrypt_string(encrypted_data: str) -> str:
    """
    Generic string decryption using simple Fernet encryption
    
    Args:
        encrypted_data: Base64 encoded encrypted string
        
    Returns:
        Plain text string
    """
    return decrypt_api_key(encrypted_data)


# Convenience functions for database usage
def encrypt_field(value: str) -> str:
    """Encrypt a field value for database storage"""
    return encrypt_string(value)


def decrypt_field(encrypted_value: str) -> str:
    """Decrypt a field value from database"""
    return decrypt_string(encrypted_value) 
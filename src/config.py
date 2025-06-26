from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings
import os


class Settings(BaseSettings):
    # Database
    database_url: str = Field(..., env="DATABASE_URL")
    
    # LLM API Keys
    openai_api_key: str = Field(default="", env="OPENAI_API_KEY")
    anthropic_api_key: str = Field(default="", env="ANTHROPIC_API_KEY")
    
    # Default LLM settings
    default_llm_provider: str = Field(default="anthropic", env="DEFAULT_LLM_PROVIDER")
    default_openai_model: str = Field(default="gpt-4o", env="DEFAULT_OPENAI_MODEL")
    default_anthropic_model: str = Field(default="claude-sonnet-4-20250514	", env="DEFAULT_ANTHROPIC_MODEL")
    
    # AWS
    aws_region: str = Field(default="us-east-1", env="AWS_REGION")
    aws_kms_key_id: str = Field(default="", env="AWS_KMS_KEY_ID")
    
    # Encryption (for development - use AWS KMS in production)
    encryption_password: str = Field(default="scintilla_dev_encryption_key_2024", env="ENCRYPTION_PASSWORD")
    
    # Authentication
    allowed_domains: str = Field(default="ignitetech.com,ignitetech.ai", env="ALLOWED_DOMAINS")
    jwt_secret_key: str = Field(default="development_jwt_secret", env="JWT_SECRET_KEY")
    google_oauth_client_id: str = Field(default="", env="GOOGLE_OAUTH_CLIENT_ID")
    google_oauth_client_secret: str = Field(default="", env="GOOGLE_OAUTH_CLIENT_SECRET")
    
    # Application
    debug: bool = Field(default=False, env="DEBUG")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    host: str = Field(default="0.0.0.0", env="HOST")
    api_port: int = Field(default=8000, env="API_PORT")
    
    # Test Mode - bypass MCP for faster development
    test_mode: bool = Field(default=False, env="TEST_MODE")
    
    class Config:
        env_file = ".env"
        case_sensitive = False
    
    @property
    def allowed_domains_list(self) -> List[str]:
        return [domain.strip() for domain in self.allowed_domains.split(",")]


# Global settings instance
settings = Settings()

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://scintilla:scintilla@localhost/scintilla")

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# AWS KMS
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
KMS_KEY_ID = os.getenv("KMS_KEY_ID")

# Server
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# Test Mode - bypass MCP for faster development
TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"

 
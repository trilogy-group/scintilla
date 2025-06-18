#!/usr/bin/env python3
"""
Database initialization script for Scintilla

This script:
1. Initializes Alembic (if not already done)
2. Creates the initial migration
3. Runs the migration to create tables
"""

import os
import sys
import subprocess
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config import settings
import structlog

logger = structlog.get_logger()


def run_command(command, description):
    """Run a shell command and handle errors"""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(
            command, 
            shell=True, 
            check=True, 
            capture_output=True, 
            text=True,
            cwd=project_root
        )
        print(f"✅ {description} completed")
        if result.stdout:
            print(f"   Output: {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed")
        print(f"   Error: {e.stderr.strip()}")
        return False


def check_database_connection():
    """Test database connection"""
    print("🔍 Testing database connection...")
    try:
        from src.db.base import engine
        from sqlalchemy import text
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        print("✅ Database connection successful")
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        print("\n💡 Make sure PostgreSQL is running and DATABASE_URL is correct")
        print(f"   Current DATABASE_URL: {settings.database_url}")
        return False


def init_alembic():
    """Initialize Alembic if not already done"""
    if (project_root / "alembic" / "versions").exists():
        print("✅ Alembic already initialized")
        return True
    
    return run_command(
        "alembic init alembic",
        "Initializing Alembic"
    )


def create_initial_migration():
    """Create the initial migration"""
    # Check if migrations already exist
    versions_dir = project_root / "alembic" / "versions"
    if versions_dir.exists() and list(versions_dir.glob("*.py")):
        print("✅ Migrations already exist")
        return True
    
    return run_command(
        'alembic revision --autogenerate -m "Initial migration: users, bots, endpoints, conversations, messages"',
        "Creating initial migration"
    )


def run_migrations():
    """Run pending migrations"""
    return run_command(
        "alembic upgrade head",
        "Running migrations"
    )


def main():
    """Main initialization process"""
    print("🚀 Initializing Scintilla database...\n")
    
    # Check environment variables
    required_vars = [
        "DATABASE_URL", 
        "OPENAI_API_KEY", 
        "ANTHROPIC_API_KEY", 
        "AWS_KMS_KEY_ID", 
        "JWT_SECRET_KEY"
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\n💡 Create a .env file or set these environment variables")
        return False
    
    print("✅ Environment variables configured")
    
    # Test database connection
    if not check_database_connection():
        return False
    
    # Initialize Alembic
    if not init_alembic():
        return False
    
    # Create initial migration
    if not create_initial_migration():
        return False
    
    # Run migrations
    if not run_migrations():
        return False
    
    print("\n🎉 Database initialization completed!")
    print("\n📋 Next steps:")
    print("   1. Start the API: python -m src.main")
    print("   2. Visit: http://localhost:8000/docs")
    print("   3. Create your first bot with MCP endpoints")
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 
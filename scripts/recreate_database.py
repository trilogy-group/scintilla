#!/usr/bin/env python3
"""
Recreate Database Schema - Production Safe

This script:
1. Drops ALL existing tables 
2. Recreates them from SQLAlchemy models
3. Includes safety prompts for production

⚠️  WARNING: This will DELETE ALL DATA in the database!
"""

import sys
import os
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine
from src.config import settings
from src.db.models import Base
import structlog

# Configure logging
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

def confirm_destructive_action():
    """Confirm user wants to proceed with destructive database operation"""
    print("\n🚨 DESTRUCTIVE DATABASE OPERATION 🚨")
    print("="*50)
    print("This will:")
    print("  • DROP ALL TABLES")
    print("  • DELETE ALL DATA")
    print("  • RECREATE SCHEMA FROM MODELS")
    print("="*50)
    print(f"Database: {settings.database_url}")
    print("="*50)
    
    if "localhost" not in settings.database_url and "127.0.0.1" not in settings.database_url:
        print("🔥 THIS APPEARS TO BE A REMOTE/PRODUCTION DATABASE!")
        print("🔥 DOUBLE CHECK YOU WANT TO PROCEED!")
        print("="*50)
    
    response = input("\nType 'DESTROY_AND_RECREATE' to confirm: ")
    return response == "DESTROY_AND_RECREATE"

async def drop_and_recreate_tables():
    """Drop all tables and recreate from models"""
    
    # Create async engine
    async_database_url = settings.database_url.replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(async_database_url)
    
    try:
        async with engine.begin() as conn:
            logger.info("🗑️  Dropping all tables...")
            
            # Drop all tables using SQLAlchemy metadata
            await conn.run_sync(Base.metadata.drop_all)
            logger.info("✅ All tables dropped")
            
            logger.info("🏗️  Creating all tables from models...")
            
            # Create all tables from current models
            await conn.run_sync(Base.metadata.create_all)
            logger.info("✅ All tables created")
            
            # Verify tables were created
            result = await conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                ORDER BY table_name
            """))
            
            tables = [row[0] for row in result.fetchall()]
            logger.info("📋 Tables created", tables=tables, count=len(tables))
            
            print("\n✅ Database schema recreated successfully!")
            print(f"📊 Created {len(tables)} tables:")
            for table in tables:
                print(f"   • {table}")
                
    except Exception as e:
        logger.error("❌ Database operation failed", error=str(e))
        raise
    finally:
        await engine.dispose()

async def main():
    """Main execution function"""
    print("🔧 Scintilla Database Recreation Tool")
    
    # Check database connection
    try:
        # Test connection with sync engine first
        sync_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
        sync_engine = create_engine(sync_url)
        
        with sync_engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            logger.info("📡 Database connection successful", version=version[:50])
        
        sync_engine.dispose()
        
    except Exception as e:
        logger.error("❌ Database connection failed", error=str(e))
        print(f"\n❌ Cannot connect to database: {e}")
        print("💡 Check your DATABASE_URL and ensure the database is running")
        sys.exit(1)
    
    # Confirm destructive action
    if not confirm_destructive_action():
        print("\n🚫 Operation cancelled by user")
        sys.exit(0)
    
    print("\n🚀 Starting database recreation...")
    
    try:
        await drop_and_recreate_tables()
        print("\n🎉 Success! Database schema has been recreated.")
        print("\n📋 Next steps:")
        print("   1. Verify the application starts: python src/main.py")
        print("   2. Check API docs: http://localhost:8000/docs")
        print("   3. Create your first user via the web interface")
        
    except Exception as e:
        print(f"\n❌ Failed to recreate database: {e}")
        logger.error("Database recreation failed", error=str(e))
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 
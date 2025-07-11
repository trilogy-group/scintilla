from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import Session
from contextlib import contextmanager, asynccontextmanager
import structlog
import ssl

from src.config import settings

logger = structlog.get_logger()

# Create SSL context for RDS (disables certificate verification)
def create_ssl_context():
    """Create SSL context for RDS connection with disabled certificate verification."""
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    return ssl_context

# Create SQLAlchemy engine
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,  # Verify connections before use
    pool_recycle=300,    # Recycle connections every 5 minutes
    echo=settings.debug  # Log SQL queries in debug mode
)

# Create sessionmaker
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create async engine for FastAPI endpoints with SSL configuration
async_database_url = settings.database_url.replace("postgresql://", "postgresql+asyncpg://")

# Only use SSL for remote databases (not localhost)
connect_args = {}
if "localhost" not in async_database_url and "127.0.0.1" not in async_database_url:
    connect_args['ssl'] = create_ssl_context()

async_engine = create_async_engine(
    async_database_url,
    pool_pre_ping=True,
    pool_recycle=300,
    echo=settings.debug,
    connect_args=connect_args
)

# Create async sessionmaker
AsyncSessionLocal = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False
)

# Create base class for models
Base = declarative_base()


def get_db() -> Session:
    """
    FastAPI dependency to get database session (sync).
    Use with: Depends(get_db)
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error("Database session error", error=str(e))
        db.rollback()
        raise
    finally:
        db.close()


async def get_db_session() -> AsyncSession:
    """
    FastAPI dependency to get async database session.
    Use with: Depends(get_db_session)
    """
    async with AsyncSessionLocal() as db:
        try:
            yield db
        except Exception as e:
            logger.error("Async database session error", error=str(e))
            await db.rollback()
            raise
        finally:
            await db.close()


@contextmanager
def get_db_context():
    """
    Context manager for database sessions.
    Use for non-FastAPI contexts.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        logger.error("Database transaction error", error=str(e))
        db.rollback()
        raise
    finally:
        db.close()


def create_tables():
    """Create all tables. Used in development/testing."""
    Base.metadata.create_all(bind=engine)


def drop_tables():
    """Drop all tables. Used in development/testing."""
    Base.metadata.drop_all(bind=engine) 
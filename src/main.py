import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog
import uvicorn
from contextlib import asynccontextmanager

from src.config import settings
from src.api.query import router as query_router
from src.api.bots import router as bots_router
from src.api.sources import router as sources_router
from src.api.conversations import router as conversations_router
from src.api.mcp_management import router as mcp_router

# Import connection pool for cleanup
from src.agents.langchain_mcp import _mcp_pool
# Import global MCP management
from src.global_mcp import initialize_global_mcp_agent, get_global_mcp_agent, clear_global_mcp_agent

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer() if settings.debug else structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown with MCP pre-loading"""
    
    # Startup
    logger.info("Starting Scintilla application with MCP pre-loading")
    
    # Pre-load MCP tools for the default user at startup
    try:
        from src.db.base import AsyncSessionLocal
        import uuid
        
        # Use a default user ID for server-level tool caching
        # In production, you might want to load tools for all active users
        default_user_id = uuid.UUID('58d43e65-1176-49a4-ab61-0f765d8adb01')
        
        logger.info("Pre-loading MCP tools at server startup...")
        
        async with AsyncSessionLocal() as db:
            await initialize_global_mcp_agent(db, default_user_id)
                
    except Exception as e:
        logger.error("Failed to pre-load MCP tools at startup", error=str(e))
        # Continue startup even if MCP pre-loading fails
    
    yield
    
    # Shutdown
    logger.info("Shutting down Scintilla application")
    
    # Clean up global MCP agent
    try:
        clear_global_mcp_agent()
    except Exception as e:
        logger.error("Error cleaning up global MCP agent", error=str(e))
    
    # Clean up connection pools
    try:
        await _mcp_pool.close_all()
        logger.info("MCP connection pool closed")
    except Exception as e:
        logger.error("Error closing MCP connection pool", error=str(e))


# Create FastAPI app with performance optimizations
app = FastAPI(
    title="Scintilla",
    description="IgniteTech's federated search & chat tool",
    version="0.1.0",
    debug=settings.debug,
    lifespan=lifespan,
    # Performance optimizations
    docs_url="/docs" if settings.debug else None,  # Disable docs in production
    redoc_url="/redoc" if settings.debug else None,  # Disable redoc in production
    openapi_url="/openapi.json" if settings.debug else None,  # Disable OpenAPI in production
)

# Add CORS middleware with optimizations
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # React dev server (CRA)
        "http://localhost:5173",  # Vite dev server
        "http://127.0.0.1:5173",  # Vite dev server (alternative)
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Performance optimization: cache preflight responses for 1 hour
    max_age=3600,
)

# Include routers
app.include_router(query_router, prefix="/api", tags=["query"])
app.include_router(bots_router, prefix="/api", tags=["bots"])
app.include_router(sources_router, prefix="/api", tags=["sources"])
app.include_router(conversations_router, prefix="/api", tags=["conversations"])
app.include_router(mcp_router, prefix="/api/mcp", tags=["mcp"])


@app.get("/health")
async def health_check():
    """Health check endpoint with MCP status"""
    mcp_agent = get_global_mcp_agent()
    
    mcp_status = {
        "loaded": mcp_agent is not None,
        "tool_count": len(mcp_agent.tools) if mcp_agent else 0,
        "servers": mcp_agent.get_loaded_servers() if mcp_agent else []
    }
    
    return {
        "status": "healthy",
        "service": "scintilla", 
        "version": "0.1.0",
        "mcp": mcp_status
    }


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Scintilla API",
        "version": "0.1.0",
        "docs": "/docs"
    }

# The get_global_mcp_agent function is now imported from src.global_mcp

if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=settings.api_port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
        # Performance optimizations for uvicorn
        loop="asyncio",  # Use asyncio event loop
        access_log=settings.debug,  # Disable access log in production
        server_header=False,  # Don't send server header
        date_header=False,  # Don't send date header for small perf gain
    ) 
"""
Scintilla FastAPI Application

Main entry point for the Scintilla federated search and chat tool.
"""

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import structlog

from src.config import settings, TEST_MODE
from src.api import query, conversations, bots, sources, mcp_management, auth, local_agents, agent_tokens
# Removed global_mcp import - using FastMCPAgent approach

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()
logger.info("Main module loaded - about to define lifespan")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager with non-blocking startup"""
    try:
        # Startup
        logger.info("Starting Scintilla application", test_mode=TEST_MODE)
        
        logger.info("Scintilla application started - tools load from sources on-demand")
        
        yield
        
        # Shutdown
        logger.info("Shutting down Scintilla application")
    except Exception as e:
        logger.error("Error during application lifespan", error=str(e), error_type=type(e).__name__)
        import traceback
        logger.error("Lifespan error traceback", traceback=traceback.format_exc())
        raise


# Create FastAPI app
app = FastAPI(
    title="Scintilla",
    description="IgniteTech's federated search and chat tool",
    version="0.1.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
logger.info("About to include auth router")
app.include_router(auth.router, prefix="/api", tags=["authentication"])
logger.info("Auth router included successfully")
app.include_router(query.router, prefix="/api", tags=["query"])
app.include_router(conversations.router, prefix="/api", tags=["conversations"])
app.include_router(bots.router, prefix="/api", tags=["bots"])
app.include_router(sources.router, prefix="/api/sources", tags=["sources"])
app.include_router(mcp_management.router, prefix="/api", tags=["mcp"])
app.include_router(local_agents.router, prefix="/api", tags=["local-agents"])
app.include_router(agent_tokens.router, prefix="/api", tags=["agent-tokens"])


@app.get("/health")
async def health_check():
    """Health check endpoint with FastMCP status"""
    return {
        "status": "healthy",
        "service": "scintilla",
        "version": "0.1.0", 
        "startup": "non-blocking",
        "architecture": "fast_database_cached",
        "tools": "loaded_from_sources_on_demand",
        "test_mode": TEST_MODE
    }


@app.get("/")
async def root():
    """Root endpoint - redirect to React app"""
    return RedirectResponse(url="/static/index.html")


# Serve static files (for development)
try:
    app.mount("/static", StaticFiles(directory="web/dist"), name="static")
except RuntimeError:
    # Directory doesn't exist, skip static files
    logger.warning("Static files directory not found, skipping static file serving")


if __name__ == "__main__":
    import uvicorn
    
    logger.info("Starting Scintilla server", 
                host=settings.host, 
                port=settings.api_port,
                test_mode=TEST_MODE)
    
    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.api_port,
        reload=True,
        log_level=settings.log_level.lower()
    ) 
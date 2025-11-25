"""
FastAPI application entry point for QueryForge
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.core.config import settings
from app.core.database import init_database_async, verify_schema
from app.api.routes import pipeline

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager
    Handles startup and shutdown events
    """
    # Startup
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    
    try:
        # Initialize database
        await init_database_async()
        logger.info("Database initialized successfully")
        
        # Verify schema
        verify_schema()
        logger.info("Database schema verified")
        
        # Create necessary directories
        import os
        os.makedirs(settings.DATA_DIRECTORY, exist_ok=True)
        os.makedirs(settings.SANDBOX_DIRECTORY, exist_ok=True)
        logger.info("Required directories created/verified")
        
        logger.info(f"{settings.APP_NAME} startup complete")
        
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info(f"Shutting down {settings.APP_NAME}")
    
    # Cleanup sandbox directory
    import shutil
    try:
        if os.path.exists(settings.SANDBOX_DIRECTORY):
            # Clear sandbox but keep directory
            for item in os.listdir(settings.SANDBOX_DIRECTORY):
                item_path = os.path.join(settings.SANDBOX_DIRECTORY, item)
                if os.path.isfile(item_path):
                    os.unlink(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
            logger.info("Sandbox directory cleaned")
    except Exception as e:
        logger.warning(f"Error cleaning sandbox: {e}")
    
    logger.info(f"{settings.APP_NAME} shutdown complete")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Automated Data Pipeline Generation System",
    lifespan=lifespan
)

# Configure CORS middleware for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint
    
    Returns application status and configuration summary
    """
    return {
        "status": "healthy",
        "application": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "database": "connected",
        "data_directory": settings.DATA_DIRECTORY,
        "sandbox_directory": settings.SANDBOX_DIRECTORY
    }


@app.get("/", tags=["Root"])
async def root():
    """
    Root endpoint with API information
    """
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health"
    }


# Include API routers
app.include_router(pipeline.router, prefix="/pipeline", tags=["Pipeline"])

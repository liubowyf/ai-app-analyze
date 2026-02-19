"""FastAPI application entry point for APK Analysis Platform."""
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.database import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager for startup and shutdown events.

    Startup:
        - Create database tables

    Shutdown:
        - Cleanup resources (placeholder for future use)
    """
    # Startup: Create database tables
    Base.metadata.create_all(bind=engine)

    yield

    # Shutdown: Cleanup if needed
    # Placeholder for future cleanup logic


# Create FastAPI application
app = FastAPI(
    title="APK Analysis Platform API",
    description="API for APK intelligent dynamic analysis and network monitoring",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)


# Root endpoint
@app.get("/")
async def root():
    """
    Root endpoint returning API information.

    Returns:
        dict: API message, version, and current timestamp
    """
    return {
        "message": "Welcome to APK Analysis Platform API",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
    }


# Health check endpoint
@app.get("/health")
async def health():
    """
    Health check endpoint for monitoring.

    Returns:
        dict: Health status and current timestamp
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
    }


# Router imports (placeholders for future implementation)
# from api.routers import tasks, apk, whitelist
# app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
# app.include_router(apk.router, prefix="/api/apk", tags=["apk"])
# app.include_router(whitelist.router, prefix="/api/whitelist", tags=["whitelist"])

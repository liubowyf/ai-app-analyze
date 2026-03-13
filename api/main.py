"""FastAPI application entry point for APK Analysis Platform."""
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from core.config import settings
from core.database import ensure_schema_ready
import models.analysis_tables  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager for startup and shutdown events.

    Startup:
        - Create database tables

    Shutdown:
        - Cleanup resources (placeholder for future use)
    """
    # Startup: Create database tables under advisory lock
    ensure_schema_ready()

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


# Router imports
from api.routers import apk, frontend, tasks, whitelist, reports

# Include routers
app.include_router(apk.router, prefix="/api/v1/apk", tags=["apk"])
app.include_router(tasks.router, prefix="/api/v1", tags=["tasks"])
app.include_router(frontend.router, prefix="/api/v1/frontend", tags=["frontend"])
app.include_router(whitelist.router, prefix="/api/v1/whitelist", tags=["whitelist"])
app.include_router(reports.router, prefix="/api/v1", tags=["reports"])

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

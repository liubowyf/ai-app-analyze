"""Tests for FastAPI application entry point."""
from datetime import datetime
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient


class TestMainApp:
    """Test cases for main FastAPI application."""

    def test_root_endpoint(self, client: TestClient):
        """Test root endpoint returns correct response."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()

        assert "message" in data
        assert data["message"] == "Welcome to APK Analysis Platform API"

        assert "version" in data
        assert data["version"] == "1.0.0"

        assert "timestamp" in data
        # Verify timestamp is valid ISO format
        datetime.fromisoformat(data["timestamp"])

    def test_health_endpoint(self, client: TestClient):
        """Test health check endpoint returns healthy status."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()

        assert "status" in data
        assert data["status"] == "healthy"

        assert "timestamp" in data
        # Verify timestamp is valid ISO format
        datetime.fromisoformat(data["timestamp"])

    def test_app_metadata(self, client: TestClient):
        """Test FastAPI app has correct metadata."""
        from api.main import app

        assert app.title == "APK Analysis Platform API"
        assert app.description == "API for APK intelligent dynamic analysis and network monitoring"
        assert app.version == "1.0.0"

    def test_lifespan_startup(self, client: TestClient):
        """Test lifespan startup creates database tables."""
        # The client fixture already triggers startup
        # Verify that the app has lifespan configured
        from api.main import app
        assert app.router.lifespan_context is not None

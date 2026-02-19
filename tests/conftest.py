"""Pytest configuration and fixtures."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


@pytest.fixture
def client():
    """Create a test client with mocked database."""
    # Mock the database components before importing the app
    with patch("api.main.Base") as mock_base, \
         patch("api.main.engine") as mock_engine:
        # Setup mock metadata
        mock_base.metadata = MagicMock()

        # Import app after mocking
        from api.main import app

        # Create test client
        with TestClient(app) as test_client:
            yield test_client

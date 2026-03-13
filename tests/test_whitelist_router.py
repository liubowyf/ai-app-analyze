"""Tests for whitelist router."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock
from datetime import datetime


def create_mock_rule(rule_id, domain, category="custom", ip_range=None, description=None, is_active=True):
    """Helper to create a mock whitelist rule."""
    mock_rule = MagicMock()
    mock_rule.id = rule_id
    mock_rule.domain = domain
    mock_rule.ip_range = ip_range
    mock_rule.category.value = category
    mock_rule.description = description
    mock_rule.is_active = is_active
    mock_rule.created_at = datetime.utcnow()
    mock_rule.updated_at = datetime.utcnow()
    mock_rule.to_dict.return_value = {
        "id": rule_id,
        "domain": domain,
        "ip_range": ip_range,
        "category": category,
        "description": description,
        "is_active": is_active,
        "created_at": mock_rule.created_at.isoformat(),
        "updated_at": mock_rule.updated_at.isoformat()
    }
    return mock_rule


class TestWhitelistRouter:
    """Test cases for whitelist router endpoints."""

    def test_create_whitelist_rule_success(self, client: TestClient):
        """Test successful creation of whitelist rule."""
        rule_data = {
            "domain": "example.com",
            "ip_range": "192.168.1.0/24",
            "category": "custom",
            "description": "Test whitelist rule",
            "is_active": True
        }

        # Mock database session
        mock_db = MagicMock()

        # Create a side effect for refresh that populates the rule with values
        def mock_refresh(rule):
            rule.id = "test-uuid-123"
            rule.created_at = datetime.utcnow()
            rule.updated_at = datetime.utcnow()

        mock_db.refresh = mock_refresh

        # Override dependency
        from api.main import app
        from core.database import get_db

        app.dependency_overrides[get_db] = lambda: mock_db

        try:
            response = client.post("/api/v1/whitelist", json=rule_data)

            assert response.status_code == 201
            data = response.json()
            assert "id" in data
            assert data["id"] == "test-uuid-123"
            assert data["domain"] == rule_data["domain"]
            assert data["category"] == rule_data["category"]

            # Verify database operations were called
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
        finally:
            app.dependency_overrides.clear()

    def test_create_whitelist_rule_minimal(self, client: TestClient):
        """Test creation with minimal required fields."""
        rule_data = {
            "domain": "minimal.com",
            "category": "system"
        }

        mock_db = MagicMock()

        def mock_refresh(rule):
            rule.id = "minimal-uuid"
            rule.created_at = datetime.utcnow()
            rule.updated_at = datetime.utcnow()

        mock_db.refresh = mock_refresh

        from api.main import app
        from core.database import get_db

        app.dependency_overrides[get_db] = lambda: mock_db

        try:
            response = client.post("/api/v1/whitelist", json=rule_data)
            assert response.status_code == 201
        finally:
            app.dependency_overrides.clear()

    def test_create_whitelist_rule_invalid_category(self, client: TestClient):
        """Test creation with invalid category."""
        rule_data = {
            "domain": "test.com",
            "category": "invalid_category"
        }

        response = client.post("/api/v1/whitelist", json=rule_data)
        assert response.status_code == 422

    def test_list_whitelist_rules_success(self, client: TestClient):
        """Test listing whitelist rules with pagination."""
        mock_db = MagicMock()

        # Create mock rules
        mock_rules = [
            create_mock_rule("rule-0", "domain0.com", "custom"),
            create_mock_rule("rule-1", "domain1.com", "custom")
        ]

        # Mock query chain
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_rules
        mock_query.count.return_value = 2

        from api.main import app
        from core.database import get_db

        app.dependency_overrides[get_db] = lambda: mock_db

        try:
            response = client.get("/api/v1/whitelist?skip=0&limit=10")

            assert response.status_code == 200
            data = response.json()
            assert "items" in data
            assert "total" in data
            assert data["total"] == 2
            assert data["skip"] == 0
            assert data["limit"] == 10
        finally:
            app.dependency_overrides.clear()

    def test_list_whitelist_rules_with_filters(self, client: TestClient):
        """Test listing whitelist rules with category filter."""
        mock_db = MagicMock()

        # Mock query chain with filters
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        mock_query.count.return_value = 0

        from api.main import app
        from core.database import get_db

        app.dependency_overrides[get_db] = lambda: mock_db

        try:
            response = client.get("/api/v1/whitelist?category=system&is_active=true")

            assert response.status_code == 200
            # Verify filter was called
            assert mock_query.filter.call_count >= 2
        finally:
            app.dependency_overrides.clear()

    def test_get_whitelist_rule_by_id_success(self, client: TestClient):
        """Test getting a specific whitelist rule by ID."""
        rule_id = "test-rule-id"
        mock_db = MagicMock()

        mock_rule = create_mock_rule(rule_id, "test.com", "cdn", "10.0.0.0/8", "Test rule")

        mock_db.query.return_value.filter.return_value.first.return_value = mock_rule

        from api.main import app
        from core.database import get_db

        app.dependency_overrides[get_db] = lambda: mock_db

        try:
            response = client.get(f"/api/v1/whitelist/{rule_id}")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == rule_id
            assert data["domain"] == "test.com"
        finally:
            app.dependency_overrides.clear()

    def test_get_whitelist_rule_by_id_not_found(self, client: TestClient):
        """Test getting a non-existent whitelist rule."""
        rule_id = "non-existent-id"
        mock_db = MagicMock()

        mock_db.query.return_value.filter.return_value.first.return_value = None

        from api.main import app
        from core.database import get_db

        app.dependency_overrides[get_db] = lambda: mock_db

        try:
            response = client.get(f"/api/v1/whitelist/{rule_id}")

            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()

    def test_update_whitelist_rule_success(self, client: TestClient):
        """Test updating a whitelist rule."""
        rule_id = "update-test-id"
        update_data = {
            "description": "Updated description",
            "is_active": False
        }

        mock_db = MagicMock()
        mock_rule = create_mock_rule(rule_id, "update.com", "custom")

        mock_db.query.return_value.filter.return_value.first.return_value = mock_rule

        from api.main import app
        from core.database import get_db

        app.dependency_overrides[get_db] = lambda: mock_db

        try:
            response = client.put(f"/api/v1/whitelist/{rule_id}", json=update_data)

            assert response.status_code == 200
            mock_db.commit.assert_called_once()
            mock_db.refresh.assert_called_once()
        finally:
            app.dependency_overrides.clear()

    def test_update_whitelist_rule_not_found(self, client: TestClient):
        """Test updating a non-existent whitelist rule."""
        rule_id = "non-existent-id"
        update_data = {"description": "Updated"}

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        from api.main import app
        from core.database import get_db

        app.dependency_overrides[get_db] = lambda: mock_db

        try:
            response = client.put(f"/api/v1/whitelist/{rule_id}", json=update_data)

            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()

    def test_delete_whitelist_rule_success(self, client: TestClient):
        """Test deleting a whitelist rule."""
        rule_id = "delete-test-id"
        mock_db = MagicMock()

        mock_rule = create_mock_rule(rule_id, "delete.com", "custom")
        mock_db.query.return_value.filter.return_value.first.return_value = mock_rule

        from api.main import app
        from core.database import get_db

        app.dependency_overrides[get_db] = lambda: mock_db

        try:
            response = client.delete(f"/api/v1/whitelist/{rule_id}")

            assert response.status_code == 204
            mock_db.delete.assert_called_once_with(mock_rule)
            mock_db.commit.assert_called_once()
        finally:
            app.dependency_overrides.clear()

    def test_delete_whitelist_rule_not_found(self, client: TestClient):
        """Test deleting a non-existent whitelist rule."""
        rule_id = "non-existent-id"
        mock_db = MagicMock()

        mock_db.query.return_value.filter.return_value.first.return_value = None

        from api.main import app
        from core.database import get_db

        app.dependency_overrides[get_db] = lambda: mock_db

        try:
            response = client.delete(f"/api/v1/whitelist/{rule_id}")

            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()

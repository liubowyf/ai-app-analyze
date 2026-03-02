"""Tests for scheduling-focused task metrics endpoint."""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


class TestTaskSchedulingMetrics:
    def test_get_task_scheduling_metrics(self, client: TestClient):
        with patch("api.routers.tasks.SessionLocal") as mock_session_local, patch(
            "api.routers.tasks.get_backend_runtime_diagnostics",
            return_value={
                "backend": "dramatiq",
                "dramatiq_ready": True,
                "fallback_reason": None,
            },
        ):
            mock_db = MagicMock(spec=Session)
            mock_session_local.return_value = mock_db

            status_query = MagicMock()
            stuck_query = MagicMock()
            mock_db.query.side_effect = [status_query, stuck_query]
            status_query.group_by.return_value.all.return_value = [
                ("queued", 3),
                ("static_analyzing", 2),
                ("completed", 5),
            ]
            stuck_query.filter.return_value.scalar.return_value = 1

            response = client.get("/api/v1/tasks/metrics/scheduling")

            assert response.status_code == 200
            data = response.json()
            assert data["backend"] == "dramatiq"
            assert data["can_enqueue"] is True
            assert data["queued_count"] == 3
            assert data["running_count"] == 2
            assert data["stuck_count"] == 1
            assert isinstance(data["timestamp"], str)

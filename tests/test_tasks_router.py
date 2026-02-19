"""Tests for tasks router."""
from datetime import datetime
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models.task import Task, TaskStatus, TaskPriority


def create_mock_task(task_id="test-task-id", status=TaskStatus.PENDING, retry_count=0):
    """Helper function to create a mock task with all required fields."""
    return Task(
        id=task_id,
        apk_file_name="test.apk",
        apk_file_size=1024,
        apk_md5="abc123def456",
        apk_sha256="abc123def456",
        apk_storage_path="/storage/test.apk",
        status=status,
        priority=TaskPriority.NORMAL,
        retry_count=retry_count,
        created_at=datetime.utcnow(),
        started_at=datetime.utcnow() if status != TaskStatus.PENDING else None,
        completed_at=datetime.utcnow() if status == TaskStatus.COMPLETED else None,
        updated_at=datetime.utcnow(),
    )


class TestTasksRouter:
    """Test cases for tasks router endpoints."""

    def test_create_task_success(self, client: TestClient):
        """Test successful task creation."""
        mock_task = create_mock_task(status=TaskStatus.PENDING)

        with patch("api.routers.tasks.SessionLocal") as mock_session_local:
            mock_db = MagicMock(spec=Session)
            mock_session_local.return_value = mock_db
            mock_db.query.return_value.filter.return_value.first.return_value = mock_task
            mock_db.refresh.side_effect = lambda obj: None

            response = client.post(
                "/api/v1/tasks",
                json={"task_id": "test-task-id"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == "test-task-id"
            assert data["status"] == "queued"

    def test_create_task_not_found(self, client: TestClient):
        """Test task creation with non-existent task_id."""
        with patch("api.routers.tasks.SessionLocal") as mock_session_local:
            mock_db = MagicMock(spec=Session)
            mock_session_local.return_value = mock_db
            mock_db.query.return_value.filter.return_value.first.return_value = None

            response = client.post(
                "/api/v1/tasks",
                json={"task_id": "non-existent-id"}
            )

            assert response.status_code == 404

    def test_create_task_already_started(self, client: TestClient):
        """Test task creation when task is already in progress."""
        mock_task = create_mock_task(status=TaskStatus.QUEUED)

        with patch("api.routers.tasks.SessionLocal") as mock_session_local:
            mock_db = MagicMock(spec=Session)
            mock_session_local.return_value = mock_db
            mock_db.query.return_value.filter.return_value.first.return_value = mock_task

            response = client.post(
                "/api/v1/tasks",
                json={"task_id": "test-task-id"}
            )

            assert response.status_code == 400

    def test_get_task_success(self, client: TestClient):
        """Test successful task retrieval."""
        mock_task = create_mock_task(status=TaskStatus.COMPLETED)

        with patch("api.routers.tasks.SessionLocal") as mock_session_local:
            mock_db = MagicMock(spec=Session)
            mock_session_local.return_value = mock_db
            mock_db.query.return_value.filter.return_value.first.return_value = mock_task

            response = client.get("/api/v1/tasks/test-task-id")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == "test-task-id"
            assert data["status"] == "completed"

    def test_get_task_not_found(self, client: TestClient):
        """Test task retrieval with non-existent task_id."""
        with patch("api.routers.tasks.SessionLocal") as mock_session_local:
            mock_db = MagicMock(spec=Session)
            mock_session_local.return_value = mock_db
            mock_db.query.return_value.filter.return_value.first.return_value = None

            response = client.get("/api/v1/tasks/non-existent-id")

            assert response.status_code == 404

    def test_list_tasks_default_pagination(self, client: TestClient):
        """Test task listing with default pagination."""
        mock_tasks = [create_mock_task(task_id=f"task-{i}", status=TaskStatus.COMPLETED) for i in range(5)]

        with patch("api.routers.tasks.SessionLocal") as mock_session_local:
            mock_db = MagicMock(spec=Session)
            mock_session_local.return_value = mock_db
            mock_db.query.return_value.offset.return_value.limit.return_value.all.return_value = mock_tasks
            mock_db.query.return_value.count.return_value = 5

            response = client.get("/api/v1/tasks")

            assert response.status_code == 200
            data = response.json()
            assert len(data["tasks"]) == 5
            assert data["total"] == 5
            assert data["skip"] == 0
            assert data["limit"] == 10

    def test_list_tasks_custom_pagination(self, client: TestClient):
        """Test task listing with custom pagination."""
        mock_tasks = [create_mock_task(task_id=f"task-{i}", status=TaskStatus.COMPLETED) for i in range(3)]

        with patch("api.routers.tasks.SessionLocal") as mock_session_local:
            mock_db = MagicMock(spec=Session)
            mock_session_local.return_value = mock_db
            mock_db.query.return_value.offset.return_value.limit.return_value.all.return_value = mock_tasks
            mock_db.query.return_value.count.return_value = 10

            response = client.get("/api/v1/tasks?skip=2&limit=3")

            assert response.status_code == 200
            data = response.json()
            assert len(data["tasks"]) == 3
            assert data["total"] == 10
            assert data["skip"] == 2
            assert data["limit"] == 3

    def test_retry_task_success(self, client: TestClient):
        """Test successful task retry."""
        mock_task = create_mock_task(status=TaskStatus.FAILED, retry_count=1)

        with patch("api.routers.tasks.SessionLocal") as mock_session_local:
            mock_db = MagicMock(spec=Session)
            mock_session_local.return_value = mock_db
            mock_db.query.return_value.filter.return_value.first.return_value = mock_task
            mock_db.refresh.side_effect = lambda obj: None

            response = client.post("/api/v1/tasks/test-task-id/retry")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "queued"
            assert data["retry_count"] == 2

    def test_retry_task_not_failed(self, client: TestClient):
        """Test retry on non-failed task."""
        mock_task = create_mock_task(status=TaskStatus.COMPLETED)

        with patch("api.routers.tasks.SessionLocal") as mock_session_local:
            mock_db = MagicMock(spec=Session)
            mock_session_local.return_value = mock_db
            mock_db.query.return_value.filter.return_value.first.return_value = mock_task

            response = client.post("/api/v1/tasks/test-task-id/retry")

            assert response.status_code == 400

    def test_retry_task_not_found(self, client: TestClient):
        """Test retry on non-existent task."""
        with patch("api.routers.tasks.SessionLocal") as mock_session_local:
            mock_db = MagicMock(spec=Session)
            mock_session_local.return_value = mock_db
            mock_db.query.return_value.filter.return_value.first.return_value = None

            response = client.post("/api/v1/tasks/non-existent-id/retry")

            assert response.status_code == 404

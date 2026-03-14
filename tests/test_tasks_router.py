"""Tests for tasks router."""
from datetime import datetime
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models.task import Task, TaskStatus, TaskPriority


def create_mock_task(
    task_id="test-task-id",
    status=TaskStatus.QUEUED,
    retry_count=0,
    last_success_stage=None,
    started_at=None,
):
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
        started_at=started_at,
        completed_at=datetime.utcnow() if status == TaskStatus.COMPLETED else None,
        updated_at=datetime.utcnow(),
        last_success_stage=last_success_stage,
    )


class TestTasksRouter:
    """Test cases for tasks router endpoints."""

    def test_create_task_success(self, client: TestClient):
        """Test successful task creation."""
        mock_task = create_mock_task(status=TaskStatus.QUEUED, started_at=None)

        with patch("api.routers.tasks.SessionLocal") as mock_session_local, \
             patch("api.routers.tasks.enqueue_task", return_value=True) as mock_enqueue:
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
            mock_enqueue.assert_called_once_with("test-task-id", priority=TaskPriority.NORMAL)

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
        mock_task = create_mock_task(status=TaskStatus.STATIC_ANALYZING, started_at=datetime.utcnow())

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
        mock_task = create_mock_task(
            status=TaskStatus.DYNAMIC_FAILED,
            retry_count=1,
            last_success_stage="static",
        )

        with patch("api.routers.tasks.SessionLocal") as mock_session_local, \
             patch("api.routers.tasks.enqueue_task", return_value=True) as mock_enqueue:
            mock_db = MagicMock(spec=Session)
            mock_session_local.return_value = mock_db
            mock_db.query.return_value.filter.return_value.first.return_value = mock_task
            mock_db.refresh.side_effect = lambda obj: None

            response = client.post("/api/v1/tasks/test-task-id/retry")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "dynamic_analyzing"
            assert data["retry_count"] == 2
            mock_enqueue.assert_called_once_with("test-task-id", priority=TaskPriority.NORMAL)

    def test_retry_task_from_static_failed_restarts_from_queue(self, client: TestClient):
        """Static failure retry should restart from queue/full flow."""
        mock_task = create_mock_task(
            status=TaskStatus.STATIC_FAILED,
            retry_count=0,
        )

        with patch("api.routers.tasks.SessionLocal") as mock_session_local, \
             patch("api.routers.tasks.enqueue_task", return_value=True):
            mock_db = MagicMock(spec=Session)
            mock_session_local.return_value = mock_db
            mock_db.query.return_value.filter.return_value.first.return_value = mock_task
            mock_db.refresh.side_effect = lambda obj: None

            response = client.post("/api/v1/tasks/test-task-id/retry")

        assert response.status_code == 200
        assert response.json()["status"] == "queued"

    def test_retry_task_uses_existing_static_result_when_last_success_stage_missing(self, client: TestClient):
        """Dynamic retry should resume from dynamic when static output already exists."""
        mock_task = create_mock_task(
            status=TaskStatus.DYNAMIC_FAILED,
            retry_count=2,
            last_success_stage=None,
        )
        mock_task.static_analysis_result = {"basic_info": {"package_name": "com.demo.app"}}

        with patch("api.routers.tasks.SessionLocal") as mock_session_local, \
             patch("api.routers.tasks.enqueue_task", return_value=True):
            mock_db = MagicMock(spec=Session)
            mock_session_local.return_value = mock_db
            mock_db.query.return_value.filter.return_value.first.return_value = mock_task
            mock_db.refresh.side_effect = lambda obj: None

            response = client.post("/api/v1/tasks/test-task-id/retry")

        assert response.status_code == 200
        assert response.json()["status"] == "dynamic_analyzing"

    def test_retry_task_not_failed(self, client: TestClient):
        """Completed task retry should be allowed and resume from dynamic."""
        mock_task = create_mock_task(status=TaskStatus.COMPLETED)
        mock_task.static_analysis_result = {"basic_info": {"package_name": "com.demo.done"}}

        with patch("api.routers.tasks.SessionLocal") as mock_session_local, \
             patch("api.routers.tasks.enqueue_task", return_value=True) as mock_enqueue:
            mock_db = MagicMock(spec=Session)
            mock_session_local.return_value = mock_db
            mock_db.query.return_value.filter.return_value.first.return_value = mock_task
            mock_db.refresh.side_effect = lambda obj: None

            response = client.post("/api/v1/tasks/test-task-id/retry")

            assert response.status_code == 200
            assert response.json()["status"] == "dynamic_analyzing"
            mock_enqueue.assert_called_once_with("test-task-id", priority=TaskPriority.NORMAL)

    def test_retry_task_running_task_is_allowed_and_resumes_from_dynamic(self, client: TestClient):
        """Running task retry should be accepted and reset to dynamic stage."""
        mock_task = create_mock_task(
            status=TaskStatus.DYNAMIC_ANALYZING,
            retry_count=4,
            last_success_stage="static",
        )
        mock_task.static_analysis_result = {"basic_info": {"package_name": "com.demo.running"}}

        with patch("api.routers.tasks.SessionLocal") as mock_session_local, \
             patch("api.routers.tasks.enqueue_task", return_value=True) as mock_enqueue:
            mock_db = MagicMock(spec=Session)
            mock_session_local.return_value = mock_db
            mock_db.query.return_value.filter.return_value.first.return_value = mock_task
            mock_db.refresh.side_effect = lambda obj: None

            response = client.post("/api/v1/tasks/test-task-id/retry")

        assert response.status_code == 200
        assert response.json()["status"] == "dynamic_analyzing"
        assert response.json()["retry_count"] == 5
        mock_enqueue.assert_called_once_with("test-task-id", priority=TaskPriority.NORMAL)

    def test_retry_task_not_found(self, client: TestClient):
        """Test retry on non-existent task."""
        with patch("api.routers.tasks.SessionLocal") as mock_session_local:
            mock_db = MagicMock(spec=Session)
            mock_session_local.return_value = mock_db
            mock_db.query.return_value.filter.return_value.first.return_value = None

            response = client.post("/api/v1/tasks/non-existent-id/retry")

            assert response.status_code == 404

    def test_get_task_queue_metrics(self, client: TestClient):
        """Test queue metrics endpoint."""
        with patch("api.routers.tasks.SessionLocal") as mock_session_local:
            mock_db = MagicMock(spec=Session)
            mock_session_local.return_value = mock_db
            mock_db.query.return_value.group_by.return_value.all.return_value = [
                ("queued", 3),
                ("dynamic_analyzing", 2),
                ("completed", 5),
            ]

            response = client.get("/api/v1/tasks/metrics/queue")

            assert response.status_code == 200
            data = response.json()
            assert data["total_tasks"] == 10
            assert data["in_progress"] == 5
            assert data["by_status"]["queued"] == 3
            assert data["by_status"]["dynamic_analyzing"] == 2

    def test_get_task_backend_metrics(self, client: TestClient):
        """Test backend readiness metrics endpoint."""
        with patch(
            "api.routers.tasks.get_backend_runtime_diagnostics",
            return_value={
                "backend": "dramatiq",
                "dramatiq_ready": False,
                "fallback_reason": "dramatiq_not_ready",
            },
        ):
            response = client.get("/api/v1/tasks/metrics/backend")

        assert response.status_code == 200
        data = response.json()
        assert data["backend"] == "dramatiq"
        assert data["dramatiq_ready"] is False
        assert data["can_enqueue"] is False
        assert isinstance(data["timestamp"], str)

    def test_get_task_network_requests(self, client: TestClient):
        """Compatibility route should now expose passive observation fields."""
        mock_task = create_mock_task(status=TaskStatus.COMPLETED)
        mock_request = MagicMock()
        mock_request.id = "obs-1"
        mock_request.url = None
        mock_request.method = "UNKNOWN"
        mock_request.host = "api.demo.com"
        mock_request.path = None
        mock_request.ip = "1.1.1.1"
        mock_request.port = 443
        mock_request.scheme = "https"
        mock_request.response_code = None
        mock_request.content_type = None
        mock_request.request_time = datetime(2026, 3, 6, 9, 0, 0)
        mock_request.first_seen_at = datetime(2026, 3, 6, 9, 0, 0)
        mock_request.last_seen_at = datetime(2026, 3, 6, 9, 0, 5)
        mock_request.hit_count = 4
        mock_request.source_type = "dns"
        mock_request.transport = "udp"
        mock_request.protocol = "dns"
        mock_request.capture_mode = "redroid_zeek"
        mock_request.attribution_tier = "primary"

        with patch("api.routers.tasks.SessionLocal") as mock_session_local:
            mock_db = MagicMock(spec=Session)
            mock_session_local.return_value = mock_db

            task_query = MagicMock()
            network_query = MagicMock()
            network_sorted = MagicMock()
            network_paginated = MagicMock()

            mock_db.query.side_effect = [task_query, network_query]
            task_query.filter.return_value.first.return_value = mock_task

            network_query.filter.return_value = network_query
            network_query.count.return_value = 1
            network_query.order_by.return_value = network_sorted
            network_sorted.offset.return_value = network_paginated
            network_paginated.limit.return_value.all.return_value = [mock_request]

            response = client.get("/api/v1/tasks/test-task-id/network-requests")

            assert response.status_code == 200
            data = response.json()
            assert data["task_id"] == "test-task-id"
            assert data["total"] == 1
            assert len(data["items"]) == 1
            assert data["items"][0]["domain"] == "api.demo.com"
            assert data["items"][0]["host"] == "api.demo.com"
            assert data["items"][0]["hit_count"] == 4
            assert data["items"][0]["source_type"] == "dns"
            assert data["items"][0]["transport"] == "udp"
            assert data["items"][0]["protocol"] == "dns"
            assert data["items"][0]["capture_mode"] == "redroid_zeek"
            assert data["items"][0]["attribution_tier"] == "primary"
            assert data["items"][0]["first_seen_at"] == "2026-03-06T09:00:00"
            assert data["items"][0]["last_seen_at"] == "2026-03-06T09:00:05"

    def test_get_task_network_observations_alias(self, client: TestClient):
        """Canonical observation route should expose the same payload contract."""
        mock_task = create_mock_task(status=TaskStatus.COMPLETED)
        mock_request = MagicMock()
        mock_request.id = "obs-1"
        mock_request.url = None
        mock_request.method = "UNKNOWN"
        mock_request.host = "api.demo.com"
        mock_request.path = None
        mock_request.ip = "1.1.1.1"
        mock_request.port = 443
        mock_request.scheme = "https"
        mock_request.response_code = None
        mock_request.content_type = None
        mock_request.request_time = datetime(2026, 3, 6, 9, 0, 0)
        mock_request.first_seen_at = datetime(2026, 3, 6, 9, 0, 0)
        mock_request.last_seen_at = datetime(2026, 3, 6, 9, 0, 5)
        mock_request.hit_count = 4
        mock_request.source_type = "dns"
        mock_request.transport = "udp"
        mock_request.protocol = "dns"
        mock_request.capture_mode = "redroid_zeek"
        mock_request.attribution_tier = "primary"

        with patch("api.routers.tasks.SessionLocal") as mock_session_local:
            mock_db = MagicMock(spec=Session)
            mock_session_local.return_value = mock_db

            task_query = MagicMock()
            network_query = MagicMock()
            network_sorted = MagicMock()
            network_paginated = MagicMock()

            mock_db.query.side_effect = [task_query, network_query]
            task_query.filter.return_value.first.return_value = mock_task

            network_query.filter.return_value = network_query
            network_query.count.return_value = 1
            network_query.order_by.return_value = network_sorted
            network_sorted.offset.return_value = network_paginated
            network_paginated.limit.return_value.all.return_value = [mock_request]

            response = client.get("/api/v1/tasks/test-task-id/network-observations")

            assert response.status_code == 200
            data = response.json()
            assert data["task_id"] == "test-task-id"
            assert data["items"][0]["domain"] == "api.demo.com"
            assert data["items"][0]["hit_count"] == 4

    def test_get_task_network_requests_fallback_to_dynamic_result_preview(self, client: TestClient):
        """Historical tasks should still expose observation previews from legacy JSON."""
        mock_task = create_mock_task(status=TaskStatus.COMPLETED)
        mock_task.dynamic_analysis_result = {
            "capture_mode": "redroid_zeek",
            "primary_observations_preview": [
                {
                    "id": "obs-preview-1",
                    "domain": "api.demo.com",
                    "host": "api.demo.com",
                    "ip": "1.1.1.1",
                    "hit_count": 3,
                    "source_type": "dns",
                    "transport": "udp",
                    "protocol": "dns",
                    "first_seen_at": "2026-03-06T09:00:00",
                    "last_seen_at": "2026-03-06T09:00:05",
                    "capture_mode": "redroid_zeek",
                    "attribution_tier": "primary",
                }
            ],
        }

        with patch("api.routers.tasks.SessionLocal") as mock_session_local:
            mock_db = MagicMock(spec=Session)
            mock_session_local.return_value = mock_db

            task_query = MagicMock()
            network_query = MagicMock()
            network_sorted = MagicMock()
            network_paginated = MagicMock()

            mock_db.query.side_effect = [task_query, network_query]
            task_query.filter.return_value.first.return_value = mock_task
            network_query.filter.return_value = network_query
            network_query.count.return_value = 0
            network_query.order_by.return_value = network_sorted
            network_sorted.offset.return_value = network_paginated
            network_paginated.limit.return_value.all.return_value = []

            response = client.get("/api/v1/tasks/test-task-id/network-requests")

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1
            assert data["items"][0]["domain"] == "api.demo.com"
            assert data["items"][0]["hit_count"] == 3

    def test_get_task_domains_fallback_to_json(self, client: TestClient):
        """Historical tasks should still expose passive master-domain summaries from JSON."""
        mock_task = create_mock_task(status=TaskStatus.COMPLETED)
        mock_task.dynamic_analysis_result = {
            "master_domains": {
                "master_domains": [
                    {
                        "domain": "api.demo.com",
                        "ip": "1.1.1.1",
                        "score": 66,
                        "confidence": "high",
                        "hit_count": 7,
                        "unique_ip_count": 2,
                        "source_types": ["dns", "connect"],
                        "first_seen_at": "2026-03-06T09:00:00",
                        "last_seen_at": "2026-03-06T09:00:05",
                    }
                ]
            }
        }

        with patch("api.routers.tasks.SessionLocal") as mock_session_local:
            mock_db = MagicMock(spec=Session)
            mock_session_local.return_value = mock_db

            task_query = MagicMock()
            domain_query = MagicMock()

            mock_db.query.side_effect = [task_query, domain_query]
            task_query.filter.return_value.first.return_value = mock_task
            domain_query.filter.return_value.order_by.return_value.all.return_value = []

            response = client.get("/api/v1/tasks/test-task-id/domains")

            assert response.status_code == 200
            data = response.json()
            assert data["task_id"] == "test-task-id"
            assert data["count"] == 1
            assert data["domains"][0]["domain"] == "api.demo.com"
            assert data["domains"][0]["hit_count"] == 7
            assert data["domains"][0]["unique_ip_count"] == 2
            assert data["domains"][0]["source_types"] == ["dns", "connect"]

    def test_get_task_domains_returns_passive_domain_evidence(self, client: TestClient):
        """Domain route should return observation-driven evidence fields."""
        mock_task = create_mock_task(status=TaskStatus.COMPLETED)
        mock_domain = MagicMock()
        mock_domain.domain = "api.demo.com"
        mock_domain.ip = "1.1.1.1"
        mock_domain.confidence_score = 92
        mock_domain.confidence_level = "high"
        mock_domain.request_count = 7
        mock_domain.post_count = 0
        mock_domain.evidence = ["top passive domain"]
        mock_domain.first_seen_at = datetime(2026, 3, 6, 9, 0, 0)
        mock_domain.last_seen_at = datetime(2026, 3, 6, 9, 0, 5)
        mock_domain.unique_ip_count = 2
        mock_domain.source_types_json = ["dns", "connect"]

        with patch("api.routers.tasks.SessionLocal") as mock_session_local:
            mock_db = MagicMock(spec=Session)
            mock_session_local.return_value = mock_db

            task_query = MagicMock()
            domain_query = MagicMock()
            ordered_query = MagicMock()

            mock_db.query.side_effect = [task_query, domain_query]
            task_query.filter.return_value.first.return_value = mock_task
            domain_query.filter.return_value = domain_query
            domain_query.order_by.return_value = ordered_query
            ordered_query.all.return_value = [mock_domain]

            response = client.get("/api/v1/tasks/test-task-id/domains")

            assert response.status_code == 200
            data = response.json()
            assert data["domains"][0]["domain"] == "api.demo.com"
            assert data["domains"][0]["hit_count"] == 7
            assert data["domains"][0]["unique_ip_count"] == 2
            assert data["domains"][0]["source_types"] == ["dns", "connect"]
            assert data["domains"][0]["first_seen_at"] == "2026-03-06T09:00:00"
            assert data["domains"][0]["last_seen_at"] == "2026-03-06T09:00:05"

    def test_get_task_runs(self, client: TestClient):
        """Test stage run timeline endpoint."""
        mock_task = create_mock_task(status=TaskStatus.COMPLETED)
        mock_run = MagicMock()
        mock_run.id = "run-1"
        mock_run.stage = "dynamic"
        mock_run.attempt = 1
        mock_run.status = "success"
        mock_run.worker_name = "worker-a"
        mock_run.emulator = "10.0.0.1:5555"
        mock_run.started_at = datetime.utcnow()
        mock_run.completed_at = datetime.utcnow()
        mock_run.duration_seconds = 123
        mock_run.error_message = None
        mock_run.details = {"steps": 10}

        with patch("api.routers.tasks.SessionLocal") as mock_session_local:
            mock_db = MagicMock(spec=Session)
            mock_session_local.return_value = mock_db

            task_query = MagicMock()
            runs_query = MagicMock()
            mock_db.query.side_effect = [task_query, runs_query]
            task_query.filter.return_value.first.return_value = mock_task
            runs_query.filter.return_value.order_by.return_value.all.return_value = [mock_run]

            response = client.get("/api/v1/tasks/test-task-id/runs")

            assert response.status_code == 200
            data = response.json()
            assert data["task_id"] == "test-task-id"
            assert data["count"] == 1
            assert data["summary"]["dynamic"]["runs"] == 1
            assert data["summary"]["dynamic"]["success_runs"] == 1
            assert data["items"][0]["duration_seconds"] == 123

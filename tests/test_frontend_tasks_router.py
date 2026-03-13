"""Tests for the frontend-oriented task list router."""

from __future__ import annotations

import importlib
from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from core.database import Base
from models.analysis_tables import DynamicAnalysisTable, StaticAnalysisTable
from models.task import Task, TaskPriority, TaskStatus


@pytest.fixture
def frontend_client() -> tuple[TestClient, sessionmaker]:
    """Create a test client backed by an in-memory SQLite database."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    frontend_router = importlib.import_module("api.routers.frontend")
    app = FastAPI()
    app.include_router(frontend_router.router, prefix="/api/v1/frontend", tags=["frontend"])

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[frontend_router.get_db] = override_get_db

    try:
        with TestClient(app) as client:
            yield client, testing_session_local
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def _seed_task(
    db: Session,
    *,
    task_id: str,
    created_at: datetime,
    status: TaskStatus,
    apk_file_name: str,
    app_name: str | None = None,
    package_name: str | None = None,
    static_risk_level: str | None = None,
    detected_package: str | None = None,
    master_domains: int = 0,
    total_requests: int = 0,
    static_analysis_result: dict | None = None,
) -> None:
    """Insert a task and optional normalized analysis rows."""
    task = Task(
        id=task_id,
        apk_file_name=apk_file_name,
        apk_file_size=1024,
        apk_md5=f"{task_id:0<32}"[:32],
        apk_sha256=f"{task_id:0<64}"[:64],
        apk_storage_path=f"/storage/{apk_file_name}",
        status=status,
        priority=TaskPriority.NORMAL,
        retry_count=0,
        created_at=created_at,
        started_at=created_at,
        completed_at=created_at if status == TaskStatus.COMPLETED else None,
        updated_at=created_at,
        static_analysis_result=static_analysis_result,
    )
    db.add(task)

    if any(value is not None for value in (app_name, package_name, static_risk_level)):
        db.add(
            StaticAnalysisTable(
                task_id=task_id,
                app_name=app_name,
                package_name=package_name,
                risk_level=static_risk_level,
            )
        )

    if detected_package is not None or master_domains or total_requests:
        db.add(
            DynamicAnalysisTable(
                task_id=task_id,
                detected_package=detected_package,
                master_domains=master_domains,
                total_requests=total_requests,
            )
        )


class TestFrontendTasksRouter:
    """Behavioral tests for GET /api/v1/frontend/tasks."""

    @pytest.fixture(autouse=True)
    def seed_tasks(self, frontend_client: tuple[TestClient, sessionmaker]):
        """Populate representative task rows for each test."""
        _, session_local = frontend_client
        db = session_local()
        try:
            _seed_task(
                db,
                task_id="task-alpha-001",
                created_at=datetime(2026, 3, 1, 10, 0, 0),
                status=TaskStatus.COMPLETED,
                apk_file_name="alpha.apk",
                app_name="Alpha Wallet",
                package_name="com.demo.alpha",
                static_risk_level="HIGH",
            )
            _seed_task(
                db,
                task_id="task-beta-002",
                created_at=datetime(2026, 3, 2, 10, 0, 0),
                status=TaskStatus.FAILED,
                apk_file_name="beta.apk",
                app_name="Beta Chat",
                package_name="com.demo.beta",
                static_risk_level="LOW",
            )
            _seed_task(
                db,
                task_id="task-gamma-003",
                created_at=datetime(2026, 3, 3, 10, 0, 0),
                status=TaskStatus.DYNAMIC_ANALYZING,
                apk_file_name="gamma.apk",
                detected_package="com.demo.gamma",
                master_domains=2,
                total_requests=48,
            )
            db.commit()
        finally:
            db.close()

    def test_list_tasks_returns_frontend_friendly_paginated_payload(
        self,
        frontend_client: tuple[TestClient, sessionmaker],
    ):
        """List response should expose items + pagination with page semantics."""
        client, _ = frontend_client

        response = client.get("/api/v1/frontend/tasks?page=2&page_size=1")

        assert response.status_code == 200
        data = response.json()
        assert list(data.keys()) == ["items", "pagination"]
        assert data["pagination"] == {
            "page": 2,
            "page_size": 1,
            "total": 3,
            "total_pages": 3,
            "has_next": True,
            "has_prev": True,
        }
        assert len(data["items"]) == 1
        assert data["items"][0]["id"] == "task-beta-002"
        assert data["items"][0]["app_name"] == "Beta Chat"
        assert data["items"][0]["package_name"] == "com.demo.beta"
        assert data["items"][0]["risk_level"] == "low"
        assert data["items"][0]["report_ready"] is False
        assert data["items"][0]["report_url"] is None

    @pytest.mark.parametrize(
        ("search", "expected_id"),
        [
            ("task-beta-002", "task-beta-002"),
            ("alpha wallet", "task-alpha-001"),
            ("com.demo.beta", "task-beta-002"),
        ],
    )
    def test_list_tasks_supports_search_by_id_app_name_and_package(
        self,
        frontend_client: tuple[TestClient, sessionmaker],
        search: str,
        expected_id: str,
    ):
        """Search should match task id, static app name, and package name."""
        client, _ = frontend_client

        response = client.get("/api/v1/frontend/tasks", params={"search": search})

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["total"] == 1
        assert [item["id"] for item in data["items"]] == [expected_id]

    def test_list_tasks_supports_status_filter(self, frontend_client: tuple[TestClient, sessionmaker]):
        """Status filter should narrow the result set."""
        client, _ = frontend_client

        response = client.get("/api/v1/frontend/tasks", params={"status": "failed"})

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["total"] == 1
        assert [item["id"] for item in data["items"]] == ["task-beta-002"]
        assert data["items"][0]["status"] == "failed"

    def test_list_tasks_supports_risk_level_filter_with_stable_derivation(
        self,
        frontend_client: tuple[TestClient, sessionmaker],
    ):
        """Risk filter should work for both stored and derived task risk levels."""
        client, _ = frontend_client

        response = client.get("/api/v1/frontend/tasks", params={"risk_level": "high"})

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["total"] == 2
        assert [item["id"] for item in data["items"]] == ["task-gamma-003", "task-alpha-001"]
        assert all(item["risk_level"] == "high" for item in data["items"])
        assert data["items"][0]["package_name"] == "com.demo.gamma"

    def test_list_tasks_supports_report_ready_filter_and_generates_report_url(
        self,
        frontend_client: tuple[TestClient, sessionmaker],
    ):
        """Completed tasks should expose frontend report page links."""
        client, _ = frontend_client

        response = client.get("/api/v1/frontend/tasks", params={"report_ready": "true"})

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["total"] == 1
        assert [item["id"] for item in data["items"]] == ["task-alpha-001"]
        assert data["items"][0]["report_ready"] is True
        assert data["items"][0]["report_url"] == "/reports/task-alpha-001"

    def test_list_tasks_falls_back_to_task_static_analysis_basic_info_when_normalized_rows_missing(
        self,
        frontend_client: tuple[TestClient, sessionmaker],
    ):
        """List should use task.static_analysis_result.basic_info before falling back to file name."""
        client, session_local = frontend_client
        db = session_local()
        try:
            _seed_task(
                db,
                task_id="task-legacy-004",
                created_at=datetime(2026, 3, 4, 10, 0, 0),
                status=TaskStatus.PENDING,
                apk_file_name="legacy-fallback.apk",
                static_analysis_result={
                    "basic_info": {
                        "app_name": "招商银行",
                        "package_name": "cmb.pb",
                    }
                },
            )
            db.commit()
        finally:
            db.close()

        response = client.get("/api/v1/frontend/tasks", params={"page_size": 10})

        assert response.status_code == 200
        data = response.json()
        item = next(item for item in data["items"] if item["id"] == "task-legacy-004")
        assert item["app_name"] == "招商银行"
        assert item["package_name"] == "cmb.pb"

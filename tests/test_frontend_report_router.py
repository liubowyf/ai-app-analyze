"""Tests for the frontend-oriented report API and old HTML view removal."""

from __future__ import annotations

import importlib
from datetime import datetime
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from core.database import Base
from models.analysis_tables import (
    DynamicAnalysisTable,
    MasterDomainTable,
    NetworkRequestTable,
    ScreenshotTable,
    StaticAnalysisTable,
)
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


def _seed_completed_report_task(db: Session) -> None:
    """Insert one completed task with report evidence rows."""
    task_id = "task-report-001"
    created_at = datetime(2026, 3, 6, 10, 0, 0)

    task = Task(
        id=task_id,
        apk_file_name="alpha-wallet.apk",
        apk_file_size=5 * 1024 * 1024,
        apk_md5="a" * 32,
        apk_sha256="b" * 64,
        apk_storage_path="apks/task-report-001/alpha-wallet.apk",
        status=TaskStatus.COMPLETED,
        priority=TaskPriority.NORMAL,
        created_at=created_at,
        started_at=datetime(2026, 3, 6, 10, 1, 0),
        completed_at=datetime(2026, 3, 6, 10, 8, 0),
        updated_at=datetime(2026, 3, 6, 10, 8, 0),
    )
    db.add(task)
    db.add(
        StaticAnalysisTable(
            task_id=task_id,
            app_name="Alpha Wallet",
            package_name="com.demo.alpha",
            version_name="2.3.1",
            risk_level="HIGH",
        )
    )
    task.static_analysis_result = {
        "basic_info": {
            "app_name": "Alpha Wallet",
            "package_name": "com.demo.alpha",
            "version_name": "2.3.1",
            "version_code": 231,
            "file_size": 5 * 1024 * 1024,
            "md5": "a" * 32,
            "min_sdk": 21,
            "target_sdk": 34,
            "icon_storage_path": "icons/task-report-001/app-icon.png",
            "icon_content_type": "image/png",
        },
        "permissions": [
            {"name": "android.permission.INTERNET"},
            {"name": "android.permission.ACCESS_FINE_LOCATION"},
        ],
    }
    task.dynamic_analysis_result = {
        "permission_summary": {
            "requested_permissions": [
                "android.permission.INTERNET",
                "android.permission.ACCESS_FINE_LOCATION",
            ],
            "granted_permissions": [
                "android.permission.INTERNET",
            ],
            "failed_permissions": [
                "android.permission.ACCESS_FINE_LOCATION",
            ],
        }
    }
    db.add(
        DynamicAnalysisTable(
            task_id=task_id,
            detected_package="com.demo.alpha",
            capture_mode="redroid_zeek",
            total_observations=6,
            total_requests=3,
            master_domains=2,
            unique_domains=2,
            unique_ips=2,
            source_breakdown={"dns": 3, "connect": 2, "unknown": 1},
            total_screenshots=2,
            duration_seconds=420,
        )
    )
    db.add_all(
        [
            MasterDomainTable(
                id="domain-1",
                task_id=task_id,
                domain="api.alpha.example",
                ip="1.1.1.1",
                confidence_score=98,
                confidence_level="high",
                request_count=5,
                post_count=0,
                first_seen_at=datetime(2026, 3, 6, 10, 3, 5),
                last_seen_at=datetime(2026, 3, 6, 10, 3, 30),
                unique_ip_count=1,
                source_types_json=["dns", "connect"],
            ),
            MasterDomainTable(
                id="domain-2",
                task_id=task_id,
                domain="cdn.alpha.example",
                ip="2.2.2.2",
                confidence_score=60,
                confidence_level="medium",
                request_count=1,
                post_count=0,
                first_seen_at=datetime(2026, 3, 6, 10, 3, 35),
                last_seen_at=datetime(2026, 3, 6, 10, 3, 40),
                unique_ip_count=1,
                source_types_json=["unknown"],
            ),
        ]
    )
    db.add_all(
        [
            NetworkRequestTable(
                id="request-1",
                task_id=task_id,
                url=None,
                method="UNKNOWN",
                host="api.alpha.example",
                path=None,
                ip="1.1.1.1",
                port=53,
                response_code=None,
                request_time=datetime(2026, 3, 6, 10, 3, 5),
                first_seen_at=datetime(2026, 3, 6, 10, 3, 5),
                last_seen_at=datetime(2026, 3, 6, 10, 3, 20),
                hit_count=3,
                source_type="dns",
                transport="udp",
                protocol="dns",
                capture_mode="redroid_zeek",
                attribution_tier="primary",
            ),
            NetworkRequestTable(
                id="request-2",
                task_id=task_id,
                url=None,
                method="CONNECT",
                host="api.alpha.example",
                path=None,
                ip="1.1.1.1",
                port=443,
                scheme="https",
                response_code=None,
                request_time=datetime(2026, 3, 6, 10, 3, 30),
                first_seen_at=datetime(2026, 3, 6, 10, 3, 21),
                last_seen_at=datetime(2026, 3, 6, 10, 3, 30),
                hit_count=2,
                source_type="connect",
                transport="tcp",
                protocol="https_tunnel",
                capture_mode="redroid_zeek",
                attribution_tier="primary",
            ),
            NetworkRequestTable(
                id="request-3",
                task_id=task_id,
                url=None,
                method="UNKNOWN",
                host="cdn.alpha.example",
                path=None,
                ip="2.2.2.2",
                port=443,
                scheme="https",
                response_code=None,
                request_time=datetime(2026, 3, 6, 10, 3, 40),
                first_seen_at=datetime(2026, 3, 6, 10, 3, 35),
                last_seen_at=datetime(2026, 3, 6, 10, 3, 40),
                hit_count=1,
                source_type="unknown",
                transport="tcp",
                protocol="unknown",
                capture_mode="redroid_zeek",
                attribution_tier="candidate",
            ),
        ]
    )
    db.add_all(
        [
            ScreenshotTable(
                id="shot-1",
                task_id=task_id,
                storage_path="screenshots/task-report-001/step_001.png",
                file_size=12_000,
                stage="dynamic",
                description="启动页",
                captured_at=datetime(2026, 3, 6, 10, 3, 10),
            ),
            ScreenshotTable(
                id="shot-2",
                task_id=task_id,
                storage_path="screenshots/task-report-001/step_002.png",
                file_size=18_000,
                stage="dynamic",
                description="登录页",
                captured_at=datetime(2026, 3, 6, 10, 3, 35),
            ),
            ScreenshotTable(
                id="shot-empty",
                task_id=task_id,
                storage_path=None,
                file_size=0,
                stage="dynamic",
                description="空截图占位",
                captured_at=datetime(2026, 3, 6, 10, 3, 1),
            ),
        ]
    )
    db.commit()


class TestFrontendReportRouter:
    """Behavioral tests for frontend report APIs and old route removal."""

    @pytest.fixture(autouse=True)
    def seed_task(self, frontend_client: tuple[TestClient, sessionmaker]):
        _, session_local = frontend_client
        db = session_local()
        try:
            _seed_completed_report_task(db)
        finally:
            db.close()

    def test_get_frontend_report_returns_domain_ip_first_report_dto_with_url_screenshots(
        self,
        frontend_client: tuple[TestClient, sessionmaker],
    ):
        """Report endpoint should pivot to domain/IP summaries rather than request lists."""
        client, _ = frontend_client

        response = client.get("/api/v1/frontend/reports/task-report-001")

        assert response.status_code == 200
        data = response.json()

        assert data["task"]["id"] == "task-report-001"
        assert data["task"]["app_name"] == "Alpha Wallet"
        assert data["task"]["package_name"] == "com.demo.alpha"
        assert data["static_info"] == {
            "app_name": "Alpha Wallet",
            "package_name": "com.demo.alpha",
            "version_name": "2.3.1",
            "version_code": 231,
            "min_sdk": 21,
            "target_sdk": 34,
            "apk_file_size": 5242880,
            "apk_md5": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "declared_permissions": [
                "android.permission.INTERNET",
                "android.permission.ACCESS_FINE_LOCATION",
            ],
            "icon_url": "/api/v1/frontend/reports/task-report-001/icon",
        }
        assert data["permission_summary"] == {
            "requested_permissions": [
                "android.permission.ACCESS_FINE_LOCATION",
                "android.permission.INTERNET",
            ],
            "granted_permissions": [
                "android.permission.INTERNET",
            ],
            "failed_permissions": [
                "android.permission.ACCESS_FINE_LOCATION",
            ],
        }
        assert data["summary"]["risk_level"] == "high"
        assert data["summary"]["risk_label"] == "高风险"
        assert data["evidence_summary"] == {
            "domains_count": 2,
            "ips_count": 2,
            "observation_hits": 6,
            "source_breakdown": {"dns": 3, "connect": 2, "unknown": 1},
            "capture_mode": "redroid_zeek",
            "screenshots_count": 3,
        }
        assert [item["domain"] for item in data["top_domains"]] == [
            "api.alpha.example",
            "cdn.alpha.example",
        ]
        assert data["top_domains"][0]["hit_count"] == 5
        assert data["top_domains"][0]["first_seen_at"] == "2026-03-06T10:03:05"
        assert data["top_ips"][0]["ip"] == "1.1.1.1"
        assert data["top_ips"][0]["hit_count"] == 5
        assert data["top_ips"][0]["primary_domain"] == "api.alpha.example"
        assert data["timeline"][0]["domain"] == "cdn.alpha.example"
        assert data["timeline"][0]["source_type"] == "unknown"
        assert data["timeline"][0]["last_seen_at"] == "2026-03-06T10:03:40"
        assert "requests" not in data
        screenshots_by_id = {item["id"]: item for item in data["screenshots"]}
        assert data["screenshots"][0]["id"] == "shot-2"
        assert data["screenshots"][0]["image_url"] == (
            "/api/v1/frontend/reports/task-report-001/screenshots/shot-2"
        )
        assert screenshots_by_id["shot-empty"]["image_url"] is None
        assert "image_base64" not in data["screenshots"][0]

    def test_report_screenshot_resource_is_served_via_url_reference(
        self,
        frontend_client: tuple[TestClient, sessionmaker],
    ):
        """Screenshot bytes should be fetched through a dedicated resource URL."""
        client, _ = frontend_client

        with patch(
            "api.routers.frontend.storage_client.download_file",
            return_value=b"\x89PNG\r\n\x1a\nmock-image",
        ):
            response = client.get(
                "/api/v1/frontend/reports/task-report-001/screenshots/shot-1"
            )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("image/png")
        assert response.content.startswith(b"\x89PNG\r\n\x1a\n")

    def test_report_icon_resource_is_served_via_url_reference(
        self,
        frontend_client: tuple[TestClient, sessionmaker],
    ):
        client, _ = frontend_client

        with patch(
            "api.routers.frontend.storage_client.download_file",
            return_value=b"\x89PNG\r\n\x1a\nmock-report-icon",
        ):
            response = client.get("/api/v1/frontend/reports/task-report-001/icon")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("image/png")
        assert response.content.startswith(b"\x89PNG\r\n\x1a\n")

    def test_old_html_view_route_is_not_registered(
        self,
        frontend_client: tuple[TestClient, sessionmaker],
    ):
        """The deprecated HTML view route must no longer be accessible."""
        client, _ = frontend_client

        response = client.get("/api/v1/reports/task-report-001/view")

        assert response.status_code == 404

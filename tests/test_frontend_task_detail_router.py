"""Tests for the frontend-oriented task detail and retry routes."""

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
    AnalysisRunTable,
    DynamicAnalysisTable,
    MasterDomainTable,
    NetworkRequestTable,
    ScreenshotTable,
    StaticAnalysisTable,
)
from models.task import Task, TaskPriority, TaskStatus


@pytest.fixture
def frontend_client() -> tuple[TestClient, sessionmaker]:
    """Create a frontend router test client backed by in-memory SQLite."""
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


def _seed_failed_task_detail(db: Session) -> None:
    """Insert one failed task with representative detail evidence rows."""
    task_id = "task-detail-001"
    created_at = datetime(2026, 3, 6, 9, 0, 0)

    db.add(
        Task(
            id=task_id,
            apk_file_name="alpha-wallet.apk",
            apk_file_size=5 * 1024 * 1024,
            apk_md5="a" * 32,
            apk_sha256="b" * 64,
            apk_storage_path="/storage/apks/alpha-wallet.apk",
            status=TaskStatus.FAILED,
            priority=TaskPriority.NORMAL,
            error_message="动态分析阶段失败：设备连接中断",
            retry_count=1,
            created_at=created_at,
            started_at=datetime(2026, 3, 6, 9, 1, 0),
            updated_at=datetime(2026, 3, 6, 9, 6, 0),
        )
    )
    db.add(
        StaticAnalysisTable(
            task_id=task_id,
            app_name="Alpha Wallet",
            package_name="com.demo.alpha",
            risk_level="HIGH",
        )
    )
    db.add(
        DynamicAnalysisTable(
            task_id=task_id,
            detected_package="com.demo.alpha",
            capture_mode="redroid_zeek",
            total_observations=7,
            primary_observations=6,
            candidate_observations=1,
            total_requests=3,
            unique_domains=2,
            unique_ips=2,
            master_domains=2,
            total_screenshots=2,
            source_breakdown={"dns": 4, "connect": 2, "unknown": 1},
            error_message="代理断开",
        )
    )
    db.add_all(
        [
            AnalysisRunTable(
                id="run-static-1",
                task_id=task_id,
                stage="static",
                attempt=1,
                status="success",
                worker_name="worker-a",
                started_at=datetime(2026, 3, 6, 9, 1, 0),
                completed_at=datetime(2026, 3, 6, 9, 1, 12),
                duration_seconds=12,
            ),
            AnalysisRunTable(
                id="run-dynamic-1",
                task_id=task_id,
                stage="dynamic",
                attempt=1,
                status="failed",
                worker_name="worker-b",
                emulator="emulator-5554",
                started_at=datetime(2026, 3, 6, 9, 2, 0),
                completed_at=datetime(2026, 3, 6, 9, 2, 45),
                duration_seconds=45,
                error_message="动态阶段超时",
            ),
        ]
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
                request_count=6,
                post_count=2,
                first_seen_at=datetime(2026, 3, 6, 9, 2, 5),
                last_seen_at=datetime(2026, 3, 6, 9, 2, 40),
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
                first_seen_at=datetime(2026, 3, 6, 9, 2, 15),
                last_seen_at=datetime(2026, 3, 6, 9, 2, 20),
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
                scheme=None,
                first_seen_at=datetime(2026, 3, 6, 9, 2, 5),
                last_seen_at=datetime(2026, 3, 6, 9, 2, 40),
                hit_count=4,
                source_type="dns",
                transport="udp",
                protocol="dns",
                capture_mode="redroid_zeek",
                attribution_tier="primary",
                request_time=datetime(2026, 3, 6, 9, 2, 5),
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
                first_seen_at=datetime(2026, 3, 6, 9, 2, 10),
                last_seen_at=datetime(2026, 3, 6, 9, 2, 30),
                hit_count=2,
                source_type="connect",
                transport="tcp",
                protocol="https_tunnel",
                capture_mode="redroid_zeek",
                attribution_tier="primary",
                request_time=datetime(2026, 3, 6, 9, 2, 30),
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
                first_seen_at=datetime(2026, 3, 6, 9, 2, 15),
                last_seen_at=datetime(2026, 3, 6, 9, 2, 20),
                hit_count=1,
                source_type="unknown",
                transport="tcp",
                protocol="unknown",
                capture_mode="redroid_zeek",
                attribution_tier="candidate",
                request_time=datetime(2026, 3, 6, 9, 2, 20),
            ),
        ]
    )
    db.add_all(
        [
            ScreenshotTable(
                id="shot-1",
                task_id=task_id,
                storage_path="/storage/screenshots/task-detail-001/step-001.png",
                file_size=12_000,
                stage="dynamic",
                description="启动页",
                captured_at=datetime(2026, 3, 6, 9, 2, 10),
            ),
            ScreenshotTable(
                id="shot-2",
                task_id=task_id,
                storage_path="/storage/screenshots/task-detail-001/step-002.png",
                file_size=18_000,
                stage="dynamic",
                description="登录页",
                captured_at=datetime(2026, 3, 6, 9, 2, 35),
            ),
            ScreenshotTable(
                id="shot-empty",
                task_id=task_id,
                storage_path=None,
                file_size=0,
                stage="dynamic",
                description="空截图占位",
                captured_at=datetime(2026, 3, 6, 9, 2, 1),
            ),
        ]
    )
    db.commit()


class TestFrontendTaskDetailRouter:
    """Behavioral tests for the frontend task detail/retry endpoints."""

    @pytest.fixture(autouse=True)
    def seed_task(self, frontend_client: tuple[TestClient, sessionmaker]):
        _, session_local = frontend_client
        db = session_local()
        try:
            _seed_failed_task_detail(db)
        finally:
            db.close()

    def test_get_task_detail_returns_frontend_aggregated_detail_dto(
        self,
        frontend_client: tuple[TestClient, sessionmaker],
    ):
        """Detail endpoint should expose frontend-friendly summary and preview fields."""
        client, _ = frontend_client

        response = client.get("/api/v1/frontend/tasks/task-detail-001")

        assert response.status_code == 200
        data = response.json()

        assert data["task"]["id"] == "task-detail-001"
        assert data["task"]["app_name"] == "Alpha Wallet"
        assert data["task"]["package_name"] == "com.demo.alpha"
        assert data["task"]["status"] == "failed"
        assert data["task"]["risk_level"] == "high"
        assert data["task"]["error_message"] == "动态分析阶段失败：设备连接中断"
        assert data["task"]["retry_count"] == 1

        assert data["retryable"] is True
        assert data["report_ready"] is False
        assert data["report_url"] is None

        assert data["evidence_summary"]["runs_count"] == 2
        assert data["evidence_summary"]["domains_count"] == 2
        assert data["evidence_summary"]["ips_count"] == 2
        assert data["evidence_summary"]["observation_hits"] == 7
        assert data["evidence_summary"]["network_requests_count"] == 3
        assert data["evidence_summary"]["screenshots_count"] == 3
        assert data["evidence_summary"]["capture_mode"] == "redroid_zeek"
        assert data["evidence_summary"]["source_breakdown"] == {
            "dns": 4,
            "connect": 2,
            "unknown": 1,
        }

        assert data["stage_summary"] == [
            {
                "stage": "dynamic",
                "runs": 1,
                "success_runs": 0,
                "failed_runs": 1,
                "latest_status": "failed",
                "total_duration_seconds": 45,
            },
            {
                "stage": "static",
                "runs": 1,
                "success_runs": 1,
                "failed_runs": 0,
                "latest_status": "success",
                "total_duration_seconds": 12,
            },
        ]

        assert [item["stage"] for item in data["runs_preview"]] == ["dynamic", "static"]
        assert data["runs_preview"][0]["error_message"] == "动态阶段超时"
        assert data["domains_preview"][0]["domain"] == "api.alpha.example"
        assert data["domains_preview"][0]["hit_count"] == 6
        assert data["domains_preview"][0]["unique_ip_count"] == 1
        assert data["domains_preview"][0]["source_types"] == ["dns", "connect"]
        assert data["ip_stats_preview"][0]["ip"] == "1.1.1.1"
        assert data["ip_stats_preview"][0]["hit_count"] == 6
        assert data["ip_stats_preview"][0]["domain_count"] == 1
        assert data["ip_stats_preview"][0]["primary_domain"] == "api.alpha.example"
        assert data["ip_stats_preview"][0]["source_types"] == ["connect", "dns"]
        assert data["observations_preview"][0]["domain"] == "api.alpha.example"
        assert data["observations_preview"][0]["hit_count"] == 4
        assert data["observations_preview"][0]["source_type"] == "dns"
        assert data["observations_preview"][0]["first_seen_at"] == "2026-03-06T09:02:05"
        assert data["observations_preview"][0]["last_seen_at"] == "2026-03-06T09:02:40"
        assert "network_requests_preview" not in data
        assert data["screenshots_preview"][0]["description"] == "登录页"
        assert data["screenshots_preview"][0]["image_url"] == (
            "/api/v1/frontend/tasks/task-detail-001/screenshots/shot-2"
        )
        screenshots_by_id = {item["id"]: item for item in data["screenshots_preview"]}
        assert screenshots_by_id["shot-empty"]["image_url"] is None
        assert data["errors"] == [
            {
                "source": "task",
                "stage": None,
                "message": "动态分析阶段失败：设备连接中断",
            },
            {
                "source": "run",
                "stage": "dynamic",
                "message": "动态阶段超时",
            },
        ]

    def test_retry_task_updates_status_and_returns_refreshed_detail(
        self,
        frontend_client: tuple[TestClient, sessionmaker],
    ):
        """Retry endpoint should re-queue failed tasks and return the updated detail DTO."""
        client, session_local = frontend_client

        with patch("api.routers.frontend.enqueue_task", return_value=True) as enqueue_task:
            response = client.post("/api/v1/frontend/tasks/task-detail-001/retry")

        assert response.status_code == 200
        data = response.json()
        assert data["task"]["status"] == "queued"
        assert data["task"]["retry_count"] == 2
        assert data["task"]["error_message"] is None
        assert data["retryable"] is False
        enqueue_task.assert_called_once()

        db = session_local()
        try:
            task = db.query(Task).filter(Task.id == "task-detail-001").first()
            assert task is not None
            assert task.status == TaskStatus.QUEUED
            assert task.retry_count == 2
            assert task.error_message is None
            assert task.error_stack is None
        finally:
            db.close()

    def test_get_task_detail_falls_back_to_task_static_analysis_basic_info_when_normalized_rows_missing(
        self,
        frontend_client: tuple[TestClient, sessionmaker],
    ):
        """Detail should use task.static_analysis_result.basic_info when normalized rows are absent."""
        client, session_local = frontend_client
        db = session_local()
        try:
            db.add(
                Task(
                    id="task-detail-legacy",
                    apk_file_name="legacy-detail.apk",
                    apk_file_size=4096,
                    apk_md5="c" * 32,
                    apk_sha256="d" * 64,
                    apk_storage_path="/storage/apks/legacy-detail.apk",
                    status=TaskStatus.PENDING,
                    priority=TaskPriority.NORMAL,
                    retry_count=0,
                    created_at=datetime(2026, 3, 6, 8, 0, 0),
                    updated_at=datetime(2026, 3, 6, 8, 0, 0),
                    static_analysis_result={
                        "basic_info": {
                            "app_name": "微信",
                            "package_name": "com.tencent.mm",
                        }
                    },
                )
            )
            db.commit()
        finally:
            db.close()

        response = client.get("/api/v1/frontend/tasks/task-detail-legacy")

        assert response.status_code == 200
        data = response.json()
        assert data["task"]["app_name"] == "微信"
        assert data["task"]["package_name"] == "com.tencent.mm"

    def test_get_task_detail_falls_back_to_dynamic_result_observation_summary_when_normalized_rows_missing(
        self,
        frontend_client: tuple[TestClient, sessionmaker],
    ):
        """Historical tasks should still expose observation summaries from legacy JSON payloads."""
        client, session_local = frontend_client
        db = session_local()
        try:
            db.add(
                Task(
                    id="task-detail-legacy-observation",
                    apk_file_name="legacy-observation.apk",
                    apk_file_size=4096,
                    apk_md5="e" * 32,
                    apk_sha256="f" * 64,
                    apk_storage_path="/storage/apks/legacy-observation.apk",
                    status=TaskStatus.COMPLETED,
                    priority=TaskPriority.NORMAL,
                    retry_count=0,
                    created_at=datetime(2026, 3, 6, 8, 30, 0),
                    completed_at=datetime(2026, 3, 6, 8, 35, 0),
                    updated_at=datetime(2026, 3, 6, 8, 35, 0),
                    dynamic_analysis_result={
                        "capture_mode": "redroid_zeek",
                        "network_observation_summary": {
                            "total_observations": 5,
                            "unique_domains": 1,
                            "unique_ips": 1,
                            "source_breakdown": {"dns": 5},
                        },
                        "primary_observations_preview": [
                            {
                                "id": "legacy-obs-1",
                                "domain": "legacy.alpha.example",
                                "host": "legacy.alpha.example",
                                "ip": "3.3.3.3",
                                "hit_count": 5,
                                "source_type": "dns",
                                "transport": "udp",
                                "protocol": "dns",
                                "first_seen_at": "2026-03-06T08:31:00",
                                "last_seen_at": "2026-03-06T08:34:00",
                                "capture_mode": "redroid_zeek",
                                "attribution_tier": "primary",
                            }
                        ],
                        "master_domains": {
                            "master_domains": [
                                {
                                    "domain": "legacy.alpha.example",
                                    "ip": "3.3.3.3",
                                    "score": 70,
                                    "confidence": "high",
                                    "hit_count": 5,
                                    "unique_ip_count": 1,
                                    "source_types": ["dns"],
                                    "first_seen_at": "2026-03-06T08:31:00",
                                    "last_seen_at": "2026-03-06T08:34:00",
                                }
                            ]
                        },
                    },
                )
            )
            db.commit()
        finally:
            db.close()

        response = client.get("/api/v1/frontend/tasks/task-detail-legacy-observation")

        assert response.status_code == 200
        data = response.json()
        assert data["evidence_summary"]["capture_mode"] == "redroid_zeek"
        assert data["evidence_summary"]["observation_hits"] == 5
        assert data["evidence_summary"]["domains_count"] == 1
        assert data["evidence_summary"]["ips_count"] == 1
        assert data["observations_preview"][0]["domain"] == "legacy.alpha.example"
        assert data["domains_preview"][0]["domain"] == "legacy.alpha.example"
        assert data["ip_stats_preview"][0]["ip"] == "3.3.3.3"
        assert data["ip_stats_preview"][0]["primary_domain"] == "legacy.alpha.example"

    def test_task_detail_screenshot_resource_is_served_via_url_reference(
        self,
        frontend_client: tuple[TestClient, sessionmaker],
    ):
        """Task detail screenshots should be fetched through a dedicated resource URL."""
        client, _ = frontend_client

        with patch(
            "api.routers.frontend.storage_client.download_file",
            return_value=b"\x89PNG\r\n\x1a\nmock-task-image",
        ):
            response = client.get(
                "/api/v1/frontend/tasks/task-detail-001/screenshots/shot-1"
            )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("image/png")
        assert response.content.startswith(b"\x89PNG\r\n\x1a\n")

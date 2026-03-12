from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.main import app
from api.routers.reports import get_db
from core.database import Base
from models.analysis_tables import (  # noqa: F401
    DynamicAnalysisTable,
    MasterDomainTable,
    NetworkRequestTable,
    ScreenshotTable,
    StaticAnalysisTable,
)
from models.task import Task, TaskPriority, TaskStatus


@pytest.fixture
def reports_client() -> tuple[TestClient, sessionmaker]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            yield client, testing_session_local
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def _seed_task(db: Session, *, task_id: str, status: TaskStatus) -> None:
    completed_at = datetime(2026, 3, 6, 10, 8, 0) if status == TaskStatus.COMPLETED else None
    db.add(
        Task(
            id=task_id,
            apk_file_name="alpha-wallet.apk",
            apk_file_size=5 * 1024 * 1024,
            apk_md5="a" * 32,
            apk_sha256="b" * 64,
            apk_storage_path=f"apks/{task_id}/alpha-wallet.apk",
            status=status,
            priority=TaskPriority.NORMAL,
            created_at=datetime(2026, 3, 6, 10, 0, 0),
            started_at=datetime(2026, 3, 6, 10, 1, 0),
            completed_at=completed_at,
            updated_at=datetime(2026, 3, 6, 10, 8, 0),
            dynamic_analysis_result={},
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
            total_observations=6,
            unique_domains=2,
            unique_ips=2,
            master_domains=2,
            total_screenshots=2,
            source_breakdown={"dns": 3, "connect": 2, "unknown": 1},
        )
    )
    db.add_all(
        [
            MasterDomainTable(
                id=f"{task_id}-domain-1",
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
                id=f"{task_id}-domain-2",
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
                id=f"{task_id}-request-1",
                task_id=task_id,
                url=None,
                method="UNKNOWN",
                host="api.alpha.example",
                ip="1.1.1.1",
                port=53,
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
                id=f"{task_id}-request-2",
                task_id=task_id,
                url=None,
                method="CONNECT",
                host="api.alpha.example",
                ip="1.1.1.1",
                port=443,
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
                id=f"{task_id}-request-3",
                task_id=task_id,
                url=None,
                method="UNKNOWN",
                host="cdn.alpha.example",
                ip="2.2.2.2",
                port=443,
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
                id=f"{task_id}-shot-1",
                task_id=task_id,
                storage_path=None,
                file_size=12_000,
                stage="dynamic",
                description="启动页",
                captured_at=datetime(2026, 3, 6, 10, 3, 10),
            ),
            ScreenshotTable(
                id=f"{task_id}-shot-2",
                task_id=task_id,
                storage_path=None,
                file_size=18_000,
                stage="dynamic",
                description="登录页",
                captured_at=datetime(2026, 3, 6, 10, 3, 35),
            ),
        ]
    )
    db.commit()


def test_download_report_endpoint_returns_html_attachment_for_completed_task(
    reports_client: tuple[TestClient, sessionmaker],
):
    client, session_local = reports_client
    db = session_local()
    try:
        _seed_task(db, task_id="task-report-123", status=TaskStatus.COMPLETED)
    finally:
        db.close()

    with patch(
        "api.routers.reports.HTMLReportGenerator.generate_static_report",
        return_value="<html><body>mock report</body></html>",
    ):
        response = client.get("/api/v1/reports/task-report-123/download")

    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    assert "text/html" in response.headers["content-type"]
    assert "mock report" in response.text


def test_download_report_endpoint_renders_domain_ip_summary_sections(
    reports_client: tuple[TestClient, sessionmaker],
):
    client, session_local = reports_client
    db = session_local()
    try:
        _seed_task(db, task_id="task-report-summary", status=TaskStatus.COMPLETED)
    finally:
        db.close()

    response = client.get("/api/v1/reports/task-report-summary/download")

    assert response.status_code == 200
    assert "Top Domains" in response.text
    assert "Top IPs" in response.text
    assert "观测来源拆分" in response.text
    assert "观测时间线" in response.text
    assert "api.alpha.example" in response.text
    assert "1.1.1.1" in response.text
    assert "可疑网络行为" not in response.text
    assert "网络请求样本" not in response.text


def test_download_report_endpoint_returns_404_for_missing_task(
    reports_client: tuple[TestClient, sessionmaker],
):
    client, _ = reports_client

    response = client.get("/api/v1/reports/nonexistent-task/download")

    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


def test_download_report_endpoint_returns_400_for_unfinished_task(
    reports_client: tuple[TestClient, sessionmaker],
):
    client, session_local = reports_client
    db = session_local()
    try:
        _seed_task(db, task_id="task-running-123", status=TaskStatus.DYNAMIC_ANALYZING)
    finally:
        db.close()

    response = client.get("/api/v1/reports/task-running-123/download")

    assert response.status_code == 400
    assert response.json()["detail"] == "Task not completed yet"


def test_legacy_view_report_endpoint_is_not_available(
    reports_client: tuple[TestClient, sessionmaker],
):
    client, session_local = reports_client
    db = session_local()
    try:
        _seed_task(db, task_id="task-report-123", status=TaskStatus.COMPLETED)
    finally:
        db.close()

    response = client.get("/api/v1/reports/task-report-123/view")

    assert response.status_code == 404

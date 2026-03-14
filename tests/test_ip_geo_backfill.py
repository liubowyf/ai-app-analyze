from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from core.database import Base
from models.analysis_tables import MasterDomainTable, NetworkRequestTable
from models.task import Task, TaskPriority, TaskStatus


def _build_session() -> sessionmaker:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    return testing_session_local


def _seed_task_with_missing_ip_locations(db: Session) -> None:
    task = Task(
        id="task-ip-backfill-001",
        apk_file_name="demo.apk",
        apk_file_size=1024,
        apk_md5="a" * 32,
        apk_sha256="b" * 64,
        apk_storage_path="apks/demo.apk",
        status=TaskStatus.COMPLETED,
        priority=TaskPriority.NORMAL,
        created_at=datetime(2026, 3, 14, 12, 0, 0),
        completed_at=datetime(2026, 3, 14, 12, 10, 0),
        updated_at=datetime(2026, 3, 14, 12, 10, 0),
    )
    db.add(task)
    db.add_all(
        [
            NetworkRequestTable(
                id="nr-1",
                task_id=task.id,
                host="api.alpha.example",
                ip="1.1.1.1",
                ip_location=None,
                source_type="dns",
                hit_count=2,
            ),
            NetworkRequestTable(
                id="nr-2",
                task_id=task.id,
                host="sdk.example",
                ip="8.8.8.8",
                ip_location=None,
                source_type="ssl",
                hit_count=1,
            ),
            NetworkRequestTable(
                id="nr-3",
                task_id=task.id,
                host="private.example",
                ip="192.168.1.100",
                ip_location=None,
                source_type="dns",
                hit_count=1,
            ),
            MasterDomainTable(
                id="md-1",
                task_id=task.id,
                domain="api.alpha.example",
                ip="1.1.1.1",
                ip_location=None,
                confidence_score=98,
                confidence_level="high",
                request_count=5,
                unique_ip_count=1,
            ),
            MasterDomainTable(
                id="md-2",
                task_id=task.id,
                domain="sdk.example",
                ip="8.8.8.8",
                ip_location=None,
                confidence_score=12,
                confidence_level="low",
                request_count=1,
                unique_ip_count=1,
            ),
        ]
    )
    db.commit()


def test_backfill_missing_ip_locations_updates_rows(monkeypatch):
    from modules.ip_geo.backfill import backfill_missing_ip_locations

    session_local = _build_session()
    with session_local() as db:
        _seed_task_with_missing_ip_locations(db)

    def _fake_resolve(ips: list[str]) -> dict[str, str]:
        assert ips == ["1.1.1.1", "8.8.8.8"]
        return {
            "1.1.1.1": "澳大利亚",
            "8.8.8.8": "美国 加利福尼亚",
        }

    monkeypatch.setattr("modules.ip_geo.backfill.resolve_ip_locations", _fake_resolve)

    with session_local() as db:
        result = backfill_missing_ip_locations(db, batch_size=2)

    assert result == {
        "batches": 1,
        "resolved_ips": 2,
        "updated_request_rows": 2,
        "updated_domain_rows": 2,
        "skipped_ips": 0,
    }

    with session_local() as db:
        request_rows = db.query(NetworkRequestTable).order_by(NetworkRequestTable.id.asc()).all()
        domain_rows = db.query(MasterDomainTable).order_by(MasterDomainTable.id.asc()).all()

    assert request_rows[0].ip_location == "澳大利亚"
    assert request_rows[1].ip_location == "美国 加利福尼亚"
    assert request_rows[2].ip_location is None
    assert domain_rows[0].ip_location == "澳大利亚"
    assert domain_rows[1].ip_location == "美国 加利福尼亚"


def test_backfill_missing_ip_locations_honors_limit(monkeypatch):
    from modules.ip_geo.backfill import backfill_missing_ip_locations

    session_local = _build_session()
    with session_local() as db:
        _seed_task_with_missing_ip_locations(db)

    monkeypatch.setattr(
        "modules.ip_geo.backfill.resolve_ip_locations",
        lambda ips: {ip: f"LOC-{ip}" for ip in ips},
    )

    with session_local() as db:
        result = backfill_missing_ip_locations(db, batch_size=1, limit=1)

    assert result["batches"] == 1
    assert result["resolved_ips"] == 1

    with session_local() as db:
        request_rows = db.query(NetworkRequestTable).order_by(NetworkRequestTable.id.asc()).all()
        domain_rows = db.query(MasterDomainTable).order_by(MasterDomainTable.id.asc()).all()

    updated_ips = {row.ip for row in request_rows if row.ip_location}
    updated_ips |= {row.ip for row in domain_rows if row.ip_location}
    assert len(updated_ips) == 1

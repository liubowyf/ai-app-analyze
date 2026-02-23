"""Tests for distributed emulator lease manager."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import modules.emulator_pool.lease as lease_module
from models.emulator_lease import EmulatorLeaseTable
from modules.emulator_pool.lease import EmulatorLeaseManager


def _configure_sqlite_backend(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    EmulatorLeaseTable.__table__.create(bind=engine, checkfirst=True)

    monkeypatch.setattr(lease_module, "engine", engine)
    monkeypatch.setattr(lease_module, "SessionLocal", SessionLocal)

    def _seed(db, candidates):
        for item in candidates:
            host = str(item["host"])
            port = int(item["port"])
            existing = (
                db.query(EmulatorLeaseTable)
                .filter(
                    EmulatorLeaseTable.host == host,
                    EmulatorLeaseTable.port == port,
                )
                .first()
            )
            if not existing:
                db.add(EmulatorLeaseTable(host=host, port=port))
        db.flush()

    return _seed


def test_lease_manager_acquire_and_release(monkeypatch):
    seed = _configure_sqlite_backend(monkeypatch)
    manager = EmulatorLeaseManager(lease_ttl_seconds=120)
    monkeypatch.setattr(manager, "_seed_candidates", seed)

    leased = manager.acquire(
        task_id="task-1",
        candidates=[{"host": "10.0.0.1", "port": 5555}],
    )
    assert leased is not None
    assert leased["host"] == "10.0.0.1"
    assert leased["port"] == 5555
    assert "lease_token" in leased

    leased_again = manager.acquire(
        task_id="task-2",
        candidates=[{"host": "10.0.0.1", "port": 5555}],
    )
    assert leased_again is None

    released = manager.release(leased)
    assert released is True

    leased_after_release = manager.acquire(
        task_id="task-3",
        candidates=[{"host": "10.0.0.1", "port": 5555}],
    )
    assert leased_after_release is not None


def test_lease_manager_release_with_mismatched_token(monkeypatch):
    seed = _configure_sqlite_backend(monkeypatch)
    manager = EmulatorLeaseManager(lease_ttl_seconds=120)
    monkeypatch.setattr(manager, "_seed_candidates", seed)

    leased = manager.acquire(
        task_id="task-1",
        candidates=[{"host": "10.0.0.2", "port": 5556}],
    )
    assert leased is not None

    ok = manager.release(
        {
            "host": leased["host"],
            "port": leased["port"],
            "lease_token": "wrong-token",
        }
    )
    assert ok is False

"""Tests for distributed proxy port lease manager."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import modules.traffic_monitor.proxy_port_lease as lease_module
from models.proxy_port_lease import ProxyPortLeaseTable
from modules.traffic_monitor.proxy_port_lease import ProxyPortLeaseManager


def _configure_sqlite_backend(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    ProxyPortLeaseTable.__table__.create(bind=engine, checkfirst=True)

    monkeypatch.setattr(lease_module, "engine", engine)
    monkeypatch.setattr(lease_module, "SessionLocal", SessionLocal)

    def _seed(db, ports):
        for port in ports:
            existing = (
                db.query(ProxyPortLeaseTable)
                .filter(
                    ProxyPortLeaseTable.node_name == "node-a",
                    ProxyPortLeaseTable.port == int(port),
                )
                .first()
            )
            if not existing:
                db.add(ProxyPortLeaseTable(node_name="node-a", port=int(port)))
        db.flush()

    return _seed


def test_proxy_port_lease_acquire_release(monkeypatch):
    seed = _configure_sqlite_backend(monkeypatch)
    manager = ProxyPortLeaseManager(port_start=18080, port_end=18081, node_name="node-a")
    monkeypatch.setattr(manager, "_seed_ports", seed)
    monkeypatch.setattr(manager, "_is_port_available", lambda port: True)

    lease = manager.acquire(task_id="task-1")
    assert lease is not None
    assert lease["port"] in (18080, 18081)
    assert "lease_token" in lease

    second = manager.acquire(task_id="task-2")
    assert second is not None
    assert second["port"] != lease["port"]

    third = manager.acquire(task_id="task-3")
    assert third is None

    ok = manager.release(lease)
    assert ok is True

    next_lease = manager.acquire(task_id="task-4")
    assert next_lease is not None


def test_proxy_port_lease_release_requires_token(monkeypatch):
    seed = _configure_sqlite_backend(monkeypatch)
    manager = ProxyPortLeaseManager(port_start=18090, port_end=18090, node_name="node-a")
    monkeypatch.setattr(manager, "_seed_ports", seed)
    monkeypatch.setattr(manager, "_is_port_available", lambda port: True)

    lease = manager.acquire(task_id="task-1")
    assert lease is not None

    ok = manager.release(
        {
            "node_name": lease["node_name"],
            "port": lease["port"],
            "lease_token": "wrong-token",
        }
    )
    assert ok is False

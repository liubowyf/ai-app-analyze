from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from models.analysis_tables import RedroidLeaseTable
from modules.redroid_remote.lease_manager import RedroidLeaseManager


def _session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine, tables=[RedroidLeaseTable.__table__])
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


def test_redroid_lease_manager_allocates_distinct_slots_and_releases():
    session_factory = _session_factory()
    manager = RedroidLeaseManager(
        [
            {"name": "redroid-1", "adb_serial": "61.152.73.88:16555", "container_name": "redroid-1"},
            {"name": "redroid-2", "adb_serial": "61.152.73.88:16556", "container_name": "redroid-2"},
            {"name": "redroid-3", "adb_serial": "61.152.73.88:16557", "container_name": "redroid-3"},
        ],
        ttl_seconds=600,
        acquire_timeout_seconds=1,
        poll_interval_seconds=0.2,
        session_factory=session_factory,
    )

    slot_a = manager.acquire("task-a")
    slot_b = manager.acquire("task-b")
    slot_c = manager.acquire("task-c")

    assert {slot_a["name"], slot_b["name"], slot_c["name"]} == {"redroid-1", "redroid-2", "redroid-3"}

    manager.release("task-b", slot_b["name"])
    slot_d = manager.acquire("task-d")

    assert slot_d["name"] == slot_b["name"]

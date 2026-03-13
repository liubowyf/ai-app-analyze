"""MySQL-backed lease manager for redroid execution slots."""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Any, Callable

from sqlalchemy.orm import Session

from core.database import SessionLocal
from models.analysis_tables import RedroidLeaseTable


class RedroidLeaseManager:
    """Allocate one redroid slot to one task at a time."""

    def __init__(
        self,
        slots: list[dict[str, str]],
        *,
        ttl_seconds: int = 1800,
        acquire_timeout_seconds: int = 300,
        poll_interval_seconds: float = 2.0,
        session_factory: Callable[[], Session] = SessionLocal,
    ):
        if not slots:
            raise ValueError("At least one redroid slot is required")
        self.slots = slots
        self.ttl_seconds = max(60, int(ttl_seconds or 1800))
        self.acquire_timeout_seconds = max(1, int(acquire_timeout_seconds or 300))
        self.poll_interval_seconds = max(0.2, float(poll_interval_seconds or 2.0))
        self.session_factory = session_factory

    def _ensure_slot_rows(self, db: Session) -> None:
        existing = {
            row.slot_key: row
            for row in db.query(RedroidLeaseTable).filter(
                RedroidLeaseTable.slot_key.in_([slot["name"] for slot in self.slots])
            )
        }
        changed = False
        for slot in self.slots:
            row = existing.get(slot["name"])
            if row is None:
                db.add(
                    RedroidLeaseTable(
                        slot_key=slot["name"],
                        adb_serial=slot["adb_serial"],
                        container_name=slot["container_name"],
                    )
                )
                changed = True
                continue
            if row.adb_serial != slot["adb_serial"] or row.container_name != slot["container_name"]:
                row.adb_serial = slot["adb_serial"]
                row.container_name = slot["container_name"]
                changed = True
        if changed:
            db.flush()

    def acquire(self, task_id: str) -> dict[str, str]:
        deadline = time.monotonic() + self.acquire_timeout_seconds
        while True:
            db = self.session_factory()
            try:
                self._ensure_slot_rows(db)
                now = datetime.utcnow()
                rows = (
                    db.query(RedroidLeaseTable)
                    .filter(RedroidLeaseTable.slot_key.in_([slot["name"] for slot in self.slots]))
                    .order_by(RedroidLeaseTable.slot_key.asc())
                    .with_for_update()
                    .all()
                )
                for row in rows:
                    if row.holder_task_id and row.expires_at and row.expires_at > now:
                        continue
                    row.holder_task_id = task_id
                    row.acquired_at = now
                    row.expires_at = now + timedelta(seconds=self.ttl_seconds)
                    db.commit()
                    return {
                        "name": row.slot_key,
                        "adb_serial": row.adb_serial,
                        "container_name": row.container_name,
                    }
                db.rollback()
            finally:
                db.close()

            if time.monotonic() >= deadline:
                raise RuntimeError("No redroid slot available within acquire timeout")
            time.sleep(self.poll_interval_seconds)

    def release(self, task_id: str, slot_name: str | None = None) -> None:
        db = self.session_factory()
        try:
            query = db.query(RedroidLeaseTable).filter(RedroidLeaseTable.holder_task_id == task_id)
            if slot_name:
                query = query.filter(RedroidLeaseTable.slot_key == slot_name)
            rows = query.with_for_update().all()
            for row in rows:
                row.holder_task_id = None
                row.acquired_at = None
                row.expires_at = None
            db.commit()
        finally:
            db.close()

    def release_expired(self) -> int:
        db = self.session_factory()
        try:
            now = datetime.utcnow()
            rows = (
                db.query(RedroidLeaseTable)
                .filter(RedroidLeaseTable.expires_at.isnot(None), RedroidLeaseTable.expires_at <= now)
                .with_for_update()
                .all()
            )
            for row in rows:
                row.holder_task_id = None
                row.acquired_at = None
                row.expires_at = None
            db.commit()
            return len(rows)
        finally:
            db.close()

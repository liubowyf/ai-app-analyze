"""MySQL-backed emulator lease manager for cross-worker concurrency safety."""

from __future__ import annotations

import logging
import os
import socket
import threading
import uuid
from datetime import timedelta
from typing import Dict, List, Optional

from sqlalchemy import or_, text
from sqlalchemy.orm import Session

from core.config import settings
from core.database import SessionLocal, engine
from core.time_utils import utc_now_naive
from models.emulator_lease import EmulatorLeaseTable

logger = logging.getLogger(__name__)

def build_emulator_candidates() -> List[Dict[str, int | str]]:
    """Build emulator list in preferred order from settings."""
    preferred = [
        settings.ANDROID_EMULATOR_4,
        settings.ANDROID_EMULATOR_1,
        settings.ANDROID_EMULATOR_2,
        settings.ANDROID_EMULATOR_3,
    ]
    seen = set()
    rows: List[Dict[str, int | str]] = []
    for item in preferred:
        if not item or ":" not in item or item in seen:
            continue
        seen.add(item)
        host, port_raw = item.rsplit(":", 1)
        try:
            port = int(port_raw)
        except ValueError:
            logger.warning("Skip invalid emulator address: %s", item)
            continue
        rows.append({"host": host.strip(), "port": port})
    return rows


class EmulatorLeaseManager:
    """Manage emulator leases via MySQL for distributed workers."""

    def __init__(
        self,
        lease_ttl_seconds: int = 3600,
        worker_name: Optional[str] = None,
    ):
        self.lease_ttl_seconds = max(60, min(int(lease_ttl_seconds), 12 * 3600))
        self.worker_name = worker_name or os.getenv("HOSTNAME") or socket.gethostname()
        self._schema_ready = False
        self._schema_lock = threading.Lock()

    def _ensure_schema(self) -> None:
        if self._schema_ready:
            return
        with self._schema_lock:
            if self._schema_ready:
                return
            try:
                EmulatorLeaseTable.__table__.create(bind=engine, checkfirst=True)
                self._schema_ready = True
            except Exception as exc:
                logger.warning("Failed to ensure emulator lease table: %s", exc)

    @staticmethod
    def _normalize_candidates(
        candidates: Optional[List[Dict[str, int | str]]],
    ) -> List[Dict[str, int | str]]:
        if not candidates:
            return build_emulator_candidates()
        normalized: List[Dict[str, int | str]] = []
        for row in candidates:
            if "host" not in row or "port" not in row:
                continue
            normalized.append({"host": str(row["host"]), "port": int(row["port"])})
        return normalized

    def _seed_candidates(self, db: Session, candidates: List[Dict[str, int | str]]) -> None:
        now = utc_now_naive()
        sql = text(
            """
            INSERT INTO emulator_leases (id, host, port, created_at, updated_at)
            VALUES (:id, :host, :port, :created_at, :updated_at)
            ON DUPLICATE KEY UPDATE updated_at = updated_at
            """
        )
        for item in candidates:
            db.execute(
                sql,
                {
                    "id": str(uuid.uuid4()),
                    "host": str(item["host"]),
                    "port": int(item["port"]),
                    "created_at": now,
                    "updated_at": now,
                },
            )

    def acquire(
        self,
        task_id: str,
        candidates: Optional[List[Dict[str, int | str]]] = None,
    ) -> Optional[Dict[str, str | int]]:
        """Acquire one emulator lease. Returns None if no slot available."""
        pool = self._normalize_candidates(candidates)
        if not pool:
            return None

        self._ensure_schema()

        db: Session = SessionLocal()
        now = utc_now_naive()
        expires_at = now + timedelta(seconds=self.lease_ttl_seconds)
        try:
            self._seed_candidates(db, pool)
            db.commit()

            for item in pool:
                host = str(item["host"])
                port = int(item["port"])
                lease_token = uuid.uuid4().hex

                updated = (
                    db.query(EmulatorLeaseTable)
                    .filter(
                        EmulatorLeaseTable.host == host,
                        EmulatorLeaseTable.port == port,
                    )
                    .filter(
                        or_(
                            EmulatorLeaseTable.lease_token.is_(None),
                            EmulatorLeaseTable.expires_at.is_(None),
                            EmulatorLeaseTable.expires_at <= now,
                        )
                    )
                    .update(
                        {
                            EmulatorLeaseTable.lease_token: lease_token,
                            EmulatorLeaseTable.task_id: task_id,
                            EmulatorLeaseTable.worker_name: self.worker_name,
                            EmulatorLeaseTable.holder_pid: os.getpid(),
                            EmulatorLeaseTable.leased_at: now,
                            EmulatorLeaseTable.expires_at: expires_at,
                            EmulatorLeaseTable.released_at: None,
                            EmulatorLeaseTable.updated_at: now,
                        },
                        synchronize_session=False,
                    )
                )
                if updated:
                    db.commit()
                    return {
                        "host": host,
                        "port": port,
                        "lease_token": lease_token,
                        "lease_backend": "mysql",
                    }
            db.rollback()
            return None
        except Exception as exc:
            db.rollback()
            logger.warning("Failed to acquire emulator lease for task=%s: %s", task_id, exc)
            return None
        finally:
            db.close()

    def release(self, lease_info: Dict[str, str | int]) -> bool:
        """Release lease if token/task matches."""
        host = lease_info.get("host")
        port = lease_info.get("port")
        if host is None or port is None:
            return False

        host_str = str(host)
        port_int = int(port)
        token = str(lease_info.get("lease_token") or "").strip()
        task_id = str(lease_info.get("task_id") or "").strip()

        self._ensure_schema()

        db: Session = SessionLocal()
        now = utc_now_naive()
        try:
            query = db.query(EmulatorLeaseTable).filter(
                EmulatorLeaseTable.host == host_str,
                EmulatorLeaseTable.port == port_int,
            )
            if token:
                query = query.filter(EmulatorLeaseTable.lease_token == token)
            elif task_id:
                query = query.filter(EmulatorLeaseTable.task_id == task_id)

            updated = query.update(
                {
                    EmulatorLeaseTable.lease_token: None,
                    EmulatorLeaseTable.task_id: None,
                    EmulatorLeaseTable.worker_name: None,
                    EmulatorLeaseTable.holder_pid: None,
                    EmulatorLeaseTable.leased_at: None,
                    EmulatorLeaseTable.expires_at: None,
                    EmulatorLeaseTable.released_at: now,
                    EmulatorLeaseTable.updated_at: now,
                },
                synchronize_session=False,
            )
            if updated:
                db.commit()
                return True

            db.rollback()
            existing = (
                db.query(EmulatorLeaseTable)
                .filter(
                    EmulatorLeaseTable.host == host_str,
                    EmulatorLeaseTable.port == port_int,
                )
                .first()
            )
            if not existing or not existing.lease_token:
                return True
            return False
        except Exception as exc:
            db.rollback()
            logger.warning(
                "Failed to release emulator lease %s:%s token=%s: %s",
                host_str,
                port_int,
                token[:8] if token else "-",
                exc,
            )
            return False
        finally:
            db.close()

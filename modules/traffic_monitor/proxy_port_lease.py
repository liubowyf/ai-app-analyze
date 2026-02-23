"""MySQL-backed proxy port lease manager for parallel traffic capture."""

from __future__ import annotations

import logging
import os
import socket
import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from sqlalchemy import or_, text
from sqlalchemy.orm import Session

from core.database import SessionLocal, engine
from models.proxy_port_lease import ProxyPortLeaseTable

logger = logging.getLogger(__name__)


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ProxyPortLeaseManager:
    """Manage local-node proxy port leases via MySQL."""

    def __init__(
        self,
        port_start: int = 18080,
        port_end: int = 18129,
        lease_ttl_seconds: int = 3600,
        node_name: Optional[str] = None,
        worker_name: Optional[str] = None,
    ):
        start = int(port_start)
        end = int(port_end)
        if start > end:
            start, end = end, start
        self.port_start = max(1024, start)
        self.port_end = min(65535, end)
        self.lease_ttl_seconds = max(60, min(int(lease_ttl_seconds), 12 * 3600))
        self.node_name = node_name or os.getenv("HOSTNAME") or socket.gethostname()
        self.worker_name = worker_name or self.node_name
        self._schema_ready = False
        self._schema_lock = threading.Lock()

    def _ensure_schema(self) -> None:
        if self._schema_ready:
            return
        with self._schema_lock:
            if self._schema_ready:
                return
            try:
                ProxyPortLeaseTable.__table__.create(bind=engine, checkfirst=True)
                self._schema_ready = True
            except Exception as exc:
                logger.warning("Failed to ensure proxy port lease table: %s", exc)

    def _candidate_ports(self) -> List[int]:
        return list(range(self.port_start, self.port_end + 1))

    @staticmethod
    def _is_port_available(port: int) -> bool:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("127.0.0.1", int(port)))
            return True
        except OSError:
            return False
        finally:
            sock.close()

    def _seed_ports(self, db: Session, ports: List[int]) -> None:
        now = _utc_now_naive()
        sql = text(
            """
            INSERT INTO proxy_port_leases (id, node_name, port, created_at, updated_at)
            VALUES (:id, :node_name, :port, :created_at, :updated_at)
            ON DUPLICATE KEY UPDATE updated_at = updated_at
            """
        )
        for port in ports:
            db.execute(
                sql,
                {
                    "id": str(uuid.uuid4()),
                    "node_name": self.node_name,
                    "port": int(port),
                    "created_at": now,
                    "updated_at": now,
                },
            )

    def acquire(self, task_id: str) -> Optional[Dict[str, str | int]]:
        """Acquire one proxy-port lease on current node."""
        ports = self._candidate_ports()
        if not ports:
            return None

        self._ensure_schema()

        db: Session = SessionLocal()
        now = _utc_now_naive()
        expires_at = now + timedelta(seconds=self.lease_ttl_seconds)
        try:
            self._seed_ports(db, ports)
            db.commit()

            for port in ports:
                if not self._is_port_available(port):
                    continue

                lease_token = uuid.uuid4().hex
                updated = (
                    db.query(ProxyPortLeaseTable)
                    .filter(
                        ProxyPortLeaseTable.node_name == self.node_name,
                        ProxyPortLeaseTable.port == int(port),
                    )
                    .filter(
                        or_(
                            ProxyPortLeaseTable.lease_token.is_(None),
                            ProxyPortLeaseTable.expires_at.is_(None),
                            ProxyPortLeaseTable.expires_at <= now,
                        )
                    )
                    .update(
                        {
                            ProxyPortLeaseTable.lease_token: lease_token,
                            ProxyPortLeaseTable.task_id: task_id,
                            ProxyPortLeaseTable.worker_name: self.worker_name,
                            ProxyPortLeaseTable.holder_pid: os.getpid(),
                            ProxyPortLeaseTable.leased_at: now,
                            ProxyPortLeaseTable.expires_at: expires_at,
                            ProxyPortLeaseTable.released_at: None,
                            ProxyPortLeaseTable.updated_at: now,
                        },
                        synchronize_session=False,
                    )
                )
                if updated:
                    db.commit()
                    return {
                        "node_name": self.node_name,
                        "port": int(port),
                        "lease_token": lease_token,
                        "lease_backend": "mysql",
                    }

            db.rollback()
            return None
        except Exception as exc:
            db.rollback()
            logger.warning("Failed to acquire proxy port lease task=%s: %s", task_id, exc)
            return None
        finally:
            db.close()

    def release(self, lease_info: Dict[str, str | int]) -> bool:
        """Release lease if token/task matches."""
        port = lease_info.get("port")
        if port is None:
            return False
        node_name = str(lease_info.get("node_name") or self.node_name)
        token = str(lease_info.get("lease_token") or "").strip()
        task_id = str(lease_info.get("task_id") or "").strip()

        self._ensure_schema()

        db: Session = SessionLocal()
        now = _utc_now_naive()
        try:
            query = db.query(ProxyPortLeaseTable).filter(
                ProxyPortLeaseTable.node_name == node_name,
                ProxyPortLeaseTable.port == int(port),
            )
            if token:
                query = query.filter(ProxyPortLeaseTable.lease_token == token)
            elif task_id:
                query = query.filter(ProxyPortLeaseTable.task_id == task_id)

            updated = query.update(
                {
                    ProxyPortLeaseTable.lease_token: None,
                    ProxyPortLeaseTable.task_id: None,
                    ProxyPortLeaseTable.worker_name: None,
                    ProxyPortLeaseTable.holder_pid: None,
                    ProxyPortLeaseTable.leased_at: None,
                    ProxyPortLeaseTable.expires_at: None,
                    ProxyPortLeaseTable.released_at: now,
                    ProxyPortLeaseTable.updated_at: now,
                },
                synchronize_session=False,
            )
            if updated:
                db.commit()
                return True

            db.rollback()
            existing = (
                db.query(ProxyPortLeaseTable)
                .filter(
                    ProxyPortLeaseTable.node_name == node_name,
                    ProxyPortLeaseTable.port == int(port),
                )
                .first()
            )
            if not existing or not existing.lease_token:
                return True
            return False
        except Exception as exc:
            db.rollback()
            logger.warning(
                "Failed to release proxy port lease node=%s port=%s token=%s: %s",
                node_name,
                port,
                token[:8] if token else "-",
                exc,
            )
            return False
        finally:
            db.close()

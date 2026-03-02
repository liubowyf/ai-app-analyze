"""Database table for distributed proxy-port lease coordination."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped

from core.database import Base
from core.time_utils import utc_now_naive

class ProxyPortLeaseTable(Base):
    """One row per (node_name, proxy_port) lease slot."""

    __tablename__ = "proxy_port_leases"

    id: Mapped[str] = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    node_name: Mapped[str] = Column(String(120), nullable=False)
    port: Mapped[int] = Column(Integer, nullable=False)

    lease_token: Mapped[Optional[str]] = Column(String(64), nullable=True, index=True)
    task_id: Mapped[Optional[str]] = Column(String(36), nullable=True, index=True)
    worker_name: Mapped[Optional[str]] = Column(String(120), nullable=True)
    holder_pid: Mapped[Optional[int]] = Column(Integer, nullable=True)
    leased_at: Mapped[Optional[datetime]] = Column(DateTime, nullable=True)
    expires_at: Mapped[Optional[datetime]] = Column(DateTime, nullable=True, index=True)
    released_at: Mapped[Optional[datetime]] = Column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = Column(
        DateTime,
        default=utc_now_naive,
        onupdate=utc_now_naive,
        nullable=False,
    )
    created_at: Mapped[datetime] = Column(DateTime, default=utc_now_naive, nullable=False)

    __table_args__ = (
        UniqueConstraint("node_name", "port", name="uq_proxy_port_node_port"),
        Index("idx_proxy_port_node_port", "node_name", "port"),
    )

"""Database tables for analysis results with normalized fields."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, relationship

from core.database import Base


class StaticAnalysisTable(Base):
    """
    Static analysis results table with normalized fields.

    Stores detailed static analysis data in separate fields for better query performance.
    """
    __tablename__ = "static_analysis"

    # Primary key
    id: Mapped[str] = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Foreign key to task
    task_id: Mapped[str] = Column(String(36), ForeignKey("tasks.id"), nullable=False, unique=True, index=True)

    # Basic APK info
    package_name: Mapped[Optional[str]] = Column(String(255), nullable=True, index=True)
    app_name: Mapped[Optional[str]] = Column(String(255), nullable=True)
    version_name: Mapped[Optional[str]] = Column(String(50), nullable=True)
    version_code: Mapped[Optional[str]] = Column(String(50), nullable=True)
    min_sdk: Mapped[Optional[int]] = Column(Integer, nullable=True)
    target_sdk: Mapped[Optional[int]] = Column(Integer, nullable=True)

    # Permissions count
    total_permissions: Mapped[int] = Column(Integer, default=0)
    dangerous_permissions: Mapped[int] = Column(Integer, default=0)
    permission_list: Mapped[Optional[str]] = Column(Text, nullable=True)  # JSON string

    # Components count
    activities_count: Mapped[int] = Column(Integer, default=0)
    services_count: Mapped[int] = Column(Integer, default=0)
    receivers_count: Mapped[int] = Column(Integer, default=0)
    providers_count: Mapped[int] = Column(Integer, default=0)
    exported_components: Mapped[int] = Column(Integer, default=0)

    # Signature info
    signature_valid: Mapped[Optional[int]] = Column(Integer, nullable=True)
    signature_algorithm: Mapped[Optional[str]] = Column(String(100), nullable=True)

    # Risk score
    risk_score: Mapped[int] = Column(Integer, default=0, index=True)
    risk_level: Mapped[Optional[str]] = Column(String(20), nullable=True, index=True)

    # Packed flag
    is_packed: Mapped[int] = Column(Integer, default=0)
    pack_message: Mapped[Optional[str]] = Column(Text, nullable=True)

    # Timestamp
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationship
    task = relationship("Task", back_populates="static_table")


class DynamicAnalysisTable(Base):
    """
    Dynamic analysis results table with normalized fields.
    """
    __tablename__ = "dynamic_analysis"

    # Primary key
    id: Mapped[str] = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Foreign key to task
    task_id: Mapped[str] = Column(String(36), ForeignKey("tasks.id"), nullable=False, unique=True, index=True)

    # Exploration statistics
    total_steps: Mapped[int] = Column(Integer, default=0)
    phases_completed: Mapped[Optional[str]] = Column(String(255), nullable=True)

    # Activities
    unique_activities: Mapped[int] = Column(Integer, default=0)
    activities_list: Mapped[Optional[str]] = Column(Text, nullable=True)  # JSON string

    # Screenshots
    total_screenshots: Mapped[int] = Column(Integer, default=0)

    # Network summary
    total_requests: Mapped[int] = Column(Integer, default=0)
    total_observations: Mapped[int] = Column(Integer, default=0)
    unique_domains: Mapped[int] = Column(Integer, default=0)
    unique_ips: Mapped[int] = Column(Integer, default=0)
    master_domains: Mapped[int] = Column(Integer, default=0)
    primary_observations: Mapped[int] = Column(Integer, default=0)
    candidate_observations: Mapped[int] = Column(Integer, default=0)
    capture_mode: Mapped[Optional[str]] = Column(String(32), nullable=True)
    source_breakdown: Mapped[Optional[dict]] = Column(JSON, nullable=True)
    quality_gate_status: Mapped[Optional[str]] = Column(String(32), nullable=True)

    # Status
    success: Mapped[int] = Column(Integer, default=0)
    error_message: Mapped[Optional[str]] = Column(Text, nullable=True)

    # Package detected
    detected_package: Mapped[Optional[str]] = Column(String(255), nullable=True)

    # Duration
    started_at: Mapped[Optional[datetime]] = Column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = Column(DateTime, nullable=True)
    duration_seconds: Mapped[int] = Column(Integer, default=0)

    # Relationship
    task = relationship("Task", back_populates="dynamic_table")


class NetworkRequestTable(Base):
    """
    Network request records table.
    """
    __tablename__ = "network_requests"

    # Primary key
    id: Mapped[str] = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Foreign key to task
    task_id: Mapped[str] = Column(String(36), ForeignKey("tasks.id"), nullable=False, index=True)

    # Request details
    url: Mapped[Optional[str]] = Column(Text, nullable=True)
    method: Mapped[Optional[str]] = Column(String(10), nullable=True)
    host: Mapped[Optional[str]] = Column(String(255), nullable=True, index=True)
    path: Mapped[Optional[str]] = Column(Text, nullable=True)

    # Network info
    ip: Mapped[Optional[str]] = Column(String(50), nullable=True, index=True)
    port: Mapped[int] = Column(Integer, default=80)
    scheme: Mapped[Optional[str]] = Column(String(10), nullable=True)

    # Response
    response_code: Mapped[Optional[int]] = Column(Integer, nullable=True)
    content_type: Mapped[Optional[str]] = Column(String(100), nullable=True)

    # Size
    request_size: Mapped[int] = Column(Integer, default=0)
    response_size: Mapped[int] = Column(Integer, default=0)

    # Time
    request_time: Mapped[Optional[datetime]] = Column(DateTime, nullable=True)
    first_seen_at: Mapped[Optional[datetime]] = Column(DateTime, nullable=True)
    last_seen_at: Mapped[Optional[datetime]] = Column(DateTime, nullable=True)
    hit_count: Mapped[int] = Column(Integer, default=1)

    # Passive observation metadata
    source_type: Mapped[Optional[str]] = Column(String(32), nullable=True, index=True)
    transport: Mapped[Optional[str]] = Column(String(32), nullable=True)
    protocol: Mapped[Optional[str]] = Column(String(32), nullable=True)
    capture_mode: Mapped[Optional[str]] = Column(String(32), nullable=True)
    attribution_tier: Mapped[Optional[str]] = Column(String(16), nullable=True)
    package_name: Mapped[Optional[str]] = Column(String(255), nullable=True, index=True)
    uid: Mapped[Optional[int]] = Column(Integer, nullable=True, index=True)
    process_name: Mapped[Optional[str]] = Column(String(255), nullable=True)
    attribution_confidence: Mapped[Optional[float]] = Column(Float, nullable=True)

    # Sensitive data
    has_sensitive_data: Mapped[int] = Column(Integer, default=0)
    sensitive_types: Mapped[Optional[str]] = Column(String(255), nullable=True)

    # Relationship
    task = relationship("Task", back_populates="network_requests")


class MasterDomainTable(Base):
    """
    Master domain records table.
    """
    __tablename__ = "master_domains"

    # Primary key
    id: Mapped[str] = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Foreign key to task
    task_id: Mapped[str] = Column(String(36), ForeignKey("tasks.id"), nullable=False, index=True)

    # Domain
    domain: Mapped[Optional[str]] = Column(String(255), nullable=True, index=True)
    ip: Mapped[Optional[str]] = Column(String(50), nullable=True)

    # Confidence
    confidence_score: Mapped[int] = Column(Integer, default=0)
    confidence_level: Mapped[Optional[str]] = Column(String(20), nullable=True)

    # Evidence
    evidence: Mapped[Optional[str]] = Column(Text, nullable=True)  # JSON string

    # Request stats
    request_count: Mapped[int] = Column(Integer, default=0)
    post_count: Mapped[int] = Column(Integer, default=0)
    first_seen_at: Mapped[Optional[datetime]] = Column(DateTime, nullable=True)
    last_seen_at: Mapped[Optional[datetime]] = Column(DateTime, nullable=True)
    unique_ip_count: Mapped[int] = Column(Integer, default=0)
    source_types_json: Mapped[Optional[dict]] = Column(JSON, nullable=True)
    capture_mode: Mapped[Optional[str]] = Column(String(32), nullable=True)

    # Relationship
    task = relationship("Task", back_populates="master_domains_table")


class ScreenshotTable(Base):
    """
    Screenshot records table.
    """
    __tablename__ = "screenshots"

    # Primary key
    id: Mapped[str] = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Foreign key to task
    task_id: Mapped[str] = Column(String(36), ForeignKey("tasks.id"), nullable=False, index=True)

    # Screenshot details
    storage_path: Mapped[Optional[str]] = Column(String(500), nullable=True)
    file_size: Mapped[int] = Column(Integer, default=0)

    # Context
    stage: Mapped[Optional[str]] = Column(String(50), nullable=True)
    description: Mapped[Optional[str]] = Column(String(255), nullable=True)

    # Time
    captured_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationship
    task = relationship("Task", back_populates="screenshots_table")


class AnalysisRunTable(Base):
    """
    Per-stage execution run records for one task.

    Tracks stage-level lifecycle, duration and failures:
    - static
    - dynamic
    - report
    """

    __tablename__ = "analysis_runs"

    id: Mapped[str] = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id: Mapped[str] = Column(String(36), ForeignKey("tasks.id"), nullable=False, index=True)

    stage: Mapped[str] = Column(String(32), nullable=False, index=True)
    attempt: Mapped[int] = Column(Integer, default=1, nullable=False)
    status: Mapped[str] = Column(String(20), default="running", nullable=False, index=True)

    worker_name: Mapped[Optional[str]] = Column(String(120), nullable=True)
    emulator: Mapped[Optional[str]] = Column(String(120), nullable=True)
    details: Mapped[Optional[dict]] = Column(JSON, nullable=True)

    started_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    completed_at: Mapped[Optional[datetime]] = Column(DateTime, nullable=True)
    duration_seconds: Mapped[int] = Column(Integer, default=0, nullable=False)
    error_message: Mapped[Optional[str]] = Column(Text, nullable=True)

    task = relationship("Task", back_populates="analysis_runs")

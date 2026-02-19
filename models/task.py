"""Task model for tracking APK analysis jobs."""
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from sqlalchemy import BigInteger, Column, DateTime, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped

from core.database import Base


class TaskStatus(str, Enum):
    """Task status enum."""

    PENDING = "pending"
    QUEUED = "queued"
    STATIC_ANALYZING = "static_analyzing"
    DYNAMIC_ANALYZING = "dynamic_analyzing"
    REPORT_GENERATING = "report_generating"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskPriority(str, Enum):
    """Task priority enum."""

    URGENT = "urgent"
    NORMAL = "normal"
    BATCH = "batch"


class Task(Base):
    """
    Task model for tracking APK analysis jobs.

    Attributes:
        id: Unique task identifier (UUID)
        apk_file_name: Original APK file name
        apk_file_size: APK file size in bytes
        apk_md5: MD5 hash of APK file
        apk_sha256: SHA256 hash of APK file (optional)
        apk_storage_path: Storage path for APK file
        status: Current task status
        priority: Task priority level
        error_message: Error message if task failed
        error_stack: Error stack trace if task failed
        retry_count: Number of retry attempts
        created_at: Task creation timestamp
        started_at: Task start timestamp
        completed_at: Task completion timestamp
        updated_at: Task update timestamp
        static_analysis_result: Static analysis results (JSON)
        dynamic_analysis_result: Dynamic analysis results (JSON)
        report_storage_path: Storage path for generated report
    """

    __tablename__ = "tasks"

    # Primary key
    id: Mapped[str] = Column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # APK file information
    apk_file_name: Mapped[str] = Column(String(255), nullable=False)
    apk_file_size: Mapped[int] = Column(BigInteger, nullable=False)
    apk_md5: Mapped[str] = Column(String(32), nullable=False, index=True)
    apk_sha256: Mapped[Optional[str]] = Column(String(64), nullable=True)
    apk_storage_path: Mapped[Optional[str]] = Column(String(500), nullable=True)

    # Task status and priority
    status: Mapped[TaskStatus] = Column(
        default=TaskStatus.PENDING, index=True
    )
    priority: Mapped[TaskPriority] = Column(default=TaskPriority.NORMAL)

    # Error tracking
    error_message: Mapped[Optional[str]] = Column(Text, nullable=True)
    error_stack: Mapped[Optional[str]] = Column(Text, nullable=True)
    retry_count: Mapped[int] = Column(Integer, default=0)

    # Timestamps
    created_at: Mapped[datetime] = Column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    started_at: Mapped[Optional[datetime]] = Column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = Column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Analysis results
    static_analysis_result: Mapped[Optional[Dict[str, Any]]] = Column(
        JSON, nullable=True
    )
    dynamic_analysis_result: Mapped[Optional[Dict[str, Any]]] = Column(
        JSON, nullable=True
    )
    report_storage_path: Mapped[Optional[str]] = Column(
        String(500), nullable=True
    )

    # Add explicit indexes
    __table_args__ = (
        Index("idx_task_status", "status"),
        Index("idx_task_apk_md5", "apk_md5"),
    )

    def __repr__(self) -> str:
        """
        Return string representation of Task.

        Returns:
            String representation with task ID, file name, and status
        """
        return (
            f"<Task(id={self.id}, "
            f"apk_file_name={self.apk_file_name}, "
            f"status={self.status.value})>"
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert task to dictionary.

        Returns:
            Dictionary with task data and ISO formatted timestamps
        """
        result = {
            "id": self.id,
            "apk_file_name": self.apk_file_name,
            "apk_file_size": self.apk_file_size,
            "apk_md5": self.apk_md5,
            "apk_sha256": self.apk_sha256,
            "apk_storage_path": self.apk_storage_path,
            "status": self.status.value if self.status else None,
            "priority": self.priority.value if self.priority else None,
            "error_message": self.error_message,
            "error_stack": self.error_stack,
            "retry_count": self.retry_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "static_analysis_result": self.static_analysis_result,
            "dynamic_analysis_result": self.dynamic_analysis_result,
            "report_storage_path": self.report_storage_path,
        }
        return result

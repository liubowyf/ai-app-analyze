"""Task-related schemas for API request/response models."""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from models.task import TaskStatus, TaskPriority


class TaskCreateRequest(BaseModel):
    """Request model for creating/starting a task."""

    task_id: str = Field(..., description="Task ID to start")


class TaskResponse(BaseModel):
    """Response model for task details."""

    id: str
    apk_file_name: str
    apk_file_size: int
    apk_md5: str
    apk_sha256: Optional[str] = None
    apk_storage_path: Optional[str] = None
    status: str
    priority: str
    error_message: Optional[str] = None
    error_stack: Optional[str] = None
    retry_count: int = 0
    failure_reason: Optional[str] = None
    last_success_stage: Optional[str] = None
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    updated_at: str
    static_analysis_result: Optional[Dict[str, Any]] = None
    dynamic_analysis_result: Optional[Dict[str, Any]] = None
    report_storage_path: Optional[str] = None

    class Config:
        """Pydantic config."""

        from_attributes = True


class TaskListResponse(BaseModel):
    """Response model for paginated task list."""

    tasks: List[TaskResponse]
    total: int
    skip: int
    limit: int

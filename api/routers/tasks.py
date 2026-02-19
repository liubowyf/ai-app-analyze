"""Tasks router for task management endpoints."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.schemas.task import TaskCreateRequest, TaskResponse, TaskListResponse
from core.database import SessionLocal
from models.task import Task, TaskStatus

router = APIRouter()


def get_db():
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/tasks", response_model=TaskResponse)
def create_task(request: TaskCreateRequest, db: Session = Depends(get_db)):
    """
    Create/start an analysis task.

    Updates task status from PENDING to QUEUED.

    Args:
        request: Task creation request with task_id
        db: Database session

    Returns:
        Task details with updated status

    Raises:
        HTTPException: 404 if task not found, 400 if task already started
    """
    # Find the task
    task = db.query(Task).filter(Task.id == request.task_id).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Check if task can be started
    if task.status != TaskStatus.PENDING:
        raise HTTPException(
            status_code=400, detail="Task already started or in progress"
        )

    # Update task status to QUEUED
    task.status = TaskStatus.QUEUED
    task.started_at = datetime.utcnow()
    db.commit()
    db.refresh(task)

    # Convert to response
    return TaskResponse(
        id=task.id,
        apk_file_name=task.apk_file_name,
        apk_file_size=task.apk_file_size,
        apk_md5=task.apk_md5,
        apk_sha256=task.apk_sha256,
        apk_storage_path=task.apk_storage_path,
        status=task.status.value,
        priority=task.priority.value,
        error_message=task.error_message,
        error_stack=task.error_stack,
        retry_count=task.retry_count,
        created_at=task.created_at.isoformat() if task.created_at else None,
        started_at=task.started_at.isoformat() if task.started_at else None,
        completed_at=task.completed_at.isoformat() if task.completed_at else None,
        updated_at=task.updated_at.isoformat() if task.updated_at else None,
        static_analysis_result=task.static_analysis_result,
        dynamic_analysis_result=task.dynamic_analysis_result,
        report_storage_path=task.report_storage_path,
    )


@router.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(task_id: str, db: Session = Depends(get_db)):
    """
    Get task status by ID.

    Args:
        task_id: Task identifier
        db: Database session

    Returns:
        Task details

    Raises:
        HTTPException: 404 if task not found
    """
    task = db.query(Task).filter(Task.id == task_id).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return TaskResponse(
        id=task.id,
        apk_file_name=task.apk_file_name,
        apk_file_size=task.apk_file_size,
        apk_md5=task.apk_md5,
        apk_sha256=task.apk_sha256,
        apk_storage_path=task.apk_storage_path,
        status=task.status.value,
        priority=task.priority.value,
        error_message=task.error_message,
        error_stack=task.error_stack,
        retry_count=task.retry_count,
        created_at=task.created_at.isoformat() if task.created_at else None,
        started_at=task.started_at.isoformat() if task.started_at else None,
        completed_at=task.completed_at.isoformat() if task.completed_at else None,
        updated_at=task.updated_at.isoformat() if task.updated_at else None,
        static_analysis_result=task.static_analysis_result,
        dynamic_analysis_result=task.dynamic_analysis_result,
        report_storage_path=task.report_storage_path,
    )


@router.get("/tasks", response_model=TaskListResponse)
def list_tasks(
    skip: int = Query(0, ge=0, description="Number of tasks to skip"),
    limit: int = Query(10, ge=1, le=100, description="Number of tasks to return"),
    db: Session = Depends(get_db),
):
    """
    List tasks with pagination.

    Args:
        skip: Number of tasks to skip (offset)
        limit: Number of tasks to return
        db: Database session

    Returns:
        Paginated list of tasks
    """
    # Get total count
    total = db.query(Task).count()

    # Get tasks with pagination
    tasks = db.query(Task).offset(skip).limit(limit).all()

    # Convert to response
    task_responses = [
        TaskResponse(
            id=task.id,
            apk_file_name=task.apk_file_name,
            apk_file_size=task.apk_file_size,
            apk_md5=task.apk_md5,
            apk_sha256=task.apk_sha256,
            apk_storage_path=task.apk_storage_path,
            status=task.status.value,
            priority=task.priority.value,
            error_message=task.error_message,
            error_stack=task.error_stack,
            retry_count=task.retry_count,
            created_at=task.created_at.isoformat() if task.created_at else None,
            started_at=task.started_at.isoformat() if task.started_at else None,
            completed_at=task.completed_at.isoformat() if task.completed_at else None,
            updated_at=task.updated_at.isoformat() if task.updated_at else None,
            static_analysis_result=task.static_analysis_result,
            dynamic_analysis_result=task.dynamic_analysis_result,
            report_storage_path=task.report_storage_path,
        )
        for task in tasks
    ]

    return TaskListResponse(
        tasks=task_responses, total=total, skip=skip, limit=limit
    )


@router.post("/tasks/{task_id}/retry", response_model=TaskResponse)
def retry_task(task_id: str, db: Session = Depends(get_db)):
    """
    Retry a failed task.

    Updates task status from FAILED to QUEUED and increments retry_count.

    Args:
        task_id: Task identifier
        db: Database session

    Returns:
        Task details with updated status

    Raises:
        HTTPException: 404 if task not found, 400 if task is not failed
    """
    task = db.query(Task).filter(Task.id == task_id).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != TaskStatus.FAILED:
        raise HTTPException(status_code=400, detail="Only failed tasks can be retried")

    # Update task for retry
    task.status = TaskStatus.QUEUED
    task.retry_count += 1
    task.error_message = None
    task.error_stack = None
    db.commit()
    db.refresh(task)

    return TaskResponse(
        id=task.id,
        apk_file_name=task.apk_file_name,
        apk_file_size=task.apk_file_size,
        apk_md5=task.apk_md5,
        apk_sha256=task.apk_sha256,
        apk_storage_path=task.apk_storage_path,
        status=task.status.value,
        priority=task.priority.value,
        error_message=task.error_message,
        error_stack=task.error_stack,
        retry_count=task.retry_count,
        created_at=task.created_at.isoformat() if task.created_at else None,
        started_at=task.started_at.isoformat() if task.started_at else None,
        completed_at=task.completed_at.isoformat() if task.completed_at else None,
        updated_at=task.updated_at.isoformat() if task.updated_at else None,
        static_analysis_result=task.static_analysis_result,
        dynamic_analysis_result=task.dynamic_analysis_result,
        report_storage_path=task.report_storage_path,
    )

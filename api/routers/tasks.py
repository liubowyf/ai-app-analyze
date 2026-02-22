"""Tasks router for task management endpoints."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.schemas.task import TaskCreateRequest, TaskListResponse, TaskResponse
from core.database import SessionLocal
from models.analysis_tables import AnalysisRunTable, MasterDomainTable, NetworkRequestTable
from models.task import Task, TaskStatus
from modules.task_orchestration.orchestrator import enqueue_analysis_workflow

logger = logging.getLogger(__name__)
router = APIRouter()


def get_db():
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _to_task_response(task: Task) -> TaskResponse:
    status_value = task.status.value if hasattr(task.status, "value") else task.status
    priority_value = task.priority.value if hasattr(task.priority, "value") else task.priority
    return TaskResponse(
        id=task.id,
        apk_file_name=task.apk_file_name,
        apk_file_size=task.apk_file_size,
        apk_md5=task.apk_md5,
        apk_sha256=task.apk_sha256,
        apk_storage_path=task.apk_storage_path,
        status=status_value,
        priority=priority_value,
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


@router.post("/tasks", response_model=TaskResponse)
def create_task(request: TaskCreateRequest, db: Session = Depends(get_db)):
    """
    Start an analysis task and enqueue workflow.

    Updates task status from PENDING to QUEUED.
    """
    task = db.query(Task).filter(Task.id == request.task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != TaskStatus.PENDING:
        raise HTTPException(status_code=400, detail="Task already started or in progress")

    task.status = TaskStatus.QUEUED
    task.started_at = datetime.utcnow()
    db.commit()
    db.refresh(task)

    # Use stable workflow builder to avoid chained-argument shape mismatch.
    enqueue_ok = enqueue_analysis_workflow(
        task_id=str(task.id),
        include_static=True,
        priority=task.priority,
    )
    if not enqueue_ok:
        logger.warning("Task %s marked queued but enqueue failed", task.id)

    return _to_task_response(task)


@router.get("/tasks/metrics/queue")
def get_task_queue_metrics(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get queue load snapshot by task status."""
    rows = db.query(Task.status, func.count(Task.id)).group_by(Task.status).all()
    by_status: Dict[str, int] = {}
    total = 0
    for status, count in rows:
        key = status.value if hasattr(status, "value") else str(status)
        by_status[key] = int(count)
        total += int(count)

    in_progress = 0
    for key in ("queued", "static_analyzing", "dynamic_analyzing", "report_generating"):
        in_progress += by_status.get(key, 0)

    return {
        "total_tasks": total,
        "in_progress": in_progress,
        "by_status": by_status,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/tasks/{task_id}/network-requests")
def get_task_network_requests(
    task_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    host: str | None = Query(None, description="Optional host exact filter"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Query normalized network requests for a task."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    q = db.query(NetworkRequestTable).filter(NetworkRequestTable.task_id == task_id)
    if host:
        q = q.filter(NetworkRequestTable.host == host)
    total = q.count()
    rows = (
        q.order_by(NetworkRequestTable.request_time.desc(), NetworkRequestTable.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    items: List[Dict[str, Any]] = []
    for row in rows:
        items.append(
            {
                "id": row.id,
                "url": row.url,
                "method": row.method,
                "host": row.host,
                "path": row.path,
                "ip": row.ip,
                "port": row.port,
                "scheme": row.scheme,
                "response_code": row.response_code,
                "content_type": row.content_type,
                "request_time": row.request_time.isoformat() if row.request_time else None,
            }
        )

    return {
        "task_id": task_id,
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": items,
    }


@router.get("/tasks/{task_id}/runs")
def get_task_runs(task_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get per-stage execution timeline with durations and failure reasons."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    rows = (
        db.query(AnalysisRunTable)
        .filter(AnalysisRunTable.task_id == task_id)
        .order_by(AnalysisRunTable.started_at.asc(), AnalysisRunTable.attempt.asc())
        .all()
    )
    items: List[Dict[str, Any]] = []
    for row in rows:
        items.append(
            {
                "id": row.id,
                "stage": row.stage,
                "attempt": row.attempt,
                "status": row.status,
                "worker_name": row.worker_name,
                "emulator": row.emulator,
                "started_at": row.started_at.isoformat() if row.started_at else None,
                "completed_at": row.completed_at.isoformat() if row.completed_at else None,
                "duration_seconds": row.duration_seconds,
                "error_message": row.error_message,
                "details": row.details,
            }
        )
    summary: Dict[str, Dict[str, Any]] = {}
    for item in items:
        stage = item["stage"]
        stage_summary = summary.setdefault(
            stage,
            {"runs": 0, "success_runs": 0, "failed_runs": 0, "total_duration_seconds": 0},
        )
        stage_summary["runs"] += 1
        stage_summary["total_duration_seconds"] += int(item.get("duration_seconds") or 0)
        if item.get("status") == "success":
            stage_summary["success_runs"] += 1
        elif item.get("status") == "failed":
            stage_summary["failed_runs"] += 1

    return {"task_id": task_id, "count": len(items), "summary": summary, "items": items}


@router.get("/tasks/{task_id}/domains")
def get_task_domains(task_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Query normalized master-domain results for a task."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    rows = (
        db.query(MasterDomainTable)
        .filter(MasterDomainTable.task_id == task_id)
        .order_by(MasterDomainTable.confidence_score.desc(), MasterDomainTable.id.desc())
        .all()
    )
    domains = [
        {
            "domain": row.domain,
            "ip": row.ip,
            "score": row.confidence_score,
            "confidence": row.confidence_level,
            "request_count": row.request_count,
            "post_count": row.post_count,
            "evidence": row.evidence,
        }
        for row in rows
    ]

    if not domains and task.dynamic_analysis_result:
        fallback = task.dynamic_analysis_result.get("master_domains", {})
        domains = fallback.get("master_domains", []) if isinstance(fallback, dict) else []

    return {"task_id": task_id, "count": len(domains), "domains": domains}


@router.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(task_id: str, db: Session = Depends(get_db)):
    """Get task status by ID."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return _to_task_response(task)


@router.get("/tasks", response_model=TaskListResponse)
def list_tasks(
    skip: int = Query(0, ge=0, description="Number of tasks to skip"),
    limit: int = Query(10, ge=1, le=100, description="Number of tasks to return"),
    db: Session = Depends(get_db),
):
    """List tasks with pagination."""
    total = db.query(Task).count()
    tasks = db.query(Task).offset(skip).limit(limit).all()
    task_responses = [_to_task_response(task) for task in tasks]
    return TaskListResponse(tasks=task_responses, total=total, skip=skip, limit=limit)


@router.post("/tasks/{task_id}/retry", response_model=TaskResponse)
def retry_task(task_id: str, db: Session = Depends(get_db)):
    """Retry a failed task and enqueue workflow again."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != TaskStatus.FAILED:
        raise HTTPException(status_code=400, detail="Only failed tasks can be retried")

    task.status = TaskStatus.QUEUED
    task.retry_count += 1
    task.error_message = None
    task.error_stack = None
    db.commit()
    db.refresh(task)

    enqueue_ok = enqueue_analysis_workflow(
        task_id=str(task.id),
        include_static=True,
        priority=task.priority,
    )
    if not enqueue_ok:
        logger.warning("Task %s retry enqueue failed", task.id)

    return _to_task_response(task)

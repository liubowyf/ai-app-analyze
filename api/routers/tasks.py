"""Tasks router for task management endpoints."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.schemas.task import TaskCreateRequest, TaskListResponse, TaskResponse
from core.database import SessionLocal
from models.analysis_tables import AnalysisRunTable, MasterDomainTable, NetworkRequestTable, StaticAnalysisTable
from models.task import Task, TaskStatus
from modules.task_orchestration.queue_backend import enqueue_task, get_backend_runtime_diagnostics
from modules.task_orchestration.state_machine import manual_retry_status

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
        failure_reason=task.failure_reason,
        last_success_stage=task.last_success_stage,
        created_at=task.created_at.isoformat() if task.created_at else None,
        started_at=task.started_at.isoformat() if task.started_at else None,
        completed_at=task.completed_at.isoformat() if task.completed_at else None,
        updated_at=task.updated_at.isoformat() if task.updated_at else None,
        static_analysis_result=task.static_analysis_result,
        dynamic_analysis_result=task.dynamic_analysis_result,
        report_storage_path=task.report_storage_path,
    )


def _isoformat(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    formatter = getattr(value, "isoformat", None)
    if callable(formatter):
        return formatter()
    return None


def _parse_jsonish(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return json.loads(stripped)
        except Exception:
            return value
    return value


def _has_static_analysis_result(db: Session, task: Task) -> bool:
    """Return whether the task already has reusable static-analysis output."""
    static_result = getattr(task, "static_analysis_result", None)
    if isinstance(static_result, dict) and static_result:
        return True
    return (
        db.query(StaticAnalysisTable.id)
        .filter(StaticAnalysisTable.task_id == task.id)
        .first()
        is not None
    )


def _serialize_network_observation(row: Any) -> Dict[str, Any]:
    first_seen_at = getattr(row, "first_seen_at", None) or getattr(row, "request_time", None)
    last_seen_at = getattr(row, "last_seen_at", None) or getattr(row, "request_time", None)
    domain = getattr(row, "host", None)
    return {
        "id": getattr(row, "id", None),
        "url": getattr(row, "url", None),
        "method": getattr(row, "method", None) or "UNKNOWN",
        "domain": domain,
        "host": domain,
        "path": getattr(row, "path", None),
        "ip": getattr(row, "ip", None),
        "port": getattr(row, "port", None),
        "scheme": getattr(row, "scheme", None),
        "response_code": getattr(row, "response_code", None),
        "content_type": getattr(row, "content_type", None),
        "request_time": _isoformat(first_seen_at),
        "first_seen_at": _isoformat(first_seen_at),
        "last_seen_at": _isoformat(last_seen_at),
        "hit_count": int(getattr(row, "hit_count", 0) or 1),
        "source_type": getattr(row, "source_type", None) or "unknown",
        "transport": getattr(row, "transport", None) or "unknown",
        "protocol": getattr(row, "protocol", None) or "unknown",
        "capture_mode": getattr(row, "capture_mode", None) or "redroid_zeek",
        "attribution_tier": getattr(row, "attribution_tier", None) or "primary",
        "package_name": getattr(row, "package_name", None),
        "uid": getattr(row, "uid", None),
        "process_name": getattr(row, "process_name", None),
        "attribution_confidence": getattr(row, "attribution_confidence", None),
    }


def _normalize_observation_item(item: Dict[str, Any], default_tier: str, capture_mode: str | None) -> Dict[str, Any]:
    first_seen_at = item.get("first_seen_at") or item.get("request_time")
    last_seen_at = item.get("last_seen_at") or item.get("request_time") or first_seen_at
    domain = item.get("domain") or item.get("host")
    return {
        "id": item.get("id"),
        "url": item.get("url"),
        "method": item.get("method") or "UNKNOWN",
        "domain": domain,
        "host": domain,
        "path": item.get("path"),
        "ip": item.get("ip"),
        "port": item.get("port"),
        "scheme": item.get("scheme"),
        "response_code": item.get("response_code"),
        "content_type": item.get("content_type"),
        "request_time": first_seen_at,
        "first_seen_at": first_seen_at,
        "last_seen_at": last_seen_at,
        "hit_count": int(item.get("hit_count") or item.get("count") or 1),
        "source_type": item.get("source_type") or item.get("source") or "unknown",
        "transport": item.get("transport") or "unknown",
        "protocol": item.get("protocol") or "unknown",
        "capture_mode": item.get("capture_mode") or capture_mode or "redroid_zeek",
        "attribution_tier": item.get("attribution_tier") or default_tier,
        "package_name": item.get("package_name"),
        "uid": item.get("uid"),
        "process_name": item.get("process_name"),
        "attribution_confidence": item.get("attribution_confidence"),
    }


def _fallback_network_observations(dynamic_result: Any) -> List[Dict[str, Any]]:
    if not isinstance(dynamic_result, dict):
        return []
    capture_mode = dynamic_result.get("capture_mode")
    items: List[Dict[str, Any]] = []
    preview_sources = [
        ("primary_observations_preview", "primary"),
        ("candidate_observations_preview", "candidate"),
        ("suspicious_requests", "primary"),
        ("candidate_requests", "candidate"),
    ]
    for key, tier in preview_sources:
        rows = dynamic_result.get(key)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if isinstance(row, dict):
                items.append(_normalize_observation_item(row, tier, capture_mode))
    return items


def _normalize_source_types(value: Any) -> List[str]:
    parsed = _parse_jsonish(value)
    if parsed is None:
        return []
    if isinstance(parsed, dict):
        return sorted(str(key) for key in parsed.keys())
    if isinstance(parsed, list):
        return [str(item) for item in parsed]
    return [str(parsed)]


def _serialize_master_domain(row: Any) -> Dict[str, Any]:
    hit_count = int(getattr(row, "request_count", 0) or 0)
    return {
        "domain": getattr(row, "domain", None),
        "ip": getattr(row, "ip", None),
        "score": getattr(row, "confidence_score", None),
        "confidence": getattr(row, "confidence_level", None),
        "hit_count": hit_count,
        "request_count": hit_count,
        "post_count": int(getattr(row, "post_count", 0) or 0),
        "unique_ip_count": int(getattr(row, "unique_ip_count", 0) or (1 if getattr(row, "ip", None) else 0)),
        "source_types": _normalize_source_types(getattr(row, "source_types_json", None)),
        "first_seen_at": _isoformat(getattr(row, "first_seen_at", None)),
        "last_seen_at": _isoformat(getattr(row, "last_seen_at", None)),
        "evidence": _parse_jsonish(getattr(row, "evidence", None)),
        "capture_mode": getattr(row, "capture_mode", None) or "redroid_zeek",
    }


def _fallback_master_domains(dynamic_result: Any) -> List[Dict[str, Any]]:
    if not isinstance(dynamic_result, dict):
        return []

    rows: Any = None
    masters = dynamic_result.get("master_domains")
    if isinstance(masters, dict):
        rows = masters.get("master_domains")
    elif isinstance(masters, list):
        rows = masters

    if not isinstance(rows, list):
        summary = dynamic_result.get("network_observation_summary")
        if isinstance(summary, dict):
            rows = summary.get("domain_stats")
    if not isinstance(rows, list):
        rows = dynamic_result.get("domain_stats")
    if not isinstance(rows, list):
        return []

    domains: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        domains.append(
            {
                "domain": row.get("domain"),
                "ip": row.get("ip"),
                "score": row.get("score"),
                "confidence": row.get("confidence"),
                "hit_count": int(row.get("hit_count") or row.get("request_count") or 0),
                "request_count": int(row.get("hit_count") or row.get("request_count") or 0),
                "post_count": int(row.get("post_count") or 0),
                "unique_ip_count": int(row.get("unique_ip_count") or 0),
                "source_types": _normalize_source_types(row.get("source_types") or row.get("source_types_json")),
                "first_seen_at": row.get("first_seen_at"),
                "last_seen_at": row.get("last_seen_at"),
                "evidence": row.get("evidence"),
                "capture_mode": row.get("capture_mode") or dynamic_result.get("capture_mode") or "redroid_zeek",
            }
        )
    return domains


@router.post("/tasks", response_model=TaskResponse)
def create_task(request: TaskCreateRequest, db: Session = Depends(get_db)):
    """
    Start an analysis task and enqueue workflow.

    Updates task status from queued to queued and enqueues workflow.
    """
    task = db.query(Task).filter(Task.id == request.task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != TaskStatus.QUEUED or task.started_at is not None:
        raise HTTPException(status_code=400, detail="Task already started or in progress")

    task.status = TaskStatus.QUEUED
    task.started_at = datetime.utcnow()
    db.commit()
    db.refresh(task)

    # Use stable workflow builder to avoid chained-argument shape mismatch.
    enqueue_ok = enqueue_task(str(task.id), priority=task.priority)
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


@router.get("/tasks/metrics/backend")
def get_task_backend_metrics() -> Dict[str, Any]:
    """Get queue backend runtime readiness snapshot."""
    diagnostics = get_backend_runtime_diagnostics()
    backend = str(diagnostics.get("backend", "dramatiq"))
    dramatiq_ready = bool(diagnostics.get("dramatiq_ready", False))
    can_enqueue = backend == "dramatiq" and dramatiq_ready
    fallback_reason = diagnostics.get("fallback_reason")
    go_no_go_reason = "ready" if can_enqueue else "enqueue_not_ready"
    return {
        "backend": backend,
        "dramatiq_ready": dramatiq_ready,
        "fallback_reason": fallback_reason,
        "can_enqueue": can_enqueue,
        "go_no_go_reason": go_no_go_reason,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/tasks/metrics/scheduling")
def get_task_scheduling_metrics(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get scheduling-only rollout diagnostics without E2E evidence dependency."""
    diagnostics = get_backend_runtime_diagnostics()
    backend = str(diagnostics.get("backend", "dramatiq"))
    dramatiq_ready = bool(diagnostics.get("dramatiq_ready", False))
    can_enqueue = backend == "dramatiq" and dramatiq_ready

    rows = db.query(Task.status, func.count(Task.id)).group_by(Task.status).all()
    by_status: Dict[str, int] = {}
    for status, count in rows:
        key = status.value if hasattr(status, "value") else str(status)
        by_status[key] = int(count)

    queued_count = by_status.get("queued", 0)
    running_count = sum(by_status.get(key, 0) for key in ("static_analyzing", "dynamic_analyzing", "report_generating"))
    stuck_count = (
        db.query(func.count(Task.id))
        .filter(
            Task.status.in_(["queued", "static_analyzing", "dynamic_analyzing", "report_generating"]),
            Task.started_at.is_(None),
        )
        .scalar()
        or 0
    )

    return {
        "backend": backend,
        "can_enqueue": can_enqueue,
        "queued_count": int(queued_count),
        "running_count": int(running_count),
        "stuck_count": int(stuck_count),
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
    """Query normalized network observations for a task."""
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
    items = [_serialize_network_observation(row) for row in rows]
    if not items:
        fallback_items = _fallback_network_observations(task.dynamic_analysis_result)
        if host:
            fallback_items = [item for item in fallback_items if item.get("host") == host]
        total = len(fallback_items)
        items = fallback_items[skip: skip + limit]

    return {
        "task_id": task_id,
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": items,
    }


@router.get("/tasks/{task_id}/network-observations")
def get_task_network_observations(
    task_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    host: str | None = Query(None, description="Optional host exact filter"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Canonical passive observation endpoint."""
    return get_task_network_requests(task_id=task_id, skip=skip, limit=limit, host=host, db=db)


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
    domains = [_serialize_master_domain(row) for row in rows]

    if not domains:
        domains = _fallback_master_domains(task.dynamic_analysis_result)

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

    task.status = manual_retry_status(
        task.status,
        has_static_result=_has_static_analysis_result(db, task),
        last_success_stage=task.last_success_stage,
    )
    task.retry_count += 1
    task.error_message = None
    task.error_stack = None
    task.failure_reason = None
    task.dynamic_analysis_result = None
    task.report_storage_path = None
    task.web_report_path = None
    task.completed_at = None
    db.commit()
    db.refresh(task)

    enqueue_ok = enqueue_task(str(task.id), priority=task.priority)
    if not enqueue_ok:
        logger.warning("Task %s retry enqueue failed", task.id)

    return _to_task_response(task)
